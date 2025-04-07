from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import crawl4ai
import inspect
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse, urljoin
import logging
import sys
import traceback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('crawler.log')
    ]
)
logger = logging.getLogger(__name__)

logger.info("Available attributes in crawl4ai:")
for attr_name in dir(crawl4ai):
    if not attr_name.startswith('__'):
        attr = getattr(crawl4ai, attr_name)
        attr_type = type(attr).__name__
        logger.info(f"- {attr_name}: {attr_type}")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CrawlRequest(BaseModel):
    url: str

    def validate_url(self):
        parsed = urlparse(self.url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL format")
        if parsed.scheme not in ['http', 'https']:
            raise ValueError("URL must use HTTP or HTTPS protocol")
        return self.url

def generate_test_cases(soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
    test_cases = []
    
    for link in soup.find_all('a'):
        href = link.get('href', '')
        if href:
            # Handle relative URLs
            full_url = urljoin(base_url, href)
            test_cases.append({
                "element_type": "link",
                "selector": f"a[href*='{href}']",
                "test_description": f"Verify link to {full_url}",
                "expected_result": "Link should be clickable and navigate to the correct URL"
            })
    
    for form in soup.find_all('form'):
        action = form.get('action', '')
        method = form.get('method', 'GET').upper()
        inputs = form.find_all('input')
        
        test_cases.append({
            "element_type": "form",
            "selector": f"form[action='{action}']",
            "test_description": f"Test {method} form submission with {len(inputs)} input fields",
            "expected_result": "Form should submit successfully with valid data"
        })
        
        for input_field in inputs:
            input_type = input_field.get('type', 'text')
            input_name = input_field.get('name', '')
            if input_name:
                test_cases.append({
                    "element_type": "input",
                    "selector": f"input[name='{input_name}']",
                    "test_description": f"Test {input_type} input field '{input_name}'",
                    "expected_result": f"Input should accept valid {input_type} data"
                })
    
    for button in soup.find_all(['button', 'input[type="submit"]', 'input[type="button"]']):
        button_type = button.get('type', 'button')
        button_text = button.text.strip() or button.get('value', 'Button')
        test_cases.append({
            "element_type": "button",
            "selector": f"button[type='{button_type}'], input[type='{button_type}']",
            "test_description": f"Test button click: {button_text}",
            "expected_result": "Button should be clickable and perform its intended action"
        })
    
    for select in soup.find_all('select'):
        name = select.get('name', '')
        options = select.find_all('option')
        test_cases.append({
            "element_type": "select",
            "selector": f"select[name='{name}']",
            "test_description": f"Test dropdown with {len(options)} options",
            "expected_result": "Dropdown should be clickable and allow option selection"
        })
    
    return test_cases

class SimpleCrawler:
    def __init__(self, max_depth=2, timeout=30, max_pages=50):
        self.max_depth = max_depth
        self.timeout = timeout
        self.max_pages = max_pages
        self.visited = set()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def crawl(self, start_url):
        self.visited = set()
        self._crawl_recursive(start_url, 0)
        return list(self.visited)
    
    def _crawl_recursive(self, url, depth):
        if depth > self.max_depth or len(self.visited) >= self.max_pages or url in self.visited:
            return
        
        try:
            response = requests.get(url, timeout=self.timeout, headers=self.headers)
            response.raise_for_status()
            self.visited.add(url)
            
            if 'text/html' in response.headers.get('Content-Type', ''):
                soup = BeautifulSoup(response.text, 'html.parser')
                
                if depth < self.max_depth:
                    for link in soup.find_all('a', href=True):
                        next_url = urljoin(url, link['href'])
                        if urlparse(next_url).netloc == urlparse(url).netloc:
                            self._crawl_recursive(next_url, depth + 1)
                            
        except Exception as e:
            logger.warning(f"Error crawling {url}: {str(e)}")

@app.post("/api/crawl")
async def crawl_url(request: CrawlRequest):
    try:
        try:
            url = request.validate_url()
            logger.info(f"Validated URL: {url}")
        except ValueError as e:
            logger.error(f"URL validation error: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            test_response = requests.head(url, timeout=5, headers=headers)
            test_response.raise_for_status()
            logger.info(f"URL is accessible: {url}")
        except requests.RequestException as e:
            logger.error(f"URL accessibility error: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Unable to access the URL: {str(e)}"
            )

        try:
            if hasattr(crawl4ai, 'crawl') and callable(crawl4ai.crawl):
                logger.info("Using crawl4ai.crawl function")
                pages = crawl4ai.crawl(url, max_depth=2, max_pages=50, timeout=30)
                logger.info(f"Successfully crawled {len(pages)} pages using crawl4ai.crawl")
            else:
                logger.info("Using custom crawler implementation")
                crawler = SimpleCrawler(max_depth=2, timeout=30, max_pages=50)
                pages = crawler.crawl(url)
                logger.info(f"Successfully crawled {len(pages)} pages using custom crawler")
        except Exception as e:
            logger.error(f"Crawling error: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Error while crawling: {str(e)}"
            )
        
        all_test_cases = []
        
        for page_url in pages:
            try:
                logger.info(f"Processing page: {page_url}")
                response = requests.get(page_url, timeout=10, headers=headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                page_test_cases = generate_test_cases(soup, page_url)
                all_test_cases.extend(page_test_cases)
                logger.info(f"Generated {len(page_test_cases)} test cases for {page_url}")
            except Exception as e:
                logger.warning(f"Error processing page {page_url}: {str(e)}")
                continue
        
        if not all_test_cases:
            logger.error("No test cases generated")
            raise HTTPException(
                status_code=404,
                detail="No test cases could be generated from the provided URL"
            )
        
        logger.info(f"Total test cases generated: {len(all_test_cases)}")
        return {"testCases": all_test_cases}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI server")
    uvicorn.run(app, host="0.0.0.0", port=8000)