import requests
from django.conf import settings

API_BASE = "https://api.telegram.org/bot{token}"


def _url(method: str) -> str:
    return f"{API_BASE.format(token=settings.TELEGRAM_BOT_TOKEN)}/{method}"


def send_message(chat_id, text: str) -> None:
    requests.post(_url("sendMessage"), json={"chat_id": chat_id, "text": text}, timeout=10)


def get_file_path(file_id: str) -> str:
    resp = requests.get(_url("getFile"), params={"file_id": file_id}, timeout=10)
    resp.raise_for_status()
    return resp.json()["result"]["file_path"]


def download_file(file_path: str) -> bytes:
    url = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content
