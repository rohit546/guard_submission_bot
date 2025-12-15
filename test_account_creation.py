"""
Test Guard Account Creation
One-time script to create a new prospect/account in Guard system
"""
import asyncio
import logging
from datetime import datetime, timedelta
from guard_login import GuardLogin

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Create a new account in Guard system"""
    
    # Calculate policy inception date (today + 2 days)
    policy_inception_date = (datetime.now() + timedelta(days=2)).strftime("%m/%d/%Y")
    
    # Account data
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
        "ownership_type": "tenant"  # tenant, owner, or lessors_risk
    }
    
    logger.info("=" * 80)
    logger.info("GUARD ACCOUNT CREATION TEST")
    logger.info("=" * 80)
    logger.info(f"Company: {account_data['applicant_name']}")
    logger.info(f"Address: {account_data['address1']}, {account_data['city']}, {account_data['state']}")
    logger.info(f"Policy Inception: {policy_inception_date}")
    logger.info("=" * 80)
    
    # Use default task_id for session persistence
    task_id = "default"
    handler = GuardLogin(task_id=task_id)
    
    try:
        # Initialize browser
        await handler.init_browser()
        logger.info("✅ Browser initialized")
        
        # Login
        logger.info("\nStep 1: Logging in...")
        login_result = await handler.login()
        
        if not login_result.get("success"):
            logger.error(f"❌ Login failed: {login_result.get('message')}")
            return
        
        logger.info("✅ Login successful")
        
        # Setup account
        logger.info("\nStep 2: Creating account...")
        setup_result = await handler.setup_account(account_data)
        
        if not setup_result.get("success"):
            logger.error(f"❌ Account setup failed: {setup_result.get('message')}")
            return
        
        policy_code = setup_result.get('policy_code')
        quotation_url = setup_result.get('quotation_url')
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ ACCOUNT CREATED SUCCESSFULLY!")
        logger.info("=" * 80)
        logger.info(f"Policy Code: {policy_code}")
        logger.info(f"Quotation URL: {quotation_url}")
        logger.info("=" * 80)
        logger.info("\nYou can now use this policy code in guard_quote.py:")
        logger.info(f'policy_code = "{policy_code}"')
        logger.info("=" * 80)
        
        # Keep browser open for inspection
        logger.info("\nKeeping browser open for 15 seconds for inspection...")
        await asyncio.sleep(15)
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
    finally:
        await handler.close()


if __name__ == "__main__":
    asyncio.run(main())
