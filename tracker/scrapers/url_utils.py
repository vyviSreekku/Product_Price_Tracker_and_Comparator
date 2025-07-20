import requests
import random
import time
import re
from urllib.parse import quote_plus
import html
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
from selenium.common.exceptions import WebDriverException, TimeoutException
# User-Agent rotation to avoid detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.110 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.5481.177 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.5672.124 Safari/537.36",
]

session = requests.Session()

def init_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.page_load_strategy = 'eager'  # Don't wait for all resources to load
    return webdriver.Chrome(options=options)

def fetch_url_with_retries(url, max_retries=5):
    delay = 2  # Initial delay
    for attempt in range(max_retries):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Connection": "keep-alive",
            "Referer": "https://www.google.com/",
        }
        try:
            response = session.get(url, headers=headers, timeout=10)
            if response.status_code == 503:
                print(f"⚠️ 503 Error (Attempt {attempt+1}/{max_retries}). Retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
                continue
            if response.status_code == 200:
                return response
            print(f"❌ Unexpected Status Code: {response.status_code}")
            return None
        except requests.exceptions.RequestException as err:
            print(f"❌ Request Error: {err}")
            time.sleep(delay)
            delay *= 2
    print("❌ Max retries reached. Skipping request.")
    return None

def get_amazon_product_urls(product_name, max_results=5):
    search_url = f"https://www.amazon.in/s?k={quote_plus(product_name)}"
    response = fetch_url_with_retries(search_url)
    if not response:
        return []
    matches = re.findall(r'/dp/([A-Z0-9]{10})', response.text)
    seen = set()
    urls = []
    for match in matches:
        if match not in seen:
            seen.add(match)
            urls.append(f"https://www.amazon.in/dp/{match}")
        if len(urls) == max_results:
            break
    return urls

def get_flipkart_product_urls(product_name, max_results=5):
    search_url = f"https://www.flipkart.com/search?q={quote_plus(product_name)}"
    response = fetch_url_with_retries(search_url)
    if not response:
        return []
    matches = re.findall(r'href="(/[a-zA-Z0-9\-]+/p/[a-zA-Z0-9]+)', response.text)
    seen = set()
    urls = []
    for match in matches:
        if match not in seen:
            seen.add(match)
            urls.append(f"https://www.flipkart.com{match}")
        if len(urls) == max_results:
            break
    return urls

def get_reliance_product_urls(product_name, max_results=5):
    search_url = f"https://www.reliancedigital.in/products?q={quote_plus(product_name)}"
    response = fetch_url_with_retries(search_url)
    if not response:
        return []
    
    # Look for structured JSON-LD data
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find JSON-LD scripts
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    urls = []
    
    for script in json_ld_scripts:
        try:
            # Try to parse the JSON content
            if script.string and 'ItemList' in script.string:
                import json
                data = json.loads(script.string)
                
                # Check if this is the product listing JSON
                if data.get('@type') == 'ItemList' and 'itemListElement' in data:
                    for item in data['itemListElement']:
                        if item.get('@type') == 'ListItem' and 'url' in item:
                            # Fix URL by decoding HTML entities
                            url = html.unescape(item['url'])
                            
                            # Make sure it's a full URL
                            if url.startswith('www.'):
                                url = 'https://' + url
                            
                            urls.append(url)
                            if len(urls) >= max_results:
                                return urls
        except Exception as e:
            print(f"Error parsing JSON-LD: {e}")
    
    # Fallback to the original regex method
    if not urls:
        matches = re.findall(r'href="(/product/[^\"]+)"', response.text)
        seen = set()
        for match in matches:
            if match not in seen:
                seen.add(match)
                urls.append(f"https://www.reliancedigital.in{match}")
            if len(urls) == max_results:
                break
    
    return urls

def get_croma_product_urls(product_name, max_results=5, max_retries=3):
    encoded_product = quote_plus(product_name)
    search_url = f"https://www.croma.com/searchB?q={encoded_product}%3Arelevance&text={encoded_product}"
    print("Search URL:", search_url)

    driver = None
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            driver = init_driver()
            driver.get(search_url)
            
            # Wait for products to load with increased timeout
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CLASS_NAME, "product-list"))
            )
            
            # Grab the page source after content has been dynamically loaded
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            urls = []
            seen = set()
            
            # Find product links using CSS class or tag
            product_links = soup.find_all('a', href=re.compile(r"^/.*?/p/"))
            print(f"Found {len(product_links)} <a> tags.")
            
            for tag in product_links:
                href = tag.get("href")
                if href and href not in seen:
                    full_url = f"https://www.croma.com{href}"
                    seen.add(href)
                    urls.append(full_url)
                if len(urls) >= max_results:
                    break
            
            if urls:
                print(f"Extracted product links: {urls[:5]}")
                return urls
            else:
                print("No product links found in <a> tags.")
                return []
                
        except TimeoutException as e:
            print(f"Timeout error (attempt {retry_count + 1}/{max_retries}): {str(e)}")
            retry_count += 1
            if retry_count == max_retries:
                print("Max retries reached. Could not load the page.")
                return []
                
        except Exception as e:
            print(f"Error during scraping (attempt {retry_count + 1}/{max_retries}): {str(e)}")
            retry_count += 1
            if retry_count == max_retries:
                print("Max retries reached. Could not load the page.")
                return []
                
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    print(f"Error closing driver: {str(e)}")
    
    return []