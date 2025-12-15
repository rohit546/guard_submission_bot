"""
Test automation and download trace
Works with both local and deployed versions
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

# Configuration - change to switch between local and deployed
USE_LOCAL = True  # Set to False when deploying to production

if USE_LOCAL:
    BASE_URL = "http://localhost:5001"
else:
    BASE_URL = "https://your-guard-deployment-url.com"  # Update with actual deployment URL

WEBHOOK_URL = f"{BASE_URL}/webhook"
TRACES_DIR = Path(__file__).parent / "traces"
TRACES_DIR.mkdir(parents=True, exist_ok=True)


def download_trace(task_id: str, trace_type: str = "") -> bool:
    """Download trace file for a task"""
    trace_url = f"{BASE_URL}/trace/{task_id}"
    print(f"\n[DOWNLOAD] Fetching {trace_type} trace from: {trace_url}")
    
    try:
        response = requests.get(trace_url, timeout=30)
        if response.status_code == 200:
            filename = f"{trace_type}_{task_id}.zip" if trace_type else f"{task_id}.zip"
            trace_path = TRACES_DIR / filename
            trace_path.write_bytes(response.content)
            print(f"[OK] Trace saved: {trace_path}")
            print(f"[VIEW] Run: playwright show-trace {trace_path}")
            return True
        elif response.status_code == 404:
            print(f"[INFO] Trace not found")
            return False
        else:
            print(f"[ERROR] Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
        return False


def test_and_download_trace():
    """Send test request and download trace"""
    print("=" * 80)
    print("TEST GUARD AUTOMATION AND DOWNLOAD TRACE")
    print("=" * 80)
    print(f"\n[SERVER] {BASE_URL}")
    print(f"[MODE] {'LOCAL' if USE_LOCAL else 'DEPLOYED'}")
    
    task_id = f"test_trace_{int(time.time())}"
    payload = {
        "action": "start_automation",
        "task_id": task_id,
        "data": {
            "form_data": {
                "firstName": "John",
                "lastName": "Smith",
                "companyName": "Guard Test Company LLC",
                "email": "john.smith@guardtest.com",
                "phone": "(555) 987-6543",
                "address": "456 Oak Avenue",
                "city": "Atlanta",
                "state": "GA",
                "zip": "30301"
            },
            "quote_data": {
                "coverage_type": "General Liability",
                "policy_limit": "2000000",
                "effective_date": "2025-02-01",
                "business_description": "Retail store operations"
            },
            "save_form": True,
            "run_quote_automation": True
        }
    }
    
    print(f"\n[REQUEST] Sending to: {WEBHOOK_URL}")
    print(f"[TASK ID] {task_id}")
    print(f"[DATA] Company: Guard Test Company LLC")
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        print(f"\n[OK] Request accepted: {result.get('message')}")
        print(f"[STATUS] {result.get('status')}")
    except requests.exceptions.ConnectionError:
        print(f"\n[ERROR] Could not connect to server!")
        if USE_LOCAL:
            print(f"[INFO] Make sure webhook_server.py is running")
        return
    except Exception as e:
        print(f"\n[ERROR] Request failed: {e}")
        return
    
    # Monitor status
    status_url = f"{BASE_URL}/task/{task_id}/status"
    print(f"\n[MONITOR] Checking task status...")
    
    max_wait = 300
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(status_url, timeout=10)
            if response.status_code == 200:
                status = response.json()
                current_status = status.get('status')
                
                if current_status != last_status:
                    print(f"\n[STATUS] {current_status.upper()}")
                    last_status = current_status
                
                if current_status in ['completed', 'success']:
                    print(f"\n{'=' * 80}")
                    print(f"[SUCCESS] Task completed!")
                    print(f"{'=' * 80}")
                    
                    if status.get('message'):
                        print(f"\n[MESSAGE] {status['message']}")
                    
                    # Download traces
                    print(f"\n{'=' * 80}")
                    print("[DOWNLOADING TRACES]")
                    print(f"{'=' * 80}")
                    
                    download_trace(task_id, "login")
                    download_trace(f"quote_{task_id}", "quote")
                    
                    break
                    
                elif current_status in ['failed', 'error']:
                    print(f"\n{'=' * 80}")
                    print(f"[FAILED] Task failed!")
                    print(f"{'=' * 80}")
                    if status.get('error'):
                        print(f"[ERROR] {status['error']}")
                    
                    # Try to download traces for debugging
                    download_trace(task_id)
                    break
                    
        except Exception as e:
            print(f"[WARNING] Status check error: {e}")
        
        time.sleep(3)
    
    if time.time() - start_time >= max_wait:
        print(f"\n[TIMEOUT] Task timeout after {max_wait}s")
    
    print(f"\n{'=' * 80}")
    print("[DONE]")
    print("=" * 80)


def check_server_health():
    """Check server health"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print(f"[OK] Server running at {BASE_URL}")
            return True
        return False
    except:
        print(f"[ERROR] Server not reachable at {BASE_URL}")
        return False


if __name__ == "__main__":
    print("\n[CHECK] Testing server health...")
    if check_server_health():
        print("\n" + "=" * 80)
        test_and_download_trace()
    else:
        print("\n[ABORT] Server not running")
        if USE_LOCAL:
            print("[INFO] Start with: python webhook_server.py")
        sys.exit(1)
