from django.conf import settings
from django.core.management.base import BaseCommand

from receipts.services import telegram as telegram_service


class Command(BaseCommand):
    help = "Configura el webhook de Telegram apuntando a esta app desplegada."

    def add_arguments(self, parser):
        parser.add_argument("url", help="URL pública del webhook, ej. https://siradig.onrender.com/telegram/webhook/")

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            self.stdout.write(self.style.WARNING("TELEGRAM_BOT_TOKEN no configurado, se omite."))
            return
        resp = telegram_service.set_webhook(options["url"])
        self.stdout.write(str(resp))
