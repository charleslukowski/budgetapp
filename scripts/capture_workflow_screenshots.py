"""Capture screenshots of the fuel forecast workflow using Playwright.

Run with: python scripts/capture_workflow_screenshots.py

Requires: pip install playwright
Then: playwright install chromium
"""

import os
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright not installed. Install with:")
    print("  pip install playwright")
    print("  playwright install chromium")
    sys.exit(1)

BASE_URL = "http://localhost:8000"
SCREENSHOT_DIR = "screenshots"

def capture_workflow():
    """Capture screenshots of each workflow step."""
    
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        
        print("Starting workflow...")
        
        # Step 1: Start
        page.goto(f"{BASE_URL}/fuel-forecast/new")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=f"{SCREENSHOT_DIR}/workflow_01_start.png", full_page=True)
        print("  Step 1: Start - captured")
        
        # Select "Start Fresh" and continue
        page.click('label:has-text("Start Fresh")')
        page.fill('input[name="as_of_month"]', '2025-12')
        page.click('button:has-text("Continue")')
        page.wait_for_load_state("networkidle")
        
        # Step 2: Coal Position
        page.screenshot(path=f"{SCREENSHOT_DIR}/workflow_02_coal_position.png", full_page=True)
        print("  Step 2: Coal Position - captured")
        page.click('button:has-text("Continue")')
        page.wait_for_load_state("networkidle")
        
        # Step 3: Coal Contracts
        page.screenshot(path=f"{SCREENSHOT_DIR}/workflow_03_contracts.png", full_page=True)
        print("  Step 3: Coal Contracts - captured")
        page.click('button:has-text("Continue")')
        page.wait_for_load_state("networkidle")
        
        # Step 4: Use Factors
        page.screenshot(path=f"{SCREENSHOT_DIR}/workflow_04_use_factors.png", full_page=True)
        print("  Step 4: Use Factors - captured")
        page.click('button:has-text("Continue")')
        page.wait_for_load_state("networkidle")
        
        # Step 5: Heat Rates
        page.screenshot(path=f"{SCREENSHOT_DIR}/workflow_05_heat_rates.png", full_page=True)
        print("  Step 5: Heat Rates - captured")
        page.click('button:has-text("Continue")')
        page.wait_for_load_state("networkidle")
        
        # Step 6: Generation
        page.screenshot(path=f"{SCREENSHOT_DIR}/workflow_06_generation.png", full_page=True)
        print("  Step 6: Generation - captured")
        page.click('button:has-text("Continue")')
        page.wait_for_load_state("networkidle")
        
        # Step 7: Other Costs
        page.screenshot(path=f"{SCREENSHOT_DIR}/workflow_07_other_costs.png", full_page=True)
        print("  Step 7: Other Costs - captured")
        page.click('button:has-text("Continue")')
        page.wait_for_load_state("networkidle")
        
        # Step 8: Review
        page.screenshot(path=f"{SCREENSHOT_DIR}/workflow_08_review.png", full_page=True)
        print("  Step 8: Review & Save - captured")
        
        browser.close()
        
        print(f"\nDone! Screenshots saved to {SCREENSHOT_DIR}/")


if __name__ == "__main__":
    capture_workflow()
