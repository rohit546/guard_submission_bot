"""
Test Guard Webhook on Railway - sends requests to deployed server
Usage: python test_railway_server.py
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

# Railway deployed server URL - UPDATE THIS WITH YOUR RAILWAY URL
RAILWAY_URL = "https://guardsubmissionbot-production.up.railway.app"

# Endpoints
WEBHOOK_URL = f"{RAILWAY_URL}/webhook"
HEALTH_URL = f"{RAILWAY_URL}/health"
TRACES_URL = f"{RAILWAY_URL}/traces"
TASKS_URL = f"{RAILWAY_URL}/tasks"
QUEUE_URL = f"{RAILWAY_URL}/queue/status"

# Local traces directory
TRACES_DIR = Path(__file__).parent / "downloaded_traces"


def check_server_health():
    """Check if Railway server is running"""
    print("\n" + "=" * 80)
    print("GUARD AUTOMATION - RAILWAY SERVER TEST")
    print("=" * 80)
    print(f"\n[CHECK] Testing server health...")
    print(f"[URL] {HEALTH_URL}")
    
    try:
        response = requests.get(HEALTH_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"\n[✅ HEALTHY] Server is running!")
            print(f"    Service: {data.get('service', 'N/A')}")
            print(f"    Active Workers: {data.get('active_workers', 'N/A')}/{data.get('max_workers', 'N/A')}")
            print(f"    Queue Size: {data.get('queue_size', 'N/A')}")
            print(f"    Timestamp: {data.get('timestamp', 'N/A')}")
            return True
        else:
            print(f"\n[⚠️ WARNING] Server status: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"\n[❌ ERROR] Could not connect to server!")
        print(f"[INFO] Make sure the Railway URL is correct: {RAILWAY_URL}")
        return False
    except Exception as e:
        print(f"\n[❌ ERROR] Health check failed: {e}")
        return False


def list_traces():
    """List available traces on server"""
    print("\n" + "-" * 60)
    print("[TRACES] Listing available traces...")
    print(f"[URL] {TRACES_URL}")
    
    try:
        response = requests.get(TRACES_URL, headers={"Accept": "application/json"}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            traces = data.get("traces", [])
            print(f"\n[📁 TRACES] Total: {len(traces)} / Max: {data.get('max_traces', 5)}")
            
            if traces:
                print("\n    ID                              | Size     | Created")
                print("    " + "-" * 70)
                for t in traces[:5]:  # Show top 5
                    print(f"    {t['task_id'][:35]:<35} | {t['size_kb']:>6} KB | {t['created_at'][:19]}")
            else:
                print("    No traces available yet")
            return traces
        else:
            print(f"[WARNING] Could not list traces: {response.status_code}")
            return []
    except Exception as e:
        print(f"[ERROR] Failed to list traces: {e}")
        return []


def download_trace(task_id: str):
    """Download a specific trace file"""
    trace_url = f"{RAILWAY_URL}/trace/{task_id}"
    print(f"\n[DOWNLOAD] Downloading trace: {task_id}")
    print(f"[URL] {trace_url}")
    
    try:
        response = requests.get(trace_url, timeout=30)
        if response.status_code == 200:
            TRACES_DIR.mkdir(exist_ok=True)
            trace_path = TRACES_DIR / f"{task_id}.zip"
            trace_path.write_bytes(response.content)
            print(f"[✅ OK] Trace saved: {trace_path}")
            print(f"[VIEW] Run: playwright show-trace {trace_path}")
            return True
        else:
            print(f"[❌ ERROR] Could not download trace: {response.status_code}")
            return False
    except Exception as e:
        print(f"[❌ ERROR] Download failed: {e}")
        return False


def send_automation_request(policy_code: str, quote_data: dict, task_id: str = None):
    """Send automation request to Railway server"""
    print("\n" + "=" * 80)
    print("[🚀 SEND REQUEST]")
    print("=" * 80)
    
    payload = {
        "action": "start_automation",
        "policy_code": policy_code,
        "create_account": False,
        "quote_data": quote_data
    }
    
    if task_id:
        payload["task_id"] = task_id
    
    print(f"\n[URL] {WEBHOOK_URL}")
    print(f"[POLICY] {policy_code}")
    print(f"[DATA] Combined Sales: ${quote_data.get('combined_sales', 'N/A')}")
    print(f"[DATA] Gas Gallons: {quote_data.get('gas_gallons', 'N/A')}")
    print(f"[DATA] Year Built: {quote_data.get('year_built', 'N/A')}")
    print(f"[DATA] Square Footage: {quote_data.get('square_footage', 'N/A')}")
    print(f"[DATA] MPDs (Pumps): {quote_data.get('mpds', 'N/A')}")
    
    try:
        print("\n[SENDING...]")
        response = requests.post(WEBHOOK_URL, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        task_id = result.get("task_id")
        print(f"\n[✅ ACCEPTED] Request accepted!")
        print(f"[TASK ID] {task_id}")
        print(f"[STATUS] {result.get('status', 'unknown')}")
        print(f"[MESSAGE] {result.get('message', 'N/A')}")
        
        return task_id
        
    except requests.exceptions.ConnectionError:
        print(f"\n[❌ ERROR] Could not connect to server!")
        return None
    except Exception as e:
        print(f"\n[❌ ERROR] Failed to send request: {e}")
        return None


def monitor_task(task_id: str, max_wait: int = 600):
    """Monitor task status until completion"""
    print("\n" + "-" * 60)
    print(f"[📊 MONITORING] Task: {task_id}")
    print("-" * 60)
    
    status_url = f"{RAILWAY_URL}/task/{task_id}/status"
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(status_url, timeout=10)
            if response.status_code == 200:
                status = response.json()
                current_status = status.get('status', 'unknown')
                
                if current_status != last_status:
                    elapsed = int(time.time() - start_time)
                    print(f"\n[{elapsed:3d}s] Status: {current_status.upper()}")
                    
                    if status.get('queue_position'):
                        print(f"       Queue Position: {status['queue_position']}")
                    if status.get('policy_code'):
                        print(f"       Policy Code: {status['policy_code']}")
                    if status.get('message'):
                        print(f"       Message: {status['message']}")
                    
                    last_status = current_status
                
                if current_status in ['completed', 'success']:
                    print("\n" + "=" * 80)
                    print("[🎉 SUCCESS] Task completed!")
                    print("=" * 80)
                    
                    if status.get('quotation_url'):
                        print(f"\n[QUOTE URL] {status['quotation_url']}")
                    
                    return True
                    
                elif current_status in ['failed', 'error']:
                    print("\n" + "=" * 80)
                    print("[❌ FAILED] Task failed!")
                    print("=" * 80)
                    
                    if status.get('error'):
                        print(f"\n[ERROR] {status['error']}")
                    
                    return False
                    
            elif response.status_code == 404:
                print(f"[INFO] Task not found yet...")
            
        except Exception as e:
            print(f"[WARNING] Error checking status: {e}")
        
        # Print progress dot
        print(".", end="", flush=True)
        time.sleep(5)
    
    print(f"\n\n[⏰ TIMEOUT] Task did not complete within {max_wait} seconds")
    return False


def main():
    """Main test function"""
    # Check server health first
    if not check_server_health():
        print("\n[ABORT] Server not reachable. Exiting.")
        sys.exit(1)
    
    # List existing traces
    list_traces()
    
    # Show menu
    print("\n" + "=" * 80)
    print("SELECT ACTION:")
    print("=" * 80)
    print("1. Send new automation request")
    print("2. Check task status")
    print("3. List traces")
    print("4. Download trace")
    print("5. Exit")
    
    choice = input("\nEnter choice (1-5): ").strip()
    
    if choice == "1":
        # Send new automation request
        print("\n[CONFIG] Default policy code: TEBP602893")
        custom_policy = input("Enter policy code (or press Enter for default): ").strip()
        policy_code = custom_policy if custom_policy else "TEBP602893"
        
        # Default quote data
        quote_data = {
            "combined_sales": "800000",
            "gas_gallons": "500000",
            "year_built": "2000",
            "square_footage": "4200",
            "mpds": "6"
        }
        
        # Send request
        task_id = send_automation_request(policy_code, quote_data)
        
        if task_id:
            # Ask if user wants to monitor
            monitor = input("\n[MONITOR] Monitor task progress? (y/n): ").strip().lower()
            if monitor == 'y':
                success = monitor_task(task_id)
                
                if success:
                    # Ask to download trace
                    download = input("\n[TRACE] Download trace? (y/n): ").strip().lower()
                    if download == 'y':
                        download_trace("default")  # Default trace
    
    elif choice == "2":
        # Check task status
        task_id = input("\nEnter task ID: ").strip()
        if task_id:
            status_url = f"{RAILWAY_URL}/task/{task_id}/status"
            try:
                response = requests.get(status_url, timeout=10)
                print(f"\n[STATUS] {response.json()}")
            except Exception as e:
                print(f"[ERROR] {e}")
    
    elif choice == "3":
        # List traces
        list_traces()
    
    elif choice == "4":
        # Download trace
        task_id = input("\nEnter task ID (or 'default'): ").strip()
        if task_id:
            download_trace(task_id)
    
    elif choice == "5":
        print("\n[EXIT] Goodbye!")
        sys.exit(0)
    
    print("\n" + "=" * 80)
    print("[DONE]")
    print("=" * 80)


if __name__ == "__main__":
    main()

