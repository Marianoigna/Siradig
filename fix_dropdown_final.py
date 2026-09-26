with open('extension/content_script.js', 'r', encoding='utf-8') as f:
    c = f.read()
old_text = '    if (mes && exists("#mesDesde")) {\n      setValue("#mesDesde", mes);\n      console.log("[SIRADIG Auto] Paso: Mes seleccionado:", mes);\n    }'
new_text = '    if (mes && exists("#mesDesde")) {\n      const sel = document.querySelector("#mesDesde");\n      if (sel) { sel.value = mes; sel.dispatchEvent(new Event("change", { bubbles: true })); }\n      setValue("#mesDesde", mes);\n      console.log("[SIRADIG Auto] Paso: Mes seleccionado (change event):", mes);\n    }'
if old_text in c:
    c = c.replace(old_text, new_text)
    with open('extension/content_script.js', 'w', encoding='utf-8') as f:
        f.write(c)
    print('OK: dropdown mes corregido')
else:
    print('No se encontro el texto exacto - verificando archivo...')
    # Intento alternativo con linea aproximada
    lines = c.split('\n')
    for i, line in enumerate(lines):
        if 'Paso: Mes seleccionado' in line:
            print('Linea', i+1, ':', line)
