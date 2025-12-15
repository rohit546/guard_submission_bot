"""
Guard Login Automation
Handles login, session management, and navigation for Guard portal
"""
import asyncio
import logging
import imaplib
import email
from email.header import decode_header
import re
import time
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright, Page, BrowserContext
from config import (
    GUARD_USERNAME, GUARD_PASSWORD, GUARD_LOGIN_URL,
    SESSION_DIR, SCREENSHOT_DIR, TRACE_DIR, 
    BROWSER_HEADLESS, BROWSER_TIMEOUT, ENABLE_TRACING
)
import os
from dotenv import load_dotenv

# Load environment for 2FA email credentials
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_guard_verification_code(max_retries=5, retry_delay=10):
    """
    Fetch Guard verification code from Gmail via IMAP
    
    Args:
        max_retries: Maximum number of attempts to find the email (default 5)
        retry_delay: Seconds to wait between retries (default 10)
    
    Returns:
        str: 6-digit verification code or None if not found
    """
    gmail_user = os.getenv('GUARD_2FA_EMAIL', '')
    gmail_password = os.getenv('GUARD_2FA_PASSWORD', '').replace(' ', '')
    
    if not gmail_user or not gmail_password:
        logger.error("2FA email credentials not configured in .env")
        return None
    
    logger.info(f"Fetching verification code from {gmail_user}...")
    logger.info(f"Will try up to {max_retries} times with {retry_delay}s delays")
    
    for attempt in range(1, max_retries + 1):
        logger.info(f"Attempt {attempt}/{max_retries}...")
        
        try:
            # Connect to Gmail
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.login(gmail_user, gmail_password)
            mail.select("INBOX")
            
            # Search for emails from last 24 hours (to get fresh verification code)
            # Use US Eastern Time for date calculation
            from datetime import datetime, timedelta
            import pytz
            
            # Get current time in US Eastern timezone
            us_eastern = pytz.timezone('US/Eastern')
            now_eastern = datetime.now(us_eastern)
            yesterday_eastern = now_eastern - timedelta(days=1)
            since_date = yesterday_eastern.strftime("%d-%b-%Y")
            
            logger.info(f"Searching emails since: {since_date} (US Eastern Time)")
            status, messages = mail.search(None, f'(SINCE {since_date})')
            
            if status != "OK":
                logger.warning(f"Failed to search emails on attempt {attempt}")
                mail.close()
                mail.logout()
                time.sleep(retry_delay)
                continue
            
            # Get last 5 from recent emails
            email_ids = messages[0].split()
            if not email_ids:
                logger.warning(f"No recent emails found on attempt {attempt}")
                mail.close()
                mail.logout()
                time.sleep(retry_delay)
                continue
            
            recent_emails = email_ids[-5:] if len(email_ids) >= 5 else email_ids
            logger.info(f"Checking last {len(recent_emails)} recent emails (from last 2 minutes)...")
            
            # Check each email (newest first)
            for email_id in reversed(recent_emails):
                try:
                    status, msg_data = mail.fetch(email_id, "(RFC822)")
                    
                    if status != "OK":
                        continue
                    
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            
                            # Get sender
                            from_email = msg.get("From", "")
                            
                            # Get subject
                            subject = decode_header(msg["Subject"])[0][0]
                            if isinstance(subject, bytes):
                                subject = subject.decode()
                            
                            # Check if it's from Guard
                            if "guard" not in from_email.lower() and "guard" not in subject.lower():
                                continue
                            
                            # Check email timestamp - only accept emails from last 90 seconds
                            email_date_str = msg.get("Date", "")
                            if email_date_str:
                                try:
                                    from email.utils import parsedate_to_datetime
                                    email_date = parsedate_to_datetime(email_date_str)
                                    email_age_seconds = (datetime.now(email_date.tzinfo) - email_date).total_seconds()
                                    
                                    if email_age_seconds > 90:
                                        logger.debug(f"Email too old ({email_age_seconds:.0f}s), skipping")
                                        continue
                                    
                                    logger.info(f"Found FRESH Guard email ({email_age_seconds:.0f}s old): {subject}")
                                except Exception as e:
                                    logger.debug(f"Could not parse email date: {e}")
                                    logger.info(f"Found Guard email: {subject}")
                            else:
                                logger.info(f"Found Guard email: {subject}")
                            
                            # Get email body
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() == "text/plain":
                                        body = part.get_payload(decode=True).decode()
                                        break
                                    elif part.get_content_type() == "text/html":
                                        body = part.get_payload(decode=True).decode()
                            else:
                                body = msg.get_payload(decode=True).decode()
                            
                            # Extract verification code
                            # Guard format: "Your Agency Service Center verification code is 551473"
                            code_match = re.search(r'verification code is (\d{6})', body, re.IGNORECASE)
                            if not code_match:
                                # Fallback: any 6-digit number
                                code_match = re.search(r'\b(\d{6})\b', body)
                            
                            if code_match:
                                verification_code = code_match.group(1)
                                logger.info(f"✅ Verification code found: {verification_code}")
                                mail.close()
                                mail.logout()
                                return verification_code
                
                except Exception as e:
                    logger.debug(f"Error processing email: {e}")
                    continue
            
            mail.close()
            mail.logout()
            
            logger.warning(f"No Guard verification email found on attempt {attempt}")
            
            if attempt < max_retries:
                logger.info(f"Waiting {retry_delay}s before retry (email may take 30-40s to arrive)...")
                time.sleep(retry_delay)
        
        except Exception as e:
            logger.error(f"IMAP error on attempt {attempt}: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
    
    logger.error("Failed to fetch verification code after all retries")
    return None


class GuardLogin:
    """Handles Guard portal login and session management"""
    
    def __init__(self, username: str = None, password: str = None, task_id: str = "default", trace_id: str = None):
        """
        Initialize Guard login handler
        
        Args:
            username: Guard username (uses config if not provided)
            password: Guard password (uses config if not provided)
            task_id: Unique identifier for this task (for browser data isolation)
            trace_id: Custom trace file identifier (uses task_id if not provided)
        """
        self.username = username or GUARD_USERNAME
        self.password = password or GUARD_PASSWORD
        self.task_id = task_id
        self.trace_id = trace_id or task_id
        
        # Browser objects
        self.playwright = None
        self.context = None
        self.page = None
        
        # Paths
        self.browser_data_dir = SESSION_DIR / f"browser_data_{task_id}"
        self.screenshot_dir = SCREENSHOT_DIR / task_id
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Trace settings
        self.enable_tracing = ENABLE_TRACING
        self.trace_path = None
        if self.enable_tracing:
            self.trace_path = TRACE_DIR / f"{self.trace_id}.zip"
        
        logger.info(f"GuardLogin initialized for task: {task_id}")
        logger.info(f"Browser data: {self.browser_data_dir}")
        if self.enable_tracing:
            logger.info(f"Trace will be saved to: {self.trace_path}")
    
    async def init_browser(self):
        """Initialize browser with persistent session"""
        logger.info("Step 1: Initializing browser with persistent session...")
        
        self.playwright = await async_playwright().start()
        
        # Browser arguments for Guard portal
        args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage'
        ]
        
        logger.info(f"Using browser data from: {self.browser_data_dir}")
        if self.enable_tracing:
            logger.info(f"Tracing ENABLED - will save to: {self.trace_path}")
        
        # Launch persistent context (saves cookies, session)
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.browser_data_dir),
            headless=BROWSER_HEADLESS,
            args=args,
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=True
        )
        
        # Start tracing if enabled
        if self.enable_tracing:
            await self.context.tracing.start(screenshots=True, snapshots=True, sources=True)
            logger.info("Trace recording started")
        
        # Get or create page
        if len(self.context.pages) > 0:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()
        
        # Set timeout
        self.page.set_default_timeout(BROWSER_TIMEOUT)
        
        logger.info("Browser initialized successfully")
    
    async def login(self):
        """
        Perform login to Guard portal
        Simple HTML form login (no Angular complexity like Encova)
        """
        logger.info("Step 2: Navigating to Guard login page...")
        await self.page.goto(GUARD_LOGIN_URL, wait_until='domcontentloaded', timeout=60000)
        
        # Take screenshot of login page
        screenshot_path = self.screenshot_dir / "01_login_page.png"
        await self.page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info(f"Screenshot saved: {screenshot_path}")
        
        # Check if already logged in (check for redirect or dashboard elements)
        current_url = self.page.url
        if '/auth' not in current_url:
            logger.info("✅ Already logged in (not on auth page)")
            return {
                "success": True,
                "message": "Already logged in",
                "already_logged_in": True
            }
        
        logger.info("Step 3: Filling login form...")
        
        try:
            # Wait for login form to be visible
            await self.page.wait_for_selector('input[name="Username"]', timeout=10000)
            logger.info("Login form loaded")
            
            # Fill User Code field
            logger.info(f"Entering User Code: {self.username}")
            username_input = await self.page.wait_for_selector('input[name="Username"]')
            await username_input.click()
            await username_input.fill(self.username)
            await asyncio.sleep(0.5)
            
            # Fill Password field
            logger.info("Entering Password...")
            password_input = await self.page.wait_for_selector('input[name="Password"]')
            await password_input.click()
            await password_input.fill(self.password)
            await asyncio.sleep(0.5)
            
            # Check "Remember User Code" checkbox if not already checked
            remember_checkbox = await self.page.query_selector('input[type="checkbox"]')
            if remember_checkbox:
                is_checked = await remember_checkbox.is_checked()
                if not is_checked:
                    await remember_checkbox.click()
                    logger.info("Checked 'Remember User Code'")
            
            # Take screenshot before clicking login
            screenshot_path = self.screenshot_dir / "02_before_login.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            
            # Click LOGIN button
            logger.info("Step 4: Clicking LOGIN button...")
            login_button = await self.page.wait_for_selector('button:has-text("LOGIN"), input[type="submit"][value="LOGIN"]')
            await login_button.click()
            logger.info("LOGIN button clicked")
            
            # Wait for navigation or 2FA page
            try:
                # Wait for URL to change (could be dashboard or 2FA page)
                await self.page.wait_for_load_state('networkidle', timeout=15000)
                current_url = self.page.url
                logger.info(f"Page loaded - current URL: {current_url}")
                
                # Check if redirected to 2FA verification page
                if '/verify' in current_url or 'verification' in current_url.lower():
                    logger.info("🔐 2FA verification page detected!")
                    
                    # Take screenshot of 2FA page
                    screenshot_path = self.screenshot_dir / "03_2fa_page.png"
                    await self.page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.info(f"Screenshot saved: {screenshot_path}")
                    
                    # Wait 10 seconds for Guard to send the new verification email
                    logger.info("⏳ Waiting 10 seconds for new verification email to arrive...")
                    await asyncio.sleep(10)
                    
                    # Fetch verification code from email
                    logger.info("Fetching verification code from Gmail...")
                    verification_code = await asyncio.to_thread(fetch_guard_verification_code, max_retries=5, retry_delay=10)
                    
                    if not verification_code:
                        logger.error("Failed to fetch verification code from email")
                        return {
                            "success": False,
                            "message": "Failed to fetch 2FA verification code from email"
                        }
                    
                    logger.info(f"Got verification code: {verification_code}")
                    
                    # Fill verification code field
                    logger.info("Entering verification code...")
                    code_input = await self.page.wait_for_selector('input[name="Token"], input#Token, input[type="text"]', timeout=5000)
                    await code_input.click()
                    await code_input.fill(verification_code)
                    await asyncio.sleep(0.5)
                    
                    # Check "Remember this device for 5 days" checkbox
                    try:
                        # Try multiple selectors for remember device checkbox
                        remember_checkbox = await self.page.query_selector('input#rememberDevice, input[name="rememberDevice"], input[type="checkbox"]')
                        if remember_checkbox:
                            is_checked = await remember_checkbox.is_checked()
                            if not is_checked:
                                await remember_checkbox.click()
                                logger.info("✅ Checked 'Remember this device for 5 days'")
                            else:
                                logger.info("✅ 'Remember this device for 5 days' already checked")
                        else:
                            logger.warning("Remember device checkbox not found")
                    except Exception as e:
                        logger.warning(f"Could not check remember device: {e}")
                    
                    # Take screenshot before clicking CONTINUE
                    screenshot_path = self.screenshot_dir / "04_before_2fa_submit.png"
                    await self.page.screenshot(path=str(screenshot_path), full_page=True)
                    
                    # Click CONTINUE button
                    logger.info("Clicking CONTINUE button...")
                    continue_button = await self.page.wait_for_selector('button:has-text("CONTINUE"), input[type="submit"]', timeout=5000)
                    await continue_button.click()
                    logger.info("CONTINUE button clicked")
                    
                    # Wait for navigation after 2FA
                    await asyncio.sleep(3)
                    await self.page.wait_for_load_state('networkidle', timeout=15000)
                    current_url = self.page.url
                    logger.info(f"After 2FA - current URL: {current_url}")
                
                # Check if we're successfully logged in
                if '/auth' in current_url or '/verify' in current_url:
                    logger.warning("Still on auth/verify page after login")
                
                # Take screenshot of dashboard/home page
                screenshot_path = self.screenshot_dir / "05_after_login.png"
                await self.page.screenshot(path=str(screenshot_path), full_page=True)
                logger.info(f"Screenshot saved: {screenshot_path}")
                
                if '/auth' in current_url or '/verify' in current_url:
                    # Still on auth page - login might have failed
                    logger.warning("Still on auth page after login attempt")
                    
                    # Check for error messages
                    error_msg = await self.page.query_selector('.error, .alert, [class*="error"]')
                    if error_msg:
                        error_text = await error_msg.text_content()
                        logger.error(f"Login error message: {error_text}")
                        return {
                            "success": False,
                            "message": f"Login failed: {error_text}"
                        }
                    
                    return {
                        "success": False,
                        "message": "Login failed - still on auth page"
                    }
                
                logger.info("✅ Login successful!")
                return {
                    "success": True,
                    "message": "Login successful",
                    "dashboard_url": current_url
                }
                
            except Exception as e:
                logger.warning(f"Navigation timeout or error: {e}")
                
                # Check current URL to see if login succeeded despite timeout
                current_url = self.page.url
                if '/auth' not in current_url:
                    logger.info("✅ Login appears successful (not on auth page)")
                    screenshot_path = self.screenshot_dir / "03_after_login.png"
                    await self.page.screenshot(path=str(screenshot_path), full_page=True)
                    return {
                        "success": True,
                        "message": "Login successful",
                        "dashboard_url": current_url
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Login navigation timeout: {str(e)}"
                    }
            
        except Exception as e:
            logger.error(f"Login error: {e}", exc_info=True)
            
            # Take error screenshot
            screenshot_path = self.screenshot_dir / "error_login.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.error(f"Error screenshot saved: {screenshot_path}")
            
            return {
                "success": False,
                "message": f"Login error: {str(e)}"
            }
    
    async def close(self):
        """Close browser and save trace"""
        try:
            if self.enable_tracing and self.context:
                logger.info(f"Stopping trace recording and saving to: {self.trace_path}")
                await self.context.tracing.stop(path=str(self.trace_path))
                
                # Verify trace file was created
                if self.trace_path.exists():
                    file_size = self.trace_path.stat().st_size
                    logger.info(f"Trace saved successfully: {self.trace_path} ({file_size} bytes)")
                    logger.info(f"View trace with: playwright show-trace {self.trace_path}")
                else:
                    logger.warning(f"Trace file not found at: {self.trace_path}")
            
            if self.context:
                await self.context.close()
            
            if self.playwright:
                await self.playwright.stop()
            
            logger.info("Browser closed and playwright stopped")
        except Exception as e:
            logger.error(f"Error closing browser: {e}", exc_info=True)


    async def setup_account(self, account_data: dict):
        """
        Setup account/prospect information (one-time process)
        This fills the initial form and creates the prospect in Guard system
        
        Args:
            account_data: Dictionary with account information
            
        Returns:
            dict: Result with policy_code and quotation_url
        """
        from datetime import timedelta
        import pytz
        
        logger.info("Starting account setup process...")
        
        QUOTE_FORM_URL = "https://gigezrate.guard.com/dotnet/mvc/uw/ezrate/asc_prerate/home/Index"
        
        try:
            # Navigate to quote form
            logger.info("Navigating to account setup form...")
            await self.page.goto(QUOTE_FORM_URL, wait_until="networkidle", timeout=60000)
            
            screenshot_path = self.screenshot_dir / "01_account_form.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            
            logger.info("Filling account information...")
            
            # Legal Entity
            if account_data.get("legal_entity"):
                logger.info(f"Legal Entity: {account_data['legal_entity']}")
                await self.page.select_option("#BizType", account_data["legal_entity"])
                await asyncio.sleep(1)
            
            # Applicant Name
            if account_data.get("applicant_name"):
                logger.info(f"Applicant Name: {account_data['applicant_name']}")
                await self.page.fill("#Name", account_data["applicant_name"])
            
            # DBA
            if account_data.get("dba"):
                await self.page.fill("#InsuredDBA", account_data["dba"])
            
            # Address
            if account_data.get("address1"):
                await self.page.fill("#Address1", account_data["address1"])
            if account_data.get("address2"):
                await self.page.fill("#Address2", account_data["address2"])
            
            # ZIP Code
            if account_data.get("zipcode"):
                await self.page.fill("#ZipCode", account_data["zipcode"])
                await asyncio.sleep(2)
            
            # State and City
            if account_data.get("state"):
                await self.page.fill("#State", account_data["state"])
                await asyncio.sleep(1)
            if account_data.get("city"):
                await self.page.fill("#City", account_data["city"])
            
            # Contact Information
            if account_data.get("contact_name"):
                await self.page.fill("#ContactName", account_data["contact_name"])
            
            if account_data.get("contact_phone"):
                phone = account_data["contact_phone"]
                if isinstance(phone, dict):
                    await self.page.fill("#ContactPhone_Prefix", phone.get("area", ""))
                    await self.page.fill("#ContactPhone_Suffix", phone.get("prefix", ""))
                    await self.page.fill("#ContactPhone_LastFour", phone.get("suffix", ""))
            
            if account_data.get("email"):
                await self.page.fill("#EmailAddress", account_data["email"])
            if account_data.get("website"):
                await self.page.fill("#WebsiteAddress", account_data["website"])
            
            # Years in Business
            if account_data.get("years_in_business"):
                await self.page.fill("#YearsInBusiness", str(account_data["years_in_business"]))
            
            # Producer and CSR
            if account_data.get("producer_id"):
                await self.page.select_option("#ProducerId", account_data["producer_id"])
            if account_data.get("csr_id"):
                await self.page.select_option("#CSRID", account_data["csr_id"])
            
            # Description
            if account_data.get("description"):
                await self.page.fill("#DescriptionOfOperations", account_data["description"])
            
            # Policy Inception Date
            if account_data.get("policy_inception"):
                await self.page.fill("#POBegin", account_data["policy_inception"])
                await self.page.click("body")
                await asyncio.sleep(1)
            
            # Headquarters State
            if account_data.get("headquarters_state"):
                await self.page.select_option("#Govstate", account_data["headquarters_state"])
                await asyncio.sleep(2)
            
            # Industry dropdowns based on ownership type
            ownership_type = account_data.get("ownership_type", "owner").lower()
            
            if ownership_type == "lessors_risk":
                industry_id, sub_industry_id, business_type_id = "7", "26", "79"
                logger.info(f"Ownership: Lessors Risk - Industry: 7, 26, 79")
            else:
                industry_id = account_data.get("industry_id", "11")
                sub_industry_id = account_data.get("sub_industry_id", "45")
                business_type_id = account_data.get("business_type_id", "127")
                logger.info(f"Ownership: {ownership_type.title()} - Industry: {industry_id}, {sub_industry_id}, {business_type_id}")
            
            # Primary Industry
            await self.page.select_option("#IndustryID", industry_id)
            await asyncio.sleep(3)
            
            # Sub Industry
            await self.page.wait_for_function(
                """() => {
                    const dropdown = document.querySelector('#SubIndustryID');
                    return dropdown && !dropdown.disabled && dropdown.options.length > 1;
                }""",
                timeout=15000
            )
            await self.page.select_option("#SubIndustryID", sub_industry_id)
            await asyncio.sleep(3)
            
            # Business Type
            await self.page.wait_for_function(
                """() => {
                    const dropdown = document.querySelector('#BusinessTypeID');
                    return dropdown && !dropdown.disabled && dropdown.options.length > 1;
                }""",
                timeout=15000
            )
            await self.page.select_option("#BusinessTypeID", business_type_id)
            await asyncio.sleep(5)
            
            # Lines of Business
            if account_data.get("lines_of_business"):
                for lob in account_data["lines_of_business"]:
                    checkbox_id = f"#LOBs_{lob}"
                    await self.page.check(checkbox_id)
                    logger.info(f"✓ Checked LOB: {lob}")
                    await asyncio.sleep(1)
                    
                    # Handle tenant/owner questions for Businessowners
                    if lob == "CB":
                        await asyncio.sleep(2)
                        
                        if ownership_type == "tenant":
                            await self.page.click("#lobdirective_tenant_radio_Y")
                            logger.info("✓ Tenant = Yes")
                        else:
                            await self.page.click("#lobdirective_tenant_radio_N")
                            await asyncio.sleep(2)
                            
                            if ownership_type == "lessors_risk":
                                await self.page.click("#lobdirective_lro_radio_Y")
                                logger.info("✓ Lessors Risk = Yes")
                            else:
                                await self.page.click("#lobdirective_lro_radio_N")
                                logger.info("✓ Owner (Lessors Risk = No)")
                        
                        # Re-check checkbox
                        await asyncio.sleep(1)
                        await self.page.check(checkbox_id, force=True)
            
            screenshot_path = self.screenshot_dir / "02_account_filled.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            
            # Click Save
            logger.info("Clicking Save button...")
            await self.page.click("#save_btn")
            
            # Wait for redirect to execStoredProc
            await self.page.wait_for_url("**/execStoredProc/**", timeout=30000)
            logger.info("✅ Redirected to execStoredProc page")
            
            screenshot_path = self.screenshot_dir / "03_after_save.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            
            # Click Continue
            await asyncio.sleep(2)
            selectors = ["a:has-text('continue')", "a:has-text('Continue')"]
            
            for selector in selectors:
                try:
                    if await self.page.locator(selector).count() > 0:
                        await asyncio.gather(
                            self.page.wait_for_url("**/EZR_AddNewProspectShell/**", timeout=30000),
                            self.page.click(selector)
                        )
                        logger.info(f"✅ Clicked Continue")
                        break
                except:
                    continue
            
            # Extract policy code and URL
            quotation_url = self.page.url
            policy_code = None
            if "MGACODE=" in quotation_url:
                policy_code = quotation_url.split("MGACODE=")[1].split("&")[0]
                logger.info(f"✅ Policy Code: {policy_code}")
            
            screenshot_path = self.screenshot_dir / "04_quotation_page.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            
            logger.info(f"✅ Account setup complete!")
            logger.info(f"Quotation URL: {quotation_url}")
            
            return {
                "success": True,
                "policy_code": policy_code,
                "quotation_url": quotation_url
            }
            
        except Exception as e:
            logger.error(f"Account setup error: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }


    async def run_full_automation(self, policy_code: str, quote_data: dict = None) -> dict:
        """
        Complete automation flow: login + run quote automation
        This is the main entry point that should be called by webhook
        
        Args:
            policy_code: The MGACODE for the quote (e.g., TEBP690442)
            quote_data: Dictionary containing quote data from webhook:
                - combined_sales: Inside Sales / Annual Sales
                - gas_gallons: Annual Gallons of Gasoline
                - year_built: Year building was built
                - square_footage: Total building square footage
                - mpds: Number of Gas Pumps
            
        Returns:
            dict: Result containing:
                - success: bool - overall success status
                - policy_code: str - the policy code used
                - message: str - description of what happened
        """
        result = {
            "success": False,
            "policy_code": policy_code,
            "message": ""
        }
        
        try:
            # Step 1: Initialize browser and login
            logger.info("Step 1: Initializing browser...")
            await self.init_browser()
            
            logger.info("Step 2: Authenticating to Guard portal...")
            login_result = await self.login()
            if not login_result.get("success"):
                logger.error("Authentication failed")
                result["message"] = "Authentication failed"
                return result
            logger.info("✅ Authentication successful")
            
            # Step 3: Close login browser and start quote automation
            logger.info("Step 3: Closing login browser, starting quote automation...")
            await self.close()
            logger.info("Login browser closed")
            
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
            
            logger.info(f"Quote parameters: {quote_params}")
            
            # Initialize quote handler with same task_id for session sharing
            quote_handler = GuardQuote(
                policy_code=policy_code,
                task_id=self.task_id,  # Share session
                **quote_params
            )
            
            try:
                # Initialize browser
                await quote_handler.init_browser()
                
                # Login (should use existing session)
                if not await quote_handler.login():
                    result["message"] = "Quote login failed"
                    return result
                
                # Navigate to quote URL
                if not await quote_handler.navigate_to_quote():
                    result["message"] = "Navigation to quote page failed"
                    return result
                
                # Fill quote details
                await quote_handler.fill_quote_details()
                
                logger.info(f"✅ Quote automation completed for policy {policy_code}")
                result["success"] = True
                result["message"] = f"Quote automation completed successfully for policy {policy_code}"
                
            except Exception as e:
                logger.error(f"❌ Quote automation error: {e}", exc_info=True)
                result["message"] = f"Quote automation error: {str(e)}"
            finally:
                try:
                    await quote_handler.close()
                except Exception as e:
                    logger.warning(f"Error closing quote browser: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Full automation error: {e}", exc_info=True)
            result["message"] = f"Automation error: {str(e)}"
            return result


async def test_guard_login():
    """Test Guard login automation"""
    logger.info("=" * 80)
    logger.info("TESTING GUARD LOGIN AUTOMATION")
    logger.info("=" * 80)
    
    handler = GuardLogin(task_id="test_login")
    
    try:
        await handler.init_browser()
        result = await handler.login()
        
        if result.get("success"):
            logger.info("✅ Login test successful!")
        else:
            logger.warning(f"⚠️ Login test incomplete: {result.get('message')}")
        
        # Wait a bit to see the result
        await asyncio.sleep(5)
        
    except Exception as e:
        logger.error(f"❌ Login test failed: {e}", exc_info=True)
    finally:
        await handler.close()


if __name__ == "__main__":
    # Run test
    asyncio.run(test_guard_login())
