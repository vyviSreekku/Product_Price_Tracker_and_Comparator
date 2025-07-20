from django.core.management.base import BaseCommand
import json
from tracker.scrapers.amazon import scrape_amazon_products
from tracker.scrapers.flipkart import scrape_flipkart_products
from tracker.scrapers.reliance import scrape_reliance_product_page
from tracker.scrapers.brand import get_brand_product_details
from tracker.scrapers.croma import scrape_croma_product_page  # 👈 Import Croma scraper

class Command(BaseCommand):
    help = "Scrape Amazon, Flipkart, Reliance, Croma or Brand for up to 5 product results"

    def add_arguments(self, parser):
        parser.add_argument("platform", type=str, help="Platform to scrape (Amazon, Flipkart, Reliance, Croma, or Brand)")
        parser.add_argument("product_name", type=str, help="Name of the product to search for")

    def handle(self, *args, **kwargs):
        platform = kwargs["platform"].lower()
        product_name = kwargs["product_name"].strip()

        if platform == "amazon":
            details = scrape_amazon_products(product_name)
        elif platform == "flipkart":
            details = scrape_flipkart_products(product_name)
        elif platform == "reliance":
            details = scrape_reliance_product_page(product_name)
        elif platform == "croma":
            details = scrape_croma_product_page(product_name)  # 👈 Add Croma logic
        elif platform == "brand":
            details = get_brand_product_details(product_name)
        else:
            self.stdout.write(self.style.ERROR("❌ Invalid platform. Use 'Amazon', 'Flipkart', 'Reliance', 'Croma', or 'Brand'."))
            return

        output = []

        if isinstance(details, list) and all(isinstance(item, tuple) and len(item) == 2 for item in details):
            for item_details, url in details:
                output.append({
                    "platform": platform,
                    "product_name": product_name,
                    "details": item_details,
                    "url": url,
                })
        else:
            output.append({
                "platform": platform,
                "product_name": product_name,
                "error": "Invalid data format returned from scraper.",
            })

        self.stdout.write(json.dumps(output, indent=2))