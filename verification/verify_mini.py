from playwright.sync_api import sync_playwright
import os

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Load the local HTML file
        file_path = os.path.abspath("mini.html")
        page.goto(f"file://{file_path}")

        # Wait for the card to render
        page.wait_for_selector("#box")

        # Take a screenshot of the main card
        page.locator("#box").screenshot(path="verification/mini_ui_fix.png")

        # Also take a screenshot of the controls area specifically to verify visibility
        page.locator(".header-row").screenshot(path="verification/controls_fix.png")

        browser.close()

if __name__ == "__main__":
    run()
