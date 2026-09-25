// Autocompleta formularios de SIRADIG para múltiples categorías.

console.log("[SIRADIG Auto] content_script.js inyectado en", location.href);

const CATEGORIA_LINKS = {
  medicos: "link_agregar_gastos_medicos",
  indumentaria: "link_agregar_gastos_indu_equip",
  cuota_medico: "link_agregar_cuotas_medico_asistenciales",
};

// --- Funciones de Utilidad ---

function irACategoria(categoriaKey) {
  const linkId = CATEGORIA_LINKS[categoriaKey];
  if (!linkId) return false;
  const link = document.getElementById(linkId);
  if (!link) return false;
  link.click();
  return true;
}

function findButtonByText(texto) {
  const candidato = Array.from(document.querySelectorAll("button, a, input[type=button], span")).find(
    (el) => el.textContent.trim().toLowerCase() === texto.toLowerCase()
  );
  if (!candidato) return null;
  return candidato.closest("button, a, input[type=button]") || candidato;
}

function setValue(selector, value) {
  const el = document.querySelector(selector);
  if (!el || value === undefined || value === null || value === "") return false;
  el.value = value;
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

function exists(selector) {
  return !!document.querySelector(selector);
}

// --- Lógica de Negocio / Inferencia ---

function inferConcepto(categoria) {
  const texto = (categoria || "").toLowerCase();
  return texto.includes("equipo") || texto.includes("equipamiento") ? "2" : "1";
}

function inferMes(fechaEmision) {
  const match = (fechaEmision || "").match(/^\d{1,2}\/(\d{1,2})\/\d{4}$/);
  if (!match) return null;
  return String(parseInt(match[1], 10));
}

function inferTipoComprobante(tipo, letra) {
  const t = (tipo || "").toLowerCase();
  const l = (letra || "").toUpperCase();
  if (t.includes("factura") && l === "B") return "6";
  if (t.includes("factura") && l === "C") return "11";
  if (t.includes("recibo") && l === "B") return "9";
  if (t.includes("recibo") && l === "C") return "15";
  if (t.includes("tique") || t.includes("ticket")) return "82";
  return null;
}

function findAltaButton() {
  return (
    document.querySelector("#btn_alta_comprobante") || 
    document.querySelector("#btn_alta_mes") ||
    Array.from(document.querySelectorAll("a, button, input[type=button]")).find((el) => {
      const txt = (el.textContent || el.value || "").toLowerCase();
      return txt.includes("alta de comprobante") || txt.includes("agregar mes individual");
    })
  );
}

// --- Acción Principal ---

async function fillReceipt(receipt) {
  const pendientes = [];

  // 1. CUIT del Emisor (común)
  if (!setValue("#numeroDoc", receipt.cuit_emisor)) {
    if (exists("#numeroDoc")) pendientes.push("CUIT (#numeroDoc)");
  }

  // 2. Campos previos según categoría
  if (exists("#idConcepto")) {
    setValue("#idConcepto", inferConcepto(receipt.categoria_gasto_siradig));
  }
  
  // 3. Abrir Modal de Alta
  const botonAlta = findAltaButton();
  if (!botonAlta) {
    pendientes.push("No se encontró botón para iniciar la carga (Alta/Agregar)");
    return pendientes;
  }

  botonAlta.click();
  await new Promise((resolve) => setTimeout(resolve, 600));

  // 4. Completar datos según el tipo de formulario detectado
  
  // Caso Cuota Médico-asistencial
  if (exists("#detalleIndividualMes")) {
    const mes = inferMes(receipt.fecha_emision);
    if (!mes || !setValue("#detalleIndividualMes", mes)) pendientes.push("Mes (#detalleIndividualMes)");
    if (!setValue("#detalleIndividualMontoMensual", receipt.importe_total)) {
      pendientes.push("Monto Mensual (#detalleIndividualMontoMensual)");
    }
  } 
  // Caso Comprobante Estándar (Médicos, Indumentaria, etc.)
  else if (exists("#cmpFechaEmision")) {
    if (!setValue("#cmpFechaEmision", receipt.fecha_emision)) pendientes.push("Fecha (#cmpFechaEmision)");

    const tipoValue = inferTipoComprobante(receipt.tipo_comprobante, receipt.letra);
    if (!tipoValue || !setValue("#cmpTipo", tipoValue)) {
      pendientes.push("Tipo de comprobante (#cmpTipo)");
    }

    // Usar campos nuevos de la BD (punto_venta, numero_solo) con fallback al split del viejo numero_comprobante
    if (receipt.punto_venta) {
      setValue("#cmpPuntoVenta", receipt.punto_venta);
    } else {
      const { puntoVenta } = splitNumeroComprobanteLegacy(receipt.numero_comprobante);
      setValue("#cmpPuntoVenta", puntoVenta);
    }

    if (receipt.numero_solo) {
      setValue("#cmpNumero", receipt.numero_solo);
    } else {
      const { numero } = splitNumeroComprobanteLegacy(receipt.numero_comprobante);
      setValue("#cmpNumero", numero);
    }

    setValue("#cmpMontoFacturado", receipt.importe_total);
    pendientes.push("Monto Reintegrado - completar a mano");
  } else {
    pendientes.push("Formulario interno no reconocido");
  }

  // 5. Intentar cerrar/agregar
  const botonAgregar = findButtonByText("Agregar");
  if (botonAgregar) {
    botonAgregar.click();
  } else {
    pendientes.push("No se pudo hacer click automático en 'Agregar'");
  }

  return pendientes;
}

// Helper legacy por si vienen comprobantes viejos sin los campos nuevos
function splitNumeroComprobanteLegacy(numero) {
  const partes = (numero || "").split("-");
  if (partes.length === 2) return { puntoVenta: partes[0].trim(), numero: partes[1].trim() };
  return { puntoVenta: null, numero: (numero || "").trim() || null };
}

function guardarFormulario() {
  const boton = findButtonByText("Guardar");
  if (!boton) return false;
  boton.click();
  return true;
}

// --- Navegacion automatica hasta Deducciones y Desgravaciones ---

function waitFor(findFn, { timeout = 8000, interval = 200 } = {}) {
  return new Promise((resolve) => {
    const start = Date.now();
    const check = () => {
      const el = findFn();
      if (el) return resolve(el);
      if (Date.now() - start > timeout) return resolve(null);
      setTimeout(check, interval);
    };
    check();
  });
}

function findEmpresaButton() {
  return document.querySelector(".btn_empresa");
}

function findCargaFormularioButton() {
  const span = Array.from(document.querySelectorAll("span.ui-button-text")).find(
    (s) => s.textContent.trim().toLowerCase() === "carga de formulario"
  );
  if (!span) return null;
  return span.closest("button, a, input[type=button]") || span.parentElement;
}

function findDeduccionesAnchor() {
  return (
    Array.from(document.querySelectorAll('a[href="#header_deducciones"]')).find((a) =>
      a.textContent.toLowerCase().includes("deducciones y desgravaciones")
    ) || document.querySelector('a[href="#header_deducciones"]')
  );
}

// Ejecuta el paso correspondiente a la pantalla actual del flujo de navegacion
async function runNavigationStep() {
  const href = location.href;
  console.log("[SIRADIG Auto] runNavigationStep en", href);

  if (href.includes("menu_sel_empresa.jsp")) {
    const btn = await waitFor(findEmpresaButton);
    console.log("[SIRADIG Auto] boton empresa:", btn);
    if (!btn) return false;
    btn.click();
    return true;
  }

  if (href.includes("determinarContribuyente.do")) {
    const btn = await waitFor(findCargaFormularioButton);
    console.log("[SIRADIG Auto] boton carga formulario:", btn);
    if (!btn) return false;
    btn.click();
    return true;
  }

  if (href.includes("verMenuDeducciones.do")) {
    const anchor = await waitFor(findDeduccionesAnchor);
    console.log("[SIRADIG Auto] anchor deducciones:", anchor);
    if (!anchor) return false;
    anchor.click();
    chrome.storage.local.set({ navFlowActive: false });
    return true;
  }

  return false;
}

// Al cargar cualquier pagina de SIRADIG, continua el flujo si esta activo
chrome.storage.local.get(["navFlowActive"], (data) => {
  if (data.navFlowActive) {
    console.log("[SIRADIG Auto] navFlowActive detectado al cargar la pagina");
    runNavigationStep();
  }
});

// --- Escucha de Mensajes ---

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "GOTO_CATEGORY") {
    const ok = irACategoria(message.categoriaKey);
    sendResponse(ok ? { ok: true } : { ok: false });
    return;
  }

  if (message.type === "START_NAV_FLOW") {
    chrome.storage.local.set({ navFlowActive: true }, async () => {
      const ok = await runNavigationStep();
      sendResponse({ ok });
    });
    return true;
  }

  if (message.type === "GUARDAR_FORMULARIO") {
    const ok = guardarFormulario();
    sendResponse(ok ? { ok: true } : { ok: false });
    return;
  }

  if (message.type === "FILL_RECEIPT") {
    fillReceipt(message.receipt)
      .then((pendientes) => {
        if (pendientes.length === 0) {
          sendResponse({ ok: true });
        } else {
          sendResponse({ ok: true, warning: `Faltó: ${pendientes.join(", ")}` });
        }
      })
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true; 
  }
});
