# Security Configuration

This document outlines the security setup for the Price Tracker application after API key removal.

## Environment Variables Setup

1. Copy the `.env.template` file to `.env`:
   ```bash
   cp .env.template .env
   ```

2. Fill in the actual values in your `.env` file:
   - `SECRET_KEY`: Generate a new Django secret key for production
   - `FIREBASE_API_KEY`: Your Firebase web API key
   - `FIREBASE_ADMIN_SDK_PATH`: Path to your Firebase Admin SDK JSON file
   - `GOOGLE_AI_API_KEY`: Your Google AI API key for Gemini

## Firebase Setup

1. Download your Firebase Admin SDK JSON file from the Firebase Console
2. Place it in a secure location outside the project directory
3. Update the `FIREBASE_ADMIN_SDK_PATH` in your `.env` file to point to this location
4. Use the provided template (`watchthatprice-firebase-adminsdk-template.json`) as a reference

## Security Best Practices

- Never commit `.env` files or Firebase Admin SDK files to version control
- Use different API keys for development and production
- Regularly rotate your API keys
- Keep the Firebase Admin SDK file in a secure location with restricted permissions
- Set `DEBUG=False` in production environments

## Installation

After setting up the environment variables, install the required dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Django secret key | Yes |
| `FIREBASE_API_KEY` | Firebase web API key | Yes |
| `FIREBASE_ADMIN_SDK_PATH` | Path to Firebase Admin SDK JSON | Yes |
| `GOOGLE_AI_API_KEY` | Google AI API key | Yes |
| `DEBUG` | Debug mode (True/False) | No (default: True) |
