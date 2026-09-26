import asyncio
from playwright.async_api import async_playwright
import requests
API_URL = "https://siradig.onrender.com/api/receipts/pending/"
TOKEN = "144f9c9861f822af77f2d2d5d430e9bc6700816d"  # Reemplazar con token de tu dashboard (ej: desde popup)

def obtener_recibo_db():
    try:
        headers = {"Authorization": f"Token {TOKEN}"} if TOKEN != "tu_token_aqui" else {}
        resp = requests.get(API_URL, headers=headers, timeout=5)
        if resp.status_code == 200:
            datos = resp.json()
            if datos and len(datos) > 0:
                r = datos[0]
                return {
                    "fecha_emision": r.get("fecha_emision", "15/06/2026"),
                    "cuit_emisor": r.get("cuit_emisor", "20123456789"),
                    "razon_social": r.get("razon_social", "ASIM LAURA SOLEDAD"),
                    "tipo_comprobante": r.get("tipo_comprobante", "Factura B"),
                    "letra": r.get("letra", "B"),
                    "numero_comprobante": r.get("numero_comprobante", "001-00000001"),
                    "importe_total": r.get("importe_total", 250000),
                    "categoria": r.get("categoria_gasto_siradig", "Gastos médicos y paramédicos")
                }
        print("No se encontraron recibos pendientes en DB. Usando ejemplo.")
    except Exception as e:
        print(f"Error conectando a DB: {e}. Usando ejemplo local.")
    return {
        "fecha_emision": "15/06/2026",
        "cuit_emisor": "20123456789",
        "razon_social": "ASIM LAURA SOLEDAD",
        "tipo_comprobante": "Factura B",
        "letra": "B",
        "numero_comprobante": "001-00000001",
        "importe_total": 250000,
        "categoria": "Gastos médicos y paramédicos"
    }

async def autocompletar_siradig():
    DATOS = obtener_recibo_db()
    print("Datos cargados (DB o local):", DATOS["razon_social"], "- Fecha:", DATOS["fecha_emision"])
    print("Conectando a Chrome con Playwright...")
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0]
            print(f"Pagina activa: {page.url}")
            if "radig" not in page.url:
                print("Advertencia: No esta en AFIP/SIRADIG.")
            link = await page.query_selector("#link_agregar_gastos_medicos")
            if link:
                await link.click()
                print("Paso 4: Click link medicos OK")
            await page.wait_for_selector("#numeroDoc", timeout=5000)
            await page.fill("#numeroDoc", DATOS["cuit_emisor"])
            print("Paso 5: CUIT OK")
            mes = DATOS["fecha_emision"].split("/")[1]
            await page.select_option("#mesDesde", mes)
            print(f"Paso 6: Mes {mes} OK")
            await page.click("#btn_alta_comprobante")
            print("Paso 7: Alta OK")
            await page.wait_for_selector("#cmpFechaEmision", timeout=5000)
            await page.fill("#cmpFechaEmision", DATOS["fecha_emision"])
            print("Paso 8: Fecha OK")
            await page.select_option("#cmpTipo", "6")
            print("Paso 9: Tipo OK")
            await page.fill("#cmpPuntoVenta", "001")
            await page.fill("#cmpNumero", "00000001")
            print("Paso 11: Numero OK")
            await page.fill("#cmpMontoFacturado", str(DATOS["importe_total"]))
            print("Paso 12: Monto OK")
            await page.fill("#cmpMontoReintegrado", "0")
            print("Paso 13: Reintegrado = 0 OK")
            await asyncio.sleep(1)
            await page.click("text=Agregar")
            print("Paso 14: Agregar OK")
            await page.wait_for_timeout(800)
            await page.click("text=Guardar")
            print("Paso 15: Guardar OK")
            print("Carga automatica completada con datos de DB o local!")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(autocompletar_siradig())
