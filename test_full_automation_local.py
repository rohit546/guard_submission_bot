"""
GUARD FULL AUTOMATION TEST - LOCAL SERVER
==========================================
Tests the complete flow: Account Creation → Quote Filling
Against LOCAL server (localhost:5001)

Usage: python test_full_automation_local.py
"""
import requests
import time
import sys
from datetime import datetime, timedelta

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# ============================================================================
# CONFIGURATION - LOCAL SERVER
# ============================================================================

SERVER_URL = "http://localhost:5001"

# ============================================================================
# FULL AUTOMATION DATA - Everything needed for Account + Quote
# ============================================================================

def get_full_automation_data():
    """
    Returns complete data for full automation (account creation + quote)
    """
    policy_inception_date = (datetime.now() + timedelta(days=2)).strftime("%m/%d/%Y")
    
    return {
        "action": "start_automation",
        "task_id": f"local_full_{int(time.time())}",
        "create_account": True,
        
        "account_data": {
            "legal_entity": "L",
            "applicant_name": "LOCAL TEST GAS LLC",
            "dba": "Local Test Gas & Go",
            "address1": "280 Griffin St",
            "address2": "",
            "zipcode": "30253-3100",
            "city": "McDonough",
            "state": "GA",
            "contact_name": "Test User",
            "contact_phone": {
                "area": "404",
                "prefix": "555",
                "suffix": "9999"
            },
            "email": "test@localtest.com",
            "website": "www.localtest.com",
            "years_in_business": "5",
            "description": "Gas station with convenience store",
            "producer_id": "2774846",
            "csr_id": "16977940",
            "policy_inception": policy_inception_date,
            "headquarters_state": "GA",
            "industry_id": "11",
            "sub_industry_id": "45",
            "business_type_id": "127",
            "lines_of_business": ["CB"],
            "ownership_type": "tenant"
        },
        
        "quote_data": {
            "combined_sales": "1000000",
            "gas_gallons": "600000",
            "year_built": "2010",
            "square_footage": "4000",
            "mpds": "6"
        }
    }


def get_existing_policy_data():
    """Use existing policy code (skip account creation)"""
    return {
        "action": "start_automation",
        "task_id": f"local_quote_{int(time.time())}",
        "create_account": False,
        "policy_code": "BIBP608141",  # Use existing policy from successful account creation
        
        "quote_data": {
            "combined_sales": "1200000",
            "gas_gallons": "750000",
            "year_built": "2005",
            "square_footage": "4500",
            "mpds": "8"
        }
    }


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def check_server_health():
    """Check if local server is running"""
    print("\n" + "=" * 80)
    print("🛡️  GUARD FULL AUTOMATION TEST - LOCAL")
    print("=" * 80)
    print(f"\n[SERVER] {SERVER_URL}")
    print(f"[CHECK] Testing server health...")
    
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Server is HEALTHY!")
            print(f"   Service: {data.get('service', 'N/A')}")
            print(f"   Workers: {data.get('active_workers', 0)}/{data.get('max_workers', 3)}")
            print(f"   Queue: {data.get('queue_size', 0)}")
            return True
        else:
            print(f"\n❌ Server returned: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Could not connect to local server!")
        print(f"   Make sure to run: python webhook_server.py")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def send_automation(data: dict):
    """Send automation request"""
    print("\n" + "=" * 80)
    print("📤 SENDING AUTOMATION REQUEST")
    print("=" * 80)
    
    account = data.get("account_data", {})
    quote = data.get("quote_data", {})
    
    if data.get("create_account"):
        print(f"\n📋 ACCOUNT CREATION DATA:")
        print(f"   Business: {account.get('applicant_name', 'N/A')}")
        print(f"   DBA: {account.get('dba', 'N/A')}")
        print(f"   Address: {account.get('address1', '')}, {account.get('city', '')}, {account.get('state', '')}")
    else:
        print(f"\n📋 USING EXISTING POLICY: {data.get('policy_code', 'N/A')}")
    
    print(f"\n💰 QUOTE DATA:")
    print(f"   Combined Sales: ${int(quote.get('combined_sales', 0)):,}")
    print(f"   Gas Gallons: {int(quote.get('gas_gallons', 0)):,}")
    print(f"   Year Built: {quote.get('year_built', 'N/A')}")
    print(f"   Square Footage: {int(quote.get('square_footage', 0)):,} sq ft")
    print(f"   Gas Pumps: {quote.get('mpds', 'N/A')}")
    
    print(f"\n🚀 Sending request...")
    
    try:
        response = requests.post(f"{SERVER_URL}/webhook", json=data, timeout=30)
        result = response.json()
        
        task_id = result.get("task_id")
        status = result.get("status")
        
        print(f"\n📬 RESPONSE:")
        print(f"   Status: {status}")
        print(f"   Task ID: {task_id}")
        print(f"   Message: {result.get('message', 'N/A')}")
        
        if status == "accepted":
            print(f"\n✅ Request accepted!")
            return task_id
        else:
            print(f"\n❌ Request not accepted: {result}")
            return None
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None


def monitor_task(task_id: str, max_wait: int = 600):
    """Monitor task until completion"""
    print("\n" + "=" * 80)
    print(f"📊 MONITORING TASK: {task_id}")
    print("=" * 80)
    print("\n⏳ Monitoring... (this may take 5-10 minutes)\n")
    
    status_url = f"{SERVER_URL}/task/{task_id}/status"
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(status_url, timeout=10)
            if response.status_code == 200:
                status_data = response.json()
                current_status = status_data.get('status', 'unknown')
                elapsed = int(time.time() - start_time)
                
                if current_status != last_status:
                    print(f"[{elapsed:4d}s] Status: {current_status.upper()}")
                    
                    if status_data.get('policy_code'):
                        print(f"        Policy Code: {status_data['policy_code']}")
                    if status_data.get('message'):
                        print(f"        Message: {status_data['message']}")
                    if status_data.get('quotation_url'):
                        print(f"        Quote URL: {status_data['quotation_url']}")
                    
                    last_status = current_status
                
                if current_status in ['completed', 'success']:
                    print("\n" + "=" * 80)
                    print("🎉 SUCCESS!")
                    print("=" * 80)
                    return True
                
                elif current_status in ['failed', 'error']:
                    print("\n" + "=" * 80)
                    print("❌ FAILED")
                    print("=" * 80)
                    if status_data.get('error'):
                        print(f"Error: {status_data['error']}")
                    return False
                    
        except Exception as e:
            print(f"[WARN] {e}")
        
        time.sleep(5)
    
    print(f"\n⏰ TIMEOUT after {max_wait}s")
    return False


# ============================================================================
# MAIN
# ============================================================================

def main():
    if not check_server_health():
        print("\n❌ Start local server first: python webhook_server.py")
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print("SELECT TEST MODE:")
    print("=" * 80)
    print("\n1. Full Automation (Create Account + Quote)")
    print("2. Quote Only (Use existing policy BIBP608141)")
    print("3. Exit")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        data = get_full_automation_data()
    elif choice == "2":
        data = get_existing_policy_data()
    elif choice == "3":
        print("\n👋 Bye!")
        sys.exit(0)
    else:
        print("\n❌ Invalid choice")
        sys.exit(1)
    
    task_id = send_automation(data)
    
    if task_id:
        monitor = input("\nMonitor task? (y/n): ").strip().lower()
        if monitor == 'y':
            monitor_task(task_id)
    
    print("\n" + "=" * 80)
    print("DONE")
    print("=" * 80)


if __name__ == "__main__":
    main()

