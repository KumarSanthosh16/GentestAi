from playwright.async_api import async_playwright
import asyncio
import json

class AccessibilityService:
    @staticmethod
    async def run_accessibility_tests(url):
        # Launch the browser asynchronously
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)  # Set to False for debugging
            page = await browser.new_page()

            try:
                # Inject axe-core script via CDN
                await page.add_script_tag(url="https://cdn.jsdelivr.net/npm/axe-core@4.3.1/axe.min.js")
                
                # Wait until the script is loaded and the axe object is available
                await page.wait_for_function("typeof axe !== 'undefined'")

                # Run axe-core accessibility tests
                result = await page.evaluate('axe.run()')
                violations = result.get('violations', [])

            except Exception as e:
                print(f"Error running axe-core tests: {e}")
                violations = []

            await browser.close()

            # Collect and return violations
            return [
                {
                    'description': violation['description'],
                    'help': violation['help'],
                    'impact': violation.get('impact', 'unknown'),
                    'id': violation['id']
                }
                for violation in violations
            ]
    
    @staticmethod
    def categorize_impacts(results):
        # Categorize the accessibility violations by impact
        impact_count = {'critical': 0, 'minor': 0, 'moderate': 0, 'serious': 0}
        for result in results:
            impact = result['impact']
            impact_count[impact] = impact_count.get(impact, 0) + 1
        return impact_count
