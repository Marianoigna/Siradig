import json
import logging
import time

from django.conf import settings
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

logger = logging.getLogger(__name__)

# Modelos actuales estables (ordenados por preferencia: rápidos y baratos primero)
MODELOS_CANDIDATOS = [
    "gemini-1.5-flash",        # Rápido, barato, buena calidad - RECOMENDADO
    "gemini-1.5-flash-8b",     # Más rápido aún, menor calidad (8B params)
    "gemini-2.0-flash-exp",    # Experimental, más capaz
    "gemini-1.5-pro",          # Más caro/lento, mayor razonamiento
]

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
        # Reintentos con backoff exponencial para errores transitorios (503, 429)
        for intento in range(2):  # 1 intento original + 1 reintento
            try:
                response = client.models.generate_content(
                    model=modelo,
                    contents=[PROMPT, types.Part.from_bytes(data=file_bytes, mime_type=mime_type)],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ESQUEMA_FACTURA,
                    ),
                )
                datos = json.loads(response.text)
                
                # Procesamos el número de comprobante antes de devolverlo
                texto_num = datos.get("numero_comprobante", "")
                pv, solo_num = procesar_numero_comprobante(texto_num)
                datos["punto_venta"] = pv
                datos["numero_solo"] = solo_num
                
                logger.info("OCR exitoso con modelo %s", modelo)
                return datos
                
            except genai_errors.ClientError as exc:
                # 404 = modelo no existe / deprecado -> NO reintentar, pasar al siguiente modelo
                if getattr(exc, 'status_code', None) == 404:
                    logger.warning("Modelo %s deprecado/no encontrado (404), probando siguiente: %s", modelo, exc)
                    ultimo_error = exc
                    break  # Salta al siguiente modelo
                # 429 = rate limit -> reintentar con backoff
                elif getattr(exc, 'status_code', None) == 429:
                    logger.warning("Rate limit en %s (429), intento %d/2", modelo, intento + 1)
                    ultimo_error = exc
                    if intento == 0:
                        time.sleep(2 ** intento)  # 1s, 2s
                        continue
                # Otros 4xx -> no reintentar
                logger.error("Error cliente en %s: %s", modelo, exc)
                ultimo_error = exc
                break
                
            except genai_errors.ServerError as exc:
                # 503 = sobrecarga -> reintentar con backoff
                if getattr(exc, 'status_code', None) == 503:
                    logger.warning("Modelo %s saturado (503), intento %d/2", modelo, intento + 1)
                    ultimo_error = exc
                    if intento == 0:
                        time.sleep(2 ** intento)
                        continue
                # Otros 5xx -> reintentar una vez
                logger.warning("Error servidor en %s: %s, intento %d/2", modelo, exc, intento + 1)
                ultimo_error = exc
                if intento == 0:
                    time.sleep(2 ** intento)
                    continue
            except Exception as exc:
                logger.exception("Error inesperado con modelo %s", modelo)
                ultimo_error = exc
                break
    
    logger.error("Todos los modelos fallaron. Último error: %s", ultimo_error)
    raise ultimo_error


# (Asegúrate de que la función procesar_numero_comprobante siga al final del archivo)
def procesar_numero_comprobante(texto_ocr):
    # Si viene "00005-00001234"
    if "-" in texto_ocr:
        partes = texto_ocr.split("-")
        pv = partes[0].strip().zfill(5) # Rellena con ceros hasta 5
        num = partes[1].strip().zfill(8) # Rellena con ceros hasta 8
        return pv, num
    else:
        # Si no hay guion, intentamos adivinar o lo ponemos todo en el numero
        return "", texto_ocr.strip().zfill(8)
