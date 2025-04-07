from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl, ValidationError
import requests
from bs4 import BeautifulSoup
import re
import urllib.parse
import logging
from typing import List, Dict, Set, Optional, Any, Union
import json
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.requests import Request
from lxml import etree
import subprocess
import os

# from accessibility_service import AccessibilityService

class CustomCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            response = Response(status_code=200)
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
            return response

        response: Response = await call_next(request)

        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"

        return response


logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Web Crawler, Accessibility Checker and Test Case Generator", # Updated title
             description="A service that crawls websites, checks accessibility, and generates test cases with XPath and CSS Selectors") # Updated description

app.add_middleware(CustomCORSMiddleware)

class CrawlRequest(BaseModel):
    url: HttpUrl
    max_pages: int = 10
    max_depth: int = 3
    include_external: bool = False

class CrawlStatus(BaseModel):
    job_id: str
    status: str
    pages_crawled: int = 0
    total_pages: Optional[int] = None
    test_cases_generated: int = 0
    accessibility_issues_found: int = 0

class TestCase(BaseModel):
    id: str
    url: str
    element_type: str
    xpath: str
    css_selector: str
    test_type: str
    description: str
    element_text: Optional[str] = None
    attributes: Optional[Dict[str, Union[str, List[str]]]] = None

crawl_jobs = {}
crawl_results = {}

ACCESSIBILITY_CHECKER_SCRIPT = os.path.join(os.path.dirname(__file__), 'accessibility_checker.js')
NODE_EXECUTABLE = "node"


def is_valid_url(url: str, base_domain: str) -> bool:
    """Check if URL is valid and belongs to the same domain."""
    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.netloc:
            return True
        return base_domain == parsed.netloc or parsed.netloc.endswith('.' + base_domain)
    except Exception as e:
        logger.warning(f"URL validation error for {url}: {e}")
        return False

def get_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc
    except Exception:
        return ""

def get_links(soup: BeautifulSoup, base_url: str, base_domain: str, include_external: bool) -> List[str]:
    """Extract all links from a page."""
    links = set()
    for anchor in soup.find_all('a', href=True):
        href = anchor['href'].strip()
        if not href or href.startswith('#') or href.startswith('mailto:') or href.startswith('tel:') or href.startswith('javascript:'):
            continue

        try:
            full_url = urllib.parse.urljoin(base_url, href)
            full_url = urllib.parse.urlunparse(urllib.parse.urlparse(full_url)._replace(fragment=""))

            if not full_url.startswith(('http://', 'https://')):
                 logger.debug(f"Skipping non-HTTP(S) URL: {full_url}")
                 continue

            parsed_full = urllib.parse.urlparse(full_url)
            link_domain = parsed_full.netloc

            if not link_domain:
                logger.debug(f"Skipping URL with no domain: {full_url}")
                continue

            if include_external:
                links.add(full_url)
            elif base_domain == link_domain or link_domain.endswith('.' + base_domain):
                links.add(full_url)
            else:
                 logger.debug(f"Skipping external link: {full_url} (base domain: {base_domain})")

        except Exception as e:
            logger.warning(f"Error processing link '{href}' on page {base_url}: {e}")

    return list(links)


def get_element_xpath(element):
    """Generate XPath for a given BeautifulSoup element."""
    components = []
    child = element
    while child and hasattr(child, 'parent') and child.parent and child.name:
        siblings = [sib for sib in child.parent.find_all(child.name, recursive=False) if sib.name]
        if len(siblings) > 1:
            count = 1
            for sib in siblings:
                if sib is child:
                    components.append(f"{child.name}[{count}]")
                    break
                count += 1
        else:
            components.append(child.name)

        if child.name == 'html':
            break
        child = child.parent

    if not components or components[-1] != 'html':
         if not components or components[-1] != 'html':
             components.append('html')

    return "/" + "/".join(components[::-1])


def get_element_css_selector(element):
    """Generate a basic CSS selector for a given BeautifulSoup element."""
    if not element or not hasattr(element, 'name') or not element.name:
        return ""

    selector_parts = [element.name]
    element_id = element.get('id')
    if element_id and not re.search(r'\s', element_id):
         selector_parts.append(f"#{element_id}")
         return "".join(selector_parts)


    element_classes = element.get('class')
    if element_classes:
        valid_classes = [cls for cls in element_classes if cls]
        if valid_classes:
            selector_parts.append(f".{'.'.join(valid_classes)}")

    return "".join(selector_parts)


def generate_form_test_cases(url: str, soup: BeautifulSoup, html_tree) -> List[TestCase]:
    """Generate test cases for forms with XPath and CSS Selectors."""
    test_cases = []
    forms = soup.find_all('form')

    for i, form in enumerate(forms):
        try:
            form_id = form.get('id')
            form_name = form.get('name')
            form_identifier = form_id or form_name or f"form-{i}"

            form_xpath = get_element_xpath(form)
            form_css_selector = get_element_css_selector(form)
            if not form_xpath or not form_css_selector: continue

            attributes = {k: v for k, v in form.attrs.items()}

            test_cases.append(TestCase(
                id=f"{url}-form-{form_identifier}-submit",
                url=url,
                element_type="form",
                xpath=form_xpath,
                css_selector=form_css_selector,
                test_type="submission",
                description=f"Test form submission for {form_identifier}",
                attributes=attributes
            ))

            inputs = form.find_all(['input', 'textarea', 'select', 'button'])
            for j, input_field in enumerate(inputs):
                try:
                    input_id = input_field.get('id')
                    input_name = input_field.get('name')
                    input_type = input_field.get('type', input_field.name)
                    input_identifier = input_id or input_name or f"{input_type}-{j}"


                    input_xpath = get_element_xpath(input_field)
                    input_css_selector = get_element_css_selector(input_field)
                    if not input_xpath or not input_css_selector: continue

                    attributes = {k: v for k, v in input_field.attrs.items()}
                    element_text = input_field.text.strip() if input_field.name == 'button' else input_field.get('value')

                    test_types = []
                    if input_field.name == 'textarea':
                        test_types.extend(["validation", "input"])
                    elif input_field.name == 'select':
                        test_types.append("selection")
                    elif input_field.name == 'button' or input_type == 'button':
                         test_types.append("click")
                    elif input_type in ['text', 'email', 'password', 'url', 'search', 'tel', 'number']:
                        test_types.extend(["validation", "input"])
                    elif input_type in ['checkbox', 'radio']:
                        test_types.append("selection")
                    elif input_type == 'submit':
                        test_types.append("submission_button_click")

                    for test_type in test_types:
                        test_cases.append(TestCase(
                            id=f"{url}-form-{form_identifier}-input-{input_identifier}-{test_type}",
                            url=url,
                            element_type=input_field.name,
                            xpath=input_xpath,
                            css_selector=input_css_selector,
                            test_type=test_type,
                            description=f"Test {test_type} for {input_type} field '{input_identifier}' in form '{form_identifier}'",
                            element_text=element_text,
                            attributes=attributes
                        ))
                except Exception as e:
                    logger.warning(f"Error generating test case for input '{input_identifier}' in form '{form_identifier}' on {url}: {e}", exc_info=False) # Disable stack trace for cleaner logs
        except Exception as e:
            logger.warning(f"Error generating test cases for form {i} on {url}: {e}", exc_info=False)

    return test_cases

def generate_button_test_cases(url: str, soup: BeautifulSoup, html_tree) -> List[TestCase]:
    """Generate test cases for buttons (outside forms) with XPath and CSS Selectors."""
    test_cases = []
    buttons = soup.find_all(lambda tag: tag.name == 'button' or (tag.name == 'input' and tag.get('type') in ['button', 'submit', 'reset']) and not tag.find_parent('form'))


    for i, button in enumerate(buttons):
        try:
            button_id = button.get('id')
            button_name = button.get('name')
            button_identifier = button_id or button_name or f"button-outside-form-{i}"

            button_xpath = get_element_xpath(button)
            button_css_selector = get_element_css_selector(button)
            if not button_xpath or not button_css_selector: continue

            button_text = button.text.strip() if button.name == 'button' else button.get('value', '').strip()
            attributes = {k: v for k, v in button.attrs.items()}

            test_cases.append(TestCase(
                id=f"{url}-button-{button_identifier}-click",
                url=url,
                element_type=button.name,
                xpath=button_xpath,
                css_selector=button_css_selector,
                test_type="click",
                description=f"Test clicking button: {button_text or button_identifier}",
                element_text=button_text,
                attributes=attributes
            ))
        except Exception as e:
            logger.warning(f"Error generating test cases for button {i} outside form on {url}: {e}", exc_info=False)

    return test_cases

def generate_navigation_test_cases(url: str, soup: BeautifulSoup, html_tree) -> List[TestCase]:
    """Generate test cases for navigation elements with XPath and CSS Selectors."""
    test_cases = []
    nav_elements = soup.select('nav, [role="navigation"], #nav, #navigation, .nav, .navigation, #menu, .menu')

    for i, nav in enumerate(nav_elements):
        try:
            nav_id = nav.get('id', '')
            nav_classes = '.'.join(nav.get('class', []))
            nav_identifier = nav_id or nav_classes or f"nav-area-{i}"

            nav_xpath = get_element_xpath(nav)
            nav_css_selector = get_element_css_selector(nav)
            if not nav_xpath or not nav_css_selector: continue

            attributes = {k: v for k, v in nav.attrs.items()}

            test_cases.append(TestCase(
                id=f"{url}-nav-{nav_identifier}-exists",
                url=url,
                element_type="navigation_area",
                xpath=nav_xpath,
                css_selector=nav_css_selector,
                test_type="existence",
                description=f"Test navigation area '{nav_identifier}' exists",
                attributes=attributes
            ))

            links = nav.find_all('a', href=True)
            for j, link in enumerate(links):
                try:
                    link_text = link.text.strip()
                    link_href = link.get('href', '')
                    link_identifier = link_text or f"link-{j}"

                    link_xpath = get_element_xpath(link)
                    link_css_selector = get_element_css_selector(link)
                    if not link_xpath or not link_css_selector: continue

                    attributes = {k: v for k, v in link.attrs.items()}


                    test_cases.append(TestCase(
                        id=f"{url}-nav-{nav_identifier}-link-{j}-click",
                        url=url,
                        element_type="link",
                        xpath=link_xpath,
                        css_selector=link_css_selector,
                        test_type="click_navigation",
                        description=f"Test navigation link '{link_identifier}' (href: {link_href}) in '{nav_identifier}'",
                        element_text=link_text,
                        attributes=attributes
                    ))
                    # test_cases.append(TestCase(
                    #     id=f"{url}-nav-{nav_identifier}-link-{j}-href-check",
                    #     url=url, element_type="link", xpath=link_xpath, css_selector=link_css_selector,
                    #     test_type="assertion", description=f"Assert navigation link '{link_identifier}' href is '{link_href}'",
                    #     attributes={'href': link_href}
                    # ))
                except Exception as e:
                    logger.warning(f"Error generating test case for link {j} in navigation '{nav_identifier}' on {url}: {e}", exc_info=False)
        except Exception as e:
            logger.warning(f"Error generating test cases for navigation area {i} on {url}: {e}", exc_info=False)

    return test_cases


def generate_heading_test_cases(url: str, soup: BeautifulSoup, html_tree) -> List[TestCase]:
    """Generate test cases for headings (h1 to h6) with XPath and CSS Selectors."""
    test_cases = []
    for level in range(1, 7):
        headings = soup.find_all(f'h{level}')
        for j, heading in enumerate(headings):
            try:
                heading_text = heading.text.strip()
                heading_id = heading.get('id')
                heading_identifier = heading_id or f"h{level}-{j}"

                heading_xpath = get_element_xpath(heading)
                heading_css_selector = get_element_css_selector(heading)
                if not heading_xpath or not heading_css_selector: continue

                attributes = {k: v for k, v in heading.attrs.items()}

                test_cases.append(TestCase(
                    id=f"{url}-h{level}-{heading_identifier}-existence",
                    url=url,
                    element_type=f"h{level}",
                    xpath=heading_xpath,
                    css_selector=heading_css_selector,
                    test_type="existence",
                    description=f"Test existence of H{level} heading '{heading_identifier}'",
                    element_text=heading_text,
                    attributes=attributes
                ))
                if heading_text:
                    test_cases.append(TestCase(
                        id=f"{url}-h{level}-{heading_identifier}-text-check",
                        url=url,
                        element_type=f"h{level}",
                        xpath=heading_xpath,
                        css_selector=heading_css_selector,
                        test_type="assertion",
                        description=f"Test text content of H{level} '{heading_identifier}' is '{heading_text}'",
                        element_text=heading_text
                    ))
            except Exception as e:
                logger.warning(f"Error generating test cases for h{level} heading {j} on {url}: {e}", exc_info=False)
    return test_cases

def generate_image_test_cases(url: str, soup: BeautifulSoup, html_tree) -> List[TestCase]:
    """Generate test cases for images with XPath and CSS Selectors."""
    test_cases = []
    images = soup.find_all('img')
    for i, img in enumerate(images):
        try:
            alt_text = img.get('alt')
            src = img.get('src', '')
            img_id = img.get('id')
            img_identifier = img_id or f"img-{i}"

            img_xpath = get_element_xpath(img)
            img_css_selector = get_element_css_selector(img)
            if not img_xpath or not img_css_selector: continue

            attributes = {k: v for k, v in img.attrs.items()}

            test_cases.append(TestCase(
                id=f"{url}-img-{img_identifier}-existence",
                url=url,
                element_type="img",
                xpath=img_xpath,
                css_selector=img_css_selector,
                test_type="existence",
                description=f"Test existence of image '{img_identifier}' (src: '{src}')",
                attributes=attributes
            ))
            test_cases.append(TestCase(
                id=f"{url}-img-{img_identifier}-alt-presence-check",
                url=url,
                element_type="img",
                xpath=img_xpath,
                css_selector=img_css_selector,
                test_type="assertion",
                description=f"Test image '{img_identifier}' has an 'alt' attribute (even if empty for decorative images)",
                attributes={'alt': alt_text if alt_text is not None else "ATTRIBUTE_SHOULD_EXIST"}
            ))
            # Optional: Check src validity (could involve another request)
            # if src:
            #     test_cases.append(TestCase(
            #         id=f"{url}-img-{img_identifier}-src-check", url=url, element_type="img", xpath=img_xpath, css_selector=img_css_selector,
            #         test_type="assertion", description=f"Test src attribute of image '{img_identifier}' is '{src}'",
            #         attributes={'src': src}
            #     ))
        except Exception as e:
            logger.warning(f"Error generating test cases for image {i} on {url}: {e}", exc_info=False)
    return test_cases

def generate_page_load_test_cases(url: str, title: str) -> List[TestCase]:
    """Generate basic page load test cases."""
    test_cases = []

    if title:
        test_cases.append(TestCase(
            id=f"{url}-page-title-check",
            url=url,
            element_type="document",
            xpath="/html/head/title",
            css_selector="html > head > title",
            test_type="assertion",
            description=f"Test page title matches '{title}'",
            element_text=title
        ))

    test_cases.append(TestCase(
        id=f"{url}-page-load-performance",
        url=url,
        element_type="document",
        xpath="/html",
        css_selector="html",
        test_type="performance_check",
        description="Conceptual: Test page load time is within acceptable threshold"
    ))

    return test_cases


def generate_test_cases(url: str, soup: BeautifulSoup, html_tree) -> List[TestCase]:
    """Generate various test cases for a page."""
    test_cases = []
    start_time = time.time()
    logger.info(f"Generating test cases for: {url}")

    title = soup.title.string.strip() if soup.title and soup.title.string else "No Title Found"

    generators = [
        generate_page_load_test_cases,
        generate_form_test_cases,
        generate_button_test_cases,
        generate_navigation_test_cases,
        generate_heading_test_cases,
        generate_image_test_cases
    ]

    for generator in generators:
        try:
            if generator in [generate_page_load_test_cases]:
                 test_cases.extend(generator(url, title))
            else:
                 test_cases.extend(generator(url, soup, html_tree))
        except Exception as e:
            logger.error(f"Error running test case generator {generator.__name__} for {url}: {e}", exc_info=True)


    end_time = time.time()
    logger.info(f"Generated {len(test_cases)} test cases for {url} in {end_time - start_time:.2f} seconds.")
    return test_cases


def run_accessibility_check(url: str) -> Dict[str, Any]:
    """Runs the Node.js accessibility checker script and returns the parsed results."""
    start_time = time.time()
    logger.info(f"Starting accessibility check for: {url}")
    if not os.path.exists(ACCESSIBILITY_CHECKER_SCRIPT):
        logger.error(f"Accessibility checker script not found at: {ACCESSIBILITY_CHECKER_SCRIPT}")
        return {"error": "Accessibility checker script not found."}

    command = [NODE_EXECUTABLE, ACCESSIBILITY_CHECKER_SCRIPT, url]
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=90
        )

        stdout = process.stdout.strip()
        stderr = process.stderr.strip()

        if process.returncode != 0:
            logger.error(f"Accessibility script failed for {url} (exit code {process.returncode}). Stderr: {stderr}")
            try:
                 error_json = json.loads(stdout)
                 if isinstance(error_json, dict) and 'error' in error_json:
                      return error_json
            except json.JSONDecodeError:
                 pass
            return {"error": f"Accessibility script failed (code {process.returncode})", "stderr": stderr, "stdout": stdout}


        if not stdout:
             logger.warning(f"Accessibility script for {url} produced no output.")
             return {"error": "Accessibility script produced no output.", "stderr": stderr}

        try:
            result = json.loads(stdout)
            end_time = time.time()
            violation_count = len(result.get("violations", []))
            logger.info(f"Accessibility check for {url} completed in {end_time - start_time:.2f} seconds. Found {violation_count} violations.")
            return result
        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to parse accessibility JSON output for {url}. Error: {json_err}. Output: {stdout[:500]}...")
            return {"error": "Failed to parse accessibility JSON output.", "details": str(json_err)}

    except subprocess.TimeoutExpired:
        logger.error(f"Accessibility check timed out for {url} after 90 seconds.")
        return {"error": "Accessibility check timed out."}
    except FileNotFoundError:
        logger.error(f"Node.js executable '{NODE_EXECUTABLE}' not found. Please ensure Node.js is installed and in PATH.")
        return {"error": f"Node.js executable '{NODE_EXECUTABLE}' not found."}
    except Exception as e:
        logger.error(f"An unexpected error occurred running accessibility check for {url}: {e}", exc_info=True)
        return {"error": "An unexpected error occurred during accessibility check.", "details": str(e)}


async def crawl_website(job_id: str, url: str, max_pages: int, max_depth: int, include_external: bool):
    """Background task to crawl a website, generate test cases, and run accessibility checks."""
    start_time_crawl = time.time()
    logger.info(f"Starting crawl job {job_id} for {url} (max_pages={max_pages}, max_depth={max_depth})")
    try:
        base_domain = get_domain(url)
        if not base_domain:
             raise ValueError(f"Could not determine base domain for URL: {url}")

        visited: Set[str] = set()
        to_visit_queue: Dict[str, int] = {url: 0}

        results = {}
        total_accessibility_violations = 0

        crawl_jobs[job_id] = CrawlStatus(
            job_id=job_id,
            status="in_progress",
            pages_crawled=0,
            total_pages=1,
            test_cases_generated=0,
            accessibility_issues_found=0
        )

        processed_count = 0
        while to_visit_queue and processed_count < max_pages:
            current_url, depth = min(to_visit_queue.items(), key=lambda item: item[1])
            del to_visit_queue[current_url]

            if current_url in visited:
                continue

            if depth > max_depth:
                 logger.info(f"Skipping {current_url}: Exceeded max depth ({depth} > {max_depth})")
                 continue

            visited.add(current_url)
            processed_count += 1
            page_start_time = time.time()

            current_status = crawl_jobs.get(job_id)
            if not current_status:
                logger.warning(f"Job {job_id} was cancelled or removed.")
                return

            current_status.pages_crawled = len(visited)
            current_status.total_pages = len(visited) + len(to_visit_queue)


            try:
                logger.info(f"[{len(visited)}/{max_pages}] Crawling (depth {depth}): {current_url}")

                headers = {'User-Agent': 'Mozilla/5.0 (compatible; TestCrawler/1.0; +http://example.com/bot)'}
                response = requests.get(current_url, timeout=20, headers=headers, allow_redirects=True)
                response.raise_for_status()

                actual_url = response.url
                if actual_url != current_url:
                    logger.info(f"Redirected from {current_url} to {actual_url}")
                    current_url = actual_url
                    new_domain = get_domain(actual_url)
                    if include_external and new_domain != base_domain:
                        logger.info(f"Following redirect across domains: {new_domain} (original: {base_domain})")
                        pass


                content_type = response.headers.get('content-type', '').lower()
                if 'html' not in content_type:
                    logger.info(f"Skipping non-HTML content ({content_type}): {current_url}")
                    continue


                html_content = response.text
                if not html_content:
                    logger.warning(f"Empty HTML content for {current_url}")
                    continue

                try:
                    soup = BeautifulSoup(html_content, 'lxml')
                    html_tree = etree.HTML(html_content)
                except Exception as parse_err:
                    logger.error(f"Failed to parse HTML for {current_url}: {parse_err}")
                    continue

                page_title = soup.title.string.strip() if soup.title and soup.title.string else "No Title"

                test_cases = generate_test_cases(current_url, soup, html_tree)

                accessibility_report = run_accessibility_check(current_url)

                page_violations = 0
                if isinstance(accessibility_report, dict) and 'violations' in accessibility_report:
                    page_violations = len(accessibility_report['violations'])
                    total_accessibility_violations += page_violations

                results[current_url] = {
                    "url": current_url,
                    "title": page_title,
                    "status_code": response.status_code,
                    "content_type": content_type,
                    "test_cases": [tc.dict() for tc in test_cases],
                    "accessibility_report": accessibility_report.get("violations", [])
                }

                current_status.test_cases_generated += len(test_cases)
                current_status.accessibility_issues_found = total_accessibility_violations

                if depth < max_depth:
                    found_links = get_links(soup, current_url, base_domain, include_external)
                    logger.debug(f"Found {len(found_links)} potential links on {current_url}")
                    added_count = 0
                    for link in found_links:
                        if link not in visited and link not in to_visit_queue:
                             if (len(visited) + len(to_visit_queue)) < max_pages * 1.5:
                                  to_visit_queue[link] = depth + 1
                                  added_count += 1
                             # else:
                                  # logger.debug(f"Queue limit reached, not adding link: {link}")


                    logger.debug(f"Added {added_count} new unique links to the queue from {current_url}")
                    current_status.total_pages = len(visited) + len(to_visit_queue)


                page_end_time = time.time()
                logger.info(f"Finished processing {current_url} in {page_end_time - page_start_time:.2f}s")

                time.sleep(0.5)

            except requests.exceptions.RequestException as req_err:
                logger.error(f"Request failed for {current_url}: {req_err}")
                results[current_url] = {
                    "url": current_url, "error": f"Request failed: {req_err}"
                }
            except Exception as e:
                logger.error(f"Error processing {current_url}: {str(e)}", exc_info=True)
                results[current_url] = {
                    "url": current_url, "error": f"Processing error: {e}"
                }
            finally:
                 if job_id in crawl_jobs:
                     crawl_jobs[job_id].pages_crawled = len(visited)
                     crawl_jobs[job_id].total_pages = len(visited) + len(to_visit_queue)


        final_status = "completed"
        if processed_count >= max_pages:
             logger.info(f"Crawl job {job_id} finished: Reached max pages limit ({max_pages}).")
        elif not to_visit_queue:
             logger.info(f"Crawl job {job_id} finished: Explored all reachable pages within depth limit.")
        else:
             logger.warning(f"Crawl job {job_id} finished: Loop exited unexpectedly.")


        crawl_results[job_id] = results
        if job_id in crawl_jobs:
            crawl_jobs[job_id].status = final_status
            crawl_jobs[job_id].pages_crawled = len(visited)
            crawl_jobs[job_id].test_cases_generated = sum(len(page.get("test_cases", [])) for page in results.values())
            crawl_jobs[job_id].accessibility_issues_found = total_accessibility_violations
            crawl_jobs[job_id].total_pages = len(visited)

        end_time_crawl = time.time()
        logger.info(f"Crawl job {job_id} completed in {end_time_crawl - start_time_crawl:.2f} seconds.")


    except Exception as e:
        logger.error(f"Crawl job {job_id} failed critically: {str(e)}", exc_info=True)
        if job_id in crawl_jobs:
            crawl_jobs[job_id].status = "failed"
        crawl_results[job_id] = {"critical_error": str(e)}



@app.post("/api/crawl", response_model=CrawlStatus)
async def start_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    """Start a new crawl job, including accessibility checks."""
    job_id = f"job-{int(time.time())}"

    crawl_jobs[job_id] = CrawlStatus(
        job_id=job_id,
        status="queued",
        pages_crawled=0,
        test_cases_generated=0,
        accessibility_issues_found=0
    )

    logger.info(f"Queueing crawl job {job_id} for URL: {request.url}")

    background_tasks.add_task(
        crawl_website,
        job_id,
        str(request.url),
        request.max_pages,
        request.max_depth,
        request.include_external
    )

    return crawl_jobs[job_id]

@app.get("/api/status/{job_id}", response_model=CrawlStatus)
async def get_job_status(job_id: str):
    """Get the status of a crawl job."""
    if job_id not in crawl_jobs:
        logger.warning(f"Status requested for non-existent job: {job_id}")
        raise HTTPException(status_code=404, detail="Job not found")

    return crawl_jobs[job_id]

@app.get("/api/results/{job_id}")
async def get_job_results(job_id: str):
    """Get the results of a completed crawl job, including test cases and accessibility reports."""
    if job_id not in crawl_jobs:
        logger.warning(f"Results requested for non-existent job: {job_id}")
        raise HTTPException(status_code=404, detail="Job not found")

    status = crawl_jobs[job_id].status
    if status == "queued" or status == "in_progress":
         logger.info(f"Results requested for job {job_id} which is not completed (status: {status})")
         raise HTTPException(status_code=400, detail=f"Job status is '{status}'. Results are not ready yet.")

    if job_id not in crawl_results:
         logger.warning(f"Results not found for job {job_id}, although job entry exists (status: {status})")
         return {"status_info": crawl_jobs[job_id].dict(), "results": {}, "message": "No results were generated for this job."}


    logger.info(f"Returning results for completed job {job_id}")
    return crawl_results[job_id]


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "name": "Web Crawler, Accessibility Checker and Test Case Generator Service",
        "version": "1.1.0",
        "description": "Crawls websites, generates UI test cases (XPath/CSS), and performs accessibility checks using Axe-core via Puppeteer.",
        "endpoints": {
            "start_crawl": {
                "method": "POST",
                "path": "/api/crawl",
                "body": CrawlRequest.schema_json(indent=2),
                "response": CrawlStatus.schema_json(indent=2)
             },
            "get_status": {
                "method": "GET",
                "path": "/api/status/{job_id}",
                "response": CrawlStatus.schema_json(indent=2)
                },
            "get_results": {
                "method": "GET",
                "path": "/api/results/{job_id}",
                "response": "Dictionary containing crawled page data, test cases, and accessibility reports."
                }
        },
        "requirements": [
            "Python 3.7+",
            "FastAPI, Pydantic, Requests, BeautifulSoup4, lxml, uvicorn",
            "Node.js and npm (or yarn)",
            "Run 'npm install puppeteer @axe-core/puppeteer' in the project directory"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    if not os.path.exists(ACCESSIBILITY_CHECKER_SCRIPT):
        print(f"ERROR: Accessibility checker script not found at: {ACCESSIBILITY_CHECKER_SCRIPT}")
        print("Please create 'accessibility_checker.js' and run 'npm install puppeteer @axe-core/puppeteer'")

    print(f"Node executable configured as: {NODE_EXECUTABLE}")
    print(f"Accessibility checker script path: {ACCESSIBILITY_CHECKER_SCRIPT}")
    uvicorn.run(app, host="0.0.0.0", port=8000)