import logging
from selectorlib import Extractor
from .url_utils import fetch_url_with_retries, get_flipkart_product_urls

# Configure logger
logger = logging.getLogger('tracker')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def get_flipkart_extractor():
    return Extractor.from_yaml_string("""
    product_name:
        css: 'span.VU-ZEz'
        type: Text

    price:
        css: 'div.UOCQB1'
        type: Text

    rating:
        css: 'span.Y1HWO0'
        type: Text

    num_reviews:
        css: 'span.Wphh3N'
        type: Text

    availability:
        css: 'div._16FRp0'
        type: Text

    image:
        css: 'img.DByuf4.IZexXJ.jLEJ7H'
        type: Attribute
        attribute: src
                
    description:
        css: 'div._1mXcCf, div._1YokD2._3Mn1Gg div._1mXcCf'
        multiple: true
        type: Text

    reviews:
        css: 'div._8-rIO3, div._6K-7Co'
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

def scrape_flipkart_products(product_name):
    extractor = get_flipkart_extractor()
    product_urls = get_flipkart_product_urls(product_name)
    results = []

    for url in product_urls:
        product_data = extract_product_data(url, extractor)
        if product_data:
            results.append((product_data, url))

    logger.info(f"Scraped {len(results)} products for '{product_name}'")
    return results