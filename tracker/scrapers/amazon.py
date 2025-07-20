from selectorlib import Extractor
from .url_utils import fetch_url_with_retries, get_amazon_product_urls
import logging

# Configure logging
logger = logging.getLogger('amazon_scraper')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def get_amazon_extractor():
    return Extractor.from_yaml_string("""
    product_name:
        css: 'span#productTitle'
        type: Text

    price:
        css: 'span.a-price span.a-offscreen'
        type: Text

    rating:
        css: 'span.a-icon-alt'
        type: Text

    num_reviews:
        css: 'span#acrCustomerReviewText'
        type: Text

    availability:
        css: 'div#availability span'
        type: Text

    image:
        css: 'img#landingImage'
        type: Attribute
        attribute: src
                                      
    description:
        css: 'div#productDescription p, div#feature-bullets ul li'
        multiple: true
        type: Text
                                      
    reviews:
        css: 'div.review-text-content span'
        multiple: true
        type: Text
    """)

def extract_product_data(url, extractor):
    """Extract product data from the given URL using the extractor."""
    response = fetch_url_with_retries(url)
    if not response:
        logger.warning(f"Failed to fetch URL: {url}")
        return None

    data = extractor.extract(response.text) or {}
    product_details = {
        "name": data.get("product_name", "N/A").strip() if data.get("product_name") else "N/A",
        "price": data.get("price", "N/A").strip() if data.get("price") else "N/A",
        "rating": data.get("rating", "N/A").strip() if data.get("rating") else "N/A",
        "num_reviews": data.get("num_reviews", "N/A").strip() if data.get("num_reviews") else "N/A",
        "availability": data.get("availability", "N/A").strip() if data.get("availability") else "N/A",
        "image_url": data.get("image", "N/A").strip() if data.get("image") else "N/A",
        "description": " ".join([desc.strip() for desc in (data.get("description") or []) if desc.strip()]) or "No description available.",
        "reviews": [review.strip() for review in (data.get("reviews") or []) if review.strip()] or ["No reviews available."],
    }
    return product_details

def scrape_amazon_products(product_name):
    extractor = get_amazon_extractor()
    product_urls = get_amazon_product_urls(product_name)
    results = []

    for url in product_urls:
        product_data = extract_product_data(url, extractor)
        if product_data:
            results.append((product_data, url))

    logger.info(f"Scraped {len(results)} products for '{product_name}'")
    return results