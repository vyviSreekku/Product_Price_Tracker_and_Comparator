from django.apps import AppConfig


class TrackerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tracker'

    def ready(self):
        """Initialize Firebase Admin SDK when Django starts."""
        from price_tracker.config.firebase_admin import initialize_firebase_admin
        initialize_firebase_admin()
