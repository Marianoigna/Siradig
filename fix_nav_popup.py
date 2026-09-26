with open('extension/popup.js', 'r', encoding='utf-8') as f:
    c = f.read()
marker = '  statusEl.textContent = "Consultando facturas pendientes...";'
if marker in c:
    old = marker
    new = '  statusEl.textContent = "Navegando a Gastos Medicos...";\n  await chrome.scripting.executeScript({\n    target: { tabId: tab.id },\n    func: () => {\n      if (location.href.includes("verGastosMedicos")) return;\n      const link = document.getElementById("link_agregar_gastos_medicos") ||\n        Array.from(document.querySelectorAll("a, button, span, input")).find(\n          (el) => (el.textContent || "").toLowerCase().includes("gastos medicos")\n        );\n      if (link) link.click();\n    }\n  });\n  await new Promise(r => setTimeout(r, 2500));\n  statusEl.textContent = "Consultando facturas pendientes...";'
    c = c.replace(marker, new)
    with open('extension/popup.js', 'w', encoding='utf-8') as f:
        f.write(c)
    print('Navegacion al formulario agregada en popup.js')
else:
    print('Marker no encontrado - posiblemente ya esta')
