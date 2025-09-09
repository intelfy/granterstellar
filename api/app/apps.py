from django.apps import AppConfig


class AppUtilitiesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    verbose_name = 'App Utilities'

    def ready(self):  # type: ignore[override]
        # Initialize centralized copy keys
        try:  # pragma: no cover - defensive
            from .common import keys
            keys.ready()
        except Exception:
            pass
