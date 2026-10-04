import os
import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(line_buffering=True)

BASE_URL = "http://127.0.0.1:8000"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "screenshots")

def run():
    print(f"Starting capture with Playwright into {OUTPUT_DIR}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)
        page = context.new_page()

        # 1. Log in as admin
        print("Logging in...")
        page.goto(f"{BASE_URL}/auth/login", wait_until="domcontentloaded")
        page.wait_for_selector('input[name="email"]', timeout=10000)
        page.fill('input[name="email"]', 'nevermabvuu@gmail.com')
        page.fill('input[name="password"]', 'Admin123!')
        page.click('button[type="submit"]')
        page.wait_for_load_state("domcontentloaded")
        time.sleep(1)
        print("Logged in. Current URL:", page.url)

        # 2. Fire Module: Fire selected (#qpt-fire)
        print("Navigating to Pump Selection in Fire Mode...")
        page.goto(f"{BASE_URL}/pump-selection?filter_pump_type=fire+pump", wait_until="domcontentloaded")
        page.wait_for_selector("#quickPumpTypeSwitcher", timeout=10000)
        time.sleep(1)

        # Ensure #qpt-fire is clicked and active
        if page.is_visible("#qpt-fire"):
            page.click("#qpt-fire")
            time.sleep(0.5)

        # Capture NFPA 13
        print("Capturing NFPA 13...")
        if page.is_visible("#fp_radio_nfpa13"):
            page.click("#fp_radio_nfpa13")
            time.sleep(0.5)
        page.screenshot(path=os.path.join(OUTPUT_DIR, "screenshot_fire_nfpa13.png"))
        # Also save as main fire screenshot
        page.screenshot(path=os.path.join(OUTPUT_DIR, "screenshot_fire_protection.png"))
        print("Saved screenshot_fire_nfpa13.png & screenshot_fire_protection.png")

        # Capture NFPA 14
        print("Capturing NFPA 14...")
        if page.is_visible("#fp_radio_nfpa14"):
            page.click("#fp_radio_nfpa14")
            time.sleep(0.5)
        page.screenshot(path=os.path.join(OUTPUT_DIR, "screenshot_fire_nfpa14.png"))
        print("Saved screenshot_fire_nfpa14.png")

        # Capture EN 12845
        print("Capturing EN 12845...")
        if page.is_visible("#fp_radio_en12845"):
            page.click("#fp_radio_en12845")
            time.sleep(0.5)
        page.screenshot(path=os.path.join(OUTPUT_DIR, "screenshot_fire_en12845.png"))
        print("Saved screenshot_fire_en12845.png")

        # Capture AS 2941
        print("Capturing AS 2941...")
        if page.is_visible("#fp_radio_as2941"):
            page.click("#fp_radio_as2941")
            time.sleep(0.5)
        page.screenshot(path=os.path.join(OUTPUT_DIR, "screenshot_fire_as2941.png"))
        print("Saved screenshot_fire_as2941.png")

        # Capture Custom Duty / Code Compliance
        print("Capturing Custom Fire Duty...")
        if page.is_visible("#fp_radio_custom"):
            page.click("#fp_radio_custom")
            time.sleep(0.5)
        page.screenshot(path=os.path.join(OUTPUT_DIR, "screenshot_fire_compliance.png"))
        print("Saved screenshot_fire_compliance.png")

        # 3. Fluids: Slurry, Clean Water, Viscous
        print("Navigating to Fluid Sizing (Normal selection)...")
        page.goto(f"{BASE_URL}/pump-selection?filter_pump_type=slurry", wait_until="domcontentloaded")
        page.wait_for_selector("#liquidSel", timeout=10000)
        time.sleep(1)

        # Ensure Slurry selected
        if page.is_visible("#qpt-slurry"):
            page.click("#qpt-slurry")
            time.sleep(0.5)
        page.select_option("#liquidSel", "slurry")
        time.sleep(0.5)
        print("Capturing Slurry Fluid mode...")
        page.screenshot(path=os.path.join(OUTPUT_DIR, "screenshot_fluid_slurry.png"))
        page.screenshot(path=os.path.join(OUTPUT_DIR, "screenshot_slurry_derating.png"))
        print("Saved screenshot_fluid_slurry.png & screenshot_slurry_derating.png")

        # Viscous Fluid
        print("Capturing Viscous Fluid mode...")
        page.select_option("#liquidSel", "viscous")
        time.sleep(0.5)
        page.screenshot(path=os.path.join(OUTPUT_DIR, "screenshot_fluid_viscous.png"))
        print("Saved screenshot_fluid_viscous.png")

        # Clean Water
        print("Capturing Clean Water mode...")
        if page.is_visible("#qpt-centrifugal"):
            page.click("#qpt-centrifugal")
            time.sleep(0.5)
        page.select_option("#liquidSel", "water")
        time.sleep(0.5)
        page.screenshot(path=os.path.join(OUTPUT_DIR, "screenshot_fluid_water.png"))
        print("Saved screenshot_fluid_water.png")

        # 4. Pipe Network Designer
        print("Navigating to Pipe Network Designer...")
        page.goto(f"{BASE_URL}/pipe-network", wait_until="domcontentloaded")
        page.wait_for_selector("#btn-top-mode-canvas", timeout=10000)
        time.sleep(1.5)

        # Industrial Visual Mode
        print("Capturing Pipe Network Visual Mode...")
        if page.is_visible("#btn-top-mode-canvas"):
            page.click("#btn-top-mode-canvas")
            time.sleep(0.5)
        if page.is_visible("#btn-view-industrial"):
            page.click("#btn-view-industrial")
            time.sleep(0.8)
        page.screenshot(path=os.path.join(OUTPUT_DIR, "screenshot_pipe_visual.png"))
        page.screenshot(path=os.path.join(OUTPUT_DIR, "screenshot_pipe_network.png"))
        print("Saved screenshot_pipe_visual.png & screenshot_pipe_network.png")

        # Schematic Mode
        print("Capturing Pipe Network Schematic Mode...")
        if page.is_visible("#btn-view-schematic"):
            page.click("#btn-view-schematic")
            time.sleep(0.8)
        page.screenshot(path=os.path.join(OUTPUT_DIR, "screenshot_pipe_schematic.png"))
        print("Saved screenshot_pipe_schematic.png")

        # Simple Mode
        print("Capturing Pipe Network Simple Mode...")
        if page.is_visible("#btn-top-mode-simple"):
            page.click("#btn-top-mode-simple")
            time.sleep(0.8)
        page.screenshot(path=os.path.join(OUTPUT_DIR, "screenshot_pipe_simple.png"))
        print("Saved screenshot_pipe_simple.png")

        browser.close()
        print("ALL SCREENSHOTS SUCCESSFULLY CAPTURED!")

if __name__ == "__main__":
    run()
