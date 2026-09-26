c = open('extension/popup.js', encoding='utf-8').read()
items = {
  'fetch_DB': 'await fetch' in c,
  'loop_facturas': 'lista.length' in c,
  'track_resultados': 'const resultados' in c,
  'endpoints_confirma': 'confirm/' in c and '/api/receipts/' in c,
  'resumen_final': '✅' in c,
  'token_storage': 'chrome.storage.local.get' in c,
  'navegacion_1': 'ir_deducciones' in c,
}
for k, v in items.items():
    print(k + ': ' + ('OK' if v else 'FALTA'))
print('Lineas totales:', len(c.splitlines()))
