import re
from typing import List, Dict, Any, Optional, Union

# Assuming TestCase is defined elsewhere or passed in a structured way
# from main import TestCase # Or define a minimal version here if needed

class TestCase(BaseModel): # Re-define or import if needed for type hinting
    id: str
    url: str
    element_type: str
    xpath: str
    css_selector: str
    test_type: str
    description: str
    element_text: Optional[str] = None
    attributes: Optional[Dict[str, Union[str, List[str]]]] = None

# Helper function to generate a Python-safe function name
def make_safe_function_name(name: str) -> str:
    # Remove invalid characters
    name = re.sub(r'[^\w\s-]', '', name)
    # Replace whitespace and hyphens with underscores
    name = re.sub(r'[-\s]+', '_', name).strip('_')
    # Ensure it starts with a letter or underscore
    if not name or not (name[0].isalpha() or name[0] == '_'):
        name = '_' + name
    # Ensure it's not a Python keyword (basic check)
    keywords = {"def", "class", "return", "yield", "import", "from", "pass", "if", "else", "elif"}
    if name in keywords:
        name += "_test"
    return name.lower()

# Function to generate the Selenium code for a single test case
def generate_selenium_test_case_code(test_case: TestCase) -> Optional[str]:
    """Generates a Python Selenium test function string for a single TestCase."""

    # Prioritize XPath, fallback to CSS Selector
    locator = test_case.xpath if test_case.xpath else test_case.css_selector
    by = "By.XPATH" if test_case.xpath else "By.CSS_SELECTOR"

    if not locator:
        return f"    # Skipping test: {test_case.description} - No locator found\n    pass\n"

    # Sanitize locator string for use in Python string literals
    safe_locator = locator.replace('"', '\\"').replace("'", "\\'")

    # Generate a safe function name from the test case ID or description
    func_name_base = test_case.id.split('/')[-1] # Try to get a unique part from ID
    if not func_name_base:
         func_name_base = test_case.description
    func_name = make_safe_function_name(f"test_{func_name_base}")

    # --- Code Generation based on test_type ---
    code_lines = [
        f"def {func_name}(driver, wait):",
        f"    \"\"\" {test_case.description} \"\"\"",
        f"    print(f'Running test: {test_case.description}')",
        f"    try:",
        # Add navigation only if not already on the page (simplification: always navigate)
        # In a real test suite, you might manage this state differently.
        f"        if driver.current_url != '{test_case.url}':",
        f"            print(f'Navigating to {test_case.url}')",
        f"            driver.get('{test_case.url}')"
    ]

    # Handle different test types
    if test_case.test_type in ["click", "submission", "selection"]:
        code_lines.extend([
            f"        element = wait.until(EC.element_to_be_clickable(({by}, \"{safe_locator}\")))",
            f"        print(f'Clicking element: {{({by}, \"{safe_locator}\")}}')",
            f"        element.click()",
            f"        # Add assertions here to verify the result of the click/submission",
            f"        assert True # Placeholder assertion"
        ])
    elif test_case.test_type == "input" or test_case.test_type == "validation":
        # Basic input example, real tests need varied data
        sample_input = "sample input"
        if "email" in test_case.element_type or (test_case.attributes and test_case.attributes.get("type") == "email"):
            sample_input = "test@example.com"
        elif "password" in test_case.element_type or (test_case.attributes and test_case.attributes.get("type") == "password"):
             sample_input = "password123"

        code_lines.extend([
            f"        element = wait.until(EC.presence_of_element_located(({by}, \"{safe_locator}\")))",
            f"        print(f'Sending keys to element: {{({by}, \"{safe_locator}\")}}')",
            f"        element.clear() # Clear existing value",
            f"        element.send_keys(\"{sample_input}\")",
            f"        # Add assertions here for validation or input effect",
            f"        assert True # Placeholder assertion"
        ])
    elif test_case.test_type == "existence":
        code_lines.extend([
            f"        print(f'Checking existence of element: {{({by}, \"{safe_locator}\")}}')",
            f"        element = wait.until(EC.presence_of_element_located(({by}, \"{safe_locator}\")))",
            f"        assert element is not None",
            f"        assert element.is_displayed()"
        ])
    elif test_case.test_type == "assertion":
        # Check if it's a text assertion
        if test_case.element_text is not None:
            safe_expected_text = test_case.element_text.replace('"', '\\"').replace("'", "\\'")
            code_lines.extend([
                f"        print(f'Asserting text for element: {{({by}, \"{safe_locator}\")}}')",
                f"        element = wait.until(EC.presence_of_element_located(({by}, \"{safe_locator}\")))",
                f"        expected_text = \"\"\"{safe_expected_text}\"\"\"", # Use triple quotes for multiline/complex text
                f"        actual_text = element.text.strip()",
                f"        print(f'Expected: {{expected_text}}, Actual: {{actual_text}}')",
                f"        assert actual_text == expected_text"
            ])
        # Check if it's an attribute assertion
        elif test_case.attributes:
             code_lines.extend([
                f"        print(f'Asserting attributes for element: {{({by}, \"{safe_locator}\")}}')",
                f"        element = wait.until(EC.presence_of_element_located(({by}, \"{safe_locator}\")))",
             ])
             for attr_name, expected_value in test_case.attributes.items():
                 if isinstance(expected_value, list): # Handle class lists etc.
                     # Basic check: presence of all classes
                     safe_expected_value_list = [str(v).replace('"', '\\"') for v in expected_value]
                     code_lines.append(f"        attr_value = element.get_attribute('{attr_name}')")
                     code_lines.append(f"        expected_classes = {safe_expected_value_list}")
                     code_lines.append(f"        print(f'Checking attribute [{attr_name}] contains classes: {{expected_classes}}, Actual: {{attr_value}}')")
                     code_lines.append(f"        assert all(cls in attr_value.split() for cls in expected_classes)")

                 elif isinstance(expected_value, str):
                    safe_expected_value = expected_value.replace('"', '\\"').replace("'", "\\'")
                    code_lines.append(f"        attr_value = element.get_attribute('{attr_name}')")
                    code_lines.append(f"        expected_value = \"{safe_expected_value}\"")
                    code_lines.append(f"        print(f'Checking attribute [{attr_name}]: Expected: {{expected_value}}, Actual: {{attr_value}}')")
                    # Handle boolean attributes (like 'checked', 'disabled')
                    if expected_value in ['true', 'false']:
                         code_lines.append(f"        assert str(attr_value).lower() == '{expected_value.lower()}'")
                    elif attr_name == 'href': # Resolve relative URLs if needed (basic join)
                         code_lines.extend([
                            f"        from urllib.parse import urljoin",
                            f"        base_url = '{test_case.url}'",
                            f"        absolute_expected_url = urljoin(base_url, expected_value)",
                            f"        absolute_actual_url = urljoin(base_url, attr_value)",
                            f"        print(f'Comparing resolved URLs: Expected: {{absolute_expected_url}}, Actual: {{absolute_actual_url}}')",
                            f"        assert absolute_actual_url == absolute_expected_url"
                         ])

                    else:
                        code_lines.append(f"        assert attr_value == expected_value")

        # Special case: Page title check
        elif test_case.element_type == "document" and test_case.xpath == "/html/head/title":
             safe_expected_title = test_case.description.split("'")[-2].replace('"', '\\"') # Extract from description
             code_lines.extend([
                 f"        print(f'Asserting page title')",
                 f"        expected_title = \"{safe_expected_title}\"",
                 f"        wait.until(EC.title_is(expected_title)) # Use Selenium's title check",
                 f"        actual_title = driver.title",
                 f"        print(f'Expected Title: {{expected_title}}, Actual Title: {{actual_title}}')",
                 f"        assert actual_title == expected_title"
             ])
        else:
            # Default assertion if type is 'assertion' but no specific data found
             code_lines.extend([
                f"        print(f'Generic assertion/check for element: {{({by}, \"{safe_locator}\")}}')",
                f"        element = wait.until(EC.presence_of_element_located(({by}, \"{safe_locator}\")))",
                f"        assert element.is_displayed() # Default assertion: check visibility"
            ])

    elif test_case.test_type == "performance":
        # Performance testing is complex. This just adds a placeholder comment.
        code_lines.extend([
            f"        # Performance test: {test_case.description}",
            f"        # Manual check or integration with performance tools needed.",
            f"        # Example: Check load time (very basic)",
            f"        load_time = driver.execute_script('return performance.timing.loadEventEnd - performance.timing.navigationStart')",
            f"        print(f'Page load time (ms): {{load_time}}')",
            f"        assert load_time < 5000 # Example threshold: 5 seconds"
        ])
    else:
         code_lines.extend([
            f"        # Test type '{test_case.test_type}' not explicitly handled for element: {{({by}, \"{safe_locator}\")}}",
            f"        # Defaulting to existence check",
            f"        print(f'Checking existence of element: {{({by}, \"{safe_locator}\")}}')",
            f"        element = wait.until(EC.presence_of_element_located(({by}, \"{safe_locator}\")))",
            f"        assert element is not None",
        ])


    # Add error handling
    code_lines.extend([
        f"    except TimeoutException:",
        f"        print(f'Test Failed: Element not found or timed out for {{({by}, \"{safe_locator}\")}}')",
        f"        assert False, 'Element not found or timed out'",
        f"    except Exception as e:",
        f"        print(f'Test Failed: An error occurred - {{e}}')",
        f"        assert False, f'An error occurred: {{e}}'",
        f"    else:",
        f"        print(f'Test Passed: {test_case.description}')"
    ])

    # Indent lines correctly and join
    indented_code = "\n".join(["    " + line if i > 0 else line for i, line in enumerate(code_lines)])
    return indented_code + "\n"


# Function to generate the full script for a list of test cases (usually for one page)
def generate_selenium_script_for_page(url: str, test_cases: List[TestCase], page_title: str = "") -> str:
    """Generates a complete Python Selenium script string for a list of TestCases."""

    script_imports = [
        "import pytest", # Using pytest fixtures for setup/teardown
        "from selenium import webdriver",
        "from selenium.webdriver.common.by import By",
        "from selenium.webdriver.support.ui import WebDriverWait",
        "from selenium.webdriver.support import expected_conditions as EC",
        "from selenium.common.exceptions import TimeoutException",
        "import time",
        "\n"
    ]

    # Basic pytest fixture for WebDriver setup and teardown
    script_setup = [
        "@pytest.fixture(scope='module') # Use 'module' scope for efficiency",
        "def driver_setup():",
        "    # --- Choose your driver ---",
        "    # options = webdriver.ChromeOptions()",
        "    # options.add_argument('--headless') # Optional: Run headless",
        "    # driver = webdriver.Chrome(options=options)",
        "    # OR",
        "    # options = webdriver.FirefoxOptions()",
        "    # options.add_argument('--headless')",
        "    # driver = webdriver.Firefox(options=options)",
        "    # --- Basic Chrome ---",
        "    driver = webdriver.Chrome() ",
        "    driver.maximize_window()",
        "    yield driver # Provide the driver to tests",
        "    print('Closing WebDriver')",
        "    driver.quit()",
        "\n",
        "@pytest.fixture(scope='module')",
        "def wait(driver_setup):",
        "    # Default wait time for elements (adjust as needed)",
        "    return WebDriverWait(driver_setup, 15)",
        "\n",
        f"# --- Tests for Page: {page_title or url} ---",
        f"# URL: {url}",
        "\n"
    ]

    # Generate code for each test case
    test_functions = []
    for tc in test_cases:
        # Create a TestCase object if needed (if input is dict)
        if isinstance(tc, dict):
             try:
                 # Ensure attributes is a dict if present
                 if 'attributes' in tc and not isinstance(tc['attributes'], dict):
                     tc['attributes'] = {} # Or try to parse if it's a string? Safer to clear.
                 tc_obj = TestCase(**tc)
             except Exception as e:
                 print(f"Warning: Could not parse test case dict: {tc}. Error: {e}")
                 continue # Skip this test case
        else:
            tc_obj = tc

        test_code = generate_selenium_test_case_code(tc_obj)
        if test_code:
            # Add fixtures to function signature (pytest convention)
            test_code = test_code.replace("(driver, wait):", "(driver_setup, wait):", 1)
            test_functions.append(test_code)

    # Combine all parts
    full_script = "\n".join(script_imports + script_setup + test_functions)

    # Add instructions comment at the end
    full_script += "\n\n"
    full_script += "# To run these tests:\n"
    full_script += "# 1. Make sure you have Python installed.\n"
    full_script += "# 2. Install necessary libraries: pip install selenium pytest\n"
    full_script += "# 3. Download the appropriate WebDriver (e.g., chromedriver, geckodriver) and ensure it's in your PATH or specify its location.\n"
    full_script += "#    - ChromeDriver: https://chromedriver.chromium.org/downloads\n"
    full_script += "#    - GeckoDriver (Firefox): https://github.com/mozilla/geckodriver/releases\n"
    full_script += "# 4. Save this code as a Python file (e.g., test_page.py).\n"
    full_script += "# 5. Run pytest from your terminal in the same directory: pytest\n"

    return full_script