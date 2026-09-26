with open('extension/content_script.js', 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

# Find line with '#cmpFechaEmision' in standard case and insert after it
for i, line in enumerate(lines):
    if 'if (!setValue("#cmpFechaEmision", receipt.fecha_emision))' in line:
        # Insert after the next line (which is the closing }); and before tipoValue
        # Let's insert after the line that sets fecha
        j = i + 1
        while j < len(lines) and 'tipoValue' not in lines[j]:
            j += 1
        # Insert before tipoValue line
        insert_text = [
            '',
            '    // Seleccionar mes desde fecha de emision',
            '    const mes = inferMes(receipt.fecha_emision);',
            '    if (mes && exists("#mesDesde")) {',
            '      setValue("#mesDesde", mes);',
            '      console.log("[SIRADIG Auto] Mes seleccionado:", mes);',
            '    }'
        ]
        lines = lines[:j] + insert_text + lines[j:]
        break

with open('extension/content_script.js', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('Mes agregado en formulario estandar')
