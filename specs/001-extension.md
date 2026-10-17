# SPEC-001: Extensión Web y Automatización DOM de Carga SIRADIG

- **Identificador**: `SPEC-001`
- **Título**: Extensión Web y Automatización DOM de Carga SIRADIG
- **Estado**: `Baseline (As-Is / Implementado)`
- **Fecha**: 2026-10-12
- **Ámbito**: Subsistema cliente (`extension/`) y suite de automatización local (`autocompletar.py`).

---

## 1. Propósito y Alcance

### 1.1 Objetivo del Subsistema
La extensión de navegador actúa como puente automatizado entre el backend de **SIRADIG Auto** y el formulario web oficial **F572 web (SIRADIG)** alojado en la infraestructura de AFIP/ARCA (`https://serviciosjava2.afip.gob.ar/radig/`). 

Su misión es eliminar la carga manual de comprobantes mediante la lectura de deducciones pendientes desde la API REST del proyecto y la inyección programática de dichos valores en los controles correspondientes del DOM de AFIP.

### 1.2 Principio de Seguridad
- **Cero manipulación de credenciales**: La extensión no solicita, almacena, captura ni transmite el CUIT ni la Clave Fiscal del usuario.
- El usuario debe autenticarse manualmente en el portal de AFIP y abrir el servicio SIRADIG antes de ejecutar cualquier acción de autocompletado.

### 1.3 Archivos y Componentes Cubiertos
| Archivo | Tipo de Componente | Función Principal |
|---|---|---|
| `extension/manifest.json` | Configuración Manifest V3 | Declaración de permisos, dominios autorizados y scripts inyectados. |
| `extension/popup.html` | Interfaz de Usuario (Action) | Vista popup para ingresar token de API e iniciar acciones. |
| `extension/popup.js` | Controlador de Interfaz | Gestión de configuración local, consulta de API y orquestación batch. |
| `extension/content_script.js` | Inyección DOM | Automatización de clicks, llenado de inputs y navegación en el portal AFIP. |
| `extension/autocompletar.py` | Herramienta de Testing / E2E | Automatización complementaria con Playwright vía Chrome DevTools Protocol (CDP). |

---

## 2. Arquitectura de la Extensión (Manifest V3)

### 2.1 Permisos y Alcance de Host
Declarados en `manifest.json`:
- **Permisos**:
  - `storage`: Almacenamiento local del token de autenticación del backend (`chrome.storage.local`).
  - `activeTab`: Acceso temporal a la pestaña activa en primer plano para ejecutar scripts y enviar mensajes.
  - `scripting`: Capacidad de inyectar funciones de automatización directas en el contexto de la pestaña activa.
- **Host Permissions**:
  - `https://serviciosjava2.afip.gob.ar/*`: Dominio donde corre la aplicación web de AFIP SIRADIG.
  - `https://siradig.onrender.com/*`: Dominio del backend en producción donde se expone la API REST.

### 2.2 Estrategia de Inyección del Content Script
- **URL Matches**:
  - `https://serviciosjava2.afip.gob.ar/radig/jsp/*`
  - `<all_urls>` (Permite actuar en transiciones o redirecciones durante la sesión activa).
- **Parámetros de ejecución**:
  - `all_frames: true`: Garantiza la inyección dentro de iframes o frames internos utilizados por la arquitectura legacy basada en JSP/Struts de AFIP.

---

## 3. Contrato de Integración con el Backend (API)

### 3.1 Endpoint Base
- URL Base configurada: `https://siradig.onrender.com`
- Mecanismo de autenticación: `TokenAuthentication` de Django REST Framework mediante la cabecera:
  ```http
  Authorization: Token <apiToken>
  ```

### 3.2 Obtención de Comprobantes Pendientes
- **Método y Ruta**: `GET /api/receipts/pending/`
- **Respuesta esperada** (`200 OK` - Lista de comprobantes con estado `pendiente_carga`):
  ```json
  [
    {
      "id": 1,
      "fecha_emision": "15/06/2026",
      "cuit_emisor": "20123456789",
      "razon_social": "EMPRESA EJEMPLO S.A.",
      "tipo_comprobante": "Factura",
      "letra": "B",
      "numero_comprobante": "0001-00001234",
      "punto_venta": "0001",
      "numero_solo": "00001234",
      "importe_total": "15000.00",
      "importe_iva": "3150.00",
      "categoria_gasto_siradig": "Gastos médicos y paramédicos",
      "origen": "telegram",
      "estado": "pendiente_carga",
      "created_at": "2026-06-15T12:00:00Z"
    }
  ]
  ```

### 3.3 DTO Normalizado en Cliente (`popup.js`)
Para cada elemento recibido, se asegura una estructura defensiva con valores por defecto antes de ser enviada al `content_script`:
- `id`: `factura.id`
- `razon_social`: `factura.razon_social` || `"SIN RAZON SOCIAL"`
- `cuit_emisor`: `factura.cuit_emisor` || `"00000000000"`
- `importe_total`: `factura.importe_total` || `0`
- `fecha_emision`: `factura.fecha_emision` || `"01/01/2025"`
- `tipo_comprobante`: `factura.tipo_comprobante` || `"Factura"`
- `letra`: `factura.letra` || `"B"`
- `numero_comprobante`: `factura.numero_comprobante` || `"0000-00000000"`
- `punto_venta`: `factura.punto_venta` || split de comprobante `[0]` || `"0000"`
- `numero_solo`: `factura.numero_solo` || split de comprobante `[1]` || `"00000000"`
- `categoria_gasto_siradig`: `factura.categoria_gasto_siradig` || `"Gastos médicos y paramédicos"`

---

## 4. Casos de Uso y Flujos de la Extensión

```
+-----------------------------------------------------------------------------------+
|                                  USUARIO                                          |
+-----------------------------------------------------------------------------------+
          |                                               |
   (Guarda Token)                             (Click Carga Automática)
          v                                               v
+-----------------------+                    +------------------------------------+
|   chrome.storage      |                    |             popup.js               |
| apiToken: "..."       |                    | 1. Redirige a verGastosMedicos.do  |
+-----------------------+                    | 2. GET /api/receipts/pending/      |
                                             +------------------------------------+
                                                              |
                                                   (Itera cada factura)
                                                              v
                                             +------------------------------------+
                                             |  chrome.tabs.sendMessage()         |
                                             |  type: "FILL_RECEIPT"              |
                                             +------------------------------------+
                                                              |
                                                              v
                                             +------------------------------------+
                                             |         content_script.js          |
                                             | - #numeroDoc                       |
                                             | - Click Botón Alta Comprobante     |
                                             | - Llenado modal / formulario       |
                                             | - Click "Agregar" -> "Guardar"     |
                                             +------------------------------------+
                                                              |
                                                  (Respuesta { ok: true })
                                                              v
                                             +------------------------------------+
                                             |             popup.js               |
                                             | Sync PUT /confirm/ o /error/       |
                                             +------------------------------------+
```

### CU-01: Configuración del Token de API
- **Actor**: Usuario autenticado en el dashboard web.
- **Precondición**: El usuario copia su API Token desde el dashboard de SIRADIG Auto.
- **Flujo**:
  1. El usuario abre el popup de la extensión.
  2. Si existe un token previo en `chrome.storage.local` con clave `apiToken`, se carga en el input `#token`.
  3. El usuario ingresa/modifica el token y presiona `#save` ("Guardar token").
  4. La extensión persiste `{ apiToken: tokenInput.value.trim() }` en `chrome.storage.local`.
  5. Se actualiza el texto de estado: `"Token guardado."`.

### CU-02: Navegación Asistida a "Deducciones y Desgravaciones"
Existen dos mecanismos implementados para asistir la navegación en AFIP:

#### Modo Directo (`popup.js` vía `chrome.scripting.executeScript`)
Disparado por el botón `#ir_deducciones`:
1. Verifica que la pestaña activa pertenezca a `serviciosjava2.afip.gob.ar/radig`.
2. **Paso 1 (Inmediato)**: Dispara click en `.btn_empresa` (selección de empleador).
3. **Paso 2 (delay 2500 ms)**: Dispara click en enlace/botón con texto `"carga de formulario"`.
4. **Paso 3 (delay 6000 ms)**: Dispara click en selector `a[href="#header_deducciones"]` o elemento cuyo texto incluya `"deducciones"`.

#### Modo Reactivo de Página (`content_script.js` vía `navFlowActive`)
Implementado para reaccionar a recargas sucesivas de páginas mediante bandera en storage:
- Al recibir mensaje `{ type: "START_NAV_FLOW" }`, almacena `navFlowActive: true`.
- En cada carga de documento con `navFlowActive == true`:
  - En `menu_sel_empresa.jsp`: espera y pulsa `.btn_empresa`.
  - En `determinarContribuyente.do`: espera y pulsa el botón con `span.ui-button-text` igual a `"carga de formulario"`.
  - En `verMenuDeducciones.do`: espera y pulsa `a[href="#header_deducciones"]`, finalizando el flujo con `navFlowActive: false`.

### CU-03: Carga y Autocompletado Batch de Facturas
Disparado por el botón `#auto_cargar`:
1. Verifica si la pestaña activa se encuentra en SIRADIG.
2. Si la URL actual no contiene `verGastosMedicos`, fuerza la navegación con `chrome.tabs.update` a:
   `https://serviciosjava2.afip.gob.ar/radig/jsp/verGastosMedicos.do` y aguarda 1500 ms.
3. Lee `apiToken` desde `chrome.storage.local`.
4. Realiza petición HTTP a `${API_BASE}/api/receipts/pending/`.
5. Si no hay elementos o la respuesta falla, emite el mensaje de aviso o error correspondiente en el popup.
6. Si hay facturas, itera secuencialmente cada una:
   - Envía a la pestaña activa el mensaje `{ type: "FILL_RECEIPT", receipt }`.
   - Espera respuesta asíncrona `{ ok: true }` o `{ ok: false, error: ... }`.
   - Espera un retardo de 2000 ms entre cada factura si quedan elementos pendientes.
7. Sincroniza cada resultado reportado con la API.
8. Informa en el popup la cantidad de comprobantes exitosos y fallidos.

---

## 5. Diccionario DOM y Mapeos de Datos (`content_script.js`)

### 5.1 Enlaces de Categorías Principales
Mapeo de accesos directos desde la vista de menú (`CATEGORIA_LINKS`):
- `medicos`: `#link_agregar_gastos_medicos`
- `indumentaria`: `#link_agregar_gastos_indu_equip`
- `cuota_medico`: `#link_agregar_cuotas_medico_asistenciales`

### 5.2 Lógica de Inferencia de Datos en Cliente
- **Inferencia de Mes (`inferMes`)**: Extrae el mes de una fecha en formato `DD/MM/YYYY` (ej: `"15/06/2026"` -> `"6"`).
- **Inferencia de Concepto (`inferConcepto`)**: 
  - Si el texto de `categoria_gasto_siradig` contiene `"equipo"` o `"equipamiento"`, devuelve `"2"`.
  - En caso contrario devuelve `"1"`.
- **Inferencia de Código de Tipo de Comprobante AFIP (`inferTipoComprobante`)**:
  | Tipo Comprobante | Letra | Código AFIP devuelto |
  |---|---|---|
  | Factura | B | `6` |
  | Factura | C | `11` |
  | Recibo | B | `9` |
  | Recibo | C | `15` |
  | Ticket / Tique | * | `82` |
  | Otro / No coincide | * | `null` |

### 5.3 Mapeo de Selectores DOM por Formulario

#### A. Controles Generales y Cabecera
| Dato / Acción | Selector DOM AFIP | Notas |
|---|---|---|
| CUIT del Emisor | `#numeroDoc` | Se dispara evento `input` y `change`. |
| Mes previo a alta | `#mesDesde` | Aplica en formularios donde el mes se selecciona previo al modal. |
| Concepto | `#idConcepto` | Aplica en Indumentaria/Equipamiento (`1` o `2`). |
| Apertura de Alta | `#btn_alta_comprobante`<br>`#btn_alta_mes`<br>`#btn_alta`<br>`#alta_comprobante`<br>`#agregar` | Búsqueda por cascada de IDs o por coincidencia de texto ("alta", "agregar", "nuevo comprobante"). Se reintenta hasta 25 veces cada 200ms. |

#### B. Formulario Estándar (Médicos, Indumentaria y Equipamiento)
Detectado por la presencia del input `#cmpFechaEmision`:
| Campo Comprobante | Selector DOM AFIP | Transformación aplicada |
|---|---|---|
| Fecha de Emisión | `#cmpFechaEmision` | `receipt.fecha_emision` |
| Mes de Imputación | `#mesDesde` (si existe en modal) | `inferMes(receipt.fecha_emision)` |
| Tipo de Comprobante | `#cmpTipo` | `inferTipoComprobante(tipo, letra)` |
| Punto de Venta | `#cmpPuntoVenta` | `receipt.punto_venta` (fallback a split de `numero_comprobante`) |
| Número de Comprobante | `#cmpNumero` | `receipt.numero_solo` (fallback a split de `numero_comprobante`) |
| Monto Facturado | `#cmpMontoFacturado` | `receipt.importe_total` |
| Monto Reintegrado | `#cmpMontoReintegrado` | Forzado a `"0"` con delay de 500ms. Se marca advertencia para revisión manual. |

#### C. Formulario de Cuota Médico-Asistencial
Detectado por la presencia de `#detalleIndividualMes`:
| Campo Comprobante | Selector DOM AFIP | Transformación aplicada |
|---|---|---|
| Mes | `#detalleIndividualMes` | `inferMes(receipt.fecha_emision)` |
| Monto Mensual | `#detalleIndividualMontoMensual` | `receipt.importe_total` |

#### D. Acciones de Cierre y Persistencia en AFIP
1. Búsqueda y click en botón con texto exacto `"Agregar"` (espera de 1000 ms).
2. Búsqueda y click en botón con texto exacto `"Guardar"`.

---

## 6. Mensajería Interna de la Extensión

El `content_script.js` expone un listener mediante `chrome.runtime.onMessage`:

| Mensaje `type` | Parámetros | Acción Realizada | Respuesta (`sendResponse`) |
|---|---|---|---|
| `GOTO_CATEGORY` | `categoriaKey` | Realiza click en el selector de categoría según `CATEGORIA_LINKS`. | `{ ok: boolean }` |
| `START_NAV_FLOW` | Ninguno | Activa `navFlowActive: true` y ejecuta `runNavigationStep()`. | `{ ok: boolean }` |
| `GUARDAR_FORMULARIO` | Ninguno | Busca y presiona el botón "Guardar". | `{ ok: boolean }` |
| `FILL_RECEIPT` | `receipt: object` | Ejecuta `fillReceipt(receipt)`. | `{ ok: true }`<br>`{ ok: true, warning: string }`<br>`{ ok: false, error: string }` |

---

## 7. Herramienta de Testing y Automatización Local (`autocompletar.py`)

### 7.1 Rol y Propósito
El script `extension/autocompletar.py` sirve como arnés de prueba de integración y automatización End-to-End asistida sin depender de la UI del popup. Se conecta directamente a una instancia local de Chrome abierta por el usuario en modo depuración.

### 7.2 Arquitectura y Dependencias
- **Librería de automatización**: Playwright (`playwright.async_api.async_playwright`).
- **Mecanismo de conexión**: Chrome DevTools Protocol vía `connect_over_cdp("http://localhost:9222")`.
- **Cliente HTTP**: `requests` para interacción con la API de SIRADIG Auto.

### 7.3 Flujo de Ejecución del Test
1. **Extracción del Comprobante de Prueba**:
   - Intenta consumir `GET /api/receipts/pending/` usando el token configurado.
   - Si no hay respuesta o falla la conexión, utiliza un fixture estático predeterminado:
     ```python
     {
         "fecha_emision": "15/06/2026",
         "cuit_emisor": "20123456789",
         "razon_social": "ASIM LAURA SOLEDAD",
         "tipo_comprobante": "Factura B",
         "letra": "B",
         "numero_comprobante": "001-00000001",
         "importe_total": 250000,
         "categoria": "Gastos médicos y paramédicos"
     }
     ```
2. **Conexión CDP y Verificación de Contexto**:
   - Se adhiere a la primera pestaña del navegador conectado en `localhost:9222`.
   - Verifica que la URL pertenezca al dominio `radig`.
3. **Automatización Paso a Paso en AFIP**:
   - Click en `#link_agregar_gastos_medicos`.
   - Fill `#numeroDoc` con CUIT.
   - Select `#mesDesde` calculado desde la fecha.
   - Click `#btn_alta_comprobante`.
   - Fill `#cmpFechaEmision`.
   - Select `#cmpTipo` con valor fijo `"6"`.
   - Fill `#cmpPuntoVenta` con `"001"` y `#cmpNumero` con `"00000001"`.
   - Fill `#cmpMontoFacturado` con el importe total.
   - Fill `#cmpMontoReintegrado` con `"0"`.
   - Pausa de espera (3 segundos).
   - Click en texto `"Agregar"`.
   - Pausa y click en texto `"Guardar"`.
4. **Confirmación en API**:
   - Envía `PUT https://siradig.onrender.com/api/receipts/{numero_comprobante}/confirm/` con cabecera de autenticación.

---

## 8. Discrepancias Identificadas y Deuda Técnica

Para guiar los próximos ciclos de desarrollo orientado a especificaciones (SDD), se detallan las siguientes discrepancias detectadas entre el código actual de la extensión y el backend:

### 8.1 Discrepancia en Endpoints de Sincronización Post-Carga
- **En `popup.js`**: 
  - Para éxito llama a: `PUT /api/receipts/${id}/confirm/`
  - Para fallo llama a: `PUT /api/receipts/${id}/error/`
- **En `autocompletar.py`**:
  - Llama a: `PUT /api/receipts/${numero_comprobante}/confirm/`
- **En `receipts/urls.py` del Backend**:
  - Las URLs `.../confirm/` y `.../error/` **no existen**. El backend solo expone:
    - `GET /api/receipts/pending/` (`PendingReceiptListAPIView`)
    - `PATCH/PUT /api/receipts/<int:pk>/` (`ReceiptUpdateAPIView`)
- **Impacto**: La sincronización de estado desde la extensión actualmente falla silenciosamente en el bloque catch o devuelve HTTP 404/405.

### 8.2 Desalineación de Categoría con la Constitución del Proyecto
- `docs/constitution.md` define que el MVP solo admite:
  `"Gastos de Adquisición de Indumentaria y Equipamiento"`
- Sin embargo, `popup.js` redirige forzosamente a:
  `https://serviciosjava2.afip.gob.ar/radig/jsp/verGastosMedicos.do`
- `autocompletar.py` hace click sobre `#link_agregar_gastos_medicos`.
- El content script contiene soporte para ambas categorías, pero la orquestación actual está sesgada a Gastos Médicos.

### 8.3 Uso de Tiempos de Espera Cableados (`setTimeout`)
- La navegación en `popup.js` (`#ir_deducciones`) usa timeouts de 2.5s y 6.0s en lugar de observar la navegación real o interactuar con `content_script.js`.
- Esto produce vulnerabilidad ante lentitud o demoras en la respuesta del portal de AFIP.
