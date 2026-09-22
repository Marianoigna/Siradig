import json
import logging

from django.conf import settings
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

logger = logging.getLogger(__name__)

# Se intenta primero el modelo preferido; si Gemini devuelve error de servidor
# (503, sobrecarga) se reintenta con modelos alternativos mas estables.
MODELOS_CANDIDATOS = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.0-flash"]

ESQUEMA_FACTURA = {
    "type": "OBJECT",
    "properties": {
        "fecha_emision": {"type": "STRING", "description": "Fecha de emisión (DD/MM/AAAA)"},
        "cuit_emisor": {"type": "STRING", "description": "CUIT solo números"},
        "razon_social": {"type": "STRING", "description": "Nombre o razón social"},
        "tipo_comprobante": {"type": "STRING", "description": "Ej: Factura, Ticket"},
        "letra": {"type": "STRING", "description": "A, B, C o Sin letra"},
        "numero_comprobante": {"type": "STRING", "description": "Ej: 0001-00001234"},
        "importe_total": {"type": "NUMBER", "description": "Importe total"},
        "importe_iva": {"type": "NUMBER", "description": "Importe IVA (0 si no figura)"},
        "categoria_gasto_siradig": {"type": "STRING", "description": "Medicina, Farmacia, Prepaga, Otro"},
    },
    "required": ["fecha_emision", "cuit_emisor", "razon_social", "importe_total"],
}

PROMPT = """
Eres un contador experto en SIRADIG (AFIP). Extrae los datos de esta factura.
Reglas: CUIT solo números. Si no hay IVA, pon 0. Sé exacto con los montos.
"""


def extraer_datos_factura(file_bytes: bytes, mime_type: str = "image/jpeg") -> dict | None:
    """Envía la imagen/PDF a Gemini y devuelve el JSON estructurado, o None si falla."""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    ultimo_error = None
    for modelo in MODELOS_CANDIDATOS:
        try:
            response = client.models.generate_content(
                model=modelo,
                contents=[PROMPT, types.Part.from_bytes(data=file_bytes, mime_type=mime_type)],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ESQUEMA_FACTURA,
                ),
            )
            return json.loads(response.text)
        except genai_errors.ServerError as exc:
            logger.warning("Modelo %s no disponible (%s), probando el siguiente", modelo, exc)
            ultimo_error = exc
            continue
    raise ultimo_error
