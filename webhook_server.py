"""
Webhook server for Guard Insurance automation
Receives data from Next.js app and triggers Guard automation
"""
import asyncio
import json
import logging
import threading
import queue
import time
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
from guard_login import GuardLogin
from config import (
    WEBHOOK_HOST, WEBHOOK_PORT, WEBHOOK_PATH, LOG_DIR, TRACE_DIR,
    MAX_WORKERS
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'webhook_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Enable CORS for Next.js
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Store active sessions
active_sessions = {}

# Queue system
task_queue = queue.Queue()
active_workers = 0
worker_lock = threading.Lock()
queue_position = {}

# Browser lock - only ONE browser at a time
browser_lock = threading.Lock()
browser_in_use = False


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "guard-automation",
        "timestamp": datetime.now().isoformat(),
        "active_workers": active_workers,
        "max_workers": MAX_WORKERS,
        "queue_size": task_queue.qsize()
    }), 200


@app.route(WEBHOOK_PATH, methods=['POST', 'OPTIONS'])
def webhook_receiver():
    """
    Main webhook endpoint for Guard automation
    
    Expected payload:
    {
        "action": "start_automation",
        "task_id": "optional_unique_id",
        "policy_code": "TEBP602893",  // Optional if create_account is true
        "create_account": false,  // Set to true to create new account first
        "quote_data": {
            "combined_sales": "800000",
            "gas_gallons": "500000",
            "year_built": "2000",
            "square_footage": "4200",
            "mpds": "6"
        }
    }
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    
    try:
        # Get JSON payload
        if not request.is_json:
            return jsonify({
                "status": "error",
                "message": "Content-Type must be application/json"
            }), 400
        
        payload = request.get_json()
        if not payload:
            return jsonify({
                "status": "error",
                "message": "No payload received"
            }), 400
        
        logger.info(f"[GUARD] Webhook request received: {list(payload.keys())}")
        
        # Extract data
        action = payload.get('action', 'start_automation')
        policy_code = payload.get('policy_code')
        quote_data = payload.get('quote_data', {})
        create_account = payload.get('create_account', False)
        account_data = payload.get('account_data', {})
        
        # Validate required fields
        if not create_account and not policy_code:
            return jsonify({
                "status": "error",
                "message": "policy_code is required (or set create_account to true)"
            }), 400
        
        if action == 'start_automation':
            # Generate task_id
            task_id = payload.get('task_id') or f"guard_{policy_code or 'new'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            logger.info(f"[GUARD] Starting automation task: {task_id}")
            logger.info(f"[GUARD] Create Account: {create_account}")
            logger.info(f"[GUARD] Policy Code: {policy_code or 'Will be created'}")
            logger.info(f"[GUARD] Quote Data: {quote_data}")
            
            # Check worker availability
            with worker_lock:
                current_workers = active_workers
                queue_size = task_queue.qsize()
            
            # Initialize task status
            active_sessions[task_id] = {
                "status": "queued" if current_workers >= MAX_WORKERS else "running",
                "task_id": task_id,
                "policy_code": policy_code,
                "create_account": create_account,
                "queued_at": datetime.now().isoformat(),
                "quote_data": quote_data,
                "queue_position": queue_size + 1 if current_workers >= MAX_WORKERS else 0,
                "active_workers": current_workers,
                "max_workers": MAX_WORKERS
            }
            
            # Add to queue
            task_queue.put((task_id, policy_code, quote_data, create_account, account_data))
            
            if current_workers >= MAX_WORKERS:
                logger.info(f"[GUARD] Task {task_id} queued at position {queue_size + 1}")
            else:
                logger.info(f"[GUARD] Task {task_id} will start immediately")
            
            return jsonify({
                "status": "accepted",
                "task_id": task_id,
                "policy_code": policy_code,
                "message": "Guard automation task started",
                "status_url": f"/task/{task_id}/status"
            }), 202
        
        return jsonify({
            "status": "error",
            "message": f"Unknown action: {action}"
        }), 400
        
    except Exception as e:
        logger.error(f"[GUARD] Webhook error: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e),
            "error_type": type(e).__name__
        }), 500


@app.route('/task/<task_id>/status', methods=['GET'])
def get_task_status(task_id: str):
    """Get status of an automation task"""
    if task_id in active_sessions:
        return jsonify(active_sessions[task_id]), 200
    else:
        return jsonify({
            "status": "error",
            "message": f"Task {task_id} not found"
        }), 404


@app.route('/tasks', methods=['GET'])
def list_tasks():
    """List all tasks"""
    return jsonify({
        "tasks": list(active_sessions.values()),
        "total": len(active_sessions),
        "active_workers": active_workers,
        "max_workers": MAX_WORKERS,
        "queue_size": task_queue.qsize()
    }), 200


@app.route('/queue/status', methods=['GET'])
def queue_status():
    """Get queue status"""
    return jsonify({
        "queue_size": task_queue.qsize(),
        "active_workers": active_workers,
        "max_workers": MAX_WORKERS,
        "browser_in_use": browser_in_use
    }), 200


def run_automation_task_sync(task_id: str, policy_code: str, quote_data: dict, create_account: bool = False, account_data: dict = None):
    """Run automation task synchronously in a thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(run_automation_task(task_id, policy_code, quote_data, create_account, account_data))
    finally:
        loop.close()


async def run_automation_task(task_id: str, policy_code: str, quote_data: dict, create_account: bool = False, account_data: dict = None):
    """Run Guard automation task asynchronously"""
    logger.info(f"[TASK {task_id}] Starting Guard automation")
    logger.info(f"[TASK {task_id}] Create Account: {create_account}")
    logger.info(f"[TASK {task_id}] Policy Code: {policy_code or 'Will be created'}")
    logger.info(f"[TASK {task_id}] Quote Data: {json.dumps(quote_data, indent=2)}")
    
    login_handler = None
    
    try:
        logger.info(f"[TASK {task_id}] Initializing Guard login...")
        login_handler = GuardLogin(task_id="default")
        
        # If create_account is true, create new account first
        if create_account:
            logger.info(f"[TASK {task_id}] Creating new account...")
            
            # Use default account data if not provided
            if not account_data:
                from datetime import timedelta
                policy_inception_date = (datetime.now() + timedelta(days=2)).strftime("%m/%d/%Y")
                account_data = {
                    "legal_entity": "L",  # LLC
                    "applicant_name": "TEST COMPANY LLC",
                    "dba": "Test Business",
                    "address1": "280 Griffin St",
                    "address2": "",
                    "zipcode": "30253-3100",
                    "city": "McDonough",
                    "state": "GA",
                    "contact_name": "John Doe",
                    "contact_phone": {
                        "area": "404",
                        "prefix": "555",
                        "suffix": "9999"
                    },
                    "email": "harveyspectra@gmail.com",
                    "website": "www.testbusiness.com",
                    "years_in_business": "5",
                    "producer_id": "2774846",
                    "csr_id": "16977940",
                    "description": "Retail grocery store operations",
                    "policy_inception": policy_inception_date,
                    "headquarters_state": "GA",
                    "industry_id": "11",
                    "sub_industry_id": "45",
                    "business_type_id": "127",
                    "lines_of_business": ["CB"],
                    "ownership_type": "tenant"
                }
                logger.info(f"[TASK {task_id}] Using default account data")
            
            await login_handler.init_browser()
            login_result = await login_handler.login()
            
            if not login_result.get("success"):
                logger.error(f"[TASK {task_id}] Login failed")
                active_sessions[task_id] = {
                    "status": "failed",
                    "task_id": task_id,
                    "error": "Login failed",
                    "failed_at": datetime.now().isoformat()
                }
                return
            
            # Create account
            account_result = await login_handler.setup_account(account_data)
            await login_handler.close()
            
            if not account_result.get("success"):
                logger.error(f"[TASK {task_id}] Account creation failed")
                active_sessions[task_id] = {
                    "status": "failed",
                    "task_id": task_id,
                    "error": "Account creation failed",
                    "failed_at": datetime.now().isoformat()
                }
                return
            
            # Extract policy code and URL
            policy_code = account_result.get("policy_code")
            quotation_url = account_result.get("quotation_url")
            logger.info(f"[TASK {task_id}] ✅ Account created! Policy Code: {policy_code}")
            logger.info(f"[TASK {task_id}] Quotation URL: {quotation_url}")
            
            # Update session with new policy code
            active_sessions[task_id]["policy_code"] = policy_code
            active_sessions[task_id]["quotation_url"] = quotation_url
            
            # After account creation, run quote automation directly (already logged in)
            logger.info(f"[TASK {task_id}] Running quote automation...")
            
            # Import here to avoid circular imports
            from guard_quote import GuardQuote
            
            # Extract quote data with defaults
            quote_params = {
                "combined_sales": quote_data.get("combined_sales", "1000000") if quote_data else "1000000",
                "gas_gallons": quote_data.get("gas_gallons", "100000") if quote_data else "100000",
                "year_built": quote_data.get("year_built", "2025") if quote_data else "2025",
                "square_footage": quote_data.get("square_footage", "2000") if quote_data else "2000",
                "mpds": quote_data.get("mpds", "6") if quote_data else "6"
            }
            
            # Initialize quote handler with same task_id for session sharing
            quote_handler = GuardQuote(
                policy_code=policy_code,
                task_id="default",  # Share session
                **quote_params
            )
            
            try:
                # Initialize browser (session already exists)
                await quote_handler.init_browser()
                
                # Login (should use existing session)
                if not await quote_handler.login():
                    logger.error(f"[TASK {task_id}] Quote login failed")
                    active_sessions[task_id] = {
                        "status": "failed",
                        "task_id": task_id,
                        "error": "Quote login failed",
                        "failed_at": datetime.now().isoformat()
                    }
                    return
                
                # Navigate to quote URL
                if not await quote_handler.navigate_to_quote():
                    logger.error(f"[TASK {task_id}] Navigation to quote page failed")
                    active_sessions[task_id] = {
                        "status": "failed",
                        "task_id": task_id,
                        "error": "Navigation to quote page failed",
                        "failed_at": datetime.now().isoformat()
                    }
                    return
                
                # Fill quote details
                await quote_handler.fill_quote_details()
                
                logger.info(f"[TASK {task_id}] ✅ Quote automation completed for policy {policy_code}")
                active_sessions[task_id] = {
                    "status": "completed",
                    "task_id": task_id,
                    "policy_code": policy_code,
                    "completed_at": datetime.now().isoformat(),
                    "message": f"Quote automation completed successfully for policy {policy_code}",
                    "quotation_url": quotation_url
                }
                
            except Exception as e:
                logger.error(f"[TASK {task_id}] ❌ Quote automation error: {e}", exc_info=True)
                active_sessions[task_id] = {
                    "status": "failed",
                    "task_id": task_id,
                    "error": f"Quote automation error: {str(e)}",
                    "failed_at": datetime.now().isoformat()
                }
            finally:
                try:
                    await quote_handler.close()
                except Exception as e:
                    logger.warning(f"[TASK {task_id}] Error closing quote browser: {e}")
            
            return  # Exit after account creation + quote flow
        
        # Run full automation (login + quote) - for existing policy code
        logger.info(f"[TASK {task_id}] Running full automation...")
        automation_result = await login_handler.run_full_automation(
            policy_code=policy_code,
            quote_data=quote_data
        )
        
        if automation_result.get("success"):
            logger.info(f"[TASK {task_id}] ✅ SUCCESS! {automation_result.get('message')}")
            
            active_sessions[task_id] = {
                "status": "completed",
                "task_id": task_id,
                "policy_code": policy_code,
                "completed_at": datetime.now().isoformat(),
                "message": automation_result.get("message"),
                "result": automation_result
            }
        else:
            logger.error(f"[TASK {task_id}] ❌ Failed: {automation_result.get('message')}")
            active_sessions[task_id] = {
                "status": "failed",
                "task_id": task_id,
                "policy_code": policy_code,
                "error": automation_result.get("message"),
                "failed_at": datetime.now().isoformat()
            }
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"[TASK {task_id}] ❌ Error: {e}")
        logger.error(f"[TASK {task_id}] Full traceback:\n{error_details}")
        active_sessions[task_id] = {
            "status": "error",
            "task_id": task_id,
            "policy_code": policy_code,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": error_details,
            "failed_at": datetime.now().isoformat()
        }
    finally:
        if login_handler:
            try:
                await login_handler.close()
            except:
                pass


def worker_thread():
    """Worker thread that processes tasks from the queue"""
    global active_workers, browser_in_use
    
    while True:
        try:
            # Get task from queue (blocks until task available)
            task = task_queue.get(timeout=1)
            task_id, policy_code, quote_data, create_account, account_data = task
            
            # Update status to "waiting_for_browser"
            if task_id in active_sessions:
                active_sessions[task_id]["status"] = "waiting_for_browser"
                active_sessions[task_id]["picked_at"] = datetime.now().isoformat()
            
            # Acquire browser lock
            logger.info(f"[QUEUE] Task {task_id} waiting for browser lock...")
            browser_lock.acquire()
            browser_in_use = True
            
            # Increment active workers
            with worker_lock:
                active_workers += 1
                logger.info(f"[QUEUE] Task {task_id} acquired browser lock. Active: {active_workers}/{MAX_WORKERS}")
            
            try:
                # Update task status to running
                if task_id in active_sessions:
                    active_sessions[task_id]["status"] = "running"
                    active_sessions[task_id]["queue_position"] = 0
                    active_sessions[task_id]["started_at"] = datetime.now().isoformat()
                
                # Remove from queue position tracking
                if task_id in queue_position:
                    del queue_position[task_id]
                
                logger.info(f"[QUEUE] Processing task {task_id}")
                
                # Run automation
                run_automation_task_sync(task_id, policy_code, quote_data, create_account, account_data)
                
            except Exception as e:
                logger.error(f"[QUEUE] Error processing task {task_id}: {e}", exc_info=True)
                if task_id in active_sessions:
                    active_sessions[task_id]["status"] = "error"
                    active_sessions[task_id]["error"] = str(e)
            finally:
                # Decrement active workers
                with worker_lock:
                    active_workers -= 1
                    logger.info(f"[QUEUE] Task {task_id} finished. Active: {active_workers}/{MAX_WORKERS}")
                
                # Release browser lock
                browser_in_use = False
                browser_lock.release()
                logger.info(f"[QUEUE] Task {task_id} released browser lock")
                
                # Mark task as done
                task_queue.task_done()
                
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"[QUEUE] Worker thread error: {e}", exc_info=True)


def init_workers():
    """Initialize worker threads"""
    logger.info("=" * 80)
    logger.info("INITIALIZING GUARD AUTOMATION WORKERS")
    logger.info("=" * 80)
    
    # Start worker threads
    for i in range(MAX_WORKERS):
        worker = threading.Thread(target=worker_thread, daemon=True, name=f"Guard-Worker-{i+1}")
        worker.start()
        logger.info(f"  Worker {i+1}/{MAX_WORKERS} started")
    
    logger.info("=" * 80)
    logger.info("Guard Automation Server ready to accept requests...")
    logger.info("=" * 80)


# Initialize workers when module loads
init_workers()

if __name__ == '__main__':
    logger.info(f"Starting Guard webhook server on {WEBHOOK_HOST}:{WEBHOOK_PORT}")
    logger.info(f"Webhook endpoint: http://{WEBHOOK_HOST}:{WEBHOOK_PORT}{WEBHOOK_PATH}")
    logger.info(f"Health check: http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/health")
    logger.info(f"Queue status: http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/queue/status")
    logger.info(f"Logs directory: {LOG_DIR}")
    
    app.run(host=WEBHOOK_HOST, port=WEBHOOK_PORT, debug=False)
