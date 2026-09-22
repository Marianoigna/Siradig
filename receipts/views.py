import json

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.conf import settings
from rest_framework import generics, permissions
from rest_framework.authentication import TokenAuthentication

from .models import Receipt, UserProfile
from .serializers import ReceiptSerializer
from .services import ocr as ocr_service
from .services import telegram as telegram_service


@login_required
def dashboard_home(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    receipts = request.user.receipts.order_by('-created_at')
    context = {
        'profile': profile,
        'receipts': receipts,
        'pendientes': receipts.filter(estado='pendiente_carga').count(),
        'cargados': receipts.filter(estado='cargado_en_siradig').count(),
        'total_deducible': sum(r.importe_total or 0 for r in receipts),
        'telegram_link': f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={profile.telegram_link_token}",
    }
    return render(request, 'receipts/dashboard.html', context)


@csrf_exempt
@require_POST
def telegram_webhook(request):
    update = json.loads(request.body.decode('utf-8'))
    message = update.get('message') or {}
    chat_id = message.get('chat', {}).get('id')
    text = message.get('text', '')

    if not chat_id:
        return HttpResponse(status=200)

    if text.startswith('/start'):
        _handle_start(chat_id, text)
        return HttpResponse(status=200)

    photo = message.get('photo')
    document = message.get('document')
    if photo or document:
        _handle_receipt_file(chat_id, photo, document)
    else:
        telegram_service.send_message(chat_id, "Enviame una foto o PDF de tu comprobante.")

    return HttpResponse(status=200)


def _handle_start(chat_id, text):
    parts = text.split(maxsplit=1)
    token = parts[1].strip() if len(parts) > 1 else ''
    profile = UserProfile.objects.filter(telegram_link_token=token).first()
    if not profile:
        telegram_service.send_message(chat_id, "Token inválido. Generá el link desde tu dashboard.")
        return
    profile.telegram_chat_id = str(chat_id)
    profile.save(update_fields=['telegram_chat_id'])
    telegram_service.send_message(chat_id, "¡Cuenta vinculada! Ya podés enviarme fotos de tus comprobantes.")


def _handle_receipt_file(chat_id, photo, document):
    profile = UserProfile.objects.filter(telegram_chat_id=str(chat_id)).first()
    if not profile:
        telegram_service.send_message(chat_id, "Primero vinculá tu cuenta con el link del dashboard (/start <token>).")
        return

    if photo:
        file_id = photo[-1]['file_id']  # la última es la de mayor resolución
        mime_type = 'image/jpeg'
        filename = f"{file_id}.jpg"
    else:
        file_id = document['file_id']
        mime_type = document.get('mime_type', 'application/octet-stream')
        filename = document.get('file_name', f"{file_id}")

    file_path = telegram_service.get_file_path(file_id)
    file_bytes = telegram_service.download_file(file_path)

    receipt = Receipt.objects.create(
        user=profile.user,
        origen='telegram',
        estado='pendiente_revision',
    )
    receipt.archivo_original.save(filename, ContentFile(file_bytes), save=True)

    try:
        datos = ocr_service.extraer_datos_factura(file_bytes, mime_type=mime_type)
    except Exception:
        telegram_service.send_message(chat_id, "No pude leer los datos del comprobante, quedó guardado para revisión manual.")
        return

    if datos:
        for campo in ['fecha_emision', 'cuit_emisor', 'razon_social', 'tipo_comprobante', 'letra',
                      'numero_comprobante', 'importe_total', 'importe_iva', 'categoria_gasto_siradig']:
            if campo in datos:
                setattr(receipt, campo, datos[campo])
        receipt.raw_ocr_json = datos
        receipt.estado = 'pendiente_carga'
        receipt.save()
        telegram_service.send_message(
            chat_id,
            f"Comprobante procesado: {receipt.razon_social} - ${receipt.importe_total}. Ya está pendiente de carga en SIRADIG.",
        )
    else:
        telegram_service.send_message(chat_id, "No pude leer los datos del comprobante, quedó guardado para revisión manual.")


class PendingReceiptListAPIView(generics.ListAPIView):
    serializer_class = ReceiptSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Receipt.objects.filter(user=self.request.user, estado='pendiente_carga').order_by('created_at')


class ReceiptUpdateAPIView(generics.UpdateAPIView):
    serializer_class = ReceiptSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Receipt.objects.filter(user=self.request.user)

