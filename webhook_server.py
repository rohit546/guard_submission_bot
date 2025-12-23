"""
Webhook server for Guard Insurance automation
Receives data from Next.js app and triggers Guard automation
Version: 2.0.0 - Added trace system, cleanup scheduler
"""
import asyncio
import json
import logging
import threading
import queue
import time
import shutil
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
from guard_login import GuardLogin
from config import (
    WEBHOOK_HOST, WEBHOOK_PORT, WEBHOOK_PATH, LOG_DIR, TRACE_DIR, SESSION_DIR,
    MAX_WORKERS, COVERSHEET_WEBHOOK_URL
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

# Cleanup scheduler configuration
CLEANUP_INTERVAL_HOURS = 6  # Run cleanup every 6 hours
CLEANUP_MAX_AGE_DAYS = 2  # Delete files older than 2 days
MAX_TRACE_FILES = 5  # Keep only last 5 trace files

# Cleanup scheduler thread
cleanup_thread = None
cleanup_stop_event = threading.Event()


def extract_submission_id(task_id: str) -> str:
    """
    Extract submission_id from task_id
    Format: guard_{submission_id}_{timestamp} or guard_{timestamp}
    Returns submission_id if found, otherwise returns task_id
    """
    if not task_id:
        return None
    
    # Try to extract submission_id from format: guard_{submission_id}_{timestamp}
    parts = task_id.split('_')
    if len(parts) >= 3:
        # Format: guard_{submission_id}_{timestamp}
        # Check if middle part looks like a UUID (has dashes) or is a valid submission ID
        submission_id = parts[1]
        # If it's a UUID format (has dashes), return it
        if '-' in submission_id and len(submission_id) > 10:
            return submission_id
        # Otherwise, might be a different format, try to return it anyway
        if len(submission_id) > 5:  # Reasonable length for submission ID
            return submission_id
    
    # If format doesn't match, return task_id as fallback
    return task_id


def notify_coversheet_completion(task_id: str, submission_id: str = None, success: bool = True, 
                                 result_data: dict = None, error: str = None, error_details: str = None):
    """
    Notify Coversheet when automation completes (success or failure)
    
    Args:
        task_id: The task ID that was sent in the original request
        submission_id: Extract from task_id if not provided
        success: True if completed successfully, False if failed
        result_data: Dict with policy_code, quote_url, message (if success)
        error: Error message string (if failed)
        error_details: Full error details/stack trace (if failed)
    """
    try:
        # Extract submission_id from task_id if not provided
        if not submission_id:
            submission_id = extract_submission_id(task_id)
        
        # Prepare payload
        payload = {
            "carrier": "guard",
            "task_id": task_id,
            "submission_id": submission_id or task_id,
            "status": "completed" if success else "failed",
            "completed_at": datetime.utcnow().isoformat() + "Z"
        }
        
        if success and result_data:
            payload["result"] = {
                "policy_code": result_data.get("policy_code"),
                "quote_url": result_data.get("quote_url"),
                "message": result_data.get("message", "Automation completed successfully")
            }
        else:
            payload["error"] = error or "Automation failed"
            if error_details:
                payload["error_details"] = error_details
        
        # Skip webhook if URL is not configured
        if not COVERSHEET_WEBHOOK_URL or COVERSHEET_WEBHOOK_URL == '':
            logger.info(f"[WEBHOOK] Skipping Coversheet notification - URL not configured")
            return
        
        # Send webhook callback
        logger.info(f"[WEBHOOK] Notifying Coversheet: {payload['status']} for task {task_id}")
        logger.info(f"[WEBHOOK] URL: {COVERSHEET_WEBHOOK_URL}")
        logger.info(f"[WEBHOOK] Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            COVERSHEET_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        logger.info(f"[WEBHOOK] ✅ Successfully notified Coversheet: {payload['status']}")
        logger.info(f"[WEBHOOK] Response: {response.status_code} - {response.text[:200]}")
        
    except requests.exceptions.HTTPError as e:
        # More detailed error logging for HTTP errors
        error_msg = f"HTTP {e.response.status_code}: {e.response.reason}"
        if e.response.status_code == 404:
            error_msg += f" - Endpoint not found. Please verify the URL: {COVERSHEET_WEBHOOK_URL}"
            error_msg += f"\n[WEBHOOK] Response body: {e.response.text[:500]}"
        logger.warning(f"[WEBHOOK] ⚠️ Failed to notify Coversheet: {error_msg}")
        # Don't fail the automation if webhook fails - just log it
    except requests.exceptions.RequestException as e:
        logger.warning(f"[WEBHOOK] ⚠️ Failed to notify Coversheet: {e}")
        # Don't fail the automation if webhook fails - just log it
    except Exception as e:
        logger.warning(f"[WEBHOOK] ⚠️ Error notifying Coversheet: {e}", exc_info=True)
        # Don't fail the automation if webhook fails - just log it


def cleanup_old_files():
    """
    Cleanup old files to prevent disk space issues:
    - Delete browser_data folders older than CLEANUP_MAX_AGE_DAYS
    - Keep only MAX_TRACE_FILES most recent trace files
    - Delete old log files older than CLEANUP_MAX_AGE_DAYS
    - Delete all screenshot folders
    """
    logger.info("[CLEANUP] Starting scheduled cleanup...")
    now = time.time()
    max_age_seconds = CLEANUP_MAX_AGE_DAYS * 24 * 60 * 60
    deleted_count = 0
    
    try:
        # 1. Cleanup old browser_data folders (except browser_data_default)
        logger.info("[CLEANUP] Cleaning up old browser_data folders...")
        for folder in SESSION_DIR.glob("browser_data_*"):
            if folder.name == "browser_data_default":
                continue  # Keep the default browser data folder
            try:
                folder_age = now - folder.stat().st_mtime
                if folder_age > max_age_seconds:
                    shutil.rmtree(folder)
                    deleted_count += 1
                    logger.info(f"[CLEANUP] Deleted old browser_data: {folder.name}")
            except Exception as e:
                logger.debug(f"[CLEANUP] Could not delete {folder}: {e}")
        
        # 2. Keep only last MAX_TRACE_FILES trace files
        logger.info("[CLEANUP] Cleaning up old trace files...")
        trace_files = sorted(TRACE_DIR.glob("*.zip"), key=lambda f: f.stat().st_mtime, reverse=True)
        if len(trace_files) > MAX_TRACE_FILES:
            for trace_file in trace_files[MAX_TRACE_FILES:]:
                try:
                    trace_file.unlink()
                    deleted_count += 1
                    logger.info(f"[CLEANUP] Deleted old trace: {trace_file.name}")
                except Exception as e:
                    logger.debug(f"[CLEANUP] Could not delete trace {trace_file}: {e}")
        
        # 3. Cleanup old log files
        logger.info("[CLEANUP] Cleaning up old log files...")
        for log_file in LOG_DIR.glob("*.log"):
            if log_file.name == "webhook_server.log":
                continue  # Don't delete current log
            try:
                file_age = now - log_file.stat().st_mtime
                if file_age > max_age_seconds:
                    log_file.unlink()
                    deleted_count += 1
                    logger.info(f"[CLEANUP] Deleted old log: {log_file.name}")
            except Exception as e:
                logger.debug(f"[CLEANUP] Could not delete log {log_file}: {e}")
        
        # 4. Delete old screenshot folders
        logger.info("[CLEANUP] Cleaning up screenshot folders...")
        screenshots_dir = LOG_DIR / "screenshots"
        if screenshots_dir.exists():
            for folder in screenshots_dir.iterdir():
                if folder.is_dir():
                    try:
                        folder_age = now - folder.stat().st_mtime
                        if folder_age > max_age_seconds:
                            shutil.rmtree(folder)
                            deleted_count += 1
                            logger.info(f"[CLEANUP] Deleted screenshot folder: {folder.name}")
                    except Exception as e:
                        logger.debug(f"[CLEANUP] Could not delete screenshot folder {folder}: {e}")
        
        logger.info(f"[CLEANUP] Cleanup completed. Deleted {deleted_count} items.")
        
    except Exception as e:
        logger.error(f"[CLEANUP] Error during cleanup: {e}")


def cleanup_scheduler():
    """Background thread that runs cleanup periodically"""
    logger.info(f"[CLEANUP] Scheduler started - will run every {CLEANUP_INTERVAL_HOURS} hours")
    
    while not cleanup_stop_event.is_set():
        # Wait for interval (check stop event every minute)
        for _ in range(CLEANUP_INTERVAL_HOURS * 60):
            if cleanup_stop_event.is_set():
                break
            time.sleep(60)  # Sleep 1 minute at a time
        
        if not cleanup_stop_event.is_set():
            cleanup_old_files()
    
    logger.info("[CLEANUP] Scheduler stopped")


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
            # If submission_id is provided, use format: guard_{submission_id}_{timestamp}
            submission_id = payload.get('submission_id')
            if submission_id:
                task_id = payload.get('task_id') or f"guard_{submission_id}_{int(datetime.now().timestamp())}"
            else:
                task_id = payload.get('task_id') or f"guard_{policy_code or 'new'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            logger.info(f"[GUARD] Starting automation task: {task_id}")
            if submission_id:
                logger.info(f"[GUARD] Submission ID: {submission_id}")
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
                "submission_id": submission_id,  # Store submission_id for webhook callback
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


@app.route('/trace/<task_id>', methods=['GET'])
def get_trace(task_id: str):
    """Download trace file for a specific task"""
    try:
        # Try multiple trace file patterns
        trace_candidates = [
            TRACE_DIR / f"{task_id}.zip",  # Exact task_id
            TRACE_DIR / f"default.zip",  # Default trace
            *list(TRACE_DIR.glob(f"*{task_id}*.zip")),  # Any file containing task_id
        ]
        
        # Find the first existing trace file
        trace_path = None
        for candidate in trace_candidates:
            if candidate.exists() and candidate.is_file():
                trace_path = candidate
                break
        
        if not trace_path:
            logger.warning(f"Trace not found for task: {task_id}")
            logger.info(f"Searched paths: {[str(p) for p in trace_candidates[:3]]}")
            return jsonify({
                "status": "not_found",
                "message": f"Trace not found for task {task_id}"
            }), 404
        
        logger.info(f"Serving trace for task {task_id}: {trace_path}")
        return send_file(
            str(trace_path),
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{trace_path.name}"
        )
    except Exception as e:
        logger.error(f"Error serving trace for task {task_id}: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/traces', methods=['GET'])
def list_traces():
    """List all available trace files - returns HTML UI or JSON"""
    try:
        traces = []
        for trace_file in sorted(TRACE_DIR.glob("*.zip"), key=lambda f: f.stat().st_mtime, reverse=True):
            try:
                stat = trace_file.stat()
                traces.append({
                    "task_id": trace_file.stem,
                    "filename": trace_file.name,
                    "size_bytes": stat.st_size,
                    "size_kb": round(stat.st_size / 1024, 2),
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "url": f"/trace/{trace_file.stem}"
                })
            except Exception as e:
                logger.debug(f"Error getting info for {trace_file}: {e}")
        
        # Return HTML if browser request, JSON otherwise
        if 'text/html' in request.headers.get('Accept', ''):
            html = '''<!DOCTYPE html>
<html><head><title>Guard Automation - Traces</title>
<style>
body{font-family:'Segoe UI',Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;background:#f5f5f5}
h1{color:#2c3e50;border-bottom:3px solid #3498db;padding-bottom:10px}
.info{background:#e8f4f8;padding:15px;border-radius:8px;margin-bottom:20px}
table{width:100%;border-collapse:collapse;background:white;box-shadow:0 2px 5px rgba(0,0,0,0.1);border-radius:8px;overflow:hidden}
th{background:#3498db;color:white;padding:12px;text-align:left}
td{padding:12px;text-align:left;border-bottom:1px solid #eee}
tr:hover{background:#f8f9fa}
a{color:#3498db;text-decoration:none;font-weight:bold}
a:hover{text-decoration:underline}
.size{color:#7f8c8d}
.date{color:#95a5a6;font-size:0.9em}
.download-btn{background:#27ae60;color:white;padding:6px 12px;border-radius:4px;font-size:0.85em}
.download-btn:hover{background:#219a52;text-decoration:none}
.empty{text-align:center;padding:40px;color:#7f8c8d}
</style></head>
<body>
<h1>🛡️ Guard Automation - Traces</h1>
<div class="info">
<strong>Total:</strong> ''' + str(len(traces)) + ''' traces | <strong>Max stored:</strong> ''' + str(MAX_TRACE_FILES) + '''<br>
<small>Traces are automatically cleaned up. Only the most recent ''' + str(MAX_TRACE_FILES) + ''' are kept.</small>
</div>'''
            
            if traces:
                html += '''<table>
<tr><th>Task ID</th><th>Size</th><th>Created</th><th>Action</th></tr>'''
                for t in traces:
                    html += f'''<tr>
<td><code>{t["task_id"]}</code></td>
<td class="size">{t["size_kb"]} KB</td>
<td class="date">{t["created_at"][:19].replace('T', ' ')}</td>
<td><a href="{t["url"]}" class="download-btn">⬇ Download</a></td>
</tr>'''
                html += '</table>'
            else:
                html += '<div class="empty">📭 No traces available yet.<br>Run an automation task to generate traces.</div>'
            
            html += '''
<div style="margin-top:30px;text-align:center;color:#95a5a6;font-size:0.85em">
Guard Insurance Automation Server | <a href="/health">Health Check</a> | <a href="/tasks">Tasks</a>
</div>
</body></html>'''
            return html, 200, {'Content-Type': 'text/html'}
        
        return jsonify({
            "total": len(traces),
            "max_traces": MAX_TRACE_FILES,
            "traces": traces
        }), 200
    except Exception as e:
        logger.error(f"Error listing traces: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


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
    trace_id = None
    
    # Create trace_id from company name if account_data is provided
    if account_data and account_data.get('applicant_name'):
        company_name = account_data.get('applicant_name', '')
        # Sanitize company name for filename (remove special chars, limit length)
        safe_company = "".join(c if c.isalnum() else "_" for c in company_name)[:30].lower()
        trace_id = safe_company
        logger.info(f"[TASK {task_id}] Trace ID: {trace_id}")
    elif policy_code:
        trace_id = policy_code.lower()
    
    try:
        logger.info(f"[TASK {task_id}] Initializing Guard login...")
        login_handler = GuardLogin(task_id="default", trace_id=trace_id)
        
        # If create_account is true, create new account first
        if create_account:
            logger.info(f"[TASK {task_id}] Creating new account...")
            
            # ==================================================================
            # APPLY HARDCODED DEFAULTS FOR ACCOUNT DATA
            # ==================================================================
            from datetime import timedelta
            policy_inception_date = (datetime.now() + timedelta(days=2)).strftime("%m/%d/%Y")
            
            # Default account data (used if nothing provided)
            if not account_data:
                account_data = {
                    "legal_entity": "L",
                    "applicant_name": "TEST COMPANY LLC",
                    "dba": "",
                    "address1": "280 Griffin St",
                    "address2": "",
                    "zipcode": "30253-3100",
                    "city": "McDonough",
                    "state": "GA",
                    "contact_name": "John Doe",
                    "contact_phone": {"area": "404", "prefix": "555", "suffix": "9999"},
                    "email": "test@example.com",
                    "years_in_business": "5",
                    "ownership_type": "tenant"
                }
                logger.info(f"[TASK {task_id}] Using default account data")
            
            # Apply HARDCODED values (user doesn't need to send these)
            account_data["website"] = ""  # Hardcoded
            # NOTE: description is sent by user (mandatory field)
            account_data["producer_id"] = "2774846"  # Hardcoded
            account_data["csr_id"] = "16977940"  # Hardcoded
            account_data["policy_inception"] = policy_inception_date  # Auto-calculated
            account_data["headquarters_state"] = account_data.get("state", "GA")  # Copy from state
            account_data["industry_id"] = "11"  # Hardcoded (Gas Station)
            account_data["sub_industry_id"] = "45"  # Hardcoded
            account_data["business_type_id"] = "127"  # Hardcoded
            account_data["lines_of_business"] = ["CB"]  # Hardcoded (Commercial Business)
            
            logger.info(f"[TASK {task_id}] Applied hardcoded defaults to account data")
            
            # Update trace_id with company name if not already set
            if not trace_id and account_data.get('applicant_name'):
                company_name = account_data.get('applicant_name', '')
                safe_company = "".join(c if c.isalnum() else "_" for c in company_name)[:30].lower()
                trace_id = safe_company
                # Update login_handler with new trace_id
                login_handler.trace_id = trace_id
                if login_handler.enable_tracing:
                    from config import TRACE_DIR
                    login_handler.trace_path = TRACE_DIR / f"{trace_id}.zip"
                logger.info(f"[TASK {task_id}] Updated Trace ID: {trace_id}")
            
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
                # Notify Coversheet of failure
                submission_id = None
                if task_id in active_sessions:
                    submission_id = active_sessions[task_id].get('submission_id')
                notify_coversheet_completion(
                    task_id=task_id,
                    submission_id=submission_id,
                    success=False,
                    error="Login failed",
                    error_details=None
                )
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
                # Notify Coversheet of failure
                submission_id = None
                if task_id in active_sessions:
                    submission_id = active_sessions[task_id].get('submission_id')
                notify_coversheet_completion(
                    task_id=task_id,
                    submission_id=submission_id,
                    success=False,
                    error="Account creation failed",
                    error_details=None
                )
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
                "mpds": quote_data.get("mpds", "6") if quote_data else "6",
                "employees": quote_data.get("employees", "3") if quote_data else "3"  # Default to 3 if not provided
            }
            
            # Initialize quote handler with same task_id for session sharing
            # Use quote_{trace_id} for quote trace file
            quote_trace_id = f"quote_{trace_id}" if trace_id else f"quote_{policy_code.lower()}"
            quote_handler = GuardQuote(
                policy_code=policy_code,
                task_id="default",  # Share session
                trace_id=quote_trace_id,
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
                
                # Notify Coversheet of successful completion (account + quote)
                submission_id = None
                if task_id in active_sessions:
                    submission_id = active_sessions[task_id].get('submission_id')
                
                notify_coversheet_completion(
                    task_id=task_id,
                    submission_id=submission_id,
                    success=True,
                    result_data={
                        "policy_code": policy_code,
                        "quote_url": quotation_url,
                        "message": f"Account created and quote completed successfully for policy {policy_code}"
                    }
                )
                
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                error_message = f"Quote automation error: {str(e)}"
                logger.error(f"[TASK {task_id}] ❌ Quote automation error: {e}", exc_info=True)
                active_sessions[task_id] = {
                    "status": "failed",
                    "task_id": task_id,
                    "error": error_message,
                    "failed_at": datetime.now().isoformat()
                }
                
                # Notify Coversheet of failure
                submission_id = None
                if task_id in active_sessions:
                    submission_id = active_sessions[task_id].get('submission_id')
                
                notify_coversheet_completion(
                    task_id=task_id,
                    submission_id=submission_id,
                    success=False,
                    error=error_message,
                    error_details=error_details
                )
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
            
            # Notify Coversheet of successful completion
            # Get submission_id from active_sessions if stored, otherwise extract from task_id
            submission_id = None
            if task_id in active_sessions:
                submission_id = active_sessions[task_id].get('submission_id')
            
            notify_coversheet_completion(
                task_id=task_id,
                submission_id=submission_id,
                success=True,
                result_data={
                    "policy_code": policy_code,
                    "quote_url": automation_result.get("quote_url"),
                    "message": automation_result.get("message", "Guard automation completed successfully")
                }
            )
        else:
            logger.error(f"[TASK {task_id}] ❌ Failed: {automation_result.get('message')}")
            active_sessions[task_id] = {
                "status": "failed",
                "task_id": task_id,
                "policy_code": policy_code,
                "error": automation_result.get("message"),
                "failed_at": datetime.now().isoformat()
            }
            
            # Notify Coversheet of failure
            submission_id = None
            if task_id in active_sessions:
                submission_id = active_sessions[task_id].get('submission_id')
            
            notify_coversheet_completion(
                task_id=task_id,
                submission_id=submission_id,
                success=False,
                error=automation_result.get("message", "Automation failed"),
                error_details=None
            )
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        error_message = str(e)
        logger.error(f"[TASK {task_id}] ❌ Error: {e}")
        logger.error(f"[TASK {task_id}] Full traceback:\n{error_details}")
        active_sessions[task_id] = {
            "status": "error",
            "task_id": task_id,
            "policy_code": policy_code,
            "error": error_message,
            "error_type": type(e).__name__,
            "traceback": error_details,
            "failed_at": datetime.now().isoformat()
        }
        
        # Notify Coversheet of error
        submission_id = None
        if task_id in active_sessions:
            submission_id = active_sessions[task_id].get('submission_id')
        
        notify_coversheet_completion(
            task_id=task_id,
            submission_id=submission_id,
            success=False,
            error=error_message,
            error_details=error_details
        )
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
    """Initialize worker threads and cleanup scheduler"""
    global cleanup_thread
    
    logger.info("=" * 80)
    logger.info("GUARD AUTOMATION WEBHOOK SERVER v2.0.0")
    logger.info("=" * 80)
    logger.info(f"Queue System: {MAX_WORKERS} worker threads (with browser locking)")
    logger.info(f"Browser Lock: Only 1 browser instance at a time")
    logger.info(f"Cleanup: Every {CLEANUP_INTERVAL_HOURS}h, delete files older than {CLEANUP_MAX_AGE_DAYS} days")
    logger.info(f"Traces: Keep only last {MAX_TRACE_FILES} trace files")
    logger.info("Starting worker threads...")
    
    # Start worker threads
    for i in range(MAX_WORKERS):
        worker = threading.Thread(target=worker_thread, daemon=True, name=f"Guard-Worker-{i+1}")
        worker.start()
        logger.info(f"  Worker {i+1}/{MAX_WORKERS} started")
    
    # Start cleanup scheduler thread
    cleanup_thread = threading.Thread(target=cleanup_scheduler, daemon=True, name="Cleanup-Scheduler")
    cleanup_thread.start()
    logger.info("  Cleanup scheduler started")
    
    # Run initial cleanup on startup
    logger.info("  Running initial cleanup...")
    cleanup_old_files()
    
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
    logger.info(f"Traces: http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/traces")
    logger.info(f"Logs directory: {LOG_DIR}")
    
    app.run(host=WEBHOOK_HOST, port=WEBHOOK_PORT, debug=False)
