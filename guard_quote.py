"""
Guard Quote Automation
Simple workflow: Login → Navigate to quote URL → Fill quote
"""
import asyncio
import logging
from pathlib import Path
from guard_login import GuardLogin

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GuardQuote:
    def __init__(self, policy_code: str, task_id: str = "quote", 
                 trace_id: str = None,
                 combined_sales: str = "1000000", 
                 gas_gallons: str = "100000",
                 year_built: str = "2025",
                 square_footage: str = "2000",
                 mpds: str = "6",
                 employees: str = "3"):
        """
        Initialize Guard Quote automation
        
        Args:
            policy_code: The MGACODE for the quote (e.g., TEBP690442)
            task_id: Unique identifier for this task
            trace_id: Custom trace file identifier (e.g., quote_company_name)
            combined_sales: Inside Sales / Annual Sales / Convenience Store Receipts
            gas_gallons: Annual Gallons of Gasoline
            year_built: Year building was built
            square_footage: Total building square footage (used for both total and occupied)
            mpds: Number of Gas Pumps (MPDs)
            employees: Number of employees (default: 3)
        """
        self.policy_code = policy_code
        self.quotation_url = f"https://gigezrate.guard.com/dotnet/mvc/uw/EZRate/EZR_AddNewProspectShell/Home/Index?MGACODE={policy_code}"
        self.task_id = task_id
        self.trace_id = trace_id or f"quote_{policy_code}"
        self.login_handler = GuardLogin(task_id=task_id, trace_id=self.trace_id)
        self.page = None
        
        # Webhook data
        self.combined_sales = combined_sales
        self.gas_gallons = gas_gallons
        self.year_built = year_built
        self.square_footage = square_footage
        self.mpds = mpds
        self.employees = employees  # User input or default "3"
        
        # Hardcoded values (same for every automation)
        self.damage_to_premises = "100000"
        self.stories = "1"  # Hardcoded to 1 story
        self.residential_units = "0"
        self.vacancy_percent = "0"
        self.gas_sales_percent = "40"
        self.cbd_percent = "0"
        self.tobacco_percent = "10"
        self.alcohol_percent = "10"
        
        logger.info(f"GuardQuote initialized")
        logger.info(f"Policy Code: {policy_code}")
        logger.info(f"Quotation URL: {self.quotation_url}")
        logger.info(f"Combined Sales: ${combined_sales}")
        logger.info(f"Gas Gallons: {gas_gallons}")
        logger.info(f"Year Built: {year_built}")
        logger.info(f"Square Footage: {square_footage}")
        logger.info(f"MPDs: {mpds}")
    
    async def init_browser(self):
        """Initialize browser through login handler"""
        await self.login_handler.init_browser()
        self.page = self.login_handler.page
        logger.info("✅ Browser initialized")
    
    async def login(self):
        """Perform login"""
        logger.info("\n" + "=" * 80)
        logger.info("STEP 1: LOGIN")
        logger.info("=" * 80)
        
        result = await self.login_handler.login()
        if not result.get("success"):
            logger.error(f"❌ Login failed: {result.get('message')}")
            return False
        
        logger.info("✅ Login successful")
        return True
    
    async def navigate_to_quote(self):
        """Navigate to the quotation URL"""
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: NAVIGATE TO QUOTE")
        logger.info("=" * 80)
        logger.info(f"Navigating to: {self.quotation_url}")
        
        try:
            # Use domcontentloaded instead of networkidle - quote page has continuous background activity
            await self.page.goto(self.quotation_url, wait_until="domcontentloaded", timeout=60000)
            # Wait a bit for JavaScript to initialize
            await asyncio.sleep(3)
            
            # Take screenshot
            screenshot_path = self.login_handler.screenshot_dir / "01_quote_page.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            
            # Check current URL
            current_url = self.page.url
            logger.info(f"Current URL: {current_url}")
            
            if "mvcerrorpage" in current_url.lower():
                logger.error("❌ Landed on error page")
                return False
            
            logger.info("✅ Successfully navigated to quote page")
            return True
            
        except Exception as e:
            logger.error(f"❌ Navigation failed: {e}")
            return False
    
    async def fill_quote_details(self):
        """Fill quote details - SEQUENTIAL flow through all panels"""
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: FILL QUOTE DETAILS")
        logger.info("=" * 80)
        
        try:
            # ================================================================
            # PANEL 1: POLICY INFORMATION
            # ================================================================
            logger.info("\n" + "=" * 80)
            logger.info("PANEL 1: POLICY INFORMATION")
            logger.info("=" * 80)
            
            await self.page.wait_for_load_state("domcontentloaded", timeout=15000)
            await asyncio.sleep(2)
            
            # Wait for the Industry dropdown to be visible
            logger.info("Waiting for Policy Information page to load...")
            try:
                await self.page.wait_for_selector('#ProductID', timeout=15000, state="visible")
                logger.info("✅ Policy Information page loaded")
            except Exception as e:
                logger.error(f"❌ Policy Information page not loaded: {e}")
                screenshot_path = self.login_handler.screenshot_dir / "error_policy_info.png"
                await self.page.screenshot(path=str(screenshot_path), full_page=True)
                raise
            
            # Step 1: Select Industry Type = "Retail BOP" (value="5")
            logger.info("Selecting Industry Type: Retail BOP (value=5)")
            await self.page.select_option('#ProductID', value="5")
            logger.info("✅ Industry Type selected: Retail BOP")
            
            # Wait 3 seconds for page to update after selecting Industry Type
            logger.info("Waiting 3 seconds for page to update...")
            await asyncio.sleep(3)
            
            # Step 2: Select "No" for the business ownership question
            logger.info("Selecting 'No' for business ownership question")
            no_radio_selector = 'input[type="radio"][id*="otherbiz_radio_N"]'
            no_radio = await self.page.query_selector(no_radio_selector)
            if no_radio:
                await no_radio.click()
                await asyncio.sleep(0.5)
                logger.info("✅ Selected 'No' for ownership question")
            else:
                logger.warning("Could not find 'No' radio button for ownership question")
            
            # Take screenshot before clicking NEXT
            screenshot_path = self.login_handler.screenshot_dir / "02_policy_info_filled.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            
            # Step 3: Click NEXT button
            logger.info("Clicking NEXT button on Policy Information...")
            next_button = await self.page.query_selector('button.FSbutton-Next')
            if next_button:
                await next_button.click()
                await asyncio.sleep(2)
                await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                logger.info("✅ NEXT button clicked on Policy Information")
            else:
                logger.error("❌ Could not find NEXT button on Policy Information")
                raise Exception("NEXT button not found on Policy Information")
            
            # Take screenshot after clicking NEXT
            screenshot_path = self.login_handler.screenshot_dir / "03_after_policy_info.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            logger.info(f"Current URL: {self.page.url}")
            
            # ================================================================
            # PANEL 2: LOCATION ADDRESSES
            # ================================================================
            logger.info("\n" + "=" * 80)
            logger.info("PANEL 2: LOCATION ADDRESSES")
            logger.info("=" * 80)
            
            await asyncio.sleep(2)
            
            # Wait for location page to load - check for pick_me link
            logger.info("Waiting for Location page to load...")
            try:
                await self.page.wait_for_selector('a[id="pickme_lnk"]', timeout=15000, state="visible")
                logger.info("✅ Location page loaded - found pick_me link")
            except Exception as e:
                logger.warning(f"pick_me link not found, checking for location form: {e}")
            
            # Click "pick me" link for previously used location
            pick_me_link = await self.page.query_selector('a[id="pickme_lnk"]')
            if pick_me_link:
                logger.info("Clicking 'pick me' link for previously used location...")
                await pick_me_link.click()
                await asyncio.sleep(3)
                logger.info("✅ 'pick me' link clicked")
                
                # Take screenshot after picking location
                screenshot_path = self.login_handler.screenshot_dir / "04_after_pick_me.png"
                await self.page.screenshot(path=str(screenshot_path), full_page=True)
                logger.info(f"Screenshot saved: {screenshot_path}")
            else:
                logger.warning("pick_me link not found - location may need manual entry")
            
            # Click VERIFY button
            logger.info("Clicking VERIFY button...")
            await asyncio.sleep(1)
            verify_button = await self.page.query_selector('button[id="verify_Btn"]')
            if verify_button:
                await verify_button.click()
                await asyncio.sleep(2)
                logger.info("✅ VERIFY button clicked")
            else:
                logger.warning("Could not find VERIFY button")
            
            # Click SAVE button
            logger.info("Clicking SAVE button...")
            await asyncio.sleep(1)
            save_button = await self.page.query_selector('button[id="add_button"]')
            if save_button:
                await save_button.click()
                logger.info("✅ SAVE button clicked")
                await asyncio.sleep(3)
                
                # Take screenshot after save
                screenshot_path = self.login_handler.screenshot_dir / "05_after_save.png"
                await self.page.screenshot(path=str(screenshot_path), full_page=True)
                logger.info(f"Screenshot saved: {screenshot_path}")
            else:
                logger.warning("Could not find SAVE button")
            
            # Click "I'm done adding locations" button
            logger.info("Clicking 'I'm done adding locations' button...")
            await asyncio.sleep(3)
            
            # Try to wait for the button to appear
            try:
                await self.page.wait_for_selector('button[name="next_btn"]', timeout=15000, state="visible")
                logger.info("✅ Done button found")
            except Exception as e:
                logger.warning(f"Timeout waiting for done button: {e}")
            
            # Try multiple selectors for the done button
            done_button = await self.page.query_selector('button[name="next_btn"]')
            if not done_button:
                done_button = await self.page.query_selector('button[id="next_btn"]')
            if not done_button:
                done_button = await self.page.query_selector('button:has-text("done adding")')
            if not done_button:
                done_button = await self.page.query_selector('button.FSbutton-Next')
            
            if done_button:
                await done_button.click()
                logger.info("✅ 'I'm done adding locations' button clicked")
                await asyncio.sleep(4)
                await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
            else:
                logger.error("❌ Could not find 'I'm done adding locations' button!")
                screenshot_path = self.login_handler.screenshot_dir / "error_no_done_button.png"
                await self.page.screenshot(path=str(screenshot_path), full_page=True)
                raise Exception("Done button not found on Location page")
            
            # Take screenshot after location
            screenshot_path = self.login_handler.screenshot_dir / "06_after_location.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            logger.info(f"Current URL: {self.page.url}")
            
            # ================================================================
            # PANEL 3: LIABILITY LIMITS
            # ================================================================
            logger.info("\n" + "=" * 80)
            logger.info("PANEL 3: LIABILITY LIMITS")
            logger.info("=" * 80)
            
            await asyncio.sleep(2)
            
            # Wait for Liability Limits panel to load
            logger.info("Waiting for Liability Limits panel to load...")
            try:
                await self.page.wait_for_selector('input[id*="annualrevenue"], input[name="bop_annualrevenue"]', timeout=15000, state="visible")
                logger.info("✅ Liability Limits panel loaded")
            except Exception as e:
                logger.warning(f"Liability Limits panel detection issue: {e}")
            
            # Scroll to make sure fields are visible
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await asyncio.sleep(1)
            
            # Fill Total Annual Sales/Rental Receipts
            logger.info("Filling Total Annual Sales/Rental Receipts...")
            sales_input = await self.page.query_selector('input[id*="annualrevenue"]')
            if not sales_input:
                sales_input = await self.page.query_selector('input[name="bop_annualrevenue"]')
            if not sales_input:
                sales_input = await self.page.query_selector('input[id="notable.bop_annualrevenue.h"]')
            
            if sales_input:
                await sales_input.fill(self.combined_sales)
                await asyncio.sleep(0.5)
                logger.info(f"✅ Total Annual Sales/Rental Receipts: ${self.combined_sales}")
            else:
                logger.warning("Could not find Total Annual Sales input")
            
            # Fill Total Number of Employees
            logger.info("Filling Total Number of Employees...")
            employees_input = await self.page.query_selector('input[id*="employees"]')
            if not employees_input:
                employees_input = await self.page.query_selector('input[name="bop_employees"]')
            if not employees_input:
                employees_input = await self.page.query_selector('input[id="notable.bop_employees.h"]')
            
            if employees_input:
                await employees_input.fill(self.employees)
                await asyncio.sleep(0.5)
                logger.info(f"✅ Total Number of Employees: {self.employees}")
            else:
                logger.warning("Could not find Total Number of Employees input")
            
            # Select "No" for Hired/Non-owned Auto coverage
            logger.info("Selecting 'No' for Hired/Non-owned Auto coverage...")
            await asyncio.sleep(1)
            no_auto_radio = await self.page.query_selector('input[id*="nonownedauto"][value="N"]')
            if not no_auto_radio:
                no_auto_radio = await self.page.query_selector('input[name*="nonownedauto"][value="N"]')
            if not no_auto_radio:
                no_auto_radio = await self.page.query_selector('input[id="nonownedauto_1_radio_N"]')
            
            if no_auto_radio:
                await no_auto_radio.click()
                await asyncio.sleep(0.5)
                logger.info("✅ Selected 'No' for Auto coverage")
            else:
                logger.warning("Could not find 'No' radio button for Auto coverage")
            
            # Take screenshot before clicking NEXT
            screenshot_path = self.login_handler.screenshot_dir / "07_liability_filled.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            
            # Click NEXT button
            logger.info("Clicking NEXT button on Liability Limits...")
            await asyncio.sleep(1)
            next_button = await self.page.query_selector('button[name="next_btn"]')
            if next_button:
                await next_button.click()
                await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                logger.info("✅ NEXT button clicked on Liability Limits")
            else:
                logger.warning("Could not find NEXT button on Liability Limits")
            
            # Take screenshot after Liability Limits
            screenshot_path = self.login_handler.screenshot_dir / "08_after_liability.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            logger.info(f"Current URL: {self.page.url}")
            
            # ================================================================
            # PANEL 4: POLICY LEVEL COVERAGES
            # ================================================================
            logger.info("\n" + "=" * 80)
            logger.info("PANEL 4: POLICY LEVEL COVERAGES")
            logger.info("=" * 80)
            
            await asyncio.sleep(3)
            
            # Wait for Policy Level Coverages panel to load
            damage_selectors = [
                'input[name*="ptentir_limit"]',
                'input[id*="ptentir_limit"]',
                'input.GTnumeric[data-min="50000"]'
            ]
            
            damage_input = None
            for selector in damage_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000, state="visible")
                    damage_input = await self.page.query_selector(selector)
                    if damage_input:
                        logger.info(f"✅ Found Damage To Premises input with selector: {selector}")
                        break
                except Exception:
                    continue
            
            if damage_input:
                logger.info("✅ Policy Level Coverages panel loaded")
                current_value = await damage_input.get_attribute('value')
                logger.info(f"Current Damage To Premises value: {current_value}")
                await damage_input.fill(self.damage_to_premises)
                logger.info(f"✅ Damage To Premises Rented To You set to: ${self.damage_to_premises}")
            else:
                logger.warning("⚠️ Could not find Damage To Premises input")
            
            await asyncio.sleep(1)
            
            # Uncheck Cyber Suite checkbox
            logger.info("Unchecking Cyber Suite checkbox...")
            cyber_selectors = [
                'input[name*="CYBERSUITE"][name*="OnPolicy_checkbox"]',
                'input[name*="CoverageContainer.Coverages[_CYBERSUITE_"][type="CHECKBOX"]',
                'input[id*="CYBERSUITE"][type="checkbox"]'
            ]
            
            cyber_checkbox = None
            for selector in cyber_selectors:
                cyber_checkbox = await self.page.query_selector(selector)
                if cyber_checkbox:
                    logger.info(f"✅ Found Cyber Suite checkbox with selector: {selector}")
                    break
            
            if cyber_checkbox:
                is_checked = await cyber_checkbox.is_checked()
                logger.info(f"Cyber Suite checkbox current state: {'checked' if is_checked else 'unchecked'}")
                if is_checked:
                    await cyber_checkbox.click()
                    await asyncio.sleep(0.5)
                    logger.info("✅ Cyber Suite checkbox unchecked")
            else:
                logger.warning("⚠️ Could not find Cyber Suite checkbox")
            
            await asyncio.sleep(1)
            
            # Take screenshot before clicking NEXT
            screenshot_path = self.login_handler.screenshot_dir / "09_policy_coverages_filled.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            
            # Click NEXT button on Policy Level Coverages
            logger.info("Clicking NEXT button on Policy Level Coverages...")
            next_button = await self.page.query_selector('button[name="next_btn"]')
            if next_button:
                await next_button.click()
                await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                logger.info("✅ NEXT button clicked on Policy Level Coverages")
                await asyncio.sleep(2)
            else:
                logger.warning("⚠️ Could not find NEXT button on Policy Level Coverages")
            
            # Take screenshot
            screenshot_path = self.login_handler.screenshot_dir / "10_after_policy_coverages.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            logger.info(f"Current URL: {self.page.url}")
            
            # ================================================================
            # PANEL 5: ADDITIONAL INSUREDS
            # ================================================================
            logger.info("\n" + "=" * 80)
            logger.info("PANEL 5: ADDITIONAL INSUREDS")
            logger.info("=" * 80)
            
            logger.info("No additional insureds needed, clicking NEXT...")
            await asyncio.sleep(3)
            
            # Find and click NEXT button
            next_button_selectors = [
                'button[name="next_btn"]',
                'button.FSbutton-Next',
                'button:has-text("NEXT")'
            ]
            
            next_button = None
            for selector in next_button_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000, state="visible")
                    next_button = await self.page.query_selector(selector)
                    if next_button:
                        logger.info(f"✅ Found NEXT button with selector: {selector}")
                        break
                except Exception:
                    continue
            
            if next_button:
                await next_button.click()
                await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                logger.info("✅ NEXT button clicked on Additional Insureds")
                await asyncio.sleep(3)
            else:
                logger.warning("⚠️ Could not find NEXT button on Additional Insureds")
            
            # Take screenshot
            screenshot_path = self.login_handler.screenshot_dir / "11_after_additional_insureds.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            logger.info(f"Current URL: {self.page.url}")
            
            # ================================================================
            # PANEL 6: LOCATION INFORMATION
            # ================================================================
            logger.info("\n" + "=" * 80)
            logger.info("PANEL 6: LOCATION INFORMATION")
            logger.info("=" * 80)
            
            logger.info("Waiting for Location Information panel to load...")
            
            # Wait for the panel to be fully loaded
            try:
                await self.page.wait_for_selector('input[name*="bplocation"], select[name*="bplocation"]', timeout=10000, state="attached")
                logger.info("✅ Location Information panel detected")
                await asyncio.sleep(3)
            except Exception as e:
                logger.warning(f"⚠️ Location Information panel may not have loaded: {e}")
            
            # Fire hydrant radio button
            fire_hydrant_selectors = [
                'input[name*="bplocation_watersource"][value="Y"]',
                'input[id*="watersource"][value="Y"]',
                'input[name*="watersource"][value="Y"]'
            ]
            
            fire_hydrant_yes = None
            for selector in fire_hydrant_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000, state="visible")
                    fire_hydrant_yes = await self.page.query_selector(selector)
                    if fire_hydrant_yes:
                        logger.info(f"✅ Found fire hydrant radio with selector: {selector}")
                        break
                except Exception:
                    continue
            
            if fire_hydrant_yes:
                await fire_hydrant_yes.click()
                await asyncio.sleep(0.5)
                logger.info("✅ Selected 'Yes' for fire hydrant/water source")
            else:
                logger.warning("⚠️ Could not find fire hydrant radio button")
            
            # Fire station distance dropdown
            logger.info("Selecting fire station distance...")
            await asyncio.sleep(1)
            fire_station_selectors = [
                'select[name*="bplocation_firestation"]',
                'select[id*="firestation"]',
                'select[name*="firestation"]'
            ]
            
            for selector in fire_station_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=3000, state="visible")
                    if await self.page.query_selector(selector):
                        await self.page.select_option(selector, value="X")
                        logger.info("✅ Selected fire station distance: More than 5 but less than 7 road miles")
                        break
                except Exception:
                    continue
            
            await asyncio.sleep(1)
            
            # Consecutive years in business dropdown
            logger.info("Selecting consecutive years in business...")
            years_selectors = [
                'select[name="bplocation_yearsinbusiness"]',
                'select[name*="yearsinbusiness"]',
                'select[id*="yearsinbusiness"]'
            ]
            
            for selector in years_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=3000, state="visible")
                    if await self.page.query_selector(selector):
                        await self.page.select_option(selector, value="0")
                        logger.info("✅ Selected consecutive years: New Venture (0)")
                        break
                except Exception:
                    continue
            
            # Question 1: Location open/occupied (Yes)
            logger.info("Selecting 'Yes' for location open/occupied question...")
            open_radio_selectors = [
                'input[name*="bplocation_currentlyopen"][value="Y"]',
                'input[id*="currentlyopen"][value="Y"]',
                'input[name*="currentlyopen"][value="Y"]'
            ]
            
            for selector in open_radio_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=3000, state="visible")
                    open_radio = await self.page.query_selector(selector)
                    if open_radio:
                        await open_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'Yes' for location open/occupied")
                        break
                except Exception:
                    continue
            
            # Question 2: Hurricane Idalia damage (No)
            logger.info("Selecting 'No' for Hurricane Idalia damage...")
            idalia_radio_selectors = [
                'input[name*="bplocation_hurricaneidalia"][value="N"]',
                'input[name*="idalia"][value="N"]',
                'input[id*="hurricaneidalia"][value="N"]'
            ]
            
            for selector in idalia_radio_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=3000, state="visible")
                    idalia_radio = await self.page.query_selector(selector)
                    if idalia_radio:
                        await idalia_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'No' for Hurricane Idalia damage")
                        break
                except Exception:
                    continue
            
            # Question 3: Hurricane DEBBY damage (No)
            logger.info("Selecting 'No' for Hurricane DEBBY damage...")
            debby_radio_selectors = [
                'input[name*="bplocation_hurricanedebby"][value="N"]',
                'input[name*="debby"][value="N"]',
                'input[id*="hurricanedebby"][value="N"]'
            ]
            
            for selector in debby_radio_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=3000, state="visible")
                    debby_radio = await self.page.query_selector(selector)
                    if debby_radio:
                        await debby_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'No' for Hurricane DEBBY damage")
                        break
                except Exception:
                    continue
            
            await asyncio.sleep(1)
            
            # Take screenshot before clicking NEXT
            screenshot_path = self.login_handler.screenshot_dir / "12_location_info_filled.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            
            # Click NEXT button on Location Information
            logger.info("Clicking NEXT button on Location Information...")
            next_button = await self.page.query_selector('button[name="next_btn"]')
            if next_button:
                await next_button.click()
                await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                logger.info("✅ NEXT button clicked on Location Information")
                await asyncio.sleep(2)
            else:
                logger.warning("⚠️ Could not find NEXT button on Location Information")
            
            # Take screenshot
            screenshot_path = self.login_handler.screenshot_dir / "13_after_location_info.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            logger.info(f"Current URL: {self.page.url}")
            
            # ================================================================
            # PANEL 7: WINDSTORM/HAIL
            # ================================================================
            logger.info("\n" + "=" * 80)
            logger.info("PANEL 7: WINDSTORM/HAIL")
            logger.info("=" * 80)
            
            await asyncio.sleep(2)
            
            # Question 1: Separate windstorm/hail policy (No = 0)
            logger.info("Selecting 'No' for separate windstorm/hail policy...")
            separate_policy_selectors = [
                'input[name="bplocationdeductibles_separatewindpolicy"][value="0"]',
                'input[id="bplocationdeductibles_separatewindpolicy_radio_0"]',
                'input[name="bplocationdeductibles_separatewindpolicy_radio"][value="0"]'
            ]
            
            for selector in separate_policy_selectors:
                separate_policy_radio = await self.page.query_selector(selector)
                if separate_policy_radio:
                    await separate_policy_radio.click()
                    await asyncio.sleep(0.5)
                    logger.info("✅ Selected 'No' for separate windstorm/hail policy")
                    break
            
            # Question 2: Exclude wind/hail coverage (No = 0)
            logger.info("Selecting 'No' for excluding wind/hail coverage...")
            exclude_coverage_selectors = [
                'input[name="bplocationdeductibles_windhail_excl"][value="0"]',
                'input[id="bplocationdeductibles_windhail_excl_radio_0"]',
                'input[name="bplocationdeductibles_windhail_excl_radio"][value="0"]'
            ]
            
            for selector in exclude_coverage_selectors:
                exclude_coverage_radio = await self.page.query_selector(selector)
                if exclude_coverage_radio:
                    await exclude_coverage_radio.click()
                    await asyncio.sleep(0.5)
                    logger.info("✅ Selected 'No' for excluding wind/hail coverage")
                    break
            
            await asyncio.sleep(1)
            
            # Take screenshot before clicking NEXT
            screenshot_path = self.login_handler.screenshot_dir / "14_windstorm_filled.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            
            # Click NEXT button on Windstorm/Hail
            logger.info("Clicking NEXT button on Windstorm/Hail...")
            next_button = await self.page.query_selector('button[name="next_btn"]')
            if next_button:
                await next_button.click()
                await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                logger.info("✅ NEXT button clicked on Windstorm/Hail")
                await asyncio.sleep(2)
            else:
                logger.warning("⚠️ Could not find NEXT button on Windstorm/Hail")
            
            # Take screenshot
            screenshot_path = self.login_handler.screenshot_dir / "15_after_windstorm.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            logger.info(f"Current URL: {self.page.url}")
            
            # ================================================================
            # PANEL 8: BUILDING INFORMATION
            # ================================================================
            logger.info("\n" + "=" * 80)
            logger.info("PANEL 8: BUILDING INFORMATION")
            logger.info("=" * 80)
            
            await asyncio.sleep(2)
            
            # Field 1: Occupancy dropdown (TE = Tenant, OM = Owner)
            logger.info("Selecting Occupancy type...")
            occupancy_selectors = [
                'select[name="OccupancyType"]',
                'select[id="Occupancy"]',
                'select#Occupancy'
            ]
            
            for selector in occupancy_selectors:
                if await self.page.query_selector(selector):
                    await self.page.select_option(selector, value="OM")
                    logger.info("✅ Selected Occupancy: Owner Occupied (OM)")
                    break
            
            # Field 2: Building Type - Stand Alone Building
            logger.info("Selecting Building Type: Stand Alone Building...")
            building_type_selectors = [
                'input[name="OccupancyType_radio"][id="OccupancyType_radio_STANDALONE"]',
                'input[value="STANDALONE"][type="radio"]',
                'input[id="OccupancyType_radio_STANDALONE"]'
            ]
            
            for selector in building_type_selectors:
                building_type_radio = await self.page.query_selector(selector)
                if building_type_radio:
                    await building_type_radio.click()
                    await asyncio.sleep(0.5)
                    logger.info("✅ Selected Building Type: Stand Alone Building")
                    break
            
            await asyncio.sleep(1)
            
            # Field 3: Sole Occupant (Yes = SOLE)
            logger.info("Selecting Sole Occupant: Yes...")
            sole_occupant_selectors = [
                'input[name="SoleOccupant"][value="SOLE"]',
                'input[id="SoleOccupant"][value="SOLE"]',
                'input[id="SoleOccupant_radio_SOLE"]'
            ]
            
            for selector in sole_occupant_selectors:
                sole_occupant_radio = await self.page.query_selector(selector)
                if sole_occupant_radio:
                    await sole_occupant_radio.click()
                    await asyncio.sleep(0.5)
                    logger.info("✅ Selected Sole Occupant: Yes")
                    break
            
            # Field 4: Building Industry dropdown - CONVEN
            logger.info("Selecting Building Industry: Convenience Stores & Gas Stations...")
            industry_selectors = [
                'select[name="EZRate_Industry"]',
                'select[id="EZRate_Industry"]'
            ]
            
            for selector in industry_selectors:
                if await self.page.query_selector(selector):
                    await self.page.select_option(selector, value="CONVEN")
                    logger.info("✅ Selected Building Industry: CONVEN (Convenience Stores & Gas Stations)")
                    # Wait for Class Code and Construction dropdowns to load
                    logger.info("⏳ Waiting 3 seconds for dropdowns to load...")
                    await asyncio.sleep(3)
                    break
            
            # Field 5: Class Code dropdown - 0932101
            logger.info("Selecting Class Code: 0932101...")
            classcode_selectors = [
                'select[name="ClassCode"]',
                'select[id="ClassCode"]'
            ]
            
            for selector in classcode_selectors:
                if await self.page.query_selector(selector):
                    await self.page.select_option(selector, value="0932101")
                    logger.info("✅ Selected Class Code: 0932101")
                    break
            
            # Field 6: Construction dropdown - FM (Masonry)
            logger.info("Selecting Construction: Masonry...")
            construction_selectors = [
                'select[name="Construction"]',
                'select[id="Construction"]'
            ]
            
            for selector in construction_selectors:
                if await self.page.query_selector(selector):
                    await self.page.select_option(selector, value="FM")
                    logger.info("✅ Selected Construction: FM (Masonry)")
                    break
            
            await asyncio.sleep(1)
            
            # Field 7: Annual Sales/Rental Receipts at this Building
            logger.info("Filling Annual Sales/Rental Receipts at this Building...")
            grosssales_selectors = [
                'input[name="GrossSales"]',
                'input[id="GrossSales"]',
                'input[id="Grosssales"]'
            ]
            
            for selector in grosssales_selectors:
                grosssales_input = await self.page.query_selector(selector)
                if grosssales_input:
                    await grosssales_input.click()
                    await grosssales_input.fill("")
                    await grosssales_input.type(self.combined_sales)
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ Annual Sales/Rental Receipts: {self.combined_sales}")
                    break
            
            # Field 8: Annual Gallons of Gasoline
            logger.info("Filling Annual Gallons of Gasoline...")
            gasoline_selectors = [
                'input[name="gallonsOfGasoline"]',
                'input[id="gallonsOfGasoline"]'
            ]
            
            for selector in gasoline_selectors:
                gasoline_input = await self.page.query_selector(selector)
                if gasoline_input:
                    await gasoline_input.click()
                    await gasoline_input.fill("")
                    await gasoline_input.type(self.gas_gallons)
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ Annual Gallons of Gasoline: {self.gas_gallons}")
                    break
            
            # Field 9: Liquor On-Premises (No)
            logger.info("Selecting 'No' for liquor consumed on-premises...")
            liquor_selectors = [
                'input[name="LiquorOnPremises"][value="N"]',
                'input[id="LiquorOnPremises_radio_N"]',
                'input[name="LiquorOnPremises_radio"][value="N"]'
            ]
            
            for selector in liquor_selectors:
                liquor_radio = await self.page.query_selector(selector)
                if liquor_radio:
                    await liquor_radio.click()
                    await asyncio.sleep(0.5)
                    logger.info("✅ Selected 'No' for liquor consumed on-premises")
                    break
            
            await asyncio.sleep(1)
            
            # Field 10: Original Year Built
            logger.info("Filling Original Year Built...")
            yearbuilt_selectors = [
                'input[name="YearBuilt"]',
                'input[id="YearBuilt"]'
            ]
            
            for selector in yearbuilt_selectors:
                yearbuilt_input = await self.page.query_selector(selector)
                if yearbuilt_input:
                    await yearbuilt_input.click()
                    await yearbuilt_input.fill("")
                    await yearbuilt_input.type(self.year_built)
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ Original Year Built: {self.year_built}")
                    break
            
            # Field 11: Number of Stories
            logger.info("Filling Number of Stories...")
            stories_selectors = [
                'input[name="Stories"]',
                'input[id="Stories"]'
            ]
            
            for selector in stories_selectors:
                stories_input = await self.page.query_selector(selector)
                if stories_input:
                    await stories_input.click()
                    await stories_input.fill("")
                    await stories_input.type(self.stories)
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ Number of Stories: {self.stories}")
                    break
            
            # Field 12: Roof Surfacing Type dropdown - Unknown
            logger.info("Selecting Roof Surfacing Type: Unknown...")
            rooftype_selectors = [
                'select[name="ROOFTYPE"]',
                'select[id="ROOFTYPE"]'
            ]
            
            for selector in rooftype_selectors:
                if await self.page.query_selector(selector):
                    await self.page.select_option(selector, value="UNKNOWN")
                    logger.info("✅ Selected Roof Surfacing Type: UNKNOWN")
                    break
            
            # Field 13: Total Building Square Footage
            logger.info("Filling Total Building Square Footage...")
            sqfootage_selectors = [
                'input[name="SquareFootage"]',
                'input[id="SquareFootage"]'
            ]
            
            for selector in sqfootage_selectors:
                sqfootage_input = await self.page.query_selector(selector)
                if sqfootage_input:
                    await sqfootage_input.click()
                    await sqfootage_input.fill("")
                    await sqfootage_input.type(self.square_footage)
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ Total Building Square Footage: {self.square_footage}")
                    break
            
            # Field 14: Total Square Footage Occupied by Insured
            logger.info("Filling Total Square Footage Occupied by Insured...")
            sqftocc_selectors = [
                'input[name="SQFTOCC"]',
                'input[id="SQFTOCC"]'
            ]
            
            for selector in sqftocc_selectors:
                sqftocc_input = await self.page.query_selector(selector)
                if sqftocc_input:
                    await sqftocc_input.click()
                    await sqftocc_input.fill("")
                    await sqftocc_input.type(self.square_footage)
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ Total Square Footage Occupied: {self.square_footage}")
                    break
            
            await asyncio.sleep(1)
            
            # Field 15: Gas pumps available 24 hours (No)
            logger.info("Selecting 'No' for gas pumps available 24 hours...")
            gaspumps_selectors = [
                'input[name="gasPumps24Hours"][value="False"]',
                'input[id="gasPumps24Hours_radio_False"]',
                'input[name="gasPumps24Hours_radio"][value="False"]'
            ]
            
            for selector in gaspumps_selectors:
                gaspumps_radio = await self.page.query_selector(selector)
                if gaspumps_radio:
                    await gaspumps_radio.click()
                    await asyncio.sleep(0.5)
                    logger.info("✅ Selected 'No' for gas pumps available 24 hours")
                    break
            
            await asyncio.sleep(1)
            
            # Field 16: Number of Residential Units
            logger.info("Filling Number of Residential Units...")
            residential_selectors = [
                'input[name="ResidentialUnits"]',
                'input[id="ResidentialUnits"]'
            ]
            
            for selector in residential_selectors:
                residential_input = await self.page.query_selector(selector)
                if residential_input:
                    await residential_input.click()
                    await residential_input.fill("")
                    await residential_input.type(self.residential_units)
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ Number of Residential Units: {self.residential_units}")
                    break
            
            # Field 17: Automatic Sprinkler System (No)
            logger.info("Selecting Automatic Sprinkler System: No...")
            sprinkler_selectors = [
                'select[name="Sprinklered"]',
                'select[id="Sprinklered"]'
            ]
            
            for selector in sprinkler_selectors:
                if await self.page.query_selector(selector):
                    await self.page.select_option(selector, value="N")
                    logger.info("✅ Selected Sprinkler System: N (No)")
                    break
            
            # Field 18: Automatic Fire Alarm (Central Station)
            logger.info("Selecting Automatic Fire Alarm: Central Station...")
            firealarm_selectors = [
                'select[name="FireAlarm"]',
                'select[id="FireAlarm"]'
            ]
            
            for selector in firealarm_selectors:
                if await self.page.query_selector(selector):
                    await self.page.select_option(selector, value="Central Station")
                    logger.info("✅ Selected Fire Alarm: Central Station")
                    break
            
            # Field 19: Ansul System (N/A)
            logger.info("Selecting Ansul System: N/A...")
            ansul_selectors = [
                'select[name="AnsulSystem"]',
                'select[id="AnsulSystem"]'
            ]
            
            for selector in ansul_selectors:
                if await self.page.query_selector(selector):
                    await self.page.select_option(selector, value="NA")
                    logger.info("✅ Selected Ansul System: NA (N/A)")
                    break
            
            # Field 20: Burglar Alarm (Central Station)
            logger.info("Selecting Burglar Alarm: Central Station...")
            burglar_selectors = [
                'select[name="BurglarAlarm"]',
                'select[id="BurglarAlarm"]'
            ]
            
            for selector in burglar_selectors:
                if await self.page.query_selector(selector):
                    await self.page.select_option(selector, value="Central Station")
                    logger.info("✅ Selected Burglar Alarm: Central Station")
                    break
            
            # Field 21: Security Cameras (Yes)
            logger.info("Selecting Security Cameras: Yes...")
            cameras_selectors = [
                'select[name="SecurityCameras"]',
                'select[id="SecurityCameras"]'
            ]
            
            for selector in cameras_selectors:
                if await self.page.query_selector(selector):
                    await self.page.select_option(selector, value="Y")
                    logger.info("✅ Selected Security Cameras: Y (Yes)")
                    break
            
            await asyncio.sleep(1)
            
            # Take screenshot of filled building info
            screenshot_path = self.login_handler.screenshot_dir / "16_building_info_filled.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            
            # Click NEXT button on Building Information
            logger.info("Clicking NEXT button on Building Information...")
            next_button = await self.page.query_selector('button[name="next_btn"]')
            if next_button:
                await next_button.click()
                await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                logger.info("✅ NEXT button clicked on Building Information")
                await asyncio.sleep(2)
            else:
                logger.warning("⚠️ Could not find NEXT button on Building Information")
            
            # Take screenshot
            screenshot_path = self.login_handler.screenshot_dir / "17_after_building_info.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            logger.info(f"Current URL: {self.page.url}")
            
            # ================================================================
            # PANEL 9: STATE SPECIFIC INFORMATION
            # ================================================================
            logger.info("\n" + "=" * 80)
            logger.info("PANEL 9: STATE SPECIFIC INFORMATION")
            logger.info("=" * 80)
            
            await asyncio.sleep(2)
            
            # Take screenshot of state specific page
            screenshot_path = self.login_handler.screenshot_dir / "18_state_specific_info.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            
            # State Specific has no fields to fill - just click NEXT
            logger.info("Clicking NEXT button on State Specific Information...")
            next_selectors = [
                'button[name="next_btn"]',
                'button.FSbutton-Next',
                'button:has-text("NEXT")'
            ]
            
            for selector in next_selectors:
                next_button = await self.page.query_selector(selector)
                if next_button:
                    await next_button.click()
                    await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                    logger.info("✅ NEXT button clicked on State Specific Information")
                    await asyncio.sleep(3)
                    break
            
            # Take screenshot
            screenshot_path = self.login_handler.screenshot_dir / "19_after_state_specific.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            logger.info(f"Current URL: {self.page.url}")
            
            # ================================================================
            # PANEL 10: CLASS SPECIFIC INFORMATION (LAST PANEL)
            # ================================================================
            logger.info("\n" + "=" * 80)
            logger.info("PANEL 10: CLASS SPECIFIC INFORMATION (FINAL)")
            logger.info("=" * 80)
            
            await asyncio.sleep(2)
            
            # Try to detect if we're on the Class Specific panel
            try:
                await self.page.wait_for_selector(
                    'input[name="conveniencestore_bld_cvg_radio"], input[name="conveniencestore_vacancy"], input[name="conveniencestore_gaspumps"]',
                    state="visible",
                    timeout=15000
                )
                logger.info("✅ Class Specific Information panel detected")
            except Exception as e:
                logger.warning(f"⚠️ Timeout waiting for Class Specific panel fields: {e}")
                # Take debug screenshot
                screenshot_path = self.login_handler.screenshot_dir / "20_class_specific_not_found.png"
                await self.page.screenshot(path=str(screenshot_path), full_page=True)
                logger.info(f"Debug screenshot saved: {screenshot_path}")
            
            await asyncio.sleep(1)
            
            # Take screenshot of Class Specific panel
            screenshot_path = self.login_handler.screenshot_dir / "21_class_specific_panel.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            
            # Field 1: Intended building use (Commercial)
            logger.info("Selecting Intended Building Use: Commercial...")
            building_use_selectors = [
                'select[name="conveniencestore_intended_building_use"]',
                'select[id="conveniencestore_intended_building_use"]'
            ]
            
            for selector in building_use_selectors:
                if await self.page.query_selector(selector):
                    await self.page.select_option(selector, value="C")
                    logger.info("✅ Selected Intended Building Use: C (Commercial)")
                    await asyncio.sleep(0.5)
                    break
            
            # Field 2: Building coverage needed? (Tenant = No, Owner = Yes)
            logger.info("Selecting 'No' for Building coverage needed (Tenant)...")
            building_coverage_selectors = [
                'input[name="conveniencestore_bld_cvg_radio"][value="N"]',
                'input[id="conveniencestore_bld_cvg_radio_N"]'
            ]
            
            for selector in building_coverage_selectors:
                building_coverage_radio = await self.page.query_selector(selector)
                if building_coverage_radio:
                    await building_coverage_radio.click()
                    await asyncio.sleep(0.5)
                    logger.info("✅ Selected 'No' for Building coverage (Tenant)")
                    break
            
            # Field 2: Building vacancy percentage (0)
            logger.info("Filling building vacancy percentage...")
            vacancy_selectors = [
                'input[name="conveniencestore_vacancy"]',
                'input[id="conveniencestore_vacancy"]'
            ]
            
            for selector in vacancy_selectors:
                vacancy_input = await self.page.query_selector(selector)
                if vacancy_input:
                    await vacancy_input.click()
                    await vacancy_input.fill("")
                    await vacancy_input.type(self.vacancy_percent)
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ Building vacancy percentage: {self.vacancy_percent}")
                    break
            
            # Field 3: Renovations/construction? (No)
            logger.info("Selecting 'No' for renovations/construction...")
            renovation_selectors = [
                'input[name="conveniencestore_bld_cvg_2_radio"][value="N"]',
                'input[id="conveniencestore_bld_cvg_2_radio_N"]'
            ]
            
            for selector in renovation_selectors:
                renovation_radio = await self.page.query_selector(selector)
                if renovation_radio:
                    await renovation_radio.click()
                    await asyncio.sleep(0.5)
                    logger.info("✅ Selected 'No' for renovations/construction")
                    break
            
            # Field 4: Number of Gas Pumps
            logger.info("Filling Number of Gas Pumps...")
            gaspumps_selectors = [
                'input[name="conveniencestore_gaspumps"]',
                'input[id="conveniencestore_gaspumps"]'
            ]
            
            for selector in gaspumps_selectors:
                gaspumps_input = await self.page.query_selector(selector)
                if gaspumps_input:
                    await gaspumps_input.click()
                    await gaspumps_input.fill("")
                    await gaspumps_input.type(self.mpds)
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ Number of Gas Pumps: {self.mpds}")
                    break
            
            # Field 5: Gas sales percentage (40%)
            logger.info("Filling gas sales percentage...")
            gassales_selectors = [
                'input[name="conveniencestore_gassales"]',
                'input[id="conveniencestore_gassales"]'
            ]
            
            for selector in gassales_selectors:
                gassales_input = await self.page.query_selector(selector)
                if gassales_input:
                    await gassales_input.click()
                    await gassales_input.fill("")
                    await gassales_input.type(self.gas_sales_percent)
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ Gas sales percentage: {self.gas_sales_percent}%")
                    break
            
            # Field 6: Convenience store annual receipts (Inside Sales)
            logger.info("Filling convenience store annual receipts (Inside Sales)...")
            receipts_selectors = [
                'input[name="conveniencestore_gaspumps_2"]',
                'input[id="conveniencestore_gaspumps_2"]'
            ]
            
            for selector in receipts_selectors:
                receipts_input = await self.page.query_selector(selector)
                if receipts_input:
                    await receipts_input.click()
                    await receipts_input.fill("")
                    await receipts_input.type(self.combined_sales)
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ Convenience store annual receipts: ${self.combined_sales}")
                    break
            
            # Field 7: Propane tank filling? (No)
            logger.info("Selecting 'No' for propane tank filling...")
            propane_selectors = [
                'input[name="conveniencestore_propane_radio_N"][value="N"]',
                'input[id="conveniencestore_propane_radio_N"]'
            ]
            
            for selector in propane_selectors:
                propane_radio = await self.page.query_selector(selector)
                if propane_radio:
                    await propane_radio.click()
                    await asyncio.sleep(0.5)
                    logger.info("✅ Selected 'No' for propane tank filling")
                    break
            
            # Field 8: Cannabis products? (No)
            logger.info("Selecting 'No' for cannabis products...")
            cannabis_selectors = [
                'input[name="conveniencestore_cannabis_radio_N"][value="N"]',
                'input[id="conveniencestore_cannabis_radio_N"]'
            ]
            
            for selector in cannabis_selectors:
                cannabis_radio = await self.page.query_selector(selector)
                if cannabis_radio:
                    await cannabis_radio.click()
                    await asyncio.sleep(0.5)
                    logger.info("✅ Selected 'No' for cannabis products")
                    break
            
            # Field 9: CBD products percentage (0%)
            logger.info("Filling CBD products percentage...")
            cbd_selectors = [
                'input[name="conveniencestore_cbd_products"]',
                'input[id="conveniencestore_cbd_products"]'
            ]
            
            for selector in cbd_selectors:
                cbd_input = await self.page.query_selector(selector)
                if cbd_input:
                    await cbd_input.click()
                    await cbd_input.fill("")
                    await cbd_input.type(self.cbd_percent)
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ CBD products percentage: {self.cbd_percent}%")
                    break
            
            # Field 10: Primary products for sale (Option 1)
            logger.info("Selecting primary products for sale (Option 1)...")
            products_selectors = [
                'select[name="conveniencestore_products_forsale"]',
                'select[id="conveniencestore_products_forsale"]'
            ]
            
            for selector in products_selectors:
                if await self.page.query_selector(selector):
                    await self.page.select_option(selector, value="1")
                    logger.info("✅ Selected Option 1 for primary products for sale")
                    break
            
            # Field 11: Tobacco products percentage (10%)
            logger.info("Filling tobacco products percentage...")
            tobacco_selectors = [
                'input[name="conveniencestore_tobacco"]',
                'input[id="conveniencestore_tobacco"]'
            ]
            
            for selector in tobacco_selectors:
                tobacco_input = await self.page.query_selector(selector)
                if tobacco_input:
                    await tobacco_input.click()
                    await tobacco_input.fill("")
                    await tobacco_input.type(self.tobacco_percent)
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ Tobacco products percentage: {self.tobacco_percent}%")
                    break
            
            # Field 12: Food preparation operations (None)
            logger.info("Selecting food preparation operations (None)...")
            foodprep_selectors = [
                'select[name="conveniencestore_foodprep"]',
                'select[id="conveniencestore_foodprep"]'
            ]
            
            for selector in foodprep_selectors:
                if await self.page.query_selector(selector):
                    await self.page.select_option(selector, value="NONE")
                    logger.info("✅ Selected 'None' for food preparation operations")
                    break
            
            # Field 13: IBHS FORTIFIED certification? (Yes)
            logger.info("Selecting 'Yes' for IBHS FORTIFIED certification...")
            fortified_selectors = [
                'input[name="conveniencestore_windmitigation_ga_radio"][value="Y"]',
                'input[id="conveniencestore_windmitigation_ga_radio_Y"]'
            ]
            
            for selector in fortified_selectors:
                fortified_radio = await self.page.query_selector(selector)
                if fortified_radio:
                    await fortified_radio.click()
                    await asyncio.sleep(1)
                    logger.info("✅ Selected 'Yes' for IBHS FORTIFIED certification")
                    break
            
            # Field 14: Compliance acknowledgment (Yes)
            logger.info("Selecting 'Yes' for compliance acknowledgment...")
            compliance_selectors = [
                'input[name="conveniencestore_windmessage_radio_N"][value="Y"]',
                'input[id="conveniencestore_windmessage_radio_Y"]'
            ]
            
            for selector in compliance_selectors:
                compliance_radio = await self.page.query_selector(selector)
                if compliance_radio:
                    await compliance_radio.click()
                    await asyncio.sleep(0.5)
                    logger.info("✅ Selected 'Yes' for compliance acknowledgment")
                    break
            
            # Field 15: High-hazard exposures? (No)
            logger.info("Selecting 'No' for high-hazard exposures...")
            highhazard_selectors = [
                'input[name="conveniencestore_highhazard_radio"][value="N"]',
                'input[id="conveniencestore_highhazard_radio_N"]'
            ]
            
            for selector in highhazard_selectors:
                highhazard_radio = await self.page.query_selector(selector)
                if highhazard_radio:
                    await highhazard_radio.click()
                    await asyncio.sleep(0.5)
                    logger.info("✅ Selected 'No' for high-hazard exposures")
                    break
            
            # Field 16: Alcohol sales percentage (10%)
            logger.info("Filling liquor/alcohol sales percentage...")
            alcohol_selectors = [
                'input[name="conveniencestore_alcoholsales"]',
                'input[id="conveniencestore_alcoholsales"]'
            ]
            
            for selector in alcohol_selectors:
                alcohol_input = await self.page.query_selector(selector)
                if alcohol_input:
                    await alcohol_input.click()
                    await alcohol_input.fill("")
                    await alcohol_input.type(self.alcohol_percent)
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ Liquor/alcohol sales percentage: {self.alcohol_percent}%")
                    break
            
            # Field 17: Auto Service/Repair operations? (No)
            logger.info("Selecting 'No' for auto service operations...")
            autoservice_selectors = [
                'input[name="conveniencestore_autoservices_radio"][value="N"]',
                'input[id="conveniencestore_autoservices_radio_N"]'
            ]
            
            for selector in autoservice_selectors:
                autoservice_radio = await self.page.query_selector(selector)
                if autoservice_radio:
                    await autoservice_radio.click()
                    await asyncio.sleep(0.5)
                    logger.info("✅ Selected 'No' for auto service operations")
                    break
            
            # Field 18: Parking lot paved within last 15 years? (Yes)
            logger.info("Selecting 'Yes' for parking lot paving...")
            parkinglot_selectors = [
                'input[name="conveniencestore_parkinglot_radio_Y"][value="Y"]',
                'input[id="conveniencestore_parkinglot_radio_Y"]'
            ]
            
            for selector in parkinglot_selectors:
                parkinglot_radio = await self.page.query_selector(selector)
                if parkinglot_radio:
                    await parkinglot_radio.click()
                    await asyncio.sleep(0.5)
                    logger.info("✅ Selected 'Yes' for parking lot paving")
                    break
            
            await asyncio.sleep(1)
            
            # Take screenshot of filled class specific info
            screenshot_path = self.login_handler.screenshot_dir / "22_class_specific_filled.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            
            # Click NEXT button on Class Specific Information (FINAL PANEL)
            logger.info("Clicking NEXT button on Class Specific Information (FINAL PANEL)...")
            next_button = await self.page.query_selector('button[name="next_btn"]')
            if next_button:
                await next_button.click()
                await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                logger.info("✅ NEXT button clicked on Class Specific Information")
                await asyncio.sleep(2)
            else:
                logger.warning("⚠️ Could not find NEXT button on Class Specific Information")
            
            # Take screenshot of quote completion page
            screenshot_path = self.login_handler.screenshot_dir / "23_quote_complete.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            logger.info(f"Current URL: {self.page.url}")
            
            # ================================================================
            # QUOTE AUTOMATION COMPLETE
            # ================================================================
            logger.info("\n" + "=" * 80)
            logger.info("✅ QUOTE AUTOMATION COMPLETE - All 10 panels processed")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"❌ Error filling quote details: {e}")
            # Take error screenshot
            screenshot_path = self.login_handler.screenshot_dir / "error_quote_details.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Error screenshot saved: {screenshot_path}")
            raise
    
    async def close(self):
        """Close browser"""
        await self.login_handler.close()


async def main():
    """Main execution"""
    policy_code = "TEBP602893"
    task_id = "default"  # Use "default" to share session across all runs (like Encova)
    
    # Example webhook data (replace with actual webhook values)
    webhook_data = {
        "combined_sales": "800000",  # Inside Sales / Annual Sales / Convenience Store Receipts
        "gas_gallons": "500000",     # Annual Gallons of Gasoline
        "year_built": "2000",        # Year building was built
        "square_footage": "4200",    # Total building square footage
        "mpds": "6"                  # Number of Gas Pumps (MPDs)
    }
    
    quote = GuardQuote(
        policy_code=policy_code, 
        task_id=task_id,
        combined_sales=webhook_data["combined_sales"],
        gas_gallons=webhook_data["gas_gallons"],
        year_built=webhook_data["year_built"],
        square_footage=webhook_data["square_footage"],
        mpds=webhook_data["mpds"]
    )
    
    try:
        # Initialize browser
        await quote.init_browser()
        
        # Login
        if not await quote.login():
            return
        
        # Navigate to quote URL
        if not await quote.navigate_to_quote():
            return
        
        # Fill quote details
        await quote.fill_quote_details()
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
    finally:
        await quote.close()


if __name__ == "__main__":
    asyncio.run(main())
