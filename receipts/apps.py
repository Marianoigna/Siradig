from django.apps import AppConfig


class ReceiptsConfig(AppConfig):
    name = 'receipts'

    def ready(self):
        from . import signals  # noqa: F401
