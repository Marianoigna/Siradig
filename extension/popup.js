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
  statusEl.textContent = "Probando carga automatica (paso 4 en adelante)...";
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) {
    statusEl.textContent = "No se encontro una pestana activa.";
    return;
  }

  // Usar receipt de ejemplo para probar desde el paso 4 (click link medicos)
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => {
      // Simplified version: starts at clicking the medical link
      const linkMedico = document.getElementById("link_agregar_gastos_medicos");
      if (linkMedico) { 
        console.log("[SIRADIG Auto] Paso 4: Click link medicos");
        linkMedico.click(); 
      } else {
        console.log("[SIRADIG Auto] ERROR: No encontro link_agregar_gastos_medicos");
        return;
      }

      // Helper functions (same as before)
      function waitFor(selector, timeout = 8000) {
        return new Promise((resolve) => {
          const start = Date.now();
          const check = () => {
            const el = document.querySelector(selector);
            if (el) return resolve(el);
            if (Date.now() - start > timeout) return resolve(null);
            setTimeout(check, 200);
          };
          check();
        });
      }
      function findByText(text) {
        const lower = text.toLowerCase();
        return Array.from(document.querySelectorAll("a, button, input[type=button], span.ui-button-text")).find(
          (el) => el.textContent.trim().toLowerCase() === lower
        );
      }
      function setValue(selector, value) {
        const el = document.querySelector(selector);
        if (!el || value === undefined || value === null || value === "") return false;
        el.value = value;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
      function splitLegacy(numero) {
        const partes = (numero || "").split("-");
        if (partes.length === 2) return { puntoVenta: partes[0].trim(), numero: partes[1].trim() };
        return { puntoVenta: null, numero: (numero || "").trim() || null };
      }
      function inferConcepto(categoria) {
        const t = (categoria || "").toLowerCase();
        return t.includes("equipo") || t.includes("equipamiento") ? "2" : "1";
      }
      function inferTipo(tipo, letra) {
        const t = (tipo || "").toLowerCase();
        const l = (letra || "").toUpperCase();
        if (t.includes("factura") && l === "B") return "6";
        if (t.includes("factura") && l === "C") return "11";
        if (t.includes("recibo") && l === "B") return "9";
        if (t.includes("recibo") && l === "C") return "15";
        if (t.includes("tique") || t.includes("ticket")) return "82";
        return null;
      }
      function inferMes(fechaEmision) {
        const match = (fechaEmision || "").match(/^\d{1,2}\/(\d{1,2})\/\d{4}$/);
        if (!match) return null;
        return String(parseInt(match[1], 10));
      }

      const receipt = {
        razon_social: "ASIM LAURA SOLEDAD",
        cuit_emisor: "20123456789",
        importe_total: 250000,
        fecha_emision: "15/06/2025",
        tipo_comprobante: "Factura B",
        letra: "B",
        numero_comprobante: "001-00000001",
        numero_solo: "00000001",
        punto_venta: "001",
        categoria_gasto_siradig: "Gastos médicos y paramédicos"
      };

      (async () => {
        await waitFor("#numeroDoc");
        console.log("[SIRADIG Auto] Esperando formulario...");
        
        // PASO 5: CUIT
        const okCuit = setValue("#numeroDoc", receipt.cuit_emisor);
        console.log("[SIRADIG Auto] Paso 5: CUIT =", receipt.cuit_emisor, "OK:", okCuit);
        const cuitEl = document.querySelector("#numeroDoc");
        if (cuitEl) cuitEl.dispatchEvent(new Event("blur", { bubbles: true }));
        await new Promise(r => setTimeout(r, 800));

        // Verificar error en CUIT
        const errorCuit = document.querySelector(".validation-error, .error, .ui-state-error") ||
                          Array.from(document.querySelectorAll("label, span, div")).find(e => e.textContent.trim().toLowerCase().includes("error"));
        if (errorCuit) {
          console.log("[SIRADIG Auto] Error en CUIT - Volver");
          const volver = findByText("Volver");
          if (volver) volver.click();
          return;
        }

        // PASO 6: Periodo
        const mes = inferMes(receipt.fecha_emision);
        if (mes) {
          const select = document.getElementById("mesDesde");
          if (select) select.value = mes;
          console.log("[SIRADIG Auto] Paso 6: Mes =", mes);
        }

        // PASO 7: Alta de Comprobante
        const btnAlta = document.getElementById("btn_alta_comprobante");
        if (btnAlta) { 
          console.log("[SIRADIG Auto] Paso 7: Click Alta"); 
          btnAlta.click(); 
        } else { 
          console.log("[SIRADIG Auto] Paso 7: No btn Alta"); 
          return; 
        }
        await waitFor("#cmpFechaEmision");

        // PASO 8: Fecha
        setValue("#cmpFechaEmision", receipt.fecha_emision);
        console.log("[SIRADIG Auto] Paso 8: Fecha =", receipt.fecha_emision);

        // PASO 9: Tipo
        const tipoValue = inferTipo(receipt.tipo_comprobante, receipt.letra);
        if (tipoValue) { 
          setValue("#cmpTipo", tipoValue); 
          console.log("[SIRADIG Auto] Paso 9: Tipo =", tipoValue); 
        }

        // PASO 10: Concepto (si existe)
        if (document.querySelector("#idConcepto")) {
          setValue("#idConcepto", inferConcepto(receipt.categoria_gasto_siradig));
        }

        // PASO 11: Numero de comprobante
        if (receipt.punto_venta) { 
          setValue("#cmpPuntoVenta", receipt.punto_venta); 
        } else { 
          const split = splitLegacy(receipt.numero_comprobante); 
          setValue("#cmpPuntoVenta", split.puntoVenta); 
        }
        if (receipt.numero_solo) { 
          setValue("#cmpNumero", receipt.numero_solo); 
        } else { 
          const split = splitLegacy(receipt.numero_comprobante); 
          setValue("#cmpNumero", split.numero); 
        }
        console.log("[SIRADIG Auto] Paso 11: Numero cargado");

        // PASO 12: Monto
        setValue("#cmpMontoFacturado", receipt.importe_total);
        console.log("[SIRADIG Auto] Paso 12: Monto =", receipt.importe_total);

        // PASO 13: Monto reintegrado = 0
        const montoReint = document.querySelector("#cmpMontoReintegrado");
        if (montoReint) { 
          montoReint.value = "0"; 
          montoReint.dispatchEvent(new Event("input", { bubbles: true })); 
        }
        console.log("[SIRADIG Auto] Paso 13: Monto Reintegrado = 0");

        // PASO 14: Click "Agregar"
        const btnAgregar = findByText("Agregar");
        if (btnAgregar) { 
          console.log("[SIRADIG Auto] Paso 14: Click Agregar"); 
          btnAgregar.click(); 
        } else { 
          console.log("[SIRADIG Auto] Paso 14: No btn Agregar"); 
          return; 
        }
        await new Promise(r => setTimeout(r, 800));

        // PASO 15: Error -> Cancelar
        const errorForm = document.querySelector(".validation-error, .error, .ui-state-error") ||
                          Array.from(document.querySelectorAll("label, span, div")).find(e => e.textContent.trim().toLowerCase().includes("error"));
        if (errorForm) {
          console.log("[SIRADIG Auto] Error en formulario - Cancelar");
          const cancelar = findByText("Cancelar");
          if (cancelar) cancelar.click();
          return;
        }

        // PASO 16: Click "Guardar"
        setTimeout(() => {
          const btnGuardar = findByText("Guardar");
          if (btnGuardar) { 
            console.log("[SIRADIG Auto] Paso 16: Click Guardar"); 
            btnGuardar.click(); 
          } else { 
            console.log("[SIRADIG Auto] Paso 16: No btn Guardar"); 
          }
        }, 1000);

        console.log("[SIRADIG Auto] Carga automatica completada para", receipt.razon_social);
      })().catch(err => {
        console.error("[SIRADIG Auto] Error en carga automatica:", err);
        const cancelar = findByText("Cancelar");
        if (cancelar) cancelar.click();
      });
    },
  }).catch(err => {
    console.error("[SIRADIG Auto] Error inyectando script:", err);
    statusEl.textContent = "Error: " + err.message;
  });
});document.getElementById("ir_deducciones").addEventListener("click", async () => {
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