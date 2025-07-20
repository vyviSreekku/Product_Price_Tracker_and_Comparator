
# tracker/scrapers/brand.py

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse, quote_plus
from bs4 import BeautifulSoup
import time
import random
import re

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.110 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.5481.177 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.5672.124 Safari/537.36",
]

def init_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    return webdriver.Chrome(options=options)

def extract_domain_from_url(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        return domain.replace("www.", "")
    except Exception:
        return None

def search_bing_for_brand_link(product_name):
    query = f"{product_name} official store"
    search_url = f"https://www.bing.com/search?q={quote_plus(query)}"

    driver = init_driver()
    driver.get(search_url)
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()

    results = soup.select("li.b_algo a[href]")

    for a_tag in results:
        href = a_tag['href']
        domain = extract_domain_from_url(href)
        if domain and 'amazon' not in domain and 'flipkart' not in domain:
            return href, domain

    return None, None

def smart_extract_image(soup):
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        return og_image["content"]

    containers = soup.select("main img, article img, div.product img, section img")
    bad_keywords = ['logo', 'icon', 'sprite', 'placeholder', 'banner', 'facebook', 'twitter', 'pixel', '1x1']
    for img in containers:
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if src and not any(bad in src.lower() for bad in bad_keywords):
            if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                return src

    for img in soup.find_all('img'):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if src and not any(bad in src.lower() for bad in bad_keywords):
            if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                return src

    return "N/A"

def is_valid_price(text):
    return bool(re.search(r'(₹|\$)\s?\d[\d,]*(\.\d{1,2})?', text))

def clean_html_text(text):
    if not text or any(tag in text for tag in ['<', '{', '}', 'function', 'style', '</']):
        return None
    return text.strip()

def smart_extract_price(soup):
    price_meta = soup.find("meta", {"property": "product:price:amount"}) or soup.find("meta", {"name": "price"})
    if price_meta and price_meta.get("content"):
        content = clean_html_text(price_meta["content"])
        if content and is_valid_price(content):
            return content

    keywords = ['price', 'cost', 'amount', 'value']
    for tag in soup.find_all():
        class_list = tag.get('class', [])
        if any(k in ' '.join(class_list).lower() for k in keywords):
            text = clean_html_text(tag.get_text(strip=True))
            if text and is_valid_price(text):
                return text

    for tag in soup.find_all():
        text = clean_html_text(tag.get_text(strip=True))
        if text and is_valid_price(text):
            return text

    return "N/A"

def scrape_brand_product_page(brand_url, product_name):
    driver = init_driver()
    driver.get(brand_url)

    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except Exception:
        pass

    time.sleep(3)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()

    title_tag = soup.find('h1') or soup.find('title')
    name = clean_html_text(title_tag.text) if title_tag else product_name
    if not name or len(name) > 100:
        name = product_name

    price = smart_extract_price(soup)

    description_tag = soup.find('meta', attrs={'name': 'description'})
    description = clean_html_text(description_tag['content']) if description_tag else 'N/A'
    if not description:
        description = 'N/A'

    image_url = smart_extract_image(soup)
    if image_url.startswith('//'):
        parsed_url = urlparse(brand_url)
        image_url = f"{parsed_url.scheme}:{image_url}"
    elif image_url.startswith('/'):
        parsed_url = urlparse(brand_url)
        image_url = f"{parsed_url.scheme}://{parsed_url.netloc}{image_url}"

    rating = "N/A"
    availability = "In Stock" if "out of stock" not in soup.get_text().lower() else "Out of Stock"
    reviews = []

    product_details = {
        "name": name,
        "price": price,
        "rating": rating,
        "num_reviews": str(len(reviews)) if reviews else "0",
        "availability": availability,
        "image_url": image_url,
        "reviews": reviews,
        "description": description,
    }

    results = [(product_details, brand_url)]
    return results

def get_brand_product_details(product_name):
    print(f"🔍 Searching Bing for: {product_name}")
    brand_link, domain = search_bing_for_brand_link(product_name)
    if brand_link and domain:
        print(f"✅ Found brand link: {brand_link}")
        print(f"🌐 Domain detected: {domain}")
        return scrape_brand_product_page(brand_link, product_name)
    else:
        return {'error': 'No brand link found on Bing'}
