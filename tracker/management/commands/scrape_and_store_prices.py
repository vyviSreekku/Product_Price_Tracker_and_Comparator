from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from tracker.models import AmazonProduct, FlipkartProduct, PriceHistory
from tracker.scrapers.amazon import scrape_amazon_products
from tracker.scrapers.flipkart import scrape_flipkart_products
from decimal import Decimal, InvalidOperation
import re
import json

class Command(BaseCommand):
    help = "Scrape Amazon and Flipkart prices and store in database"

    def add_arguments(self, parser):
        parser.add_argument('product_name', type=str, help="Name of the product to search for")

    def handle(self, *args, **kwargs):
        product_name = kwargs['product_name'].strip()
        self.stdout.write(f"Scraping prices for: {product_name}")
        amazon_results = scrape_amazon_products(product_name)
        self.process_results(amazon_results, 'amazon', product_name)
        flipkart_results = scrape_flipkart_products(product_name)
        self.process_results(flipkart_results, 'flipkart', product_name)

    def process_results(self, results, platform, product_name):
        for details, url in results:
            try:
                product_id = None
                if platform == 'amazon':
                    match = re.search(r'/dp/([A-Z0-9]{10})', url)
                    if match:
                        product_id = match.group(1)
                elif platform == 'flipkart':
                    match = re.search(r'pid=([a-zA-Z0-9]+)', url, re.IGNORECASE)
                    if match:
                        product_id = match.group(1)
                if not product_id:
                    self.stdout.write(self.style.WARNING(f"No product ID found in URL: {url}"))
                    continue
                price = details.get('price', 'N/A')
                if price == 'N/A':
                    self.stdout.write(self.style.WARNING(f"No price found for {url}"))
                    continue
                price = re.sub(r'[^\d.]', '', str(price))
                try:
                    price_decimal = Decimal(price)
                except (ValueError, InvalidOperation):
                    self.stdout.write(self.style.WARNING(f"Invalid price format for {url}"))
                    continue
                if platform == 'amazon':
                    product, created = AmazonProduct.objects.get_or_create(
                        asin=product_id,
                        defaults={
                            'name': details.get('name', 'Unknown Product'),
                            'url': url,
                            'image_url': details.get('image_url', ''),
                            'current_price': price_decimal
                        }
                    )
                else:
                    product, created = FlipkartProduct.objects.get_or_create(
                        flipkart_id=product_id,
                        defaults={
                            'name': details.get('name', 'Unknown Product'),
                            'url': url,
                            'image_url': details.get('image_url', ''),
                            'current_price': price_decimal
                        }
                    )
                if not created:
                    product.current_price = price_decimal
                    product.name = details.get('name', product.name)
                    product.image_url = details.get('image_url', product.image_url)
                    product.save()
                content_type = ContentType.objects.get_for_model(product)
                PriceHistory.objects.create(
                    content_type=content_type,
                    object_id=product.id,
                    price=price_decimal
                )
                self.stdout.write(self.style.SUCCESS(f"Saved price ₹{price_decimal} for {product.name} ({platform})"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing {url}: {str(e)}"))