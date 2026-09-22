import asyncio
from playwright.async_api import async_playwright

# Estos son los datos que extrajiste con Gemini en el Paso 1
# En producción, vendrán de tu base de datos PostgreSQL
DATOS_FACTURA = {
    "fecha_emision": "21/09/2025",
    "cuit_emisor": "27297480087",
    "razon_social": "Viviana Maria Muñoz Spizzirri",
    "tipo_comprobante": "Factura",
    "letra": "B",
    "numero_comprobante": "0005-00029829",
    "importe_total": "103315.49",
    "importe_iva": "17930.79"
}

async def autocompletar_siradig():
    print("🚀 Iniciando autocompletado del Formulario 572...")
    print("⏳ Conectando a tu navegador Chrome...")

    async with async_playwright() as p:
        try:
            # Conectarse a tu Chrome abierto en modo debug
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0]
            
            print(f"✅ Conectado. Página actual: {page.url}")

            # Verificar que estamos en el formulario simulado
            if "formulario_siradig" not in page.url:
                print("⚠️  La página actual no parece ser el formulario simulado.")
                print("   Asegúrate de tener abierto el archivo HTML en Chrome.")
                return

            print("\n⏳ Inyectando datos en el formulario...")
            await asyncio.sleep(1) # Pausa dramática para que veas qué pasa

            # 1. Fecha
            await page.fill('#fecha', DATOS_FACTURA["fecha_emision"])
            print("   ✅ Fecha completada")
            await asyncio.sleep(0.3)

            # 2. CUIT
            await page.fill('#cuit', DATOS_FACTURA["cuit_emisor"])
            print("   ✅ CUIT completado")
            await asyncio.sleep(0.3)

            # 3. Razón Social
            await page.fill('#razon_social', DATOS_FACTURA["razon_social"])
            print("   ✅ Razón Social completada")
            await asyncio.sleep(0.3)

            # 4. Tipo de Comprobante (es un <select>)
            await page.select_option('#tipo_comprobante', DATOS_FACTURA["tipo_comprobante"])
            print("   ✅ Tipo de comprobante seleccionado")
            await asyncio.sleep(0.3)

            # 5. Letra (es un <select>)
            await page.select_option('#letra', DATOS_FACTURA["letra"])
            print("   ✅ Letra seleccionada")
            await asyncio.sleep(0.3)

            # 6. Número
            await page.fill('#numero', DATOS_FACTURA["numero_comprobante"])
            print("   ✅ Número de comprobante completado")
            await asyncio.sleep(0.3)

            # 7. Importe Total
            await page.fill('#importe_total', DATOS_FACTURA["importe_total"])
            print("   ✅ Importe total completado")
            await asyncio.sleep(0.3)

            # 8. Importe IVA
            await page.fill('#importe_iva', DATOS_FACTURA["importe_iva"])
            print("   ✅ Importe IVA completado")

            print("\n🎉 ¡¡TODOS LOS DATOS FUERON INYECTADOS CON ÉXITO!!")
            print("👀 Mira tu navegador Chrome. El formulario debería estar completo.")
            print("💡 En producción, este mismo script rellenará el formulario real de AFIP.")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("\n💡 SOLUCIÓN: Asegúrate de haber abierto Chrome en modo debug.")
            print("   Cierra TODAS las ventanas de Chrome y ejecuta en PowerShell:")
            print('   & "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222')

if __name__ == "__main__":
    asyncio.run(autocompletar_siradig())