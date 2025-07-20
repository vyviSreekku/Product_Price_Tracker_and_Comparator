import logging
import numpy as np
import pandas as pd
from prophet import Prophet
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from scipy.signal import argrelextrema
from tracker.models import ScrapedProduct, PriceOfProductsHistory

# Configure logging at the top of the file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler('price_predictions.log')  # Also log to file
    ]
)
logger = logging.getLogger(__name__)

def predict_future_prices(df, days_to_forecast=30):
    """Predict future prices using Facebook Prophet"""
    try:
        # If we have less than 15 days of data, limit the forecast period
        available_days = (df['date'].max() - df['date'].min()).days
        if available_days < 15:
            days_to_forecast = min(days_to_forecast, available_days)
            if days_to_forecast < 5:  # If very limited data, don't make predictions
                logging.info("Insufficient data points for prediction (less than 5 days)")
                return None

        # Sort dataframe by date to ensure chronological order
        df = df.sort_values('date')
        
        # Convert to prophet format and remove timezone information
        prophet_df = df.rename(columns={'date': 'ds', 'price': 'y'})
        prophet_df['ds'] = prophet_df['ds'].dt.tz_localize(None)  # Remove timezone info

        # Calculate price trend for initial values
        price_series = prophet_df['y'].values
        initial_trend = (price_series[-1] - price_series[0]) / len(price_series)
        
        # Create model with settings optimized for price prediction
        model = Prophet(
            growth='linear',  # Linear growth is more appropriate for prices
            daily_seasonality=False,  # Disable daily seasonality for sparse data
            weekly_seasonality=True,  # Keep weekly patterns
            yearly_seasonality=False,  # Disable yearly for short time periods
            seasonality_mode='additive',  # More stable for price predictions
            changepoint_prior_scale=0.05,  # More conservative trend changes
            changepoint_range=0.9  # Allow changepoints through 90% of the history
        )
        
        
        model.fit(prophet_df)
        
        # Create future dataframe
        future = model.make_future_dataframe(periods=days_to_forecast)
        
        # Make predictions
        forecast = model.predict(future)
        
        # Get only the future predictions
        return forecast[['ds', 'yhat']].tail(days_to_forecast)
        
    except Exception as e:
        logging.error(f"Error in predict_future_prices: {str(e)}")
        return None

def find_price_dips(prices, order=3, min_depth_pct=3):
    """Identify significant local minima in price series
    
    Args:
        prices: numpy array of prices
        order: how many points on each side to compare
        min_depth_pct: minimum percentage drop required to consider a dip significant
    """
    # Ensure we're working with numpy array
    prices = np.array(prices)
    if len(prices) < 5:  # Need minimum points for meaningful prediction
        return np.array([])

    # Calculate rolling mean to smooth out noise
    window = 3
    smoothed_prices = np.convolve(prices, np.ones(window)/window, mode='valid')
    try:
        prices = np.array(prices)
        if len(prices) < (2 * order + 1):
            logging.warning(f"Price series too short for order {order}")
            return np.array([])
            
        min_indices = argrelextrema(prices, np.less, order=order)[0]
        
        # Filter out shallow dips
        if len(min_indices) > 0:
            mean_price = np.mean(prices)
            significant_dips = []
            
            for idx in min_indices:
                if idx > 0 and idx < len(prices) - 1:
                    # Calculate dip depth as percentage of mean price
                    dip_depth = min(prices[idx-1] - prices[idx], prices[idx+1] - prices[idx])
                    dip_pct = (dip_depth / mean_price) * 100
                    
                    if dip_pct >= min_depth_pct:
                        significant_dips.append(idx)
            
            return np.array(significant_dips)
        return min_indices
        
    except Exception as e:
        logging.error(f"Error in find_price_dips: {str(e)}")
        return np.array([])

@csrf_exempt
def get_price_predictions(request):
    """Endpoint to get price predictions for a product"""
    if request.method != 'GET':
        return JsonResponse({
            'error': 'Invalid request method',
            'code': 'INVALID_METHOD'
        }, status=405)
        
    try:
        logger.info("Starting price prediction request")
        product_url = request.GET.get('url')
        
        # Validate URL parameter
        if not product_url:
            return JsonResponse({
                'error': 'Product URL is required',
                'code': 'MISSING_URL'
            }, status=400)
            
        # Validate days parameter
        try:
            days_to_forecast = int(request.GET.get('days', 30))
            if days_to_forecast <= 0 or days_to_forecast > 180:
                return JsonResponse({
                    'error': 'Days parameter must be between 1 and 180',
                    'code': 'INVALID_DAYS'
                }, status=400)
        except ValueError:
            return JsonResponse({
                'error': 'Days parameter must be a valid integer',
                'code': 'INVALID_DAYS_FORMAT'
            }, status=400)
        
        # First try exact URL match
        logger.debug(f"Searching for product with URL: {product_url}")
        product = ScrapedProduct.objects.filter(url__iexact=product_url).first()
        
        if not product:
            # Try without query parameters
            url_parts = product_url.split('?')[0]
            logger.debug(f"No exact match, trying URL without parameters: {url_parts}")
            product = ScrapedProduct.objects.filter(url__iexact=url_parts).first()
            
            if not product:
                # Try partial match
                logger.debug("Trying partial URL match")
                product = ScrapedProduct.objects.filter(url__icontains=url_parts.split('/dp/')[-1]).first()
                
                if not product:
                    logger.warning(f"No product found for URL: {product_url}")
                    return JsonResponse({
                        'error': 'Product not found',
                        'code': 'PRODUCT_NOT_FOUND'
                    }, status=404)
        
        logger.info(f"Found product: {product.name if hasattr(product, 'name') else product.url}")
        
        # Get price history
        try:
            price_history = PriceOfProductsHistory.objects.filter(
                url=product
            ).order_by('timestamp')
            
            if not price_history.exists():
                logger.warning(f"No price history found for product: {product_url}")
                return JsonResponse({
                    'error': 'No price history found for this product',
                    'code': 'NO_PRICE_HISTORY'
                }, status=404)
                
            logger.info(f"Found {price_history.count()} price history records")
            
            # Log sample data
            sample = list(price_history.values('timestamp', 'price')[:5])
            logger.debug(f"Sample price history: {sample}")
            
        except Exception as e:
            logger.error(f"Error retrieving price history: {str(e)}", exc_info=True)
            return JsonResponse({
                'error': 'Error retrieving price history',
                'code': 'HISTORY_ERROR',
                'details': str(e)
            }, status=400)
            
        # Create DataFrame for prediction
        try:
            df = pd.DataFrame([
                {
                    'date': ph.timestamp,
                    'price': float(ph.price)
                } for ph in price_history
            ])
            logging.info(f"Price data: {df.to_dict('records')[:5]} ...")
        except Exception as e:
            logging.error(f"Error creating DataFrame: {str(e)}")
            return JsonResponse({
                'error': 'Error processing price data',
                'code': 'DATA_PROCESSING_ERROR',
                'details': str(e)
            }, status=400)
        
        logging.info(f"Created DataFrame with {len(df)} price points")
        
        if len(df) < 5:
            logging.warning(f"Insufficient data points ({len(df)}) for prediction")
            return JsonResponse({
                'error': 'Insufficient price history for predictions',
                'code': 'INSUFFICIENT_DATA',
                'required_points': 5,
                'available_points': len(df)
            }, status=400)
        
        # Try to get predictions
        forecast = predict_future_prices(df, days_to_forecast=days_to_forecast)
        
        if forecast is None:
            logging.warning("Prediction model returned None")
            return JsonResponse({
                'error': 'Could not generate reliable predictions',
                'code': 'PREDICTION_FAILED'
            }, status=400)
        
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
            ],
            'data_points': len(df),
            'forecast_days': days_to_forecast,
            'model_settings': {
                'daily_seasonality': False,
                'weekly_seasonality': True,
                'yearly_seasonality': False,
                'seasonality_mode': 'multiplicative'
            }
        }
        
        logging.info(f"Successfully generated predictions with {len(predictions['predictions'])} price dips")
        return JsonResponse(predictions)
        
    except Exception as e:
        logging.error(f"General error in get_price_predictions: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': 'Internal server error',
            'code': 'SERVER_ERROR',
            'message': str(e)
        }, status=500)
