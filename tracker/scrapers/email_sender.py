import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class EmailSender:
    def __init__(self):
        self.from_email = "vyvidhskrishna@gmail.com"
        self.app_password = "bllm umch dfmf sdqw"
        
    def send_price_alert(self, user_email, product_name, current_price, target_price, product_url):
        """
        Send an email notification when a price alert is triggered
        
        Args:
            user_email (str): Recipient's email address
            product_name (str): Name of the product
            current_price (float/decimal): Current price of the product
            target_price (float/decimal): User's target price for the alert
            product_url (str): URL to view the product
        """
        try:
            subject = f"Price Alert: {product_name} has reached your target price!"
            body = f"""
            Good news! One of your price alerts has been triggered.

            Product: {product_name}
            Current Price: ₹{current_price}
            Your Target Price: ₹{target_price}

            View the product here: {product_url}

            Visit your profile to manage your price alerts.
            """

            # Setup the MIME
            message = MIMEMultipart()
            message["From"] = self.from_email
            message["To"] = user_email
            message["Subject"] = subject

            message.attach(MIMEText(body, "plain"))

            # Connect to Gmail SMTP server and send email
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.from_email, self.app_password)
                server.send_message(message)
                logger.info(f"Price alert email sent successfully to {user_email} for {product_name}")
                
        except Exception as e:
            logger.error(f"Failed to send price alert email to {user_email} for {product_name}: {str(e)}")
            raise
