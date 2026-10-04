import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(line_buffering=True)
BASE_URL = "http://127.0.0.1:8000"

def test_carousels():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        # 1. Fire Protection
        print("Testing /features/fire-protection...")
        page.goto(f"{BASE_URL}/features/fire-protection", wait_until="domcontentloaded")
        page.wait_for_selector("#featureMediaFrame")
        
        # Check tabs exist
        assert page.is_visible("#carousel-tab-0"), "Tab 0 should be visible"
        assert page.is_visible("#carousel-tab-1"), "Tab 1 should be visible"
        assert page.is_visible("#carousel-tab-2"), "Tab 2 should be visible"
        assert page.is_visible("#carousel-tab-3"), "Tab 3 should be visible"
        assert page.is_visible("#carousel-tab-4"), "Tab 4 should be visible"

        # Check default active slide is NFPA 13
        assert page.is_visible("#carousel-slide-0"), "Slide 0 should be visible initially"
        assert not page.is_visible("#carousel-slide-1"), "Slide 1 should be hidden initially"
        
        # Click Tab 1 (NFPA 14)
        page.click("#carousel-tab-1")
        assert not page.is_visible("#carousel-slide-0"), "Slide 0 should now be hidden"
        assert page.is_visible("#carousel-slide-1"), "Slide 1 should now be visible"
        title = page.text_content("#carouselSlideTitle")
        assert "NFPA 14" in title, f"Expected NFPA 14 in title, got '{title}'"
        print("Fire Protection NFPA 14 tab click: PASS")

        # Click Next button
        page.click("button[aria-label='Next view']")
        assert page.is_visible("#carousel-slide-2"), "Slide 2 should be visible after next"
        title2 = page.text_content("#carouselSlideTitle")
        assert "EN 12845" in title2, f"Expected EN 12845 in title, got '{title2}'"
        print("Fire Protection Next arrow click (EN 12845): PASS")

        # 2. Slurry Derating
        print("Testing /features/slurry-derating...")
        page.goto(f"{BASE_URL}/features/slurry-derating", wait_until="domcontentloaded")
        page.wait_for_selector("#featureMediaFrame")
        assert page.is_visible("#carousel-tab-0"), "Slurry tab 0 visible"
        assert page.is_visible("#carousel-tab-1"), "Water tab 1 visible"
        assert page.is_visible("#carousel-tab-2"), "Viscous tab 2 visible"
        
        page.click("#carousel-tab-2")
        assert page.is_visible("#carousel-slide-2"), "Viscous slide visible"
        title_viscous = page.text_content("#carouselSlideTitle")
        assert "Viscous" in title_viscous
        print("Slurry & Viscous carousel: PASS")

        # 3. Pipe Network
        print("Testing /features/pipe-network...")
        page.goto(f"{BASE_URL}/features/pipe-network", wait_until="domcontentloaded")
        page.wait_for_selector("#featureMediaFrame")
        assert page.is_visible("#carousel-tab-0"), "Visual tab 0 visible"
        assert page.is_visible("#carousel-tab-1"), "Schematic tab 1 visible"
        assert page.is_visible("#carousel-tab-2"), "Simple tab 2 visible"

        page.click("#carousel-tab-1")
        assert page.is_visible("#carousel-slide-1"), "Schematic slide visible"
        page.click("#carousel-tab-2")
        assert page.is_visible("#carousel-slide-2"), "Simple mode slide visible"
        title_pipe = page.text_content("#carouselSlideTitle")
        assert "Simple Mode" in title_pipe
        print("Pipe Network carousel: PASS")

        browser.close()

        if errors:
            print(f"FAILED with {len(errors)} page errors: {errors}")
            sys.exit(1)
        else:
            print("ALL CAROUSEL BROWSER TESTS PASSED WITH ZERO CONSOLE ERRORS!")

if __name__ == "__main__":
    test_carousels()
