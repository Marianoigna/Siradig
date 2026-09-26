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

document.getElementById("autocompletar").addEventListener("click", async () => {
  statusEl.textContent = "Buscando proximo comprobante...";
  const { apiToken } = await chrome.storage.local.get(["apiToken"]);
  if (!apiToken) {
    statusEl.textContent = "Primero guarda tu token.";
    return;
  }

  let receipts;
  try {
    const resp = await fetch(`${API_BASE}/api/receipts/pending/`, {
      headers: { Authorization: `Token ${apiToken}` },
    });
    if (!resp.ok) throw new Error(`API respondio ${resp.status}`);
    receipts = await resp.json();
  } catch (err) {
    statusEl.textContent = `Error consultando la API: ${err.message}`;
    return;
  }

  if (!receipts.length) {
    statusEl.textContent = "No hay comprobantes pendientes.";
    return;
  }

  const receipt = receipts[0];
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) {
    statusEl.textContent = "No se encontro una pestana activa.";
    return;
  }

  chrome.tabs.sendMessage(tab.id, { type: "FILL_RECEIPT", receipt }, async (response) => {
    if (chrome.runtime.lastError) {
      statusEl.textContent = "Abri el formulario de SIRADIG (Gastos de Indumentaria y Equipamiento) primero.";
      return;
    }
    if (response && response.ok) {
      statusEl.textContent = response.warning
        ? `Completado parcialmente. ${response.warning}`
        : "Datos completados. Revisa y guarda en SIRADIG.";
      await fetch(`${API_BASE}/api/receipts/${receipt.id}/`, {
        method: "PATCH",
        headers: {
          Authorization: `Token ${apiToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ estado: "cargado_en_siradig" }),
      });
    } else {
      statusEl.textContent = `No se pudo completar: ${response ? response.error : "error desconocido"}`;
    }
  });
});

document.getElementById("guardar").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) {
    statusEl.textContent = "No se encontro una pestana activa.";
    return;
  }
  chrome.tabs.sendMessage(tab.id, { type: "GUARDAR_FORMULARIO" }, (response) => {
    if (chrome.runtime.lastError) {
      statusEl.textContent = "Abri el formulario de SIRADIG primero.";
      return;
    }
    statusEl.textContent = response && response.ok
      ? "Formulario guardado."
      : `No se pudo guardar: ${response ? response.error : "error desconocido"}`;
  });
});
document.getElementById('btn_cuota_medico').addEventListener('click', () => {
  chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
    chrome.tabs.sendMessage(tabs[0].id, {type: 'GOTO_CATEGORY', categoriaKey: 'cuota_medico'});
  });
});

document.getElementById("auto_cargar").addEventListener("click", async () => {
  statusEl.textContent = "Cargando datos de ejemplo...";

  // Datos de ejemplo (como en POC/autocompletar.py - ASIM LAURA SOLEDAD)
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

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) {
    statusEl.textContent = "No se encontró pestaña activa.";
    return;
  }

  // Enviar datos al content_script (como hace autocompletar.py con Playwright)
  chrome.tabs.sendMessage(tab.id, { type: "FILL_RECEIPT", receipt }, async (response) => {
    if (chrome.runtime.lastError) {
      statusEl.textContent = "Abre el formulario (verGastosMedicos.do) primero.";
      return;
    }
    if (response && response.ok) {
      statusEl.textContent = response.warning ? `Completado: ${response.warning}` : "Datos cargados. Revisa y guarda.";
    } else {
      statusEl.textContent = `No se pudo completar: ${response ? response.error : "desconocido"}`;
    }
  });
});

document.getElementById("ir_deducciones").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url || !tab.url.includes("serviciosjava2.afip.gob.ar/radig")) {
    statusEl.textContent = "Primero ingresa a SiRADIG (menu de seleccion de persona) desde el portal AFIP.";
    return;
  }
  statusEl.textContent = "Paso 1: Seleccionando usuario...";
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => { document.querySelector('.btn_empresa').click(); }
  }).catch(err => console.error(err));
  setTimeout(async () => {
    statusEl.textContent = "Paso 2: Carga de Formulario...";
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const carga = Array.from(document.querySelectorAll('a, span, button')).find(el => el.textContent.trim().toLowerCase() === 'carga de formulario');
        if (carga) carga.click();
      }
    });
  }, 2500);
  setTimeout(async () => {
    statusEl.textContent = "Paso 3: Deducciones...";
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const ded = document.querySelector('a[href="#header_deducciones"]') || Array.from(document.querySelectorAll('a[href="#header_deducciones"]')).find(a => a.textContent.toLowerCase().includes('deducciones'));
        if (ded) ded.click();
      }
    });
  }, 6000);
  statusEl.textContent = "Navegacion iniciada automaticamente. Revisa AFIP.";
});