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
    func: () => {
      const btn = document.querySelector('.btn_empresa');
      if (btn) btn.click();
    }
  }).catch(err => console.error(err));
  setTimeout(async () => {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const carga = Array.from(document.querySelectorAll('a, span, button')).find(el => el.textContent.trim().toLowerCase() === 'carga de formulario');
        if (carga) carga.click();
      }
    });
  }, 2500);
  setTimeout(async () => {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const ded = document.querySelector('a[href="#header_deducciones"]') || Array.from(document.querySelectorAll('a[href="#header_deducciones"]')).find(a => a.textContent.toLowerCase().includes('deducciones'));
        if (ded) ded.click();
      }
    });
  }, 6000);
  statusEl.textContent = "Navegacion iniciada.";
});

document.getElementById("auto_cargar").addEventListener("click", async () => {
  statusEl.textContent = "Probando carga automatica (paso 4 en adelante)...";
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) {
    statusEl.textContent = "No se encontro pestaña activa.";
    return;
  }

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

  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: (r) => {
      const linkMedico = document.getElementById("link_agregar_gastos_medicos");
      if (linkMedico) { console.log("[SIRADIG Auto] Paso 4: Click link medicos"); linkMedico.click();         await new Promise(r => { const chk = () => { if (document.URL.includes("verGastosMedicos") || document.URL.includes("verMenuDeducciones")) return r(); setTimeout(chk, 400); }; chk(); }); }
      else { console.log("[SIRADIG Auto] ERROR: No encontro link"); return; }

      function waitFor(s, t=8000) {
        return new Promise(res => {
          const st = Date.now();
          const chk = () => { const el = document.querySelector(s); if (el) return res(el); if (Date.now()-st > t) return res(null); setTimeout(chk, 200); };
          chk();
        });
      }
      function setValue(s, v) {
        const el = document.querySelector(s); if (!el || v === undefined || v === null || v === "") return false; el.value = v; el.dispatchEvent(new Event("input", { bubbles: true })); el.dispatchEvent(new Event("change", { bubbles: true })); return true;
      }
      function findByText(t) {
        const l = t.toLowerCase(); return Array.from(document.querySelectorAll("a, button, input[type=button], span.ui-button-text")).find(el => el.textContent.trim().toLowerCase() === l);
      }
      function splitLegacy(n) { const p = (n||"").split("-"); return p.length === 2 ? { pv: p[0].trim(), num: p[1].trim() } : { pv: null, num: (n||"").trim() || null }; }
      function inferTipo(t, l) { const a = (t||"").toLowerCase(); const b = (l||"").toUpperCase(); if (a.includes("factura") && b === "B") return "6"; if (a.includes("factura") && b === "C") return "11"; if (a.includes("recibo") && b === "B") return "9"; if (a.includes("recibo") && b === "C") return "15"; if (a.includes("tique") || a.includes("ticket")) return "82"; return null; }
      function inferMes(f) { const m = (f||"").match(/^\d{1,2}\/(\d{1,2})\/\d{4}$/); return m ? String(parseInt(m[1], 10)) : null; }

      (async () => {
        await waitFor("#numeroDoc");
        setValue("#numeroDoc", r.cuit_emisor);
        document.querySelector("#numeroDoc").dispatchEvent(new Event("blur", { bubbles: true }));
        await new Promise(res => setTimeout(res, 800));
        const okCuit = setValue("#numeroDoc", r.cuit_emisor);
        console.log("[SIRADIG] Paso 5: CUIT", r.cuit_emisor, "OK:", okCuit);

        const mes = inferMes(r.fecha_emision);
        if (mes) { document.getElementById("mesDesde").value = mes; console.log("[SIRADIG] Paso 6: Mes", mes); }

        document.getElementById("btn_alta_comprobante").click();
        console.log("[SIRADIG] Paso 7: Alta");
        await waitFor("#cmpFechaEmision");

        setValue("#cmpFechaEmision", r.fecha_emision); console.log("[SIRADIG] Paso 8: Fecha", r.fecha_emision);
        const tipo = inferTipo(r.tipo_comprobante, r.letra); if (tipo) { setValue("#cmpTipo", tipo); console.log("[SIRADIG] Paso 9: Tipo", tipo); }
        if (r.punto_venta) setValue("#cmpPuntoVenta", r.punto_venta); else { const s = splitLegacy(r.numero_comprobante); setValue("#cmpPuntoVenta", s.pv); }
        if (r.numero_solo) setValue("#cmpNumero", r.numero_solo); else { const s = splitLegacy(r.numero_comprobante); setValue("#cmpNumero", s.num); }
        console.log("[SIRADIG] Paso 11: Numero cargado");

        setValue("#cmpMontoFacturado", r.importe_total); console.log("[SIRADIG] Paso 12: Monto", r.importe_total);
        const reint = document.querySelector("#cmpMontoReintegrado"); if (reint) { reint.value = "0"; reint.dispatchEvent(new Event("input", { bubbles: true })); }
        console.log("[SIRADIG] Paso 13: Reintegrado = 0");

        const btn = findByText("Agregar"); if (btn) { btn.click(); console.log("[SIRADIG] Paso 14: Agregar"); }
        await new Promise(res => setTimeout(res, 800));

        const btnGuardar = findByText("Guardar");
        if (btnGuardar) { setTimeout(() => { btnGuardar.click(); console.log("[SIRADIG] Paso 16: Guardar"); }, 500); }
        else console.log("[SIRADIG] Paso 16: No btn Guardar");
      })();
    },
    args: [receipt]
  }).catch(err => {
    console.error("Error:", err);
    statusEl.textContent = "Error al inyectar: " + err.message;
  });
});
