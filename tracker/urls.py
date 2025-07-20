from django.urls import path
from . import views
from . import price_prediction_views

urlpatterns = [
    path('', views.home, name='home'),
    path('index/', views.index, name='index'),
    path('search/', views.search, name='search'),  # Map the root URL to the index view
    path('track/', views.track, name='track'),
    path('price-history/', views.price_history, name='price_history'),
    path('add-tracked-product/', views.add_tracked_product, name='add_tracked_product'),
    path('get-tracked-products/', views.get_tracked_products, name='get_tracked_products'),
    path('delete-tracked-product/', views.delete_tracked_product, name='delete_tracked_product'),
    path('api/login/', views.user_login, name='api_login'),
    path('api/register/', views.user_register, name='api_register'),
    path('api/logout/', views.user_logout, name='api_logout'),
    path('api/check-auth/', views.check_auth, name='api_check_auth'),
    path('api/google-auth/', views.google_auth, name='api_google_auth'),
    path('profile/', views.profile, name='profile'),
    path('api/update-account/', views.update_account_settings, name='update_account_settings'),
    path('api/change-password/', views.change_password, name='change_password'),
    path('api/delete-account/', views.delete_account, name='delete_account'),
    path('api/update-threshold/', views.update_threshold, name='update_threshold'),
    path('api/update-settings/', views.update_settings, name='update_settings'),
    path('product-page/', views.product_page, name='product_page'),
    path('api/tracked-products/', views.get_tracked_products, name='get_tracked_products'),
    path('api/save-product/', views.save_product, name='save_product'),
    path('api/predict/', price_prediction_views.get_price_predictions, name='get_price_predictions'),
    path('api/remove-saved-product/', views.remove_saved_product, name='remove_saved_product'),
    path('api/saved-products/', views.get_saved_products, name='get_saved_products'),
    path('api/add-price-alert/', views.add_price_alert, name='add_price_alert'),
    path('api/price-alerts/', views.get_price_alerts, name='get_price_alerts'),
    path('api/update-price-alert/', views.update_price_alert, name='update_price_alert'),
    path('api/remove-price-alert/', views.remove_price_alert, name='remove_price_alert'),
]