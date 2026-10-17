const fs = require("fs");
const path = require("path");
const assert = require("assert");

// Cargar content_script.js aislando su ejecución sin romper por APIs del browser ausentes
const scriptPath = path.join(__dirname, "content_script.js");
const scriptCode = fs.readFileSync(scriptPath, "utf-8");

// Mock global mínimo para que content_script.js evalúe sin errores
global.location = { href: "https://serviciosjava2.afip.gob.ar/radig/jsp/verGastosMedicos.do" };
global.chrome = {
  storage: {
    local: {
      get: (_keys, cb) => cb && cb({}),
      set: (_obj, cb) => cb && cb()
    }
  },
  runtime: {
    onMessage: {
      addListener: () => {}
    }
  }
};

// Evaluar dentro del contexto de Node
const context = {};
const evalFn = new Function(
  "chrome",
  "location",
  `${scriptCode};
  return {
    inferMes,
    inferConcepto,
    inferTipoComprobante,
    splitNumeroComprobanteLegacy,
    CATEGORIA_LINKS
  };`
);

const {
  inferMes,
  inferConcepto,
  inferTipoComprobante,
  splitNumeroComprobanteLegacy,
  CATEGORIA_LINKS
} = evalFn(global.chrome, global.location);

console.log("Corriendo tests de SPEC-001 (Extension logic)...");

// 1. Tests de inferMes
assert.strictEqual(inferMes("15/06/2026"), "6", "Mes de 15/06/2026 debe ser '6'");
assert.strictEqual(inferMes("01/01/2025"), "1", "Mes de 01/01/2025 debe ser '1'");
assert.strictEqual(inferMes("31/12/2024"), "12", "Mes de 31/12/2024 debe ser '12'");
assert.strictEqual(inferMes("fecha-invalida"), null, "Fecha inválida debe retornar null");
assert.strictEqual(inferMes(null), null, "Fecha null debe retornar null");
console.log("✓ inferMes validado según SPEC-001");

// 2. Tests de inferConcepto
assert.strictEqual(inferConcepto("Gastos de Adquisición de Equipamiento"), "2", "Equipamiento debe ser '2'");
assert.strictEqual(inferConcepto("equipamiento informatico"), "2", "Conteniendo equipo debe ser '2'");
assert.strictEqual(inferConcepto("Gastos de Indumentaria"), "1", "Indumentaria debe ser '1'");
assert.strictEqual(inferConcepto(""), "1", "Categoría vacía debe defaulting a '1'");
console.log("✓ inferConcepto validado según SPEC-001");

// 3. Tests de inferTipoComprobante
assert.strictEqual(inferTipoComprobante("Factura", "B"), "6", "Factura B debe ser '6'");
assert.strictEqual(inferTipoComprobante("Factura", "C"), "11", "Factura C debe ser '11'");
assert.strictEqual(inferTipoComprobante("Recibo", "B"), "9", "Recibo B debe ser '9'");
assert.strictEqual(inferTipoComprobante("Recibo", "C"), "15", "Recibo C debe ser '15'");
assert.strictEqual(inferTipoComprobante("Ticket", "B"), "82", "Ticket debe ser '82'");
assert.strictEqual(inferTipoComprobante("Tique fiscal", "B"), "82", "Tique debe ser '82'");
assert.strictEqual(inferTipoComprobante("Nota de Credito", "A"), null, "Tipo no soportado debe retornar null");
console.log("✓ inferTipoComprobante validado según SPEC-001");

// 4. Tests de splitNumeroComprobanteLegacy
const splitValido = splitNumeroComprobanteLegacy("0001-00001234");
assert.strictEqual(splitValido.puntoVenta, "0001", "Punto de venta debe ser '0001'");
assert.strictEqual(splitValido.numero, "00001234", "Número debe ser '00001234'");

const splitSinGuion = splitNumeroComprobanteLegacy("12345");
assert.strictEqual(splitSinGuion.puntoVenta, null, "Sin guión puntoVenta debe ser null");
assert.strictEqual(splitSinGuion.numero, "12345", "Sin guión numero debe ser '12345'");

console.log("✓ splitNumeroComprobanteLegacy validado según SPEC-001");

// 5. Validar mapeo de categorías
assert.strictEqual(CATEGORIA_LINKS.medicos, "link_agregar_gastos_medicos");
assert.strictEqual(CATEGORIA_LINKS.indumentaria, "link_agregar_gastos_indu_equip");
assert.strictEqual(CATEGORIA_LINKS.cuota_medico, "link_agregar_cuotas_medico_asistenciales");
console.log("✓ CATEGORIA_LINKS validado según SPEC-001");

console.log("\nTodos los tests de unidad de la extensión pasaron exitosamente!");
