from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.management import call_command
from django.contrib.auth.decorators import login_required
from django.db.models import Min, Max, Avg
from io import StringIO
from datetime import datetime, timedelta
from tracker.models import *
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.db import transaction
from django.views.decorators.http import require_http_methods
from scipy.signal import argrelextrema
from prophet import Prophet
import pandas as pd
import numpy as np
import json
import logging
import re
import concurrent.futures
from .price_prediction_views import predict_future_prices, find_price_dips

logging.basicConfig(filename='scraper.log', level=logging.DEBUG)

def get_scraped_data(platform, query):
    output = StringIO()
    
    try:
        logging.debug(f"Starting scrape for {platform} with query: {query}")
        print(f"\n🔍 Checking database for {platform} products matching: {query}")
        existing_products = ScrapedProduct.objects.filter(
            name__icontains=query,
            store=platform.lower()
        ).order_by('-scraped_at')[:5]

        if existing_products.exists():
            print(f"✅ Found {existing_products.count()} products in database for {platform}")
            formatted_data = []
            for product in existing_products:
                latest_price = PriceOfProductsHistory.objects.filter(
                    url=product
                ).order_by('-timestamp').first()
                
                product_data = {
                    'product_name': product.name,
                    'price': str(latest_price.price) if latest_price else 'N/A',
                    'image_url': product.image_url or '',
                    'rating': str(product.rating) if product.rating is not None else 'N/A',
                    'url': product.url,
                    'description': product.description or ''
                }
                formatted_data.append(product_data)
            print(f"📊 Retrieved latest prices for {len(formatted_data)} products from database")
            logging.debug(f"Retrieved {len(formatted_data)} products from database for {platform}")
            return platform, formatted_data
        
        print(f"❌ No products found in database for {platform}, proceeding with scraping...")
        logging.debug(f"No products found, scraping {platform}")
        call_command('scrape_products', platform, query, stdout=output)
        raw_data = json.loads(output.getvalue())
        logging.debug(f"Raw data for {platform}: {raw_data}")
        
        formatted_data = []
        if isinstance(raw_data, list):
            for item in raw_data:
                if isinstance(item, dict):
                    details = item.get('details', {})
                    url = item.get('url', '')
                    if not url or not details:
                        logging.warning(f"Skipping item with missing url/details: {item}")
                        continue
                    product_data = {
                        'product_name': details.get('name', ''),
                        'price': details.get('price', ''),
                        'image_url': details.get('image_url', ''),
                        'rating': details.get('rating', 'N/A').strip(),
                        'url': url,
                        'description': details.get('description', ''),
                        'reviews': details.get('reviews', [])
                    }
                    if product_data['product_name'] and product_data['url']:
                        formatted_data.append(product_data)
                    
                    try:
                        # Parse price
                        price_str = str(product_data['price'] or '')
                        logging.debug(f"Original price string for {url}: {price_str}")
                        
                        if platform.lower() == 'flipkart':
                            price_str = price_str.split()[0]
                            logging.debug(f"After Flipkart split: {price_str}")
                        
                        price_str = price_str.replace('\u20b9', '').replace('₹', '').replace(',', '').strip()
                        logging.debug(f"Cleaned price string: {price_str}")
                        
                        price = None
                        if price_str and price_str.lower() != 'n/a':
                            try:
                                price_str = ''.join(c for c in price_str if c.isdigit() or c == '.')
                                if price_str.count('.') > 1:
                                    price_str = price_str.rsplit('.', 1)[0]
                                if price_str:  # Ensure string is not empty
                                    price = float(price_str)
                                    logging.debug(f"Converted price: {price}")
                            except ValueError as ve:
                                logging.error(f"Price conversion error for {url}: {ve}")
                        
                        # Parse rating
                        rating_str = product_data.get('rating', 'N/A').strip()
                        rating = None
                        if rating_str.lower() != 'n/a':
                            try:
                                # Extract numeric part (e.g., "4.2" from "4.2 out of 5 stars")
                                match = re.match(r'(\d+\.\d+)', rating_str)
                                if match:
                                    rating = float(match.group(1))
                                    logging.debug(f"Converted rating: {rating}")
                            except ValueError as ve:
                                logging.error(f"Rating conversion error for {url}: {ve}")
                        
                        with transaction.atomic():
                            scraped_product, created = ScrapedProduct.objects.get_or_create(
                                url=url,
                                defaults={
                                    'name': product_data['product_name'],
                                    'description': product_data['description'],
                                    'image_url': product_data['image_url'],
                                    'store': platform.lower(),
                                    'reviews': product_data.get('reviews', []),
                                    'rating': rating  # Store numeric rating or None
                                }
                            )
                            logging.debug(f"ScrapedProduct created: {created}, URL: {url}")
                            if not created:
                                scraped_product.name = product_data['product_name']
                                scraped_product.description = product_data['description']
                                scraped_product.image_url = product_data['image_url']
                                scraped_product.rating = rating
                                scraped_product.reviews = product_data.get('reviews', [])
                                scraped_product.save()
                            if price is not None:
                                PriceOfProductsHistory.objects.create(
                                    url=scraped_product,
                                    price=price
                                )
                                logging.debug(f"Price history saved for {url}: {price}")
                    
                    except Exception as e:
                        logging.error(f"Error storing product {url}: {str(e)}")
        
        return platform, formatted_data
    except json.JSONDecodeError as je:
        logging.error(f"Invalid JSON from scrape_products for {platform}: {str(je)}")
        return platform, []
    except Exception as e:
        logging.error(f"Error scraping {platform}: {str(e)}")
        return platform, []



def home(request):
    return render(request, 'tracker/home.html')

def index(request):
    return render(request, 'tracker/index.html')

def track(request):
    return render(request, 'tracker/track.html')

@csrf_exempt
def search(request):
    if request.method == 'GET':
        query = request.GET.get('q', '').strip()
        if query:
            # Define platforms
            platforms = ['Amazon', 'Flipkart', 'Reliance', 'Brand', 'Croma']

            # Create a dictionary to store results
            results = {}

            # Use ThreadPoolExecutor to run scraping concurrently
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Map get_scraped_data to each platform and query concurrently
                future_to_platform = {executor.submit(get_scraped_data, platform, query): platform for platform in platforms}

                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_platform):
                    platform, result = future.result()
                    results[platform.lower()] = result

            return JsonResponse(results, safe=False)
        else:
            return JsonResponse({'error': 'No query provided'}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
def add_tracked_product(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            product_name = data.get('product_name', '').strip()
            if not product_name:
                return JsonResponse({'error': 'Product name required'}, status=400)
            
            # Create TrackedProduct entry - for demo purposes, use first user or create a dummy user
            user = request.user
            if user.is_anonymous:
                from django.contrib.auth.models import User
                user, created = User.objects.get_or_create(username='demo_user')
            
            # Create or get TrackedProduct entry
            tracked_product, created = TrackedProduct.objects.get_or_create(
                name=product_name,
                user=user
            )
            
            # Scrape and store prices immediately
            call_command('scrape_and_store_prices', product_name)
            
            return JsonResponse({'success': True, 'product_name': product_name})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


def get_tracked_products(request):
    if request.method == 'GET':
        # For demo purposes, use first user or create a dummy user if not authenticated
        user = request.user
        if user.is_anonymous:
            from django.contrib.auth.models import User
            user, created = User.objects.get_or_create(username='demo_user')
            
        tracked_products = TrackedProduct.objects.filter(user=user)
        results = []
        
        for tracked in tracked_products:
            # Only find associated Amazon and Flipkart products
            amazon_products = AmazonProduct.objects.filter(name__icontains=tracked.name)
            flipkart_products = FlipkartProduct.objects.filter(name__icontains=tracked.name)
            
            # Process Amazon products
            for product in amazon_products:
                content_type = ContentType.objects.get_for_model(AmazonProduct)
                history = PriceHistory.objects.filter(
                    content_type=content_type,
                    object_id=product.id
                ).order_by('timestamp')
                
                # Get a subset of history for the card view (last 10 entries)
                display_history = history.order_by('-timestamp')[:10]
                
                results.append({
                    'product_name': product.name,
                    'platform': 'amazon',
                    'product_id': product.asin,
                    'url': product.url,
                    'image_url': product.image_url or '',
                    'current_price': float(product.current_price),
                    'history': [{
                        'price': float(entry.price),
                        'timestamp': entry.timestamp.strftime('%Y-%m-%d')
                    } for entry in display_history]
                })
            
            # Process Flipkart products
            for product in flipkart_products:
                content_type = ContentType.objects.get_for_model(FlipkartProduct)
                history = PriceHistory.objects.filter(
                    content_type=content_type,
                    object_id=product.id
                ).order_by('timestamp')
                
                # Get a subset of history for the card view (last 10 entries)
                display_history = history.order_by('-timestamp')[:10]
                
                results.append({
                    'product_name': product.name,
                    'platform': 'flipkart',
                    'product_id': product.flipkart_id,
                    'url': product.url,
                    'image_url': product.image_url or '',
                    'current_price': float(product.current_price),
                    'history': [{
                        'price': float(entry.price),
                        'timestamp': entry.timestamp.strftime('%Y-%m-%d')
                    } for entry in display_history]
                })
        
        return JsonResponse({'tracked_products': results})
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

def price_history(request):
    platform = request.GET.get('platform', '').lower()
    product_id = request.GET.get('product_id', '')
    
    if not platform or not product_id:
        return JsonResponse({'error': 'Platform and product_id required'}, status=400)
    
    try:
        if platform == 'amazon':
            product = AmazonProduct.objects.get(asin=product_id)
            content_type = ContentType.objects.get_for_model(AmazonProduct)
        elif platform == 'flipkart':
            product = FlipkartProduct.objects.get(flipkart_id=product_id)
            content_type = ContentType.objects.get_for_model(FlipkartProduct)
        else:
            return JsonResponse({'error': 'Invalid platform'}, status=400)
        
        # Get all price history ordered by timestamp
        history = PriceHistory.objects.filter(
            content_type=content_type,
            object_id=product.id
        ).order_by('timestamp')
        
        # Calculate statistics
        stats = history.aggregate(
            min_price=Min('price'),
            max_price=Max('price'),
            avg_price=Avg('price')
        )
        
        data = [{
            'price': float(entry.price),
            'timestamp': entry.timestamp.strftime('%Y-%m-%d')
        } for entry in history]
        
        return JsonResponse({
            'product_name': product.name,
            'platform': platform,
            'current_price': float(product.current_price),
            'history': data,
            'stats': {
                'min_price': float(stats['min_price']) if stats['min_price'] else 0,
                'max_price': float(stats['max_price']) if stats['max_price'] else 0,
                'avg_price': float(stats['avg_price']) if stats['avg_price'] else 0
            }
        })
    except (AmazonProduct.DoesNotExist, FlipkartProduct.DoesNotExist):
        return JsonResponse({'error': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def delete_tracked_product(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            product_name = data.get('product_name', '').strip()
            platform = data.get('platform', '').lower()
            
            if not product_name or not platform:
                return JsonResponse({'error': 'Product name and platform required'}, status=400)
            
            # Get the user
            user = request.user
            if user.is_anonymous:
                from django.contrib.auth.models import User
                user, created = User.objects.get_or_create(username='demo_user')
            
            # Find and delete the tracked product
            tracked_product = TrackedProduct.objects.filter(
                name=product_name,
                user=user
            ).first()
            
            if tracked_product:
                tracked_product.delete()
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'error': 'Product not found'}, status=404)
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
def user_login(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        email = data.get('email')
        password = data.get('password')
        
        try:
            # Since we're using email to login, get the username from email
            user = User.objects.get(email=email)
            user = authenticate(username=user.username, password=password)
            if user is not None:
                login(request, user)
                return JsonResponse({
                    'success': True,
                    'message': 'Login successful',
                    'user': {
                        'name': user.get_full_name() or user.username,
                        'email': user.email
                    }
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid credentials'
                }, status=400)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'User not found'
            }, status=404)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@csrf_exempt
def user_register(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        
        if User.objects.filter(email=email).exists():
            return JsonResponse({
                'success': False,
                'message': 'Email already registered'
            }, status=400)
        
        # Create username from email
        username = email.split('@')[0]
        base_username = username
        counter = 1
        
        # Ensure unique username
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        try:
            # Create the user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            
            # Set the full name if provided
            if name:
                name_parts = name.split(' ', 1)
                user.first_name = name_parts[0]
                if len(name_parts) > 1:
                    user.last_name = name_parts[1]
                user.save()
            
            # Log the user in
            login(request, user)
            
            return JsonResponse({
                'success': True,
                'message': 'Registration successful',
                'user': {
                    'name': user.get_full_name() or user.username,
                    'email': user.email
                }
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@login_required
def user_logout(request):
    logout(request)
    return JsonResponse({
        'success': True,
        'message': 'Logout successful'
    })

@csrf_exempt
def check_auth(request):
    if request.user.is_authenticated:
        return JsonResponse({
            'authenticated': True,
            'user': {
                'name': request.user.get_full_name() or request.user.username,
                'email': request.user.email
            }
        })
    return JsonResponse({'authenticated': False})

@csrf_exempt
def google_auth(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            name = data.get('name')
            uid = data.get('uid')
            photo_url = data.get('photoURL')

            if not email or not uid:
                return JsonResponse({
                    'success': False,
                    'message': 'Email and UID are required'
                }, status=400)

            # Try to find existing user by email
            try:
                user = User.objects.get(email=email)
                # Update user info if needed
                if name and name != user.get_full_name():
                    names = name.split(' ', 1)
                    user.first_name = names[0]
                    user.last_name = names[1] if len(names) > 1 else ''
                    user.save()
            except User.DoesNotExist:
                # Create new user
                username = email.split('@')[0]
                base_username = username
                counter = 1
                # Ensure unique username
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1

                names = name.split(' ', 1) if name else [email.split('@')[0], '']
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=names[0],
                    last_name=names[1] if len(names) > 1 else ''
                )

            # Log the user in
            login(request, user)
            
            return JsonResponse({
                'success': True,
                'message': 'Authentication successful',
                'user': {
                    'name': user.get_full_name() or user.username,
                    'email': user.email
                }
            })

        except Exception as error:
            return JsonResponse({
                'success': False,
                'message': str(error)
            }, status=500)

    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@login_required
def profile(request):
    user = request.user
    context = {
        'user_data': {
            'name': user.get_full_name() or user.username,
            'email': user.email,
            'date_joined': user.date_joined,
            'is_premium': False  # You can modify this based on your premium user logic
        }
    }
    return render(request, 'tracker/profile_page.html', context)

@csrf_exempt
def update_account_settings(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Please login first'}, status=401)
        
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user = request.user
            
            # Update username if provided and different
            new_username = data.get('username')
            if new_username and new_username != user.username:
                if User.objects.filter(username=new_username).exists():
                    return JsonResponse({
                        'success': False,
                        'message': 'Username already taken'
                    }, status=400)
                user.username = new_username
            
            # Update email if provided and different
            new_email = data.get('email')
            if new_email and new_email != user.email:
                if User.objects.filter(email=new_email).exists():
                    return JsonResponse({
                        'success': False,
                        'message': 'Email already registered'
                    }, status=400)
                user.email = new_email
            
            # Update password if provided
            new_password = data.get('password')
            if new_password:
                user.set_password(new_password)
            
            user.save()
            
            # If password was changed, update session
            if new_password:
                update_session_auth_hash(request, user)
            
            return JsonResponse({
                'success': True,
                'message': 'Account settings updated successfully',
                'user': {
                    'name': user.get_full_name() or user.username,
                    'email': user.email,
                    'username': user.username
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@csrf_exempt
@login_required
def change_password(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            current_password = data.get('current_password')
            new_password = data.get('new_password')
            
            # Verify current password
            user = request.user
            if not user.check_password(current_password):
                return JsonResponse({
                    'success': False,
                    'message': 'Current password is incorrect'
                }, status=400)
            
            # Set new password
            user.set_password(new_password)
            user.save()
            
            # Update session to prevent logout
            update_session_auth_hash(request, user)
            
            return JsonResponse({
                'success': True,
                'message': 'Password changed successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@csrf_exempt
@login_required
def delete_account(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            password = data.get('password')
            
            # Verify password
            user = request.user
            if not user.check_password(password):
                return JsonResponse({
                    'success': False,
                    'message': 'Password is incorrect'
                }, status=400)
            
            # Delete user account
            user.delete()
            
            # Logout the user
            logout(request)
            
            return JsonResponse({
                'success': True,
                'message': 'Account deleted successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@csrf_exempt
@login_required
def update_threshold(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            threshold = data.get('threshold')
            
            # Update user's price alert threshold
            user_profile = request.user.userprofile
            user_profile.price_alert_threshold = int(threshold.replace('%', ''))
            user_profile.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Price alert threshold updated successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@csrf_exempt
@login_required
def update_settings(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Get user profile
            user_profile = request.user.userprofile
            
            # Update settings
            user_profile.email_notifications = data.get('email_notifications', user_profile.email_notifications)
            user_profile.push_notifications = data.get('push_notifications', user_profile.push_notifications)
            user_profile.dark_mode = data.get('dark_mode', user_profile.dark_mode)
            
            # Update threshold if provided
            if 'threshold' in data:
                user_profile.price_alert_threshold = int(data['threshold'].replace('%', ''))
            
            user_profile.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Settings updated successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

def product_page(request):
    product_url = request.GET.get('url')
    days_to_forecast = int(request.GET.get('days', 30))
    product = None
    
    if product_url:
        # Try to get the specific product by URL
        product = ScrapedProduct.objects.filter(url=product_url).first()
        latest_price = PriceOfProductsHistory.objects.filter(url=product_url).order_by('-timestamp').first()
        review_analysis = ReviewAnalysis.objects.filter(url=product_url).first()
        # Get price history for chart
        price_history = PriceOfProductsHistory.objects.filter(url=product_url).order_by('timestamp')
    
    if not product:
        # Fallback to latest product if no URL provided or product not found
        product = ScrapedProduct.objects.order_by('-scraped_at').first()
        latest_price = PriceOfProductsHistory.objects.filter(url=product.url).order_by('-timestamp').first()
        review_analysis = ReviewAnalysis.objects.filter(url=product.url).first()
        price_history = PriceOfProductsHistory.objects.filter(url=product.url).order_by('timestamp')

    # Create DataFrame for prediction
    df = pd.DataFrame([
        {
            'date': ph.timestamp,
            'price': float(ph.price)
        } for ph in price_history
    ])
      # Get predictions if we have enough data
    predictions = {}
    if len(df) >= 5:  # Need at least 5 data points for prediction
        try:
            from .price_prediction_views import predict_future_prices, find_price_dips
            
            forecast = predict_future_prices(df, days_to_forecast=days_to_forecast)
            
            if forecast is not None:
                # Find price dips in predicted prices
                forecast_prices = forecast['yhat'].values
                dip_indices = find_price_dips(forecast_prices)
                if len(dip_indices) == 0:
                    # If no dips found, use lowest predicted price
                    dip_indices = [forecast['yhat'].argmin()]
                best_times = forecast.iloc[dip_indices]
                # Format predictions for JSON
                predictions = [
                    {
                        'date': date.strftime('%Y-%m-%d'),
                        'price': float(price)
                    }
                    for date, price in zip(best_times['ds'], best_times['yhat'].round(2))
                ]
        except Exception as e:
            print(f"Error generating predictions: {str(e)}")
            predictions = {}
    
    # Calculate average and lowest prices from history
    prices = [ph.price for ph in price_history]
    avg_price = sum(prices) / len(prices) if prices else latest_price.price if latest_price else None
    lowest_price = min(prices) if prices else latest_price.price if latest_price else None
    lowest_price_date = None
    for ph in price_history:
        if ph.price == lowest_price:
            lowest_price_date = ph.timestamp.strftime("%d %b %Y")
            break
    
    # Get highest price from history to use as "original" price
    highest_price = max(prices) if prices else latest_price.price if latest_price else None    # Calculate discount percentage and estimated savings
    discount_percentage = None
    estimated_savings = None
    if latest_price and highest_price:
        current_price = float(latest_price.price)
        original_price = float(highest_price)
        if current_price != original_price:
            discount = original_price - current_price
            discount_percentage = round((discount / original_price) * 100, 2)
            estimated_savings = round(discount, 2)  # Actual amount saved

    # Import prediction functions as needed
    from .price_prediction_views import predict_future_prices
    # Serialize price history data for the chart
    price_history_data = json.dumps([
        {
            'timestamp': ph.timestamp.strftime('%Y-%m-%d'),
            'price': float(ph.price)
        } for ph in price_history
    ])

    context = {
        'product': product,
        'latest_price': latest_price,
        'review_analysis': review_analysis,
        'price_history': price_history_data,
        'avg_price': avg_price,
        'lowest_price': lowest_price,
        'highest_price': highest_price,
        'lowest_price_date': lowest_price_date,
        'discount_percentage': discount_percentage,
        'predictions': json.dumps(predictions)  # Add predictions to context
    }
    
    return render(request, 'tracker/Product_Page.html', context)

@login_required
def save_product(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            product = SavedProduct.objects.create(
                user=request.user,
                product_name=data['product_name'],
                image_url=data['image_url'],
                product_url=data['product_url'],
                price=data['price'],
                store_name=data['store_name']
            )
            return JsonResponse({'status': 'success', 'message': 'Product saved successfully'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
def remove_saved_product(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            SavedProduct.objects.filter(
                user=request.user,
                product_url=data['product_url']
            ).delete()
            return JsonResponse({'status': 'success', 'message': 'Product removed successfully'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
def get_saved_products(request):
    if request.method == 'GET':
        try:
            saved_products = SavedProduct.objects.filter(user=request.user).order_by('-saved_at')
            products_data = [{
                'product_name': product.product_name,
                'image_url': product.image_url,
                'product_url': product.product_url,
                'price': float(product.price),
                'store_name': product.store_name,
                'saved_at': product.saved_at.isoformat()
            } for product in saved_products]
            return JsonResponse({'status': 'success', 'products': products_data})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
@require_http_methods(["POST"])
def add_price_alert(request):
    try:
        data = json.loads(request.body)
        product_url = data.get('product_url')
        target_price = data.get('target_price')
        product_name = data.get('product_name', '')

        if not product_url or not target_price:
            return JsonResponse({'status': 'error', 'message': 'Missing required fields'}, status=400)

        # Get current price from saved product or recent search
        try:
            saved_product = SavedProduct.objects.get(user=request.user, product_url=product_url)
            current_price = saved_product.price
            if not product_name:
                product_name = saved_product.product_name
        except SavedProduct.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Product not found'}, status=404)        # Create or update price alert
        alert, created = PriceAlert.objects.update_or_create(
            user=request.user,
            product_url=product_url,
            defaults={
                'product_name': product_name,
                'current_price': current_price,
                'target_price': target_price,
                'is_active': True
            }
        )

        # Check if current price is already below target price
        if current_price <= target_price:
            # Import EmailSender here to avoid circular imports
            from tracker.scrapers.email_sender import EmailSender
            email_sender = EmailSender()
            
            # Send immediate email notification
            email_sender.send_price_alert(
                request.user.email,
                product_name,
                current_price,
                target_price,
                product_url
            )
            message = 'Price alert set successfully - Current price already meets your target!'
        else:
            message = 'Price alert set successfully'

        return JsonResponse({'status': 'success', 'message': message})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def get_price_alerts(request):
    try:
        alerts = PriceAlert.objects.filter(user=request.user, is_active=True).order_by('-created_at')
        alerts_data = []
        for alert in alerts:
            alerts_data.append({
                'id': alert.id,
                'product_name': alert.product_name,
                'product_url': alert.product_url,
                'current_price': float(alert.current_price),
                'target_price': float(alert.target_price),
                'created_at': alert.created_at.isoformat()
            })
        return JsonResponse({'status': 'success', 'alerts': alerts_data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def update_price_alert(request):
    try:
        data = json.loads(request.body)
        alert_id = data.get('alert_id')
        target_price = data.get('target_price')

        if not alert_id or not target_price:
            return JsonResponse({'status': 'error', 'message': 'Missing required fields'}, status=400)

        alert = PriceAlert.objects.get(id=alert_id, user=request.user)
        alert.target_price = target_price
        alert.save()

        return JsonResponse({'status': 'success', 'message': 'Price alert updated successfully'})
    except PriceAlert.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Alert not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def remove_price_alert(request):
    try:
        data = json.loads(request.body)
        alert_id = data.get('alert_id')

        if not alert_id:
            return JsonResponse({'status': 'error', 'message': 'Missing alert ID'}, status=400)

        alert = PriceAlert.objects.get(id=alert_id, user=request.user)
        alert.is_active = False
        alert.save()

        return JsonResponse({'status': 'success', 'message': 'Price alert removed successfully'})
    except PriceAlert.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Alert not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def find_price_dips(prices, order=3):
    """Identify local minima in price series"""
    min_indices = argrelextrema(prices, np.less, order=order)[0]
    return min_indices

@csrf_exempt
def get_price_predictions(request):
    """Endpoint to get price predictions for a product"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
        
    try:
        logging.info("Starting price prediction request")
        product_url = request.GET.get('url')
        days_to_forecast = int(request.GET.get('days', 30))
        
        if not product_url:
            return JsonResponse({'error': 'Product URL is required'}, status=400)
        
        logging.info(f"Getting price history for URL: {product_url}")
        
        # First get the ScrapedProduct
        product = ScrapedProduct.objects.filter(url=product_url).first()
        if not product:
            logging.warning(f"No product found for URL: {product_url}")
            return JsonResponse({'error': 'Product not found'}, status=404)
        
        # Get all relevant price history ordered by date
        price_history = PriceOfProductsHistory.objects.filter(
            url=product
        ).order_by('timestamp')
        
        if not price_history.exists():
            return JsonResponse({'error': 'No price history found for this product'}, status=404)
            
        # Create DataFrame for prediction
        df = pd.DataFrame([
            {
                'date': ph.timestamp,
                'price': float(ph.price)
            } for ph in price_history
        ])
        
        logging.info(f"Created DataFrame with {len(df)} price points")
        
        if len(df) < 5:  # Need at least 5 data points for prediction
            return JsonResponse({'error': 'Insufficient price history for predictions'}, status=400)
            
        try:
            forecast = predict_future_prices(df, days_to_forecast=days_to_forecast)
            
            if forecast is None:
                return JsonResponse({'error': 'Could not generate reliable predictions'}, status=400)
                
            # Find price dips in predicted prices
            forecast_prices = forecast['yhat'].values
            dip_indices = find_price_dips(forecast_prices)
            
            if len(dip_indices) == 0:
                logging.info("No price dips found in predictions")
                # If no dips found, return the lowest predicted price point
                dip_indices = [forecast['yhat'].argmin()]
            
            best_times = forecast.iloc[dip_indices]
            
            # Format predictions for JSON
            predictions = {
                'predictions': [
                    {
                        'date': date.strftime('%Y-%m-%d'),
                        'price': float(price)
                    }
                    for date, price in zip(best_times['ds'], best_times['yhat'].round(2))
                ],
                'price_history': [
                    {
                        'date': date.strftime('%Y-%m-%d'),
                        'price': float(price)
                    }
                    for date, price in zip(df['date'], df['price'])
                ]
            }
            
            logging.info(f"Successfully generated {len(predictions['predictions'])} predictions")
            return JsonResponse(predictions)
            
        except Exception as e:
            logging.error(f"Error in prediction generation: {str(e)}")
            return JsonResponse({'error': 'Failed to generate predictions', 'details': str(e)}, status=400)
            
    except Exception as e:
        logging.error(f"General error in get_price_predictions: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Invalid request method'}, status=405)