with open('extension/popup.js', 'r', encoding='utf-8') as f:
    c = f.read()
old = '  statusEl.textContent = "Consultando facturas pendientes...";'
new = '  // NAVEGACION DIRECTA al formulario de Gastos Medicos\n  if (!tab.url.includes("verGastosMedicos")) {\n    await chrome.tabs.update(tab.id, { url: "https://serviciosjava2.afip.gob.ar/radig/jsp/verGastosMedicos.do" });\n    await new Promise(r => setTimeout(r, 1500));\n  }\n  statusEl.textContent = "Consultando facturas pendientes...";'
c = c.replace(old, new)
with open('extension/popup.js', 'w', encoding='utf-8') as f:
    f.write(c)
print('Navegacion directa aplicada')
