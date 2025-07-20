from django.core.management.base import BaseCommand
from django.core.management import call_command
from tracker.models import TrackedProduct, SavedProduct, PriceAlert
from django.utils import timezone
from datetime import timedelta
import logging
from tracker.scrapers.email_sender import EmailSender

logger = logging.getLogger(__name__)
email_sender = EmailSender()

class Command(BaseCommand):
    help = 'Updates prices for all tracked products and checks price alerts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update all products regardless of last update time',
        )

    def handle(self, *args, **options):
        force_update = options['force']
        tracked_products = TrackedProduct.objects.all()
        
        # If not forcing update, only update products that haven't been updated in the last 1   hours
        if not force_update:
            one_hours_ago = timezone.now() - timedelta(hours=1)
            tracked_products = tracked_products.filter(
                last_updated__lt=one_hours_ago
            )

        total_products = tracked_products.count()
        self.stdout.write(f"Updating prices for {total_products} tracked products...")

        for tracked_product in tracked_products:
            try:
                self.stdout.write(f"Updating prices for: {tracked_product.name}")                # Update prices
                call_command('scrape_and_store_prices', tracked_product.name)
                tracked_product.last_updated = timezone.now()
                tracked_product.save()
                self.stdout.write(self.style.SUCCESS(f"Successfully updated prices for: {tracked_product.name}"))

                # Check price alerts after updating prices
                try:
                    # Get all active alerts for this product
                    alerts = PriceAlert.objects.filter(
                        product_name=tracked_product.name,
                        is_active=True
                    )

                    # Check each alert
                    for alert in alerts:
                        try:
                            # Get current price from saved product
                            saved_product = SavedProduct.objects.get(product_url=alert.product_url)
                            current_price = saved_product.price

                            # Update current price in alert
                            alert.current_price = current_price
                            alert.save()                            # Check if target price has been reached
                            if current_price <= alert.target_price:
                                # Send email notification
                                email_sender.send_price_alert(
                                    alert.user.email,
                                    alert.product_name,
                                    current_price,
                                    alert.target_price,
                                    alert.product_url
                                )
                                self.stdout.write(self.style.SUCCESS(
                                    f"Price alert triggered for {alert.product_name} - "
                                    f"Current: ₹{current_price}, Target: ₹{alert.target_price}"
                                ))
                        except SavedProduct.DoesNotExist:
                            continue
                        except Exception as alert_error:
                            logger.error(f"Error processing alert for {alert.product_name}: {str(alert_error)}")
                except Exception as e:
                    logger.error(f"Error checking price alerts for {tracked_product.name}: {str(e)}")
            except Exception as e:
                logger.error(f"Error updating prices for {tracked_product.name}: {str(e)}")
                self.stdout.write(self.style.ERROR(f"Failed to update prices for: {tracked_product.name}"))

        self.stdout.write(self.style.SUCCESS(f"Completed price updates for {total_products} products")) 