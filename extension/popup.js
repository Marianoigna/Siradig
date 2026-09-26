const API_BASE = "https://siradig.onrender.com";
const tokenInput = document.getElementById("token");
const statusEl = document.getElementById("status");

chrome.storage.local.get(["apiToken"], (data) => {
  if (data.apiToken) tokenInput.value = data.apiToken;
});

document.getElementById("save").addEventListener("click", () => {
  chrome.storage.local.set({ apiToken: tokenInput.value.trim() }, () => {
    statusEl.textContent = "Token guardado.";
  });
});

document.getElementById("ir_deducciones").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url || !tab.url.includes("serviciosjava2.afip.gob.ar/radig")) {
    statusEl.textContent = "Primero ingresa a SiRADIG.";
    return;
  }
  statusEl.textContent = "Navegando...";
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => { const b = document.querySelector('.btn_empresa'); if (b) b.click(); }
  });
  setTimeout(async () => {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => { const c = Array.from(document.querySelectorAll('a, span, button')).find(e => e.textContent.trim().toLowerCase() === 'carga de formulario'); if (c) c.click(); }
    });
  }, 2500);
  setTimeout(async () => {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => { const d = document.querySelector('a[href="#header_deducciones"]') || Array.from(document.querySelectorAll('a[href="#header_deducciones"]')).find(a => a.textContent.toLowerCase().includes('deducciones')); if (d) d.click(); }
    });
  }, 6000);
  statusEl.textContent = "Navegación iniciada. Revisa AFIP.";
});

document.getElementById("auto_cargar").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) { statusEl.textContent = "No se encontró pestaña activa."; return; }
  if (!tab.url || !tab.url.includes("serviciosjava2.afip.gob.ar/radig")) {
    statusEl.textContent = "⚠️ Abrí SIRADIG primero.";
    return;
  }
  // NAVEGACION DIRECTA al formulario de Gastos Medicos
  if (!tab.url.includes("verGastosMedicos")) {
    await chrome.tabs.update(tab.id, { url: "https://serviciosjava2.afip.gob.ar/radig/jsp/verGastosMedicos.do" });
    await new Promise(r => setTimeout(r, 1500));
  }
  statusEl.textContent = "Consultando facturas pendientes...";
  const tokenData = await new Promise(r => chrome.storage.local.get(["apiToken"], r));
  const token = tokenData.apiToken?.trim() || "";
  try {
    const resp = await fetch(API_BASE + "/api/receipts/pending/", {
      headers: token ? { "Authorization": "Token " + token } : {}
    });
    if (!resp.ok) { statusEl.textContent = "❌ Error al consultar la base de datos."; return; }
    const lista = await resp.json();
    if (!lista || lista.length === 0) { statusEl.textContent = "✅ No hay facturas pendientes."; return; }
    const resultados = [];
    for (let i = 0; i < lista.length; i++) {
      const factura = lista[i];
      statusEl.textContent = `Cargando factura ${i + 1} de ${lista.length}...`;
      const receipt = {
        id: factura.id,
        razon_social: factura.razon_social || "SIN RAZON SOCIAL",
        cuit_emisor: factura.cuit_emisor || "00000000000",
        importe_total: factura.importe_total || 0,
        fecha_emision: factura.fecha_emision || "01/01/2025",
        tipo_comprobante: factura.tipo_comprobante || "Factura",
        letra: factura.letra || "B",
        numero_comprobante: factura.numero_comprobante || "0000-00000000",
        punto_venta: factura.punto_venta || factura.numero_comprobante?.split("-")[0] || "0000",
        numero_solo: factura.numero_solo || factura.numero_comprobante?.split("-")[1] || "00000000",
        categoria_gasto_siradig: factura.categoria_gasto_siradig || "Gastos médicos y paramédicos"
      };
      const respuesta = await new Promise((resolve) => {
        chrome.tabs.sendMessage(tab.id, { type: "FILL_RECEIPT", receipt: receipt }, (resp) => {
          if (chrome.runtime.lastError) { resolve({ ok: false, error: "Content script no responde" }); }
          else { resolve(resp); }
        });
      });
      if (respuesta && respuesta.ok) { resultados.push({ id: factura.id, status: "success" }); }
      else { resultados.push({ id: factura.id, status: "error", error: respuesta?.error || "Error desconocido" }); }
      if (i < lista.length - 1) { await new Promise(r => setTimeout(r, 2000)); }
    }
    statusEl.textContent = "Sincronizando con la base de datos...";
    for (const resultado of resultados) {
      try {
        const endpoint = resultado.status === "success" ? `/api/receipts/${resultado.id}/confirm/` : `/api/receipts/${resultado.id}/error/`;
        await fetch(API_BASE + endpoint, {
          method: "PUT",
          headers: { "Authorization": "Token " + token, "Content-Type": "application/json" },
          body: JSON.stringify({ error_message: resultado.error || null })
        });
      } catch (e) { console.warn("No se pudo sincronizar factura", resultado.id, e); }
    }
    const exitosas = resultados.filter(r => r.status === "success").length;
    const fallidas = resultados.filter(r => r.status === "error").length;
    if (fallidas === 0) { statusEl.textContent = `✅ ¡Todas las ${exitosas} facturas cargadas correctamente!`; }
    else { statusEl.textContent = `⚠️ ${exitosas} cargadas, ${fallidas} fallaron. Revisá tu dashboard.`; }
  } catch (e) { statusEl.textContent = "❌ Error: " + e.message; }
});
