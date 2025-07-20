# 🔍 WatchThatPrice - E-commerce Price Tracker & Comparator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.1.7-green)](https://www.djangoproject.com/)

![WatchThatPrice Banner](https://via.placeholder.com/1200x300?text=WatchThatPrice+Price+Tracker+and+Comparator)

## 📚 Educational Project Disclaimer

**IMPORTANT**: This project is developed solely for educational purposes to demonstrate web scraping, price tracking, data analysis, and web development concepts. It is not intended for commercial use or monetary gain.

## 🌟 Overview

WatchThatPrice is a comprehensive e-commerce price tracking and comparison system that monitors product prices across major Indian e-commerce platforms, including Amazon and Flipkart. The application provides price history tracking, price drop alerts, and future price predictions using machine learning.

## ✨ Key Features

- **Multi-platform Price Tracking**: Monitor prices across Amazon, Flipkart, and other major e-commerce sites
- **Price History Visualization**: View historical price trends with interactive charts
- **Price Drop Alerts**: Get notified when prices drop below your desired threshold
- **User Accounts**: Personalized watchlists and settings for each user
- **Price Predictions**: ML-powered price forecasting to predict future price movements
- **Product Search**: Search products directly within the application
- **Product Comparison**: Compare prices across different platforms
- **Responsive Design**: Works on desktop and mobile devices

## 🛠️ Technology Stack

- **Backend**: Django 5.1.7
- **Frontend**: HTML, CSS, JavaScript 
- **Database**: SQLite (development), PostgreSQL (production)
- **Web Scraping**: Beautiful Soup, Selenium, Python Requests
- **Price Prediction**: Facebook Prophet (Time Series Forecasting)
- **Authentication**: Django Auth, Google Firebase Auth
- **Deployment**: Docker, AWS (optional)
- **Task Scheduling**: Cron jobs for regular price updates

## 🚀 Getting Started

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)
- Chrome browser (for Selenium)
- ChromeDriver (for Selenium)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/vyviSreekku/Product_Price_Tracker_and_Comparator.git
   cd Product_Price_Tracker_and_Comparator
   ```

2. Set up a virtual environment:
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables by copying the template:
   ```bash
   cp .env.template .env
   ```
   
5. Configure your environment variables:
   - See the SECURITY_SETUP.md file for details on required API keys

6. Run database migrations:
   ```bash
   python manage.py migrate
   ```

7. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```

8. Run the development server:
   ```bash
   python manage.py runserver
   ```

9. Access the application at: `http://localhost:8000`

### Setting Up Scheduled Price Updates

On Windows, create a scheduled task to run `update_prices.bat` daily:
```bash
# Contents of update_prices.bat
@echo off
cd /d D:\path\to\project
call venv\Scripts\activate.bat
python manage.py scrape_and_store_prices
```

On Linux/macOS, set up a cron job:
```bash
# Run daily at midnight
0 0 * * * cd /path/to/project && /path/to/venv/bin/python manage.py scrape_and_store_prices
```

## 🏗️ Project Structure

```
Product_Price_Tracker_and_Comparator/
├── manage.py               # Django management script
├── price_tracker/          # Main Django project folder
│   ├── settings.py         # Project settings
│   ├── urls.py             # Project URLs
│   └── config/             # Configuration files
├── tracker/                # Main application
│   ├── migrations/         # Database migrations
│   ├── models.py           # Data models
│   ├── urls.py             # App URLs
│   ├── views.py            # View controllers
│   ├── price_prediction_views.py  # Price prediction logic
│   ├── scrapers/           # Web scrapers for different sites
│   │   ├── amazon.py
│   │   ├── flipkart.py
│   │   └── url_utils.py
│   ├── static/             # Static assets (CSS, JS)
│   └── templates/          # HTML templates
├── requirements.txt        # Python dependencies
├── SECURITY_SETUP.md       # Security configuration guide
└── .env.template           # Environment variables template
```

## 🔧 Advanced Usage

### Price Prediction

The system uses Facebook's Prophet library to forecast future prices:

```python
# Access predictions via API
GET /api/predict/?url=<product_url>&days=30
```

### Custom Scrapers

You can add support for additional e-commerce platforms by creating new scrapers:

1. Create a new scraper in the `tracker/scrapers/` directory
2. Implement the required methods (get_product_details, get_price)
3. Register the scraper in the URL utility

## 🤝 Contributing

This project is open for educational contributions. To contribute:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -m 'Add some feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

## 📊 Project Demo

[Video Demo Link - Coming Soon]

## ⚠️ Disclaimer

This application is meant for educational purposes only. Please respect the terms of service of the websites being scraped. Some websites prohibit scraping, and this tool should not be used in violation of those terms.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgements

- [Django](https://www.djangoproject.com/)
- [Facebook Prophet](https://facebook.github.io/prophet/)
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/)
- [Selenium](https://www.selenium.dev/)
- [Firebase](https://firebase.google.com/)

---

<p align="center">
  Made with ❤️ for educational purposes
</p>
