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
  await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: () => { const b = document.querySelector('.btn_empresa'); if (b) b.click(); } });
  setTimeout(async () => {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: () => { const c = Array.from(document.querySelectorAll('a, span, button')).find(e => e.textContent.trim().toLowerCase() === 'carga de formulario'); if (c) c.click(); } });
  }, 2500);
  setTimeout(async () => {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: () => { const d = document.querySelector('a[href="#header_deducciones"]') || Array.from(document.querySelectorAll('a[href="#header_deducciones"]')).find(a => a.textContent.toLowerCase().includes('deducciones')); if (d) d.click(); } });
  }, 6000);
  statusEl.textContent = "Navegacion iniciada. Revisa AFIP.";
});

document.getElementById("auto_cargar").addEventListener("click", async () => {
  statusEl.textContent = "Navegando a formulario...";
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) { statusEl.textContent = "No se encontro pestaña."; return; }

  // Si esta en menu o deducciones, navegar al formulario
  if (tab.url && (tab.url.includes("verMenuDeducciones") || tab.url.includes("verGastosMedicos"))) {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const link = document.getElementById("link_agregar_gastos_medicos") || Array.from(document.querySelectorAll("a, button, span, input")).find(el => (el.textContent || "").toLowerCase().includes("gastos médicos"));
        if (link) link.click();
        else console.log("[Auto] Link no encontrado");
      }
    });
    await new Promise(r => setTimeout(r, 2500));
  }

  statusEl.textContent = "Cargando datos...";
  const receipt = {
    razon_social: "ASIM LAURA SOLEDAD",
    cuit_emisor: "20123456789",
    importe_total: 250000,
    fecha_emision: "15/06/2025",
    tipo_comprobante: "Factura B",
    letra: "B",
    numero_comprobante: "001-00000001",
    punto_venta: "001",
    numero_solo: "00000001",
    categoria_gasto_siradig: "Gastos médicos y paramédicos"
  };
  const [tab2] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) { statusEl.textContent = "No se encontro pestaña activa."; return; }
  chrome.tabs.sendMessage(tab2.id, { type: "FILL_RECEIPT", receipt }, (resp) => {
    if (chrome.runtime.lastError) { statusEl.textContent = "Abre el formulario de Gastos Médicos primero."; return; }
    statusEl.textContent = resp && resp.ok ? (resp.warning ? "Completado (falta: " + resp.warning + ")" : "Datos cargados. Revisa y guarda.") : "No se pudo completar";
  });
});
