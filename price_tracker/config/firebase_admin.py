import os
import firebase_admin
from firebase_admin import credentials

def initialize_firebase_admin():
    """Initialize Firebase Admin SDK with service account credentials."""
    try:
        # Get the absolute path to the service account file from environment
        cred_path = os.environ.get('FIREBASE_ADMIN_SDK_PATH', 'path/to/your/firebase-admin-sdk.json')
        
        if not os.path.exists(cred_path):
            print(f"Firebase admin SDK file not found at: {cred_path}")
            return
        
        # Initialize the app with credentials
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized successfully")
    except Exception as e:
        print(f"Error initializing Firebase Admin SDK: {str(e)}") 