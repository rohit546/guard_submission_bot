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
                 combined_sales: str = "1000000", 
                 gas_gallons: str = "100000",
                 year_built: str = "2025",
                 square_footage: str = "2000",
                 mpds: str = "6"):
        """
        Initialize Guard Quote automation
        
        Args:
            policy_code: The MGACODE for the quote (e.g., TEBP690442)
            task_id: Unique identifier for this task
            combined_sales: Inside Sales / Annual Sales / Convenience Store Receipts
            gas_gallons: Annual Gallons of Gasoline
            year_built: Year building was built
            square_footage: Total building square footage (used for both total and occupied)
            mpds: Number of Gas Pumps (MPDs)
        """
        self.policy_code = policy_code
        self.quotation_url = f"https://gigezrate.guard.com/dotnet/mvc/uw/EZRate/EZR_AddNewProspectShell/Home/Index?MGACODE={policy_code}"
        self.task_id = task_id
        self.login_handler = GuardLogin(task_id=task_id)
        self.page = None
        
        # Webhook data
        self.combined_sales = combined_sales
        self.gas_gallons = gas_gallons
        self.year_built = year_built
        self.square_footage = square_footage
        self.mpds = mpds
        
        # Hardcoded values (same for every automation)
        self.damage_to_premises = "100000"
        self.employees = "10"
        self.stories = "1"  # Always 1 story
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
        """Fill quote details on the page - loops through all panels"""
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: FILL QUOTE DETAILS")
        logger.info("=" * 80)
        
        max_panels = 15  # Safety limit to prevent infinite loops
        panel_count = 0
        
        while panel_count < max_panels:
            panel_count += 1
            logger.info(f"\n{'='*80}")
            logger.info(f"PROCESSING PANEL {panel_count}")
            logger.info(f"{'='*80}")
            
            try:
                # Wait for page to load
                await self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                await asyncio.sleep(2)  # Give page time to fully render
                logger.info("✅ Page loaded")
                
                # Check if we're on the location page (with "pick me" link or location form)
                pick_me_link = await self.page.query_selector('a[id="pickme_lnk"]')
                location_form = await self.page.query_selector('input[id*="Address"]')
                
                if pick_me_link:
                    logger.info("We're on the Location Addresses page")
                    logger.info("Clicking 'pick me' link for previously used location...")
                    await pick_me_link.click()
                    await self.page.wait_for_load_state("networkidle", timeout=10000)
                    logger.info("✅ 'pick me' link clicked")
                    
                    # Take screenshot after picking location
                    screenshot_path = self.login_handler.screenshot_dir / "02_after_pick_me.png"
                    await self.page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.info(f"Screenshot saved: {screenshot_path}")
                    
                    # Step: Click VERIFY button
                    logger.info("Clicking VERIFY button...")
                    await asyncio.sleep(1)
                    verify_button = await self.page.query_selector('button[id="verify_Btn"]')
                    if verify_button:
                        await verify_button.click()
                        await asyncio.sleep(2)  # Wait for verification
                        logger.info("✅ VERIFY button clicked")
                    else:
                        logger.warning("Could not find VERIFY button")
                    
                    # Step: Click SAVE button
                    logger.info("Clicking SAVE button...")
                    await asyncio.sleep(1)
                    save_button = await self.page.query_selector('button[id="add_button"]')
                    if save_button:
                        await save_button.click()
                        logger.info("✅ SAVE button clicked")
                        
                        # Wait longer for save to complete and button to appear
                        await asyncio.sleep(3)
                        
                        # Take screenshot after save
                        screenshot_path = self.login_handler.screenshot_dir / "03_after_save.png"
                        await self.page.screenshot(path=str(screenshot_path), full_page=True)
                        logger.info(f"Screenshot saved: {screenshot_path}")
                    else:
                        logger.warning("Could not find SAVE button")
                    
                    # Step: Click "I'm done adding locations" button
                    logger.info("Clicking 'I'm done adding locations' button...")
                    await asyncio.sleep(3)  # Increased wait for button to appear
                    
                    # Try to wait for the button to appear
                    try:
                        await self.page.wait_for_selector('button[name="next_btn"]', timeout=15000, state="visible")
                        logger.info("✅ Done button found via wait_for_selector")
                    except Exception as e:
                        logger.warning(f"Timeout waiting for done button: {e}")
                    
                    # Try multiple selectors for the done button
                    done_button = await self.page.query_selector('button[name="next_btn"]')
                    if not done_button:
                        # Try alternative with id
                        done_button = await self.page.query_selector('button[id="next_btn"]')
                    if not done_button:
                        # Try by text content
                        done_button = await self.page.query_selector('button:has-text("done adding")')
                    if not done_button:
                        # Try FSbutton-Next class
                        done_button = await self.page.query_selector('button.FSbutton-Next')
                    
                    if done_button:
                        await done_button.click()
                        logger.info("✅ 'I'm done adding locations' button clicked")
                        
                        # Wait for Liability Limits page to fully load
                        logger.info("Waiting for Liability Limits page to load...")
                        await asyncio.sleep(4)
                        
                        # Wait for the Liability Limits panel to appear by checking for specific fields
                        try:
                            # Wait for annual revenue field to be visible (indicator that page is loaded)
                            await self.page.wait_for_selector('input[id*="annualrevenue"], input[name="bop_annualrevenue"]', timeout=15000, state="visible")
                            logger.info("✅ Liability Limits panel loaded")
                        except:
                            logger.warning("Timeout waiting for Liability Limits panel, continuing anyway...")
                        
                        await asyncio.sleep(2)  # Additional buffer time
                        
                        # Take screenshot of next page
                        screenshot_path = self.login_handler.screenshot_dir / "04_after_done.png"
                        await self.page.screenshot(path=str(screenshot_path), full_page=True)
                        logger.info(f"Screenshot saved: {screenshot_path}")
                        logger.info(f"Current URL: {self.page.url}")
                        
                        # Continue to process Liability Limits and subsequent panels
                        logger.info(f"✅ Completed Location panel - continuing to Liability Limits")
                        # Loop back to top to detect and process Liability Limits panel
                        continue
                    else:
                        logger.error("❌ Could not find 'I'm done adding locations' button with any selector!")
                        # Take screenshot for debugging
                        screenshot_path = self.login_handler.screenshot_dir / "error_no_done_button.png"
                        await self.page.screenshot(path=str(screenshot_path), full_page=True)
                        logger.info(f"Error screenshot saved: {screenshot_path}")
                        # Try to continue anyway
                        continue
                
                else:
                    # Not on Location page - detect which panel we're on
                    
                    # Check if we're on Policy Information page (Panel 1)
                    industry_dropdown = await self.page.query_selector('#ProductID')
                    
                    if industry_dropdown:
                        # === POLICY INFORMATION PAGE ===
                        logger.info("We're on the Policy Information page")
                        
                        # Step 1: Select Industry Type = "Retail BOP"
                        logger.info("Selecting Industry Type: Retail BOP")
                        await self.page.select_option('#ProductID', label="Retail BOP")
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
                        logger.info("Clicking NEXT button...")
                        next_button = await self.page.query_selector('button.FSbutton-Next')
                        if next_button:
                            await next_button.click()
                            await asyncio.sleep(2)
                            await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                            logger.info("✅ NEXT button clicked on Policy Information")
                            
                            # Take screenshot of next page
                            screenshot_path = self.login_handler.screenshot_dir / f"panel_{panel_count + 1}_after_next.png"
                            await self.page.screenshot(path=str(screenshot_path), full_page=True)
                            logger.info(f"Screenshot saved: {screenshot_path}")
                            logger.info(f"Current URL: {self.page.url}")
                            logger.info(f"✅ Completed Policy Information panel - continuing to next panel")
                            continue  # Continue to next panel in the loop
                        else:
                            logger.warning("Could not find NEXT button on Policy Information")
                            continue
                    
                    # === NOT ON POLICY INFO - MUST BE ON PANELS 3-10 ===
                    # Handle Liability Limits, Coverages, Building Info, etc. sequentially
                    
                    logger.info("=" * 80)
                    await asyncio.sleep(1)
                    
                    # Scroll to make sure fields are visible
                    await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    await asyncio.sleep(1)
                    
                    # Fill Total Annual Sales/Rental Receipts
                    logger.info("Filling Total Annual Sales/Rental Receipts...")
                    # Try multiple selectors
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
                    # Try multiple selectors
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
                    # Try multiple selectors
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
                    screenshot_path = self.login_handler.screenshot_dir / "05_liability_filled.png"
                    await self.page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.info(f"Screenshot saved: {screenshot_path}")
                    
                    # Click NEXT button
                    logger.info("Clicking NEXT button...")
                    await asyncio.sleep(1)
                    next_button = await self.page.query_selector('button[name="next_btn"]')
                    if next_button:
                        await next_button.click()
                        await self.page.wait_for_load_state("networkidle", timeout=10000)
                        logger.info("✅ NEXT button clicked (Liability Limits)")
                        
                        # Take screenshot of next page
                        screenshot_path = self.login_handler.screenshot_dir / "06_after_liability.png"
                        await self.page.screenshot(path=str(screenshot_path), full_page=True)
                        logger.info(f"Screenshot saved: {screenshot_path}")
                        logger.info(f"Current URL: {self.page.url}")
                    else:
                        logger.warning("Could not find NEXT button")
                    
                    # --- Policy Level Coverages Panel ---
                    logger.info("\n=== Policy Level Coverages Panel ===")
                    logger.info("Waiting for Policy Level Coverages panel to load...")
                    await asyncio.sleep(3)
                    
                    # Wait for the Damage To Premises input to be visible
                    # Try multiple selectors
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
                        except Exception as e:
                            logger.info(f"Selector {selector} not found, trying next...")
                            continue
                    
                    if not damage_input:
                        logger.warning("⚠️ Could not find Policy Level Coverages panel - might already be filled")
                        # Don't return, continue to next section
                    else:
                        logger.info("✅ Policy Level Coverages panel loaded")
                        await asyncio.sleep(1)
                    
                    # Handle Damage To Premises Rented To You
                    if damage_input:
                        current_value = await damage_input.get_attribute('value')
                        logger.info(f"Current Damage To Premises value: {current_value}")
                        
                        # Set to 100000 for tenant ownership type
                        # If ownership is owner/LRO, leave as is (don't change)
                        # For now, we'll set to 100000 (assuming tenant)
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
                            logger.info("ℹ️ Cyber Suite checkbox already unchecked")
                    else:
                        logger.warning("⚠️ Could not find Cyber Suite checkbox")
                    
                    await asyncio.sleep(1)
                    
                    # Take screenshot before clicking NEXT
                    screenshot_path = self.login_handler.screenshot_dir / "07_policy_coverages_filled.png"
                    await self.page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.info(f"Screenshot saved: {screenshot_path}")
                    
                    # Click NEXT button
                    logger.info("Clicking NEXT button on Policy Level Coverages...")
                    next_button = await self.page.query_selector('button[name="next_btn"]')
                    if next_button:
                        await next_button.click()
                        await self.page.wait_for_load_state("networkidle", timeout=10000)
                        logger.info("✅ NEXT button clicked on Policy Level Coverages")
                        await asyncio.sleep(2)
                        
                        # Take screenshot of next page
                        screenshot_path = self.login_handler.screenshot_dir / "08_additional_insureds.png"
                        await self.page.screenshot(path=str(screenshot_path), full_page=True)
                        logger.info(f"Screenshot saved: {screenshot_path}")
                        logger.info(f"Current URL: {self.page.url}")
                    else:
                        logger.warning("⚠️ Could not find NEXT button on Policy Level Coverages")
                    
                    # --- Additional Insureds Page ---
                    logger.info("\n=== Additional Insureds Page ===")
                    logger.info("No additional insureds needed, clicking NEXT...")
                    await asyncio.sleep(3)
                    
                    # Wait for the NEXT button with multiple selector attempts
                    next_button_selectors = [
                        'button[name="next_btn"]',
                        'button.FSbutton-Next',
                        'button[type="submit"]:has-text("Next")',
                        'input[type="button"][value*="Next"]',
                        'button:has-text("NEXT")'
                    ]
                    
                    next_button = None
                    for selector in next_button_selectors:
                        try:
                            logger.info(f"Trying selector: {selector}")
                            await self.page.wait_for_selector(selector, timeout=5000, state="visible")
                            next_button = await self.page.query_selector(selector)
                            if next_button:
                                logger.info(f"✅ Found NEXT button with selector: {selector}")
                                break
                        except Exception as e:
                            logger.info(f"Selector {selector} not found: {str(e)[:50]}")
                            continue
                    
                    # Click NEXT button on Additional Insureds page
                    if next_button:
                        await next_button.click()
                        await self.page.wait_for_load_state("networkidle", timeout=10000)
                        logger.info("✅ NEXT button clicked on Additional Insureds")
                        await asyncio.sleep(3)
                        
                        # Take screenshot of next page
                        screenshot_path = self.login_handler.screenshot_dir / "09_location_information.png"
                        await self.page.screenshot(path=str(screenshot_path), full_page=True)
                        logger.info(f"Screenshot saved: {screenshot_path}")
                        logger.info(f"Current URL: {self.page.url}")
                    else:
                        logger.warning("⚠️ Could not find NEXT button on Additional Insureds")
                    
                    # --- Location Information Panel ---
                    logger.info("\n=== Location Information Panel ===")
                    logger.info("Waiting for Location Information panel to load...")
                    
                    # Wait for the panel to be fully loaded by checking for any location-specific field
                    try:
                        await self.page.wait_for_selector('input[name*="bplocation"], select[name*="bplocation"]', timeout=10000, state="attached")
                        logger.info("✅ Location Information panel detected")
                        await asyncio.sleep(3)  # Extra time for all fields to render
                    except Exception as e:
                        logger.warning(f"⚠️ Location Information panel may not have loaded: {e}")
                    
                    # Wait for fire hydrant radio button to be visible
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
                    
                    # Select fire station distance dropdown
                    logger.info("Selecting fire station distance...")
                    await asyncio.sleep(1)  # Wait for dropdown to be ready
                    fire_station_selectors = [
                        'select[name*="bplocation_firestation"]',
                        'select[id*="firestation"]',
                        'select[name*="firestation"]'
                    ]
                    
                    fire_station_dropdown = None
                    for selector in fire_station_selectors:
                        try:
                            await self.page.wait_for_selector(selector, timeout=3000, state="visible")
                            fire_station_dropdown = await self.page.query_selector(selector)
                            if fire_station_dropdown:
                                logger.info(f"✅ Found fire station dropdown with selector: {selector}")
                                break
                        except Exception:
                            continue
                    
                    if fire_station_dropdown:
                        # Select option with title value "X" (More than 5 but less than 7 road miles)
                        # Use the selector string, not the element handle
                        fire_station_selector = None
                        for selector in fire_station_selectors:
                            if await self.page.query_selector(selector):
                                fire_station_selector = selector
                                break
                        
                        if fire_station_selector:
                            await self.page.select_option(fire_station_selector, value="X")
                            await asyncio.sleep(0.5)
                            logger.info("✅ Selected fire station distance: More than 5 but less than 7 road miles")
                    else:
                        logger.warning("⚠️ Could not find fire station dropdown")
                    
                    # Wait a bit for any dynamic content to load
                    await asyncio.sleep(1)
                    
                    # Select consecutive years in business dropdown
                    logger.info("Selecting consecutive years in business...")
                    years_selectors = [
                        'select[name="bplocation_yearsinbusiness"]',
                        'select[name*="yearsinbusiness"]',
                        'select[id*="yearsinbusiness"]'
                    ]
                    
                    years_selector = None
                    for selector in years_selectors:
                        try:
                            await self.page.wait_for_selector(selector, timeout=3000, state="visible")
                            if await self.page.query_selector(selector):
                                years_selector = selector
                                logger.info(f"✅ Found consecutive years dropdown with selector: {selector}")
                                break
                        except Exception:
                            continue
                    
                    if years_selector:
                        # Select option with value "0" (New Venture)
                        await self.page.select_option(years_selector, value="0")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected consecutive years: New Venture (0)")
                    else:
                        logger.warning("⚠️ Could not find consecutive years dropdown")
                    
                    # Question 1: Is the location currently open or occupied (select Yes)
                    logger.info("Selecting 'Yes' for location open/occupied question...")
                    open_radio_selectors = [
                        'input[name*="bplocation_currentlyopen"][value="Y"]',
                        'input[id*="currentlyopen"][value="Y"]',
                        'input[name*="currentlyopen"][value="Y"]'
                    ]
                    
                    open_radio = None
                    for selector in open_radio_selectors:
                        try:
                            await self.page.wait_for_selector(selector, timeout=3000, state="visible")
                            open_radio = await self.page.query_selector(selector)
                            if open_radio:
                                logger.info(f"✅ Found open/occupied radio with selector: {selector}")
                                break
                        except Exception:
                            continue
                    
                    if open_radio:
                        await open_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'Yes' for location open/occupied")
                    else:
                        logger.warning("⚠️ Could not find location open/occupied radio button")
                    
                    # Question 2: Hurricane Idalia damage (select No)
                    logger.info("Selecting 'No' for Hurricane Idalia damage...")
                    idalia_radio_selectors = [
                        'input[name*="bplocation_hurricaneidalia"][value="N"]',
                        'input[name*="idalia"][value="N"]',
                        'input[id*="hurricaneidalia"][value="N"]'
                    ]
                    
                    idalia_radio = None
                    for selector in idalia_radio_selectors:
                        try:
                            await self.page.wait_for_selector(selector, timeout=3000, state="visible")
                            idalia_radio = await self.page.query_selector(selector)
                            if idalia_radio:
                                logger.info(f"✅ Found Hurricane Idalia radio with selector: {selector}")
                                break
                        except Exception:
                            continue
                    
                    if idalia_radio:
                        await idalia_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'No' for Hurricane Idalia damage")
                    else:
                        logger.warning("⚠️ Could not find Hurricane Idalia radio button")
                    
                    # Question 3: Hurricane DEBBY damage (select No)
                    logger.info("Selecting 'No' for Hurricane DEBBY damage...")
                    debby_radio_selectors = [
                        'input[name*="bplocation_hurricanedebby"][value="N"]',
                        'input[name*="debby"][value="N"]',
                        'input[id*="hurricanedebby"][value="N"]'
                    ]
                    
                    debby_radio = None
                    for selector in debby_radio_selectors:
                        try:
                            await self.page.wait_for_selector(selector, timeout=3000, state="visible")
                            debby_radio = await self.page.query_selector(selector)
                            if debby_radio:
                                logger.info(f"✅ Found Hurricane DEBBY radio with selector: {selector}")
                                break
                        except Exception:
                            continue
                    
                    if debby_radio:
                        await debby_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'No' for Hurricane DEBBY damage")
                    else:
                        logger.warning("⚠️ Could not find Hurricane DEBBY radio button")
                    
                    await asyncio.sleep(1)
                    
                    # Take screenshot before clicking NEXT
                    screenshot_path = self.login_handler.screenshot_dir / "10_location_info_filled.png"
                    await self.page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.info(f"Screenshot saved: {screenshot_path}")
                    
                    # Click NEXT button
                    logger.info("Clicking NEXT button on Location Information...")
                    try:
                        await self.page.wait_for_selector('button[name="next_btn"]', timeout=5000, state="visible")
                    except Exception:
                        logger.warning("⚠️ NEXT button not immediately visible, checking again...")
                    
                    next_button = await self.page.query_selector('button[name="next_btn"]')
                    if next_button:
                        await next_button.click()
                        await self.page.wait_for_load_state("networkidle", timeout=10000)
                        logger.info("✅ NEXT button clicked on Location Information")
                        await asyncio.sleep(2)
                        
                        # Take screenshot of next page
                        screenshot_path = self.login_handler.screenshot_dir / "11_windstorm_hail.png"
                        await self.page.screenshot(path=str(screenshot_path), full_page=True)
                        logger.info(f"Screenshot saved: {screenshot_path}")
                        logger.info(f"Current URL: {self.page.url}")
                    else:
                        logger.warning("⚠️ Could not find NEXT button on Location Information")
                    
                    # --- Windstorm/Hail Panel ---
                    logger.info("\n=== Windstorm/Hail Panel ===")
                    logger.info("Waiting for Windstorm/Hail panel to load...")
                    await asyncio.sleep(2)
                    
                    # Question 1: Did the insured purchase a separate policy for windstorm/hail (select No = 0)
                    logger.info("Selecting 'No' for separate windstorm/hail policy...")
                    separate_policy_selectors = [
                        'input[name="bplocationdeductibles_separatewindpolicy"][value="0"]',
                        'input[id="bplocationdeductibles_separatewindpolicy_radio_0"]',
                        'input[name="bplocationdeductibles_separatewindpolicy_radio"][value="0"]'
                    ]
                    
                    separate_policy_radio = None
                    for selector in separate_policy_selectors:
                        separate_policy_radio = await self.page.query_selector(selector)
                        if separate_policy_radio:
                            logger.info(f"✅ Found separate policy radio with selector: {selector}")
                            break
                    
                    if separate_policy_radio:
                        await separate_policy_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'No' for separate windstorm/hail policy")
                    else:
                        logger.warning("⚠️ Could not find separate policy radio button")
                    
                    # Question 2: Does insured want to exclude wind/hail coverage (select No = 0)
                    logger.info("Selecting 'No' for excluding wind/hail coverage...")
                    exclude_coverage_selectors = [
                        'input[name="bplocationdeductibles_windhail_excl"][value="0"]',
                        'input[id="bplocationdeductibles_windhail_excl_radio_0"]',
                        'input[name="bplocationdeductibles_windhail_excl_radio"][value="0"]'
                    ]
                    
                    exclude_coverage_radio = None
                    for selector in exclude_coverage_selectors:
                        exclude_coverage_radio = await self.page.query_selector(selector)
                        if exclude_coverage_radio:
                            logger.info(f"✅ Found exclude coverage radio with selector: {selector}")
                            break
                    
                    if exclude_coverage_radio:
                        await exclude_coverage_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'No' for excluding wind/hail coverage")
                    else:
                        logger.warning("⚠️ Could not find exclude coverage radio button")
                    
                    await asyncio.sleep(1)
                    
                    # Take screenshot before clicking NEXT
                    screenshot_path = self.login_handler.screenshot_dir / "12_windstorm_filled.png"
                    await self.page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.info(f"Screenshot saved: {screenshot_path}")
                    
                    # Click NEXT button
                    logger.info("Clicking NEXT button on Windstorm/Hail...")
                    next_button = await self.page.query_selector('button[name="next_btn"]')
                    if next_button:
                        await next_button.click()
                        await self.page.wait_for_load_state("networkidle", timeout=10000)
                        logger.info("✅ NEXT button clicked on Windstorm/Hail")
                        await asyncio.sleep(2)
                        
                        # Take screenshot of next page
                        screenshot_path = self.login_handler.screenshot_dir / "13_building_information.png"
                        await self.page.screenshot(path=str(screenshot_path), full_page=True)
                        logger.info(f"Screenshot saved: {screenshot_path}")
                        logger.info(f"Current URL: {self.page.url}")
                    else:
                        logger.warning("⚠️ Could not find NEXT button on Windstorm/Hail")
                    
                    # --- Building Information Page ---
                    logger.info("\n=== Building Information Page ===")
                    logger.info("Waiting for Building Information page to load...")
                    await asyncio.sleep(2)
                    
                    # Field 1: Occupancy dropdown (TE = Tenant, OM = Owner)
                    # For this example, we'll select "OM" (Owner Occupied Bldg - More than 10%)
                    logger.info("Selecting Occupancy type...")
                    occupancy_selectors = [
                        'select[name="OccupancyType"]',
                        'select[id="Occupancy"]',
                        'select#Occupancy'
                    ]
                    
                    occupancy_dropdown = None
                    for selector in occupancy_selectors:
                        occupancy_dropdown = await self.page.query_selector(selector)
                        if occupancy_dropdown:
                            logger.info(f"✅ Found occupancy dropdown with selector: {selector}")
                            break
                    
                    if occupancy_dropdown:
                        # Select "OM" (Owner Occupied) - you can change this based on business logic
                        # TE = Tenant, OM = Owner Occupied Bldg - More than 10%
                        # Use the same selector that found it
                        occupancy_selector = None
                        for selector in occupancy_selectors:
                            test = await self.page.query_selector(selector)
                            if test:
                                occupancy_selector = selector
                                break
                        
                        if occupancy_selector:
                            await self.page.select_option(occupancy_selector, value="OM")
                            await asyncio.sleep(0.5)
                            logger.info("✅ Selected Occupancy: Owner Occupied (OM)")
                        else:
                            logger.warning("⚠️ Could not determine occupancy selector")
                    else:
                        logger.warning("⚠️ Could not find occupancy dropdown")
                    
                    # Field 2: Building Type - Select "Stand Alone Building" radio button
                    logger.info("Selecting Building Type: Stand Alone Building...")
                    building_type_selectors = [
                        'input[name="OccupancyType_radio"][id="OccupancyType_radio_STANDALONE"]',
                        'input[value="STANDALONE"][type="radio"]',
                        'input[id="OccupancyType_radio_STANDALONE"]'
                    ]
                    
                    building_type_radio = None
                    for selector in building_type_selectors:
                        building_type_radio = await self.page.query_selector(selector)
                        if building_type_radio:
                            logger.info(f"✅ Found Stand Alone Building radio with selector: {selector}")
                            break
                    
                    if building_type_radio:
                        await building_type_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected Building Type: Stand Alone Building")
                    else:
                        logger.warning("⚠️ Could not find Stand Alone Building radio button")
                    
                    await asyncio.sleep(1)
                    
                    # Field 3: Sole Occupant of the Building - Select "Yes" (value="SOLE")
                    logger.info("Selecting Sole Occupant: Yes...")
                    sole_occupant_selectors = [
                        'input[name="SoleOccupant"][value="SOLE"]',
                        'input[id="SoleOccupant"][value="SOLE"]',
                        'input[id="SoleOccupant_radio_SOLE"]'
                    ]
                    
                    sole_occupant_radio = None
                    for selector in sole_occupant_selectors:
                        sole_occupant_radio = await self.page.query_selector(selector)
                        if sole_occupant_radio:
                            logger.info(f"✅ Found Sole Occupant radio with selector: {selector}")
                            break
                    
                    if sole_occupant_radio:
                        await sole_occupant_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected Sole Occupant: Yes")
                    else:
                        logger.warning("⚠️ Could not find Sole Occupant radio button")
                    
                    # Field 4: Building Industry dropdown - Select "CONVEN" (Convenience Stores & Gas Stations)
                    logger.info("Selecting Building Industry: Convenience Stores & Gas Stations...")
                    industry_selectors = [
                        'select[name="EZRate_Industry"]',
                        'select[id="EZRate_Industry"]'
                    ]
                    
                    industry_dropdown = None
                    industry_selector_found = None
                    for selector in industry_selectors:
                        industry_dropdown = await self.page.query_selector(selector)
                        if industry_dropdown:
                            industry_selector_found = selector
                            logger.info(f"✅ Found Building Industry dropdown with selector: {selector}")
                            break
                    
                    if industry_dropdown and industry_selector_found:
                        await self.page.select_option(industry_selector_found, value="CONVEN")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected Building Industry: CONVEN (Convenience Stores & Gas Stations)")
                        
                        # CRITICAL: Wait 3 seconds for other dropdowns to load after industry selection
                        logger.info("⏳ Waiting 3 seconds for Class Code and Construction dropdowns to load...")
                        await asyncio.sleep(3)
                    else:
                        logger.warning("⚠️ Could not find Building Industry dropdown")
                    
                    # Field 5: Class Code dropdown - Select "0932101"
                    logger.info("Selecting Class Code: 0932101...")
                    classcode_selectors = [
                        'select[name="ClassCode"]',
                        'select[id="ClassCode"]'
                    ]
                    
                    classcode_dropdown = None
                    classcode_selector_found = None
                    for selector in classcode_selectors:
                        classcode_dropdown = await self.page.query_selector(selector)
                        if classcode_dropdown:
                            classcode_selector_found = selector
                            logger.info(f"✅ Found Class Code dropdown with selector: {selector}")
                            break
                    
                    if classcode_dropdown and classcode_selector_found:
                        await self.page.select_option(classcode_selector_found, value="0932101")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected Class Code: 0932101")
                    else:
                        logger.warning("⚠️ Could not find Class Code dropdown")
                    
                    # Field 6: Construction dropdown - Select "FR" (Frame)
                    logger.info("Selecting Construction: Frame...")
                    construction_selectors = [
                        'select[name="Construction"]',
                        'select[id="Construction"]'
                    ]
                    
                    construction_dropdown = None
                    construction_selector_found = None
                    for selector in construction_selectors:
                        construction_dropdown = await self.page.query_selector(selector)
                        if construction_dropdown:
                            construction_selector_found = selector
                            logger.info(f"✅ Found Construction dropdown with selector: {selector}")
                            break
                    
                    if construction_dropdown and construction_selector_found:
                        await self.page.select_option(construction_selector_found, value="FM")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected Construction: FM (Masonry)")
                    else:
                        logger.warning("⚠️ Could not find Construction dropdown")
                    
                    await asyncio.sleep(1)
                    
                    # Field 7: Annual Sales/Rental Receipts at this Building
                    logger.info("Filling Annual Sales/Rental Receipts at this Building...")
                    grosssales_selectors = [
                        'input[name="GrossSales"]',
                        'input[id="GrossSales"]',
                        'input[id="Grosssales"]'
                    ]
                    
                    grosssales_input = None
                    for selector in grosssales_selectors:
                        grosssales_input = await self.page.query_selector(selector)
                        if grosssales_input:
                            logger.info(f"✅ Found Annual Sales input with selector: {selector}")
                            break
                    
                    if grosssales_input:
                        await grosssales_input.click()
                        await grosssales_input.fill("")
                        await grosssales_input.type("100000")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Annual Sales/Rental Receipts: 100,000")
                    else:
                        logger.warning("⚠️ Could not find Annual Sales input")
                    
                    # Field 8: Annual Gallons of Gasoline Sold at this Building
                    logger.info("Filling Annual Gallons of Gasoline...")
                    gasoline_selectors = [
                        'input[name="gallonsOfGasoline"]',
                        'input[id="gallonsOfGasoline"]'
                    ]
                    
                    gasoline_input = None
                    for selector in gasoline_selectors:
                        gasoline_input = await self.page.query_selector(selector)
                        if gasoline_input:
                            logger.info(f"✅ Found Gasoline input with selector: {selector}")
                            break
                    
                    if gasoline_input:
                        await gasoline_input.click()
                        await gasoline_input.fill("")
                        await gasoline_input.type("100000")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Annual Gallons of Gasoline: 100,000")
                    else:
                        logger.warning("⚠️ Could not find Gasoline input")
                    
                    # Field 9: Liquor On-Premises radio button - Select "No"
                    logger.info("Selecting 'No' for liquor consumed on-premises...")
                    liquor_selectors = [
                        'input[name="LiquorOnPremises"][value="N"]',
                        'input[id="LiquorOnPremises_radio_N"]',
                        'input[name="LiquorOnPremises_radio"][value="N"]'
                    ]
                    
                    liquor_radio = None
                    for selector in liquor_selectors:
                        liquor_radio = await self.page.query_selector(selector)
                        if liquor_radio:
                            logger.info(f"✅ Found Liquor On-Premises radio with selector: {selector}")
                            break
                    
                    if liquor_radio:
                        await liquor_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'No' for liquor consumed on-premises")
                    else:
                        logger.warning("⚠️ Could not find Liquor On-Premises radio button")
                    
                    await asyncio.sleep(1)
                    
                    # Field 10: Original Year Built
                    logger.info("Filling Original Year Built...")
                    yearbuilt_selectors = [
                        'input[name="YearBuilt"]',
                        'input[id="YearBuilt"]'
                    ]
                    
                    yearbuilt_input = None
                    for selector in yearbuilt_selectors:
                        yearbuilt_input = await self.page.query_selector(selector)
                        if yearbuilt_input:
                            logger.info(f"✅ Found Year Built input with selector: {selector}")
                            break
                    
                    if yearbuilt_input:
                        await yearbuilt_input.click()
                        await yearbuilt_input.fill("")
                        await yearbuilt_input.type("2025")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Original Year Built: 2025")
                    else:
                        logger.warning("⚠️ Could not find Year Built input")
                    
                    # Field 11: Number of Stories
                    logger.info("Filling Number of Stories...")
                    stories_selectors = [
                        'input[name="Stories"]',
                        'input[id="Stories"]'
                    ]
                    
                    stories_input = None
                    for selector in stories_selectors:
                        stories_input = await self.page.query_selector(selector)
                        if stories_input:
                            logger.info(f"✅ Found Stories input with selector: {selector}")
                            break
                    
                    if stories_input:
                        await stories_input.click()
                        await stories_input.fill("")
                        await stories_input.type("10")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Number of Stories: 10")
                    else:
                        logger.warning("⚠️ Could not find Stories input")
                    
                    # Field 12: Roof Surfacing Type dropdown
                    logger.info("Selecting Roof Surfacing Type: Unknown...")
                    rooftype_selectors = [
                        'select[name="ROOFTYPE"]',
                        'select[id="ROOFTYPE"]'
                    ]
                    
                    rooftype_dropdown = None
                    rooftype_selector_found = None
                    for selector in rooftype_selectors:
                        rooftype_dropdown = await self.page.query_selector(selector)
                        if rooftype_dropdown:
                            rooftype_selector_found = selector
                            logger.info(f"✅ Found Roof Type dropdown with selector: {selector}")
                            break
                    
                    if rooftype_dropdown and rooftype_selector_found:
                        await self.page.select_option(rooftype_selector_found, value="UNKNOWN")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected Roof Surfacing Type: UNKNOWN")
                    else:
                        logger.warning("⚠️ Could not find Roof Type dropdown")
                    
                    # Field 13: Total Building Square Footage
                    logger.info("Filling Total Building Square Footage...")
                    sqfootage_selectors = [
                        'input[name="SquareFootage"]',
                        'input[id="SquareFootage"]'
                    ]
                    
                    sqfootage_input = None
                    for selector in sqfootage_selectors:
                        sqfootage_input = await self.page.query_selector(selector)
                        if sqfootage_input:
                            logger.info(f"✅ Found Square Footage input with selector: {selector}")
                            break
                    
                    if sqfootage_input:
                        await sqfootage_input.click()
                        await sqfootage_input.fill("")
                        await sqfootage_input.type("2000")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Total Building Square Footage: 2000")
                    else:
                        logger.warning("⚠️ Could not find Square Footage input")
                    
                    # Field 14: Total Square Footage Occupied by the Insured
                    logger.info("Filling Total Square Footage Occupied by Insured...")
                    sqftocc_selectors = [
                        'input[name="SQFTOCC"]',
                        'input[id="SQFTOCC"]'
                    ]
                    
                    sqftocc_input = None
                    for selector in sqftocc_selectors:
                        sqftocc_input = await self.page.query_selector(selector)
                        if sqftocc_input:
                            logger.info(f"✅ Found SQFTOCC input with selector: {selector}")
                            break
                    
                    if sqftocc_input:
                        await sqftocc_input.click()
                        await sqftocc_input.fill("")
                        await sqftocc_input.type("2000")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Total Square Footage Occupied: 2000")
                    else:
                        logger.warning("⚠️ Could not find SQFTOCC input")
                    
                    await asyncio.sleep(1)
                    
                    # Field 14.5: Gas pumps available 24 hours - Select "No"
                    logger.info("Selecting 'No' for gas pumps available 24 hours...")
                    gaspumps_selectors = [
                        'input[name="gasPumps24Hours"][value="False"]',
                        'input[id="gasPumps24Hours_radio_False"]',
                        'input[name="gasPumps24Hours_radio"][value="False"]'
                    ]
                    
                    gaspumps_radio = None
                    for selector in gaspumps_selectors:
                        gaspumps_radio = await self.page.query_selector(selector)
                        if gaspumps_radio:
                            logger.info(f"✅ Found gas pumps 24 hours radio with selector: {selector}")
                            break
                    
                    if gaspumps_radio:
                        await gaspumps_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'No' for gas pumps available 24 hours")
                    else:
                        logger.warning("⚠️ Could not find gas pumps 24 hours radio button")
                    
                    await asyncio.sleep(1)
                    
                    # Field 15: Number of Residential Units
                    logger.info("Filling Number of Residential Units...")
                    residential_selectors = [
                        'input[name="ResidentialUnits"]',
                        'input[id="ResidentialUnits"]'
                    ]
                    
                    residential_input = None
                    for selector in residential_selectors:
                        residential_input = await self.page.query_selector(selector)
                        if residential_input:
                            logger.info(f"✅ Found Residential Units input with selector: {selector}")
                            break
                    
                    if residential_input:
                        await residential_input.click()
                        await residential_input.fill("")
                        await residential_input.type(self.residential_units)
                        await asyncio.sleep(0.5)
                        logger.info(f"✅ Number of Residential Units: {self.residential_units}")
                    else:
                        logger.warning("⚠️ Could not find Residential Units input")
                    
                    # Field 16: Automatic Sprinkler System dropdown - Select "No"
                    logger.info("Selecting Automatic Sprinkler System: No...")
                    sprinkler_selectors = [
                        'select[name="Sprinklered"]',
                        'select[id="Sprinklered"]'
                    ]
                    
                    sprinkler_dropdown = None
                    sprinkler_selector_found = None
                    for selector in sprinkler_selectors:
                        sprinkler_dropdown = await self.page.query_selector(selector)
                        if sprinkler_dropdown:
                            sprinkler_selector_found = selector
                            logger.info(f"✅ Found Sprinkler dropdown with selector: {selector}")
                            break
                    
                    if sprinkler_dropdown and sprinkler_selector_found:
                        await self.page.select_option(sprinkler_selector_found, value="N")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected Sprinkler System: N (No)")
                    else:
                        logger.warning("⚠️ Could not find Sprinkler dropdown")
                    
                    # Field 17: Automatic Fire Alarm dropdown - Select "Central Station"
                    logger.info("Selecting Automatic Fire Alarm: Central Station...")
                    firealarm_selectors = [
                        'select[name="FireAlarm"]',
                        'select[id="FireAlarm"]'
                    ]
                    
                    firealarm_dropdown = None
                    firealarm_selector_found = None
                    for selector in firealarm_selectors:
                        firealarm_dropdown = await self.page.query_selector(selector)
                        if firealarm_dropdown:
                            firealarm_selector_found = selector
                            logger.info(f"✅ Found Fire Alarm dropdown with selector: {selector}")
                            break
                    
                    if firealarm_dropdown and firealarm_selector_found:
                        await self.page.select_option(firealarm_selector_found, value="Central Station")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected Fire Alarm: Central Station")
                    else:
                        logger.warning("⚠️ Could not find Fire Alarm dropdown")
                    
                    # Field 18: Automatic Commercial Cooking Extinguishing System dropdown - Select "NA"
                    logger.info("Selecting Ansul System: N/A...")
                    ansul_selectors = [
                        'select[name="AnsulSystem"]',
                        'select[id="AnsulSystem"]'
                    ]
                    
                    ansul_dropdown = None
                    ansul_selector_found = None
                    for selector in ansul_selectors:
                        ansul_dropdown = await self.page.query_selector(selector)
                        if ansul_dropdown:
                            ansul_selector_found = selector
                            logger.info(f"✅ Found Ansul System dropdown with selector: {selector}")
                            break
                    
                    if ansul_dropdown and ansul_selector_found:
                        await self.page.select_option(ansul_selector_found, value="NA")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected Ansul System: NA (N/A)")
                    else:
                        logger.warning("⚠️ Could not find Ansul System dropdown")
                    
                    # Field 19: Automatic Burglar Alarm dropdown - Select "Central Station"
                    logger.info("Selecting Burglar Alarm: Central Station...")
                    burglar_selectors = [
                        'select[name="BurglarAlarm"]',
                        'select[id="BurglarAlarm"]'
                    ]
                    
                    burglar_dropdown = None
                    burglar_selector_found = None
                    for selector in burglar_selectors:
                        burglar_dropdown = await self.page.query_selector(selector)
                        if burglar_dropdown:
                            burglar_selector_found = selector
                            logger.info(f"✅ Found Burglar Alarm dropdown with selector: {selector}")
                            break
                    
                    if burglar_dropdown and burglar_selector_found:
                        await self.page.select_option(burglar_selector_found, value="Central Station")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected Burglar Alarm: Central Station")
                    else:
                        logger.warning("⚠️ Could not find Burglar Alarm dropdown")
                    
                    # Field 20: Security Cameras dropdown - Select "No"
                    logger.info("Selecting Security Cameras: No...")
                    cameras_selectors = [
                        'select[name="SecurityCameras"]',
                        'select[id="SecurityCameras"]'
                    ]
                    
                    cameras_dropdown = None
                    cameras_selector_found = None
                    for selector in cameras_selectors:
                        cameras_dropdown = await self.page.query_selector(selector)
                        if cameras_dropdown:
                            cameras_selector_found = selector
                            logger.info(f"✅ Found Security Cameras dropdown with selector: {selector}")
                            break
                    
                    if cameras_dropdown and cameras_selector_found:
                        await self.page.select_option(cameras_selector_found, value="N")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected Security Cameras: N (No)")
                    else:
                        logger.warning("⚠️ Could not find Security Cameras dropdown")
                    
                    await asyncio.sleep(1)
                    
                    # Take screenshot of filled building info
                    screenshot_path = self.login_handler.screenshot_dir / "14_building_info_filled.png"
                    await self.page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.info(f"Screenshot saved: {screenshot_path}")
                    
                    # Click NEXT button
                    logger.info("Clicking NEXT button on Building Information...")
                    next_button = await self.page.query_selector('button[name="next_btn"]')
                    if next_button:
                        await next_button.click()
                        await self.page.wait_for_load_state("networkidle", timeout=10000)
                        logger.info("✅ NEXT button clicked on Building Information")
                        await asyncio.sleep(2)
                        
                        # Take screenshot of next page
                        screenshot_path = self.login_handler.screenshot_dir / "15_next_page.png"
                        await self.page.screenshot(path=str(screenshot_path), full_page=True)
                        logger.info(f"Screenshot saved: {screenshot_path}")
                        logger.info(f"Current URL: {self.page.url}")
                    else:
                        logger.warning("⚠️ Could not find NEXT button on Building Information")
                    
                    # --- State Specific Information Panel ---
                    logger.info("\n=== State Specific Information Panel ===")
                    logger.info("Waiting for State Specific Information panel to load...")
                    await asyncio.sleep(2)
                    
                    # Take screenshot of the page
                    screenshot_path = self.login_handler.screenshot_dir / "16_state_specific_info.png"
                    await self.page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.info(f"Screenshot saved: {screenshot_path}")
                    
                    # State Specific has no fields to fill - just click NEXT
                    logger.info("Clicking NEXT button on State Specific Information...")
                    next_selectors = [
                        'button[name="next_btn"]',
                        'button.FSbutton-Next',
                        'button:has-text("NEXT")',
                        'input[type="button"][value="NEXT"]'
                    ]
                    
                    next_button = None
                    for selector in next_selectors:
                        try:
                            next_button = await self.page.query_selector(selector)
                            if next_button:
                                logger.info(f"✅ Found NEXT button with selector: {selector}")
                                break
                        except Exception as e:
                            logger.debug(f"Selector {selector} failed: {e}")
                            continue
                    
                    if next_button:
                        await next_button.click()
                        await self.page.wait_for_load_state("networkidle", timeout=10000)
                        logger.info("✅ NEXT button clicked on State Specific Information")
                        await asyncio.sleep(3)  # Wait for Class Specific panel to load
                        
                        # Take screenshot after clicking NEXT
                        screenshot_path = self.login_handler.screenshot_dir / "17_after_state_next.png"
                        await self.page.screenshot(path=str(screenshot_path), full_page=True)
                        logger.info(f"Screenshot saved: {screenshot_path}")
                        logger.info(f"Current URL: {self.page.url}")
                    else:
                        logger.warning("⚠️ Could not find NEXT button on State Specific Information")
                    
                    # --- Class Specific Information Panel ---
                    logger.info("\n=== Class Specific Information Panel ===")
                    logger.info("Waiting for Class Specific Information panel to load...")
                    
                    # Wait for Class Specific panel to appear and detect it
                    await asyncio.sleep(2)
                    
                    # Try to detect if we're on the Class Specific panel by looking for its unique fields
                    try:
                        await self.page.wait_for_selector(
                            'input[name="conveniencestore_bld_cvg_radio"], input[name="conveniencestore_vacancy"], input[name="conveniencestore_gaspumps"]',
                            state="visible",
                            timeout=15000
                        )
                        logger.info("✅ Class Specific Information panel detected and loaded")
                    except Exception as e:
                        logger.warning(f"⚠️ Timeout waiting for Class Specific panel fields: {e}")
                        # Take screenshot to debug
                        screenshot_path = self.login_handler.screenshot_dir / "17_class_specific_not_found.png"
                        await self.page.screenshot(path=str(screenshot_path), full_page=True)
                        logger.info(f"Debug screenshot saved: {screenshot_path}")
                        
                        # Maybe we need to click NEXT again?
                        next_button = await self.page.query_selector('button[name="next_btn"]')
                        if next_button:
                            logger.info("Found another NEXT button, clicking it...")
                            await next_button.click()
                            await self.page.wait_for_load_state("networkidle", timeout=10000)
                            await asyncio.sleep(3)
                            
                            # Try to detect fields again
                            try:
                                await self.page.wait_for_selector(
                                    'input[name="conveniencestore_bld_cvg_radio"], input[name="conveniencestore_vacancy"], input[name="conveniencestore_gaspumps"]',
                                    state="visible",
                                    timeout=10000
                                )
                                logger.info("✅ Class Specific Information panel now loaded")
                            except:
                                logger.error("❌ Still cannot find Class Specific fields after clicking NEXT")
                    
                    await asyncio.sleep(1)
                    
                    # Take screenshot of Class Specific panel
                    screenshot_path = self.login_handler.screenshot_dir / "18_class_specific_panel.png"
                    await self.page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.info(f"Screenshot saved: {screenshot_path}")
                    
                    # Field 1: Is Building coverage needed for this property? (Tenant = No, Owner = Yes)
                    # Since the data shows "3 Years under this Location - Tenant", we select No
                    logger.info("Selecting 'No' for Building coverage needed (Tenant)...")
                    building_coverage_selectors = [
                        'input[name="conveniencestore_bld_cvg_radio"][value="N"]',
                        'input[id="conveniencestore_bld_cvg_radio_N"]'
                    ]
                    
                    building_coverage_radio = None
                    for selector in building_coverage_selectors:
                        building_coverage_radio = await self.page.query_selector(selector)
                        if building_coverage_radio:
                            logger.info(f"✅ Found Building coverage radio with selector: {selector}")
                            break
                    
                    if building_coverage_radio:
                        await building_coverage_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'No' for Building coverage (Tenant)")
                    else:
                        logger.warning("⚠️ Could not find Building coverage radio button")
                    
                    # Field 2: What percentage of the building is vacant? (Always 0)
                    logger.info("Filling building vacancy percentage...")
                    vacancy_selectors = [
                        'input[name="conveniencestore_vacancy"]',
                        'input[id="conveniencestore_vacancy"]'
                    ]
                    
                    vacancy_input = None
                    for selector in vacancy_selectors:
                        vacancy_input = await self.page.query_selector(selector)
                        if vacancy_input:
                            logger.info(f"✅ Found vacancy input with selector: {selector}")
                            break
                    
                    if vacancy_input:
                        await vacancy_input.click()
                        await vacancy_input.fill("")
                        await vacancy_input.type(self.vacancy_percent)
                        await asyncio.sleep(0.5)
                        logger.info(f"✅ Building vacancy percentage: {self.vacancy_percent}")
                    else:
                        logger.warning("⚠️ Could not find vacancy input")
                    
                    # Field 3: Is the building currently undergoing any renovations? (No)
                    logger.info("Selecting 'No' for renovations/construction...")
                    renovation_selectors = [
                        'input[name="conveniencestore_bld_cvg_2_radio"][value="N"]',
                        'input[id="conveniencestore_bld_cvg_2_radio_N"]'
                    ]
                    
                    renovation_radio = None
                    for selector in renovation_selectors:
                        renovation_radio = await self.page.query_selector(selector)
                        if renovation_radio:
                            logger.info(f"✅ Found renovation radio with selector: {selector}")
                            break
                    
                    if renovation_radio:
                        await renovation_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'No' for renovations/construction")
                    else:
                        logger.warning("⚠️ Could not find renovation radio button")
                    
                    # Field 4: Number of Gas Pumps (6 for now)
                    logger.info("Filling Number of Gas Pumps...")
                    gaspumps_selectors = [
                        'input[name="conveniencestore_gaspumps"]',
                        'input[id="conveniencestore_gaspumps"]'
                    ]
                    
                    gaspumps_input = None
                    for selector in gaspumps_selectors:
                        gaspumps_input = await self.page.query_selector(selector)
                        if gaspumps_input:
                            logger.info(f"✅ Found gas pumps input with selector: {selector}")
                            break
                    
                    if gaspumps_input:
                        await gaspumps_input.click()
                        await gaspumps_input.fill("")
                        await gaspumps_input.type(self.mpds)
                        await asyncio.sleep(0.5)
                        logger.info(f"✅ Number of Gas Pumps: {self.mpds}")
                    else:
                        logger.warning("⚠️ Could not find gas pumps input")
                    
                    # Field 5: What is the percentage of gas sales to total annual sales? (40%)
                    logger.info("Filling gas sales percentage...")
                    gassales_selectors = [
                        'input[name="conveniencestore_gassales"]',
                        'input[id="conveniencestore_gassales"]'
                    ]
                    
                    gassales_input = None
                    for selector in gassales_selectors:
                        gassales_input = await self.page.query_selector(selector)
                        if gassales_input:
                            logger.info(f"✅ Found gas sales percentage input with selector: {selector}")
                            break
                    
                    if gassales_input:
                        await gassales_input.click()
                        await gassales_input.fill("")
                        await gassales_input.type(self.gas_sales_percent)
                        await asyncio.sleep(0.5)
                        logger.info(f"✅ Gas sales percentage: {self.gas_sales_percent}%")
                    else:
                        logger.warning("⚠️ Could not find gas sales percentage input")
                    
                    # Field 6: What are the annual receipts from the sale of convenience store items? (Inside Sales)
                    logger.info("Filling convenience store annual receipts (Inside Sales)...")
                    receipts_selectors = [
                        'input[name="conveniencestore_gaspumps_2"]',
                        'input[id="conveniencestore_gaspumps_2"]'
                    ]
                    
                    receipts_input = None
                    for selector in receipts_selectors:
                        receipts_input = await self.page.query_selector(selector)
                        if receipts_input:
                            logger.info(f"✅ Found convenience store receipts input with selector: {selector}")
                            break
                    
                    if receipts_input:
                        await receipts_input.click()
                        await receipts_input.fill("")
                        await receipts_input.type(self.combined_sales)
                        await asyncio.sleep(0.5)
                        logger.info(f"✅ Convenience store annual receipts: ${self.combined_sales}")
                    else:
                        logger.warning("⚠️ Could not find convenience store receipts input")
                    
                    # Field 7: Is there propane tank filling at this location? (No)
                    logger.info("Selecting 'No' for propane tank filling...")
                    propane_selectors = [
                        'input[name="conveniencestore_propane_radio_N"][value="N"]',
                        'input[id="conveniencestore_propane_radio_N"]'
                    ]
                    
                    propane_radio = None
                    for selector in propane_selectors:
                        propane_radio = await self.page.query_selector(selector)
                        if propane_radio:
                            logger.info(f"✅ Found propane radio with selector: {selector}")
                            break
                    
                    if propane_radio:
                        await propane_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'No' for propane tank filling")
                    else:
                        logger.warning("⚠️ Could not find propane radio button")
                    
                    # Field 8: Does the prospect sell cannabis/synthetic cannabinoids products? (No)
                    logger.info("Selecting 'No' for cannabis products...")
                    cannabis_selectors = [
                        'input[name="conveniencestore_cannabis_radio_N"][value="N"]',
                        'input[id="conveniencestore_cannabis_radio_N"]'
                    ]
                    
                    cannabis_radio = None
                    for selector in cannabis_selectors:
                        cannabis_radio = await self.page.query_selector(selector)
                        if cannabis_radio:
                            logger.info(f"✅ Found cannabis radio with selector: {selector}")
                            break
                    
                    if cannabis_radio:
                        await cannabis_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'No' for cannabis products")
                    else:
                        logger.warning("⚠️ Could not find cannabis radio button")
                    
                    # Field 9: What percentage of total receipts come from products containing CBD? (0%)
                    logger.info("Filling CBD products percentage...")
                    cbd_selectors = [
                        'input[name="conveniencestore_cbd_products"]',
                        'input[id="conveniencestore_cbd_products"]'
                    ]
                    
                    cbd_input = None
                    for selector in cbd_selectors:
                        cbd_input = await self.page.query_selector(selector)
                        if cbd_input:
                            logger.info(f"✅ Found CBD percentage input with selector: {selector}")
                            break
                    
                    if cbd_input:
                        await cbd_input.click()
                        await cbd_input.fill("")
                        await cbd_input.type(self.cbd_percent)
                        await asyncio.sleep(0.5)
                        logger.info(f"✅ CBD products percentage: {self.cbd_percent}%")
                    else:
                        logger.warning("⚠️ Could not find CBD percentage input")
                    
                    # Field 10: Which best describes the applicants primary products for sale? (Option 1)
                    logger.info("Selecting primary products for sale (Option 1)...")
                    products_selectors = [
                        'select[name="conveniencestore_products_forsale"]',
                        'select[id="conveniencestore_products_forsale"]'
                    ]
                    
                    products_dropdown = None
                    for selector in products_selectors:
                        products_dropdown = await self.page.query_selector(selector)
                        if products_dropdown:
                            logger.info(f"✅ Found products for sale dropdown with selector: {selector}")
                            break
                    
                    if products_dropdown:
                        await products_dropdown.select_option(value="1")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected Option 1 for primary products for sale")
                    else:
                        logger.warning("⚠️ Could not find products for sale dropdown")
                    
                    # Field 11: What percentage of total sales are from tobacco products? (10%)
                    logger.info("Filling tobacco products percentage...")
                    tobacco_selectors = [
                        'input[name="conveniencestore_tobacco"]',
                        'input[id="conveniencestore_tobacco"]'
                    ]
                    
                    tobacco_input = None
                    for selector in tobacco_selectors:
                        tobacco_input = await self.page.query_selector(selector)
                        if tobacco_input:
                            logger.info(f"✅ Found tobacco percentage input with selector: {selector}")
                            break
                    
                    if tobacco_input:
                        await tobacco_input.click()
                        await tobacco_input.fill("")
                        await tobacco_input.type(self.tobacco_percent)
                        await asyncio.sleep(0.5)
                        logger.info(f"✅ Tobacco products percentage: {self.tobacco_percent}%")
                    else:
                        logger.warning("⚠️ Could not find tobacco percentage input")
                    
                    # Field 12: Describe the food preparation operations (None)
                    logger.info("Selecting food preparation operations (None)...")
                    foodprep_selectors = [
                        'select[name="conveniencestore_foodprep"]',
                        'select[id="conveniencestore_foodprep"]'
                    ]
                    
                    foodprep_dropdown = None
                    for selector in foodprep_selectors:
                        foodprep_dropdown = await self.page.query_selector(selector)
                        if foodprep_dropdown:
                            logger.info(f"✅ Found food preparation dropdown with selector: {selector}")
                            break
                    
                    if foodprep_dropdown:
                        await foodprep_dropdown.select_option(value="NONE")
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'None' for food preparation operations")
                    else:
                        logger.warning("⚠️ Could not find food preparation dropdown")
                    
                    # Field 13: Has the building been certified by IBHS FORTIFIED? (Yes)
                    logger.info("Selecting 'Yes' for IBHS FORTIFIED certification...")
                    fortified_selectors = [
                        'input[name="conveniencestore_windmitigation_ga_radio"][value="Y"]',
                        'input[id="conveniencestore_windmitigation_ga_radio_Y"]'
                    ]
                    
                    fortified_radio = None
                    for selector in fortified_selectors:
                        fortified_radio = await self.page.query_selector(selector)
                        if fortified_radio:
                            logger.info(f"✅ Found FORTIFIED radio with selector: {selector}")
                            break
                    
                    if fortified_radio:
                        await fortified_radio.click()
                        await asyncio.sleep(1)  # Wait for compliance acknowledgment to load
                        logger.info("✅ Selected 'Yes' for IBHS FORTIFIED certification")
                    else:
                        logger.warning("⚠️ Could not find FORTIFIED radio button")
                    
                    # Field 14: Acknowledgment for proof of compliance (Yes)
                    logger.info("Selecting 'Yes' for compliance acknowledgment...")
                    compliance_selectors = [
                        'input[name="conveniencestore_windmessage_radio_N"][value="Y"]',
                        'input[id="conveniencestore_windmessage_radio_Y"]'
                    ]
                    
                    compliance_radio = None
                    for selector in compliance_selectors:
                        compliance_radio = await self.page.query_selector(selector)
                        if compliance_radio:
                            logger.info(f"✅ Found compliance radio with selector: {selector}")
                            break
                    
                    if compliance_radio:
                        await compliance_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'Yes' for compliance acknowledgment")
                    else:
                        logger.warning("⚠️ Could not find compliance radio button")
                    
                    # Field 15: High-hazard neighboring exposures? (No)
                    logger.info("Selecting 'No' for high-hazard exposures...")
                    highhazard_selectors = [
                        'input[name="conveniencestore_highhazard_radio"][value="N"]',
                        'input[id="conveniencestore_highhazard_radio_N"]'
                    ]
                    
                    highhazard_radio = None
                    for selector in highhazard_selectors:
                        highhazard_radio = await self.page.query_selector(selector)
                        if highhazard_radio:
                            logger.info(f"✅ Found high-hazard radio with selector: {selector}")
                            break
                    
                    if highhazard_radio:
                        await highhazard_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'No' for high-hazard exposures")
                    else:
                        logger.warning("⚠️ Could not find high-hazard radio button")
                    
                    # Field 16: Percentage of receipts from liquor/alcohol sales (10%)
                    logger.info("Filling liquor/alcohol sales percentage...")
                    alcohol_selectors = [
                        'input[name="conveniencestore_alcoholsales"]',
                        'input[id="conveniencestore_alcoholsales"]'
                    ]
                    
                    alcohol_input = None
                    for selector in alcohol_selectors:
                        alcohol_input = await self.page.query_selector(selector)
                        if alcohol_input:
                            logger.info(f"✅ Found alcohol sales input with selector: {selector}")
                            break
                    
                    if alcohol_input:
                        await alcohol_input.click()
                        await alcohol_input.fill("")
                        await alcohol_input.type(self.alcohol_percent)
                        await asyncio.sleep(0.5)
                        logger.info(f"✅ Liquor/alcohol sales percentage: {self.alcohol_percent}%")
                    else:
                        logger.warning("⚠️ Could not find alcohol sales input")
                    
                    # Field 17: Auto Service/Repair operations? (No)
                    logger.info("Selecting 'No' for auto service operations...")
                    autoservice_selectors = [
                        'input[name="conveniencestore_autoservices_radio"][value="N"]',
                        'input[id="conveniencestore_autoservices_radio_N"]'
                    ]
                    
                    autoservice_radio = None
                    for selector in autoservice_selectors:
                        autoservice_radio = await self.page.query_selector(selector)
                        if autoservice_radio:
                            logger.info(f"✅ Found auto service radio with selector: {selector}")
                            break
                    
                    if autoservice_radio:
                        await autoservice_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'No' for auto service operations")
                    else:
                        logger.warning("⚠️ Could not find auto service radio button")
                    
                    # Field 18: Has parking lot been paved within last 15 years? (Yes)
                    logger.info("Selecting 'Yes' for parking lot paving...")
                    parkinglot_selectors = [
                        'input[name="conveniencestore_parkinglot_radio_Y"][value="Y"]',
                        'input[id="conveniencestore_parkinglot_radio_Y"]'
                    ]
                    
                    parkinglot_radio = None
                    for selector in parkinglot_selectors:
                        parkinglot_radio = await self.page.query_selector(selector)
                        if parkinglot_radio:
                            logger.info(f"✅ Found parking lot radio with selector: {selector}")
                            break
                    
                    if parkinglot_radio:
                        await parkinglot_radio.click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Selected 'Yes' for parking lot paving")
                    else:
                        logger.warning("⚠️ Could not find parking lot radio button")
                    
                    await asyncio.sleep(1)
                    
                    # Take screenshot of filled class specific info
                    screenshot_path = self.login_handler.screenshot_dir / "18_class_specific_filled.png"
                    await self.page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.info(f"Screenshot saved: {screenshot_path}")
                    
                    # Click NEXT button
                    logger.info("Clicking NEXT button on Class Specific Information...")
                    next_button = await self.page.query_selector('button[name="next_btn"]')
                    if next_button:
                        await next_button.click()
                        await self.page.wait_for_load_state("networkidle", timeout=10000)
                        logger.info("✅ NEXT button clicked on Class Specific Information")
                        await asyncio.sleep(2)
                        
                        # Take screenshot of next page (quote summary/completion page)
                        screenshot_path = self.login_handler.screenshot_dir / "19_quote_complete.png"
                        await self.page.screenshot(path=str(screenshot_path), full_page=True)
                        logger.info(f"Screenshot saved: {screenshot_path}")
                        logger.info(f"Current URL: {self.page.url}")
                        
                        # Class Specific is the LAST panel - automation complete!
                        logger.info(f"✅ Completed all panels - processed {panel_count} panels")
                        break  # Exit the while loop
                    else:
                        logger.warning("⚠️ Could not find NEXT button on Class Specific Information")
                        # If no NEXT button on final panel, we're done
                        logger.info(f"✅ Completed all panels (last was Class Specific) - processed {panel_count} panels")
                        break  # Exit the while loop
                    
            except Exception as e:
                logger.error(f"❌ Error filling panel {panel_count}: {e}")
                # Take error screenshot
                screenshot_path = self.login_handler.screenshot_dir / f"error_panel_{panel_count}.png"
                await self.page.screenshot(path=str(screenshot_path), full_page=True)
                logger.info(f"Error screenshot saved: {screenshot_path}")
                raise
        
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ QUOTE AUTOMATION COMPLETE - Processed {panel_count} panels")
        logger.info(f"{'='*80}")
    
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
