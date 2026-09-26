import asyncio
from playwright.async_api import async_playwright

DATOS = {
    "fecha_emision": "15/06/2025",
    "cuit_emisor": "20123456789",
    "razon_social": "ASIM LAURA SOLEDAD",
    "tipo_comprobante": "Factura B",
    "letra": "B",
    "numero_comprobante": "001-00000001",
    "importe_total": 250000,
    "categoria": "Gastos médicos y paramédicos"
}

async def autocompletar_siradig():
    print("Conectando a Chrome con Playwright...")
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0]
            print(f"Pagina activa: {page.url}")
            
            if "radig" not in page.url:
                print("Advertencia: No esta en AFIP/SIRADIG.")
            
            # Paso 4: Click link medicos
            link = await page.query_selector("#link_agregar_gastos_medicos")
            if link:
                await link.click()
                print("Paso 4: Click link medicos OK")
            else:
                print("Paso 4: No encontro link (quizas ya esta en formulario)")
            
            await page.wait_for_selector("#numeroDoc", timeout=5000)
            
            # Paso 5: CUIT
            await page.fill("#numeroDoc", DATOS["cuit_emisor"])
            print("Paso 5: CUIT OK")
            await page.wait_for_timeout(500)
            
            # Paso 6: Mes
            mes = DATOS["fecha_emision"].split("/")[1]
            await page.select_option("#mesDesde", mes)
            print(f"Paso 6: Mes {mes} OK")
            
            # Paso 7: Alta
            await page.click("#btn_alta_comprobante")
            print("Paso 7: Alta OK")
            await page.wait_for_selector("#cmpFechaEmision", timeout=5000)
            
            # Paso 8: Fecha
            await page.fill("#cmpFechaEmision", DATOS["fecha_emision"])
            print("Paso 8: Fecha OK")
            
            # Paso 9: Tipo
            await page.select_option("#cmpTipo", "6")
            print("Paso 9: Tipo OK")
            
            # Paso 10: Concepto (si existe)
            concepto = await page.query_selector("#idConcepto")
            if concepto:
                await concepto.fill("1")
            
            # Paso 11: Numero
            await page.fill("#cmpPuntoVenta", "001")
            await page.fill("#cmpNumero", "00000001")
            print("Paso 11: Numero OK")
            
            # Paso 12: Monto
            await page.fill("#cmpMontoFacturado", str(DATOS["importe_total"]))
            print("Paso 12: Monto OK")
            
            # Paso 13: Reintegrado
            await page.fill("#cmpMontoReintegrado", "0")
            print("Paso 13: Reintegrado = 0 OK")
            
            # Paso 14: Agregar
            await page.click("text=Agregar")
            print("Paso 14: Agregar OK")
            await page.wait_for_timeout(800)
            
            # Paso 15: Guardar
            await page.click("text=Guardar")
            print("Paso 15: Guardar OK")
            
            print("\nCarga automatica completada con Playwright!")
        except Exception as e:
            print(f"Error: {e}")
            print("Asegurate de tener Chrome abierto con --remote-debugging-port=9222")

if __name__ == "__main__":
    asyncio.run(autocompletar_siradig())
