"""
Test local webhook server - sends data to localhost:5001
Run webhook_server.py first, then run this test
"""
import requests
import time
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

WEBHOOK_URL = "http://localhost:5001/webhook"
STATUS_URL_BASE = "http://localhost:5001/task"
TRACE_URL_BASE = "http://localhost:5001/trace"
TRACES_DIR = Path(__file__).parent / "traces"


def test_local_webhook():
    """Send a test request to local webhook server"""
    print("=" * 80)
    print("TEST GUARD WEBHOOK SERVER (LOCAL)")
    print("=" * 80)
    print("\nMake sure webhook_server.py is running first!")
    print("Run: python webhook_server.py")
    print("=" * 80)
    
    # Ask user which flow to test
    print("\nSelect test mode:")
    print("1. Use existing policy code (TEBP602893)")
    print("2. Create new account (get new policy code)")
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    # Test data - Guard automation format
    task_id = f"local_test_{int(time.time())}"
    
    if choice == "2":
        # Create new account flow
        payload = {
            "action": "start_automation",
            "task_id": task_id,
            "create_account": True,
            "quote_data": {
                "combined_sales": "800000",
                "gas_gallons": "500000",
                "year_built": "2000",
                "square_footage": "4200",
                "mpds": "6"
            }
        }
        print(f"\n[REQUEST] Sending to: {WEBHOOK_URL}")
        print(f"[TASK ID] {task_id}")
        print(f"[MODE] CREATE NEW ACCOUNT")
        print(f"[DATA] Combined Sales: $800,000 | Gas Gallons: 500,000")
        print(f"[DATA] Year Built: 2000 | Square Footage: 4,200 | Pumps: 6")
    else:
        # Use existing policy code
        payload = {
            "action": "start_automation",
            "task_id": task_id,
            "policy_code": "TEBP602893",
            "create_account": False,
            "quote_data": {
                "combined_sales": "800000",
                "gas_gallons": "500000",
                "year_built": "2000",
                "square_footage": "4200",
                "mpds": "6"
            }
        }
        print(f"\n[REQUEST] Sending to: {WEBHOOK_URL}")
        print(f"[TASK ID] {task_id}")
        print(f"[POLICY] TEBP602893 - BISMILLAH LLC")
        print(f"[DATA] Combined Sales: $800,000 | Gas Gallons: 500,000")
        print(f"[DATA] Year Built: 2000 | Square Footage: 4,200 | Pumps: 6")
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        print(f"\n[OK] Request accepted: {result.get('message', 'OK')}")
        print(f"[STATUS] {result.get('status', 'unknown')}")
        
    except requests.exceptions.ConnectionError:
        print(f"\n[ERROR] Could not connect to webhook server!")
        print(f"[INFO] Make sure webhook_server.py is running:")
        print(f"       python webhook_server.py")
        return
    except Exception as e:
        print(f"\n[ERROR] Failed to send request: {e}")
        return
    
    # Monitor task status
    status_url = f"{STATUS_URL_BASE}/{task_id}/status"
    print(f"\n[MONITOR] Checking task status...")
    print(f"[URL] {status_url}")
    
    max_wait = 300
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(status_url, timeout=10)
            if response.status_code == 200:
                status = response.json()
                current_status = status.get('status', 'unknown')
                
                if current_status != last_status:
                    print(f"\n[STATUS] {current_status.upper()}")
                    if status.get('queue_position'):
                        print(f"[QUEUE] Position: {status['queue_position']}")
                    if status.get('policy_code'):
                        print(f"[POLICY CODE] {status.get('policy_code')}")
                    if status.get('quotation_url'):
                        print(f"[QUOTE URL] {status.get('quotation_url')}")
                    last_status = current_status
                
                if current_status in ['completed', 'success']:
                    print(f"\n{'=' * 80}")
                    print(f"[SUCCESS] Task completed!")
                    print(f"{'=' * 80}")
                    
                    if status.get('message'):
                        print(f"\n[RESULT] {status.get('message')}")
                    
                    # Try to download trace
                    trace_url = f"{TRACE_URL_BASE}/{task_id}"
                    try:
                        print(f"\n[DOWNLOAD] Fetching trace from: {trace_url}")
                        trace_response = requests.get(trace_url, timeout=10)
                        if trace_response.status_code == 200:
                            trace_path = TRACES_DIR / f"{task_id}.zip"
                            trace_path.parent.mkdir(exist_ok=True)
                            trace_path.write_bytes(trace_response.content)
                            print(f"[OK] Trace saved: {trace_path}")
                            print(f"[VIEW] Run: playwright show-trace {trace_path}")
                        else:
                            print(f"[INFO] Trace not available")
                    except Exception as e:
                        print(f"[INFO] Could not download trace: {e}")
                    
                    break
                    
                elif current_status in ['failed', 'error']:
                    print(f"\n{'=' * 80}")
                    print(f"[FAILED] Task failed!")
                    print(f"{'=' * 80}")
                    if status.get('error'):
                        print(f"[ERROR] {status['error']}")
                    break
                    
            elif response.status_code == 404:
                print(f"[INFO] Task not found yet")
            
        except Exception as e:
            print(f"[WARNING] Error checking status: {e}")
        
        time.sleep(3)
    
    if time.time() - start_time >= max_wait:
        print(f"\n[TIMEOUT] Task did not complete within {max_wait} seconds")
    
    print(f"\n{'=' * 80}")
    print("[DONE]")
    print("=" * 80)


def check_server_health():
    """Check if webhook server is running"""
    try:
        response = requests.get("http://localhost:5001/health", timeout=5)
        if response.status_code == 200:
            print("[OK] Webhook server is running!")
            return True
        else:
            print(f"[WARNING] Server status: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("[ERROR] Webhook server is not running!")
        print("[INFO] Start it with: python webhook_server.py")
        return False
    except Exception as e:
        print(f"[ERROR] Health check failed: {e}")
        return False


if __name__ == "__main__":
    print("\n[CHECK] Testing server health...")
    if check_server_health():
        print("\n" + "=" * 80)
        test_local_webhook()
    else:
        print("\n[ABORT] Server not running")
        print("[INFO] Start the server:")
        print("       cd \"c:\\Users\\Dell\\Desktop\\RPA For a\\guard_automation\"")
        print("       python webhook_server.py")
        sys.exit(1)
