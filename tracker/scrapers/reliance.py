import requests
import random
import time
import re
import logging
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException

from .url_utils import fetch_url_with_retries, get_reliance_product_urls

# -------------------- USER AGENTS --------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.110 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.5481.177 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.5672.124 Safari/537.36",
]

# -------------------- LOGGER --------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# -------------------- DRIVER INIT --------------------
def init_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    return webdriver.Chrome(options=options)

# -------------------- UTILITY FUNCTIONS --------------------
def clean_html_text(text):
    if not text or any(tag in text for tag in ['<', '{', '}', 'function', 'style', '</']):
        return None
    return text.strip()

def is_valid_price(text):
    return bool(re.search(r'(₹|\$)\s?\d[\d,]*(\.\d{1,2})?', text))

def smart_extract_price(soup):
    meta_price = soup.find("meta", {"property": "product:price:amount"}) or soup.find("meta", {"itemprop": "price"})
    if meta_price and meta_price.get("content"):
        content = clean_html_text(meta_price["content"])
        if content and content.replace(",", "").replace(".", "").isdigit():
            return f"₹{content}"
    price_candidates = soup.find_all(string=re.compile(r'(₹|\$)\s?\d[\d,]*'))
    for price_text in price_candidates:
        if is_valid_price(price_text):
            return price_text.strip()
    return "N/A"

def smart_extract_image(soup):
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        return og_image["content"]
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if src and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            return src
    return "N/A"

# -------------------- REVIEWS --------------------
def extract_reviews(soup):
    reviews = []
    review_containers = soup.find_all("div", class_="rd-feedback-service-review-container")
    logger.info(f"Found {len(review_containers)} review containers")

    overall_rating = "N/A"
    rating_header = soup.find("div", class_="rd-feedback-service-rating-overall-header")
    if rating_header:
        rating_text = rating_header.get_text().strip()
        rating_match = re.search(r'(\d+(\.\d+)?)', rating_text)
        if rating_match:
            overall_rating = rating_match.group(1)

    for container in review_containers:
        try:
            title_element = container.find("div", class_="rd-feedback-service-review-row-title")
            title = clean_html_text(title_element.get_text()) if title_element else "N/A"

            description_element = container.find("div", class_="rd-feedback-service-review-row-description")
            description = clean_html_text(description_element.get_text()) if description_element else "N/A"

            reviews.append({
                "title": title,
                "description": description,
                "rating": "N/A",
                "reviewer": "Anonymous",
                "date": "N/A"
            })

        except Exception as e:
            logger.error(f"Error extracting review: {str(e)}")

    return {
        "overall_rating": overall_rating,
        "num_reviews": str(len(review_containers)),
        "reviews": reviews
    }

# -------------------- SCRAPE ONE PRODUCT --------------------
def scrape_single_product(product_url):
    driver = init_driver()
    try:
        logger.info(f"Scraping product page: {product_url}")
        driver.get(product_url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )

        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='rd-feedback-service-review'], div[id='review']"))
            )
        except TimeoutException:
            logger.warning(f"Timeout waiting for review section: {product_url}")

        time.sleep(2)

        try:
            see_more_buttons = driver.find_elements(By.XPATH,
                "//button[contains(text(), 'See more')] | //a[contains(text(), 'See more reviews')]")
            for button in see_more_buttons[:1]:
                driver.execute_script("arguments[0].click();", button)
                time.sleep(1)
        except Exception as e:
            logger.debug(f"No review expansion or error: {str(e)}")

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        title_tag = soup.find("meta", property="og:title")
        name = clean_html_text(title_tag["content"]) if title_tag else clean_html_text(soup.find("h1").text if soup.find("h1") else "N/A")

        desc_meta = soup.find("meta", attrs={'name': 'description'})
        description = clean_html_text(desc_meta["content"]) if desc_meta else "N/A"

        price = smart_extract_price(soup)
        image_url = smart_extract_image(soup)
        availability = "In Stock" if "out of stock" not in soup.get_text().lower() else "Out of Stock"

        review_data = extract_reviews(soup)

        product_details = {
            "name": name,
            "description": description,
            "price": price,
            "rating": review_data["overall_rating"],
            "num_reviews": review_data["num_reviews"],
            "availability": availability,
            "image_url": image_url,
            "reviews": review_data["reviews"]
        }

        logger.info(f"Successfully scraped: {name}")
        return (product_details, product_url)

    except Exception as e:
        logger.error(f"Failed to scrape {product_url}: {str(e)}")
        return None
    finally:
        driver.quit()

# -------------------- MAIN SCRAPER WITH CONCURRENCY --------------------
def scrape_reliance_product_page(product_name, max_threads=4):
    logger.info(f"Searching for: {product_name}")
    product_urls = get_reliance_product_urls(product_name)
    if not product_urls:
        logger.warning("No product URLs found")
        return []

    results = []
    with ThreadPoolExecutor(max_workers=min(max_threads, len(product_urls))) as executor:
        future_to_url = {executor.submit(scrape_single_product, url): url for url in product_urls}
        for future in as_completed(future_to_url):
            result = future.result()
            if result:
                results.append(result)

    return results