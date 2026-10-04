import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(line_buffering=True)
BASE_URL = "http://127.0.0.1:8000"

def test_all():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        # 1. Test /features page layout (no overlapping subheadings on images)
        print("Testing /features layout...")
        page.goto(f"{BASE_URL}/features", wait_until="domcontentloaded")
        page.wait_for_selector("img[alt='Intelligent Pump Selection & Sizing Engine']")

        # Check that there are NO absolute floating badges over the preview images
        overlays = page.query_selector_all(".absolute.top-3.left-3")
        assert len(overlays) == 0, f"Found {len(overlays)} floating badges over images in features overview!"
        
        # Verify card headers exist with badges
        badges = page.query_selector_all("span.text-\\[10px\\].font-semibold")
        print(f"Found {len(badges)} clean header badges on /features.")
        assert len(badges) >= 8, f"Expected at least 8 module badges, found {len(badges)}"
        print("Features overview layout test: PASS")

        # 2. Test Autoplay on /features/fire-protection
        print("Testing carousel autoplay on /features/fire-protection...")
        page.goto(f"{BASE_URL}/features/fire-protection", wait_until="domcontentloaded")
        page.wait_for_selector("#featureMediaFrame")

        # Check initial slide is 0 (NFPA 13)
        assert page.is_visible("#carousel-slide-0"), "Slide 0 should be visible initially"
        assert not page.is_visible("#carousel-slide-1"), "Slide 1 should be hidden initially"

        print("Waiting 5.2 seconds for autoplay to advance to Slide 1 (NFPA 14)...")
        time.sleep(5.2)

        assert not page.is_visible("#carousel-slide-0"), "Slide 0 should now be hidden after autoplay"
        assert page.is_visible("#carousel-slide-1"), "Slide 1 (NFPA 14) should now be visible via autoplay"
        title1 = page.text_content("#carouselSlideTitle")
        print(f"Autoplay successfully advanced to: {title1}")
        assert "NFPA 14" in title1

        # Test pause button
        print("Testing Play/Pause button...")
        pause_btn = page.query_selector("#btnCarouselPlayPause")
        assert pause_btn is not None, "Pause button should exist"
        page.click("#btnCarouselPlayPause")
        pause_text = page.text_content("#carouselPlayPauseText")
        assert "Paused" in pause_text, f"Expected 'Paused', got '{pause_text}'"
        print("Pause toggle: PASS")

        # Wait 5.2 seconds while paused — slide should NOT change
        time.sleep(5.2)
        assert page.is_visible("#carousel-slide-1"), "Slide 1 should remain visible while paused"
        print("Pause hold verification: PASS")

        # Resume autoplay
        page.click("#btnCarouselPlayPause")
        resume_text = page.text_content("#carouselPlayPauseText")
        assert "Autoplay" in resume_text
        print("Resume toggle: PASS")

        browser.close()

        if errors:
            print(f"FAILED with {len(errors)} page errors: {errors}")
            sys.exit(1)
        else:
            print("ALL AUTOPLAY & HEADING FIX TESTS PASSED WITH 100% SUCCESS!")

if __name__ == "__main__":
    test_all()
