// Autocompleta el modal "Alta de Comprobante", comun a varias categorias de SIRADIG.
// Selectores confirmados: numeroDoc, idConcepto (solo Indumentaria), mesDesde (solo Medicos),
// btn_alta_comprobante, cmpFechaEmision, cmpTipo, cmpPuntoVenta, cmpNumero, cmpMontoFacturado.

// Mapea la categoria interna del comprobante al link de "Agregar Deducciones y Desgravaciones"
// que hay que clickear para llegar al formulario correspondiente en SIRADIG.
const CATEGORIA_LINKS = {
  medicos: "link_agregar_gastos_medicos",
  indumentaria: "link_agregar_gastos_indu_equip",
};

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
  // El texto suele estar en un <span> interno; el click hay que hacerlo en el boton/enlace que lo contiene.
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

function inferConcepto(categoria) {
  const texto = (categoria || "").toLowerCase();
  return texto.includes("equipo") || texto.includes("equipamiento") ? "2" : "1"; // 1=Indumentaria, 2=Equipamiento
}

function inferMes(fechaEmision) {
  // Espera formato DD/MM/AAAA
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
  return null; // no hay mapeo confiable (ej. letra A no es deducible en este formulario)
}

function splitNumeroComprobante(numero) {
  const partes = (numero || "").split("-");
  if (partes.length === 2) return { puntoVenta: partes[0].trim(), numero: partes[1].trim() };
  return { puntoVenta: null, numero: (numero || "").trim() || null };
}

function findAltaComprobanteButton() {
  return (
    document.querySelector("#btn_alta_comprobante") ||
    Array.from(document.querySelectorAll("a, button, input[type=button]")).find((el) =>
      (el.textContent || el.value || "").toLowerCase().includes("alta de comprobante")
    )
  );
}

async function fillReceipt(receipt) {
  const pendientes = [];

  if (!setValue("#numeroDoc", receipt.cuit_emisor)) pendientes.push("CUIT (#numeroDoc)");

  // Campos previos que varian por categoria: se completan solo si existen en la pagina actual.
  if (exists("#idConcepto")) {
    if (!setValue("#idConcepto", inferConcepto(receipt.categoria_gasto_siradig))) {
      pendientes.push("Concepto (#idConcepto)");
    }
  }
  if (exists("#mesDesde")) {
    const mes = inferMes(receipt.fecha_emision);
    if (!mes || !setValue("#mesDesde", mes)) pendientes.push("Periodo (#mesDesde)");
  }

  const boton = findAltaComprobanteButton();
  if (!boton) {
    pendientes.push("boton 'Alta de Comprobante' (no encontrado en esta pantalla)");
    return pendientes;
  }

  boton.click();
  // Le damos tiempo al modal a renderizarse antes de completar sus campos.
  await new Promise((resolve) => setTimeout(resolve, 500));

  if (!setValue("#cmpFechaEmision", receipt.fecha_emision)) pendientes.push("Fecha (#cmpFechaEmision)");

  const tipoValue = inferTipoComprobante(receipt.tipo_comprobante, receipt.letra);
  if (!tipoValue || !setValue("#cmpTipo", tipoValue)) {
    pendientes.push("Tipo de comprobante (#cmpTipo) - revisar manualmente");
  }

  const { puntoVenta, numero } = splitNumeroComprobante(receipt.numero_comprobante);
  if (!setValue("#cmpPuntoVenta", puntoVenta)) pendientes.push("Punto de venta (#cmpPuntoVenta)");
  if (!setValue("#cmpNumero", numero)) pendientes.push("Numero de comprobante (#cmpNumero)");

  if (!setValue("#cmpMontoFacturado", receipt.importe_total)) pendientes.push("Monto (#cmpMontoFacturado)");

  // Monto Reintegrado no lo extrae el OCR (depende de reintegros de obra social/prepaga): queda a cargo del usuario.
  pendientes.push("Monto Reintegrado (#cmpMontoReintegrado) - completar a mano si corresponde");

  const botonAgregar = findButtonByText("Agregar");
  if (botonAgregar) {
    botonAgregar.click();
  } else {
    pendientes.push("boton 'Agregar' del modal (no encontrado, el comprobante no quedo guardado en la tabla)");
  }

  return pendientes;
}

function guardarFormulario() {
  const boton = findButtonByText("Guardar");
  if (!boton) return false;
  boton.click();
  return true;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "GOTO_CATEGORY") {
    const ok = irACategoria(message.categoriaKey);
    sendResponse(ok ? { ok: true } : { ok: false, error: "No se encontro el link de esa categoria en esta pagina." });
    return;
  }

  if (message.type === "GUARDAR_FORMULARIO") {
    const ok = guardarFormulario();
    sendResponse(ok ? { ok: true } : { ok: false, error: "No se encontro el boton 'Guardar' en esta pagina." });
    return;
  }

  if (message.type !== "FILL_RECEIPT") return;

  fillReceipt(message.receipt)
    .then((pendientes) => {
      if (pendientes.length === 0) {
        sendResponse({ ok: true });
      } else {
        sendResponse({ ok: true, warning: `Falta completar a mano: ${pendientes.join(", ")}` });
      }
    })
    .catch((err) => sendResponse({ ok: false, error: err.message }));

  return true; // respuesta asincronica
});
