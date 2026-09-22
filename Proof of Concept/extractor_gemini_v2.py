import os
import json
import base64
from google import genai
from google.genai import types

# La API key se lee de la variable de entorno GEMINI_API_KEY (nunca hardcodear)
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
client = genai.Client(api_key=GEMINI_API_KEY)

# 2. Esquema JSON (usando la sintaxis del nuevo SDK)
esquema_factura = {
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
        "categoria_gasto_siradig": {"type": "STRING", "description": "Medicina, Farmacia, Prepaga, Otro"}
    },
    "required": ["fecha_emision", "cuit_emisor", "razon_social", "importe_total"]
}

def extraer_datos_factura(image_path):
    print(f"⏳ Procesando {image_path} con el nuevo SDK de Gemini...")
    
    # Cargar imagen en base64
    with open(image_path, "rb") as f:
        imagen_bytes = f.read()
    
    prompt = """
    Eres un contador experto en SIRADIG (AFIP). Extrae los datos de esta factura.
    Reglas: CUIT solo números. Si no hay IVA, pon 0. Sé exacto con los montos.
    """

    try:
        # Llamada al modelo con el nuevo SDK
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=[
                prompt,
                types.Part.from_bytes(data=imagen_bytes, mime_type="image/jpeg")
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=esquema_factura,
            )
        )
        
        # El nuevo SDK devuelve el JSON directamente parseado si usamos schema
        datos = json.loads(response.text)
        return datos

    except Exception as e:
        # AQUÍ IMPRIMIMOS EL ERROR REAL PARA DEPURAR
        print(f"\n❌ ERROR REAL DE LA API: {e}")
        return None

if __name__ == "__main__":
    ruta_imagen = "factura_ejemplo.jpg" 
    
    if not os.path.exists(ruta_imagen):
        print(f"⚠️ No se encontró '{ruta_imagen}'. Pon una foto de factura con ese nombre.")
    else:
        resultado = extraer_datos_factura(ruta_imagen)
        if resultado:
            print("\n✅ ¡ÉXITO! Datos para SIRADIG:")
            print(json.dumps(resultado, indent=4, ensure_ascii=False))