with open('extension/popup.js', 'r', encoding='utf-8') as f:
    c = f.read()

old_block = '''  statusEl.textContent = "Cargando datos...";
  const receipt = {
    razon_social: "ASIM LAURA SOLEDAD",
    cuit_emisor: "27273080622",
    Periodo: "9",
    importe_total: 250000,
    fecha_emision: "15/09/2026",
    tipo_comprobante: "Factura B",
    letra: "B",
    numero_comprobante: "001-00000001",
    punto_venta: "001",
    numero_solo: "00000001",
    categoria_gasto_siradig: "Gastos m\u00e9dicos y param\u00e9dicos"
  };'''

new_block = '''  statusEl.textContent = "Consultando DB...";
  chrome.storage.local.get(["apiToken"], async (data) => {
    const token = (data && data.apiToken) ? data.apiToken.trim() : "";
    try {
      const resp = await fetch(API_BASE + "/api/receipts/pending/", {
        headers: token ? { "Authorization": "Token " + token } : {}
      });
      if (resp.ok) {
        const list = await resp.json();
        if (list && list.length > 0) {
          const r = list[0];
          const receipt = {
            razon_social: r.razon_social || "ASIM LAURA SOLEDAD",
            cuit_emisor: r.cuit_emisor || "27273080622",
            Periodo: "9",
            importe_total: r.importe_total || 250000,
            fecha_emision: r.fecha_emision || "15/09/2026",
            tipo_comprobante: r.tipo_comprobante || "Factura B",
            letra: r.letra || "B",
            numero_comprobante: r.numero_comprobante || "001-00000001",
            punto_venta: r.punto_venta || "001",
            numero_solo: r.numero_solo || "00000001",
            categoria_gasto_siradig: r.categoria_gasto_siradig || "Gastos m\u00e9dicos y param\u00e9dicos"
          };
          await cargarFormulario(tab2, receipt);
          return;
        }
      }
      statusEl.textContent = "No hay recibos pendientes en DB. Usando ejemplo local.";
    } catch (e) {
      statusEl.textContent = "Error conectando con DB.";
      console.log("DB fetch error:", e);
    }
    // Fallback local
    const receipt = {
      razon_social: "ASIM LAURA SOLEDAD",
      cuit_emisor: "27273080622",
      Periodo: "9",
      importe_total: 250000,
      fecha_emision: "15/09/2026",
      tipo_comprobante: "Factura B",
      letra: "B",
      numero_comprobante: "001-00000001",
      punto_venta: "001",
      numero_solo: "00000001",
      categoria_gasto_siradig: "Gastos m\u00e9dicos y param\u00e9dicos"
    };
    await cargarFormulario(tab2, receipt);
  });
  return;'''

# But since we need to restructure, let me do it more carefully
with open('extension/popup.js', 'r', encoding='utf-8') as f:
    c = f.read()

# Find the start of auto_cargar listener and replace the receipt definition + message part
start_marker = '  statusEl.textContent = "Cargando datos...";'
end_marker = '  chrome.tabs.sendMessage(tab.id, { type: "FILL_RECEIPT", receipt }, (resp) => {'

new_content = '''  statusEl.textContent = "Consultando DB...";
  chrome.storage.local.get(["apiToken"], async (data) => {
    const token = (data && data.apiToken) ? data.apiToken.trim() : "";
    try {
      const resp = await fetch(API_BASE + "/api/receipts/pending/", {
        headers: token ? { "Authorization": "Token " + token } : {}
      });
      if (resp.ok) {
        const list = await resp.json();
        if (list && list.length > 0) {
          const r = list[0];
          const receipt = {
            razon_social: r.razon_social || "ASIM LAURA SOLEDAD",
            cuit_emisor: r.cuit_emisor || "27273080622",
            Periodo: "9",
            importe_total: r.importe_total || 250000,
            fecha_emision: r.fecha_emision || "15/09/2026",
            tipo_comprobante: r.tipo_comprobante || "Factura B",
            letra: r.letra || "B",
            numero_comprobante: r.numero_comprobante || "001-00000001",
            punto_venta: r.punto_venta || "001",
            numero_solo: r.numero_solo || "00000001",
            categoria_gasto_siradig: r.categoria_gasto_siradig || "Gastos médicos y paramédicos"
          };
          await cargarFormulario(tab, receipt);
          return;
        }
      }
    } catch (e) {
      console.log("DB fetch error:", e);
    }
    // Fallback local
    const receipt = {
      razon_social: "ASIM LAURA SOLEDAD",
      cuit_emisor: "27273080622",
      Periodo: "9",
      importe_total: 250000,
      fecha_emision: "15/06/2026",
      tipo_comprobante: "Factura B",
      letra: "B",
      numero_comprobante: "001-00000001",
      punto_venta: "001",
      numero_solo: "00000001",
      categoria_gasto_siradig: "Gastos médicos y paramédicos"
    };
    await cargarFormulario(tab, receipt);
  });
'''

# Find where to insert the new content
c = c.replace('  statusEl.textContent = "Cargando datos...";\n  const receipt = {', new_content)

# But we also need to wrap the message sending in an async function
with open('extension/popup.js', 'w', encoding='utf-8') as f:
    f.write(c)
print('popup.js actualizado con fetch DB')
