"""
GUARD FULL AUTOMATION TEST
===========================
Tests the complete flow: Account Creation → Quote Filling

This simulates what the Online Quoting Coversheet will send.
All data for account creation AND quote is sent in ONE request.

Usage: python test_full_automation.py
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
# CONFIGURATION
# ============================================================================

# Railway Server URL
RAILWAY_URL = "https://guardsubmissionbot-production.up.railway.app"

# Local Server URL (for testing locally)
LOCAL_URL = "http://localhost:5001"

# Choose which server to use
SERVER_URL = RAILWAY_URL  # Change to LOCAL_URL for local testing

# ============================================================================
# FULL AUTOMATION DATA - Everything needed for Account + Quote
# ============================================================================

def get_full_automation_data():
    """
    Returns complete data for full automation (account creation + quote)
    This is exactly what the Online Quoting Coversheet will send.
    """
    
    # Calculate policy inception date (2 days from now)
    policy_inception_date = (datetime.now() + timedelta(days=2)).strftime("%m/%d/%Y")
    
    return {
        # ====================================================================
        # ACTION & TASK
        # ====================================================================
        "action": "start_automation",
        "task_id": f"full_auto_{int(time.time())}",
        
        # ====================================================================
        # CREATE ACCOUNT FLAG - Set to True for full flow
        # ====================================================================
        "create_account": True,
        
        # ====================================================================
        # ACCOUNT CREATION DATA
        # ====================================================================
        "account_data": {
            # Business Entity Information
            "legal_entity": "L",  # L=LLC, C=Corporation, P=Partnership, I=Individual, J=Joint Venture
            "applicant_name": "BISMILLAH GAS STATION LLC",
            "dba": "Bismillah Gas & Convenience",
            
            # Business Address
            "address1": "280 Griffin St",
            "address2": "Suite 100",
            "zipcode": "30253-3100",
            "city": "McDonough",
            "state": "GA",
            
            # Contact Information
            "contact_name": "Ahmed Khan",
            "contact_phone": {
                "area": "404",
                "prefix": "555",
                "suffix": "1234"
            },
            "email": "ahmed.khan@bismillahgas.com",
            "website": "www.bismillahgas.com",
            
            # Business Details
            "years_in_business": "5",
            "description": "Gas station with convenience store, selling fuel, snacks, beverages, and tobacco products",
            
            # Producer/Agent Information
            "producer_id": "2774846",
            "csr_id": "16977940",
            
            # Policy Information
            "policy_inception": policy_inception_date,
            "headquarters_state": "GA",
            
            # Industry Classification
            "industry_id": "11",        # Retail Trade
            "sub_industry_id": "45",    # Gas Stations
            "business_type_id": "127",  # Gas Station with Convenience Store
            
            # Lines of Business
            "lines_of_business": ["CB"],  # Commercial Business
            
            # Property Ownership
            "ownership_type": "tenant"  # "tenant" or "owner"
        },
        
        # ====================================================================
        # QUOTE DATA - Filled after account is created
        # ====================================================================
        "quote_data": {
            # Revenue Information
            "combined_sales": "1200000",      # Total Annual Sales ($1,200,000)
            "gas_gallons": "750000",          # Annual Gallons of Gasoline (750,000)
            
            # Building Information
            "year_built": "2005",             # Year Building Was Built
            "square_footage": "4500",         # Total Square Footage
            "mpds": "8",                      # Number of Gas Pumps (Multi-Product Dispensers)
            
            # Additional fields that are hardcoded in the automation:
            # - damage_to_premises: "100000"
            # - employees: "10"
            # - stories: "1"
            # - residential_units: "0"
            # - vacancy_percent: "0"
            # - gas_sales_percent: "40"
            # - cbd_percent: "0"
            # - tobacco_percent: "10"
            # - alcohol_percent: "10"
        }
    }


def get_sample_data_2():
    """Alternative sample data for testing"""
    policy_inception_date = (datetime.now() + timedelta(days=3)).strftime("%m/%d/%Y")
    
    return {
        "action": "start_automation",
        "task_id": f"full_auto_{int(time.time())}",
        "create_account": True,
        
        "account_data": {
            "legal_entity": "C",  # Corporation
            "applicant_name": "QUICK STOP FUEL INC",
            "dba": "Quick Stop Gas & Go",
            "address1": "1500 Highway 20",
            "address2": "",
            "zipcode": "30052",
            "city": "Loganville",
            "state": "GA",
            "contact_name": "Michael Johnson",
            "contact_phone": {
                "area": "770",
                "prefix": "466",
                "suffix": "5678"
            },
            "email": "mike@quickstopfuel.com",
            "website": "www.quickstopfuel.com",
            "years_in_business": "8",
            "description": "High-volume gas station with full-service convenience store",
            "producer_id": "2774846",
            "csr_id": "16977940",
            "policy_inception": policy_inception_date,
            "headquarters_state": "GA",
            "industry_id": "11",
            "sub_industry_id": "45",
            "business_type_id": "127",
            "lines_of_business": ["CB"],
            "ownership_type": "owner"
        },
        
        "quote_data": {
            "combined_sales": "2500000",
            "gas_gallons": "1200000",
            "year_built": "2010",
            "square_footage": "6000",
            "mpds": "12"
        }
    }


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def check_server_health():
    """Check if server is running"""
    print("\n" + "=" * 80)
    print("🛡️  GUARD FULL AUTOMATION TEST")
    print("=" * 80)
    print(f"\n[SERVER] {SERVER_URL}")
    print(f"[CHECK] Testing server health...")
    
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=15)
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
        print(f"\n❌ Could not connect to server!")
        print(f"   Make sure the server is running at {SERVER_URL}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def send_full_automation(data: dict):
    """Send full automation request to server"""
    print("\n" + "=" * 80)
    print("📤 SENDING FULL AUTOMATION REQUEST")
    print("=" * 80)
    
    # Display account data
    account = data.get("account_data", {})
    quote = data.get("quote_data", {})
    
    print(f"\n📋 ACCOUNT CREATION DATA:")
    print(f"   Business Name: {account.get('applicant_name', 'N/A')}")
    print(f"   DBA: {account.get('dba', 'N/A')}")
    print(f"   Legal Entity: {account.get('legal_entity', 'N/A')}")
    print(f"   Address: {account.get('address1', '')}, {account.get('city', '')}, {account.get('state', '')} {account.get('zipcode', '')}")
    print(f"   Contact: {account.get('contact_name', 'N/A')}")
    phone = account.get('contact_phone', {})
    print(f"   Phone: ({phone.get('area', '')}) {phone.get('prefix', '')}-{phone.get('suffix', '')}")
    print(f"   Email: {account.get('email', 'N/A')}")
    print(f"   Years in Business: {account.get('years_in_business', 'N/A')}")
    print(f"   Policy Inception: {account.get('policy_inception', 'N/A')}")
    print(f"   Ownership: {account.get('ownership_type', 'N/A')}")
    
    print(f"\n💰 QUOTE DATA:")
    print(f"   Combined Sales: ${int(quote.get('combined_sales', 0)):,}")
    print(f"   Gas Gallons: {int(quote.get('gas_gallons', 0)):,}")
    print(f"   Year Built: {quote.get('year_built', 'N/A')}")
    print(f"   Square Footage: {int(quote.get('square_footage', 0)):,} sq ft")
    print(f"   Gas Pumps (MPDs): {quote.get('mpds', 'N/A')}")
    
    print(f"\n🚀 Sending request...")
    
    try:
        response = requests.post(
            f"{SERVER_URL}/webhook",
            json=data,
            timeout=30
        )
        result = response.json()
        
        task_id = result.get("task_id")
        status = result.get("status")
        
        print(f"\n📬 RESPONSE:")
        print(f"   Status: {status}")
        print(f"   Task ID: {task_id}")
        print(f"   Message: {result.get('message', 'N/A')}")
        
        if status == "accepted":
            print(f"\n✅ Request accepted! Full automation started.")
            return task_id
        else:
            print(f"\n❌ Request not accepted: {result}")
            return None
            
    except Exception as e:
        print(f"\n❌ Error sending request: {e}")
        return None


def monitor_task(task_id: str, max_wait: int = 600):
    """Monitor task until completion (default 10 minutes timeout)"""
    print("\n" + "=" * 80)
    print(f"📊 MONITORING TASK: {task_id}")
    print("=" * 80)
    print("\n⏳ This may take 5-10 minutes for full automation...")
    print("   (Account creation + all quote panels)\n")
    
    status_url = f"{SERVER_URL}/task/{task_id}/status"
    start_time = time.time()
    last_status = None
    last_message = None
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(status_url, timeout=15)
            if response.status_code == 200:
                status_data = response.json()
                current_status = status_data.get('status', 'unknown')
                current_message = status_data.get('message', '')
                elapsed = int(time.time() - start_time)
                
                # Print status updates
                if current_status != last_status or current_message != last_message:
                    print(f"[{elapsed:4d}s] Status: {current_status.upper()}")
                    
                    if status_data.get('queue_position'):
                        print(f"        Queue Position: {status_data['queue_position']}")
                    if status_data.get('policy_code'):
                        print(f"        Policy Code: {status_data['policy_code']}")
                    if current_message and current_message != last_message:
                        print(f"        Message: {current_message}")
                    if status_data.get('quotation_url'):
                        print(f"        Quote URL: {status_data['quotation_url']}")
                    
                    last_status = current_status
                    last_message = current_message
                
                # Check for completion
                if current_status in ['completed', 'success']:
                    print("\n" + "=" * 80)
                    print("🎉 SUCCESS! FULL AUTOMATION COMPLETED!")
                    print("=" * 80)
                    
                    if status_data.get('policy_code'):
                        print(f"\n📋 Policy Code: {status_data['policy_code']}")
                    if status_data.get('quotation_url'):
                        print(f"🔗 Quote URL: {status_data['quotation_url']}")
                    if status_data.get('message'):
                        print(f"📝 Message: {status_data['message']}")
                    
                    return True
                
                # Check for failure
                elif current_status in ['failed', 'error']:
                    print("\n" + "=" * 80)
                    print("❌ AUTOMATION FAILED")
                    print("=" * 80)
                    
                    if status_data.get('error'):
                        print(f"\n🔴 Error: {status_data['error']}")
                    if status_data.get('traceback'):
                        print(f"\n📜 Traceback:\n{status_data['traceback'][:500]}...")
                    
                    return False
                
            elif response.status_code == 404:
                print(f"[{int(time.time() - start_time):4d}s] Task not found yet...")
                
        except Exception as e:
            print(f"[WARN] Status check error: {e}")
        
        time.sleep(5)  # Check every 5 seconds
    
    print(f"\n⏰ TIMEOUT: Task did not complete within {max_wait} seconds")
    return False


def list_traces():
    """List available traces"""
    print("\n" + "-" * 60)
    print("📁 AVAILABLE TRACES:")
    print("-" * 60)
    
    try:
        response = requests.get(
            f"{SERVER_URL}/traces",
            headers={"Accept": "application/json"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            traces = data.get("traces", [])
            
            if traces:
                for t in traces[:5]:
                    print(f"   • {t['task_id']} ({t['size_kb']} KB) - {t['created_at'][:19]}")
            else:
                print("   No traces available")
        else:
            print(f"   Could not fetch traces: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main function"""
    
    # Check server health
    if not check_server_health():
        print("\n❌ Server not available. Exiting.")
        sys.exit(1)
    
    # Show menu
    print("\n" + "=" * 80)
    print("SELECT DATA SET TO USE:")
    print("=" * 80)
    print("\n1. BISMILLAH GAS STATION LLC")
    print("   - Combined Sales: $1,200,000")
    print("   - Gas Gallons: 750,000")
    print("   - 8 Pumps, 4,500 sq ft")
    print()
    print("2. QUICK STOP FUEL INC")
    print("   - Combined Sales: $2,500,000")
    print("   - Gas Gallons: 1,200,000")
    print("   - 12 Pumps, 6,000 sq ft")
    print()
    print("3. Exit")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        data = get_full_automation_data()
    elif choice == "2":
        data = get_sample_data_2()
    elif choice == "3":
        print("\n👋 Goodbye!")
        sys.exit(0)
    else:
        print("\n❌ Invalid choice")
        sys.exit(1)
    
    # Send full automation request
    task_id = send_full_automation(data)
    
    if task_id:
        # Ask to monitor
        print("\n" + "-" * 60)
        monitor = input("Monitor task progress? (y/n): ").strip().lower()
        
        if monitor == 'y':
            success = monitor_task(task_id)
            
            # Show traces
            list_traces()
            
            if success:
                print("\n✅ Full automation completed successfully!")
            else:
                print("\n❌ Automation did not complete successfully")
        else:
            print(f"\n📋 Task ID: {task_id}")
            print(f"   Check status: {SERVER_URL}/task/{task_id}/status")
            print(f"   View traces: {SERVER_URL}/traces")
    
    print("\n" + "=" * 80)
    print("DONE")
    print("=" * 80)


if __name__ == "__main__":
    main()

