from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.contrib.auth.models import User

class Product(models.Model):
    name = models.CharField(max_length=200)
    url = models.URLField(unique=True)
    image_url = models.URLField(blank=True, null=True)
    current_price = models.DecimalField(max_digits=12, decimal_places=2)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
    
    def __str__(self):
        return f"{self.name}"

class AmazonProduct(Product):
    asin = models.CharField(max_length=10, unique=True)
    platform = models.CharField(max_length=20, default='amazon')

class FlipkartProduct(Product):
    flipkart_id = models.CharField(max_length=50, unique=True)
    platform = models.CharField(max_length=20, default='flipkart')

class PriceHistory(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    product = GenericForeignKey('content_type', 'object_id')
    price = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.product.name} - ₹{self.price} at {self.timestamp}"

class TrackedProduct(models.Model):
    name = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class ScrapedProduct(models.Model):
    name = models.CharField(max_length=500)
    url = models.URLField(max_length=1000,unique=True)
    description = models.TextField(blank=True, null=True)
    reviews = models.TextField(blank=True, null=True) 
    image_url = models.URLField(max_length=1000, blank=True, null=True)
    store = models.CharField(max_length=50)  # amazon, flipkart, croma, etc.
    scraped_at = models.DateTimeField(auto_now_add=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)
    
    class Meta:
        ordering = ['-scraped_at']
        indexes = [
            models.Index(fields=['store']),
            models.Index(fields=['scraped_at']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.store} - {self.scraped_at}"
    
class PriceOfProductsHistory(models.Model):
    url = models.ForeignKey(ScrapedProduct,on_delete=models.CASCADE,to_field='url',db_column='url')# This specifies we're referencing the 'url' fielddb_column='url')
    price = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['url']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.url} - ₹{self.price} at {self.timestamp}"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    dark_mode = models.BooleanField(default=False)
    price_alert_threshold = models.IntegerField(default=10)  # Percentage
    theme_color = models.CharField(max_length=100, default='linear-gradient(90deg, #6366f1, #f472b6)')
    
    def __str__(self):
        return f"{self.user.username}'s Profile"

# Signal to create user profile when user is created
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)

# Add after ScrapedProduct model
class ReviewAnalysis(models.Model):
    url = models.ForeignKey(
        ScrapedProduct, 
        on_delete=models.CASCADE, 
        to_field='url', 
        db_column='url',
        primary_key=True
    )
    summary = models.TextField(blank=True, null=True)
    pros = models.TextField(blank=True, null=True)
    cons = models.TextField(blank=True, null=True)
    analyzed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-analyzed_at']
        indexes = [
            models.Index(fields=['analyzed_at']),
        ]
    
    def __str__(self):
        return f"Analysis for {self.url.name} at {self.analyzed_at}"

# Add this signal after existing signals
@receiver(post_save, sender=ScrapedProduct)
def analyze_product_reviews(sender, instance, created, **kwargs):
    from tracker.scrapers.summary_and_pros_cons import analyze_reviews
    
    MIN_REVIEW_LENGTH = 100  # Minimum characters required for analysis
    
    if instance.reviews:  # Only analyze if reviews exist
        # Convert reviews string to list if needed
        reviews_list = [instance.reviews] if isinstance(instance.reviews, str) else instance.reviews
        
        # Calculate total length of all reviews
        total_length = sum(len(str(review)) for review in reviews_list)
        
        if total_length < MIN_REVIEW_LENGTH:
            print(f"Skipping analysis for {instance.name}: Not enough review content ({total_length} chars)")
            return
            
        try:
            # Analyze reviews
            summary, pros, cons = analyze_reviews(reviews_list)
            
            # Store or update analysis
            ReviewAnalysis.objects.update_or_create(
                url=instance,
                defaults={
                    'summary': summary,
                    'pros': pros,
                    'cons': cons
                }
            )
        except Exception as e:
            print(f"Failed to analyze reviews for {instance.name}: {str(e)}")

class SavedProduct(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product_name = models.CharField(max_length=255)
    image_url = models.URLField()
    product_url = models.URLField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    store_name = models.CharField(max_length=100)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product_url')  # Prevent duplicate saves

    def _str_(self):
        return f"{self.product_name} - {self.user.username}"

class PriceAlert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='price_alerts')
    product_url = models.URLField()
    product_name = models.CharField(max_length=255)
    current_price = models.DecimalField(max_digits=10, decimal_places=2)
    target_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'product_url')
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['product_url']),
        ]

    def __str__(self):
        return f"{self.product_name} - Target: ₹{self.target_price}"