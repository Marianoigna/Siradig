// Autocompleta el formulario de "Gastos de Adquisicion de Indumentaria y Equipamiento"
// Selectores confirmados: #numeroDoc (CUIT), #idConcepto (select), #cmpFechaEmision (alta de comprobante).
// El resto de los campos del alta (Tipo, Numero, Monto, Monto Reintegrado) todavia no fueron relevados.

function setValue(selector, value) {
  const el = document.querySelector(selector);
  if (!el || value === undefined || value === null || value === "") return false;
  el.value = value;
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

function inferConcepto(categoria) {
  const texto = (categoria || "").toLowerCase();
  return texto.includes("equipo") || texto.includes("equipamiento") ? "2" : "1"; // 1=Indumentaria, 2=Equipamiento
}

function findAltaComprobanteButton() {
  return Array.from(document.querySelectorAll("a, button, input[type=button]")).find((el) =>
    (el.textContent || el.value || "").toLowerCase().includes("alta de comprobante")
  );
}

async function fillReceipt(receipt) {
  const pendientes = [];

  const cuitOk = setValue("#numeroDoc", receipt.cuit_emisor);
  if (!cuitOk) pendientes.push("CUIT (#numeroDoc)");

  const conceptoOk = setValue("#idConcepto", inferConcepto(receipt.categoria_gasto_siradig));
  if (!conceptoOk) pendientes.push("Concepto (#idConcepto)");

  const boton = findAltaComprobanteButton();
  if (!boton) {
    pendientes.push("boton 'Alta de Comprobante' (no encontrado en esta pantalla)");
  } else {
    boton.click();
    // Le damos tiempo al modal/sub-formulario a renderizarse antes de completar la fecha.
    await new Promise((resolve) => setTimeout(resolve, 500));
    const fechaOk = setValue("#cmpFechaEmision", receipt.fecha_emision);
    if (!fechaOk) pendientes.push("Fecha de emision (#cmpFechaEmision)");
    pendientes.push(
      "Tipo, Numero, Monto y Monto Reintegrado del comprobante (selectores aun no relevados, completar a mano)"
    );
  }

  return pendientes;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
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
