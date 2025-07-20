import requests
import random
import time
import re
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
from selenium.common.exceptions import WebDriverException, TimeoutException

from .url_utils import fetch_url_with_retries, get_croma_product_urls

# -------------------- USER AGENTS --------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.110 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.5481.177 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.5672.124 Safari/537.36",
]

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# -------------------- HEADLESS BROWSER --------------------
def init_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    options.page_load_strategy = 'eager'  # Don't wait for all resources to load
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)  # Set page load timeout
    driver.set_script_timeout(30)     # Set script timeout
    return driver

# -------------------- HTML CLEANING --------------------
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

def extract_reviews(soup):
    reviews = []
    
    # Look for review containers based on the HTML structure provided
    review_containers = soup.find_all("div", class_="rd-feedback-service-review-container")
    
    logger.info(f"Found {len(review_containers)} review containers")
    
    # Extract overall rating if available
    overall_rating = "N/A"
    rating_header = soup.find("div", class_="rd-feedback-service-rating-overall-header")
    if rating_header:
        rating_text = rating_header.get_text().strip()
        rating_match = re.search(r'(\d+(\.\d+)?)', rating_text)
        if rating_match:
            overall_rating = rating_match.group(1)
    
    # Count total number of reviews
    num_reviews = len(review_containers)
    
    # Process each review
    for container in review_containers:
        try:
            # Get review title
            title_element = container.find("div", class_="rd-feedback-service-review-row-title")
            title = clean_html_text(title_element.get_text()) if title_element else "N/A"
            
            # Get review description/content
            description_element = container.find("div", class_="rd-feedback-service-review-row-description")
            description = clean_html_text(description_element.get_text()) if description_element else "N/A"
            
            # Get individual rating if available
            # This might need adjustment based on the actual HTML structure
            rating = "N/A"
            
            # Get reviewer name or info if available
            reviewer_info = "Anonymous"
            
            # Get review date if available
            review_date = "N/A"
            
            reviews.append({
                "title": title,
                "description": description,
                "rating": rating,
                "reviewer": reviewer_info,
                "date": review_date
            })
            
            logger.debug(f"Extracted review: {title}")
            
        except Exception as e:
            logger.error(f"Error extracting review: {str(e)}")
            continue
    
    return {
        "overall_rating": overall_rating,
        "num_reviews": str(num_reviews),
        "reviews": reviews
    }

# -------------------- SCRAPE CROMA PRODUCT PAGE --------------------
def scrape_croma_product_page(product_name, max_retries=3):
    logger.info(f"Searching Croma for: {product_name}")
    
    # Get product URLs from search results
    product_urls = get_croma_product_urls(product_name)
    if not product_urls:
        logger.warning(f"No products found for: {product_name}")
        return []
    
    results = []
    driver = None
    
    try:
        driver = init_driver()
        
        for product_url in product_urls:
            retry_count = 0
            while retry_count < max_retries:
                try:
                    logger.info(f"Scraping product page: {product_url} (attempt {retry_count + 1}/{max_retries})")
                    driver.get(product_url)

                    # Wait for body with increased timeout
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
                    )
                    
                    # Wait for reviews with shorter timeout
                    try:
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, 
                            "div[class*='ReviewContainer'], div[id*='review']"))
                        )
                    except TimeoutException:
                        logger.warning(f"Timeout waiting for reviews on {product_url} - continuing anyway")

                    time.sleep(2)

                    try:
                        see_more_buttons = driver.find_elements(By.XPATH, 
                            "//button[contains(text(), 'See more')] | //a[contains(text(), 'See more reviews')]")
                        for button in see_more_buttons[:1]:
                            driver.execute_script("arguments[0].click();", button)
                            time.sleep(1)
                    except Exception as e:
                        logger.debug(f"No review expansion needed or error expanding: {str(e)}")
                    
                    soup = BeautifulSoup(driver.page_source, 'html.parser')

                    # Product name
                    name = "N/A"
                    title_tag = soup.find("meta", property="og:title")
                    if title_tag and title_tag.get("content"):
                        name = clean_html_text(title_tag["content"])
                    else:
                        h1_tag = soup.find("h1")
                        name = clean_html_text(h1_tag.text) if h1_tag else "N/A"

                    # Description
                    description = "N/A"
                    desc_meta = soup.find("meta", attrs={'name': 'description'})
                    if desc_meta and desc_meta.get("content"):
                        description = clean_html_text(desc_meta["content"])
                    else:
                        # Try to find product description in the page
                        desc_div = soup.find("div", class_="product-description") or soup.find("div", class_="description")
                        if desc_div:
                            description = clean_html_text(desc_div.get_text())

                    # Price, Image, Availability
                    price = smart_extract_price(soup)
                    image_url = smart_extract_image(soup)
                    availability = "In Stock" if "out of stock" not in soup.get_text().lower() else "Out of Stock"
                    
                    # Extract reviews
                    review_data = extract_reviews(soup)

                    product_details = {
                        "name": name,
                        "price": price,
                        "rating": review_data["overall_rating"],
                        "num_reviews": review_data["num_reviews"],
                        "availability": availability,
                        "image_url": image_url,
                        "description": description,
                        "reviews": review_data["reviews"]
                    }

                    results.append((product_details, product_url))
                    logger.info(f"Successfully scraped product: {name} with {review_data['num_reviews']} reviews")
                    break  # Success, exit retry loop

                except TimeoutException as e:
                    logger.warning(f"Timeout error on {product_url} (attempt {retry_count + 1}/{max_retries}): {str(e)}")
                    retry_count += 1
                    if retry_count == max_retries:
                        logger.error(f"Max retries reached for {product_url}")
                        break
                    time.sleep(2)  # Wait before retry
                    
                except WebDriverException as e:
                    logger.error(f"WebDriver error on {product_url}: {str(e)}")
                    retry_count += 1
                    if retry_count == max_retries:
                        break
                    time.sleep(2)  # Wait before retry
                    
                except Exception as e:
                    logger.error(f"Unexpected error on {product_url}: {str(e)}")
                    retry_count += 1
                    if retry_count == max_retries:
                        break
                    time.sleep(2)  # Wait before retry
                
    except Exception as e:
        logger.error(f"Fatal error in scraper: {str(e)}")
        
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.error(f"Error closing driver: {str(e)}")
    
    return results