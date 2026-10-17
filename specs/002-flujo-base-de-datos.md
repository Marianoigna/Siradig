# SPEC-002: Especificación Integral del Flujo de Información e Interacción con la Base de Datos

- **Identificador**: `SPEC-002`
- **Revisión**: `REV-001 (Borrador Inicial)`
- **Título**: Especificación Integral del Flujo de Información e Interacción con la Base de Datos (I/O, Modelos, Estados y Seguridad)
- **Estado**: `PENDIENTE_DE_APROBACION`
- **Fuente de la petición**: Solicitud del usuario para especificar formalmente bajo SDD todo el flujo de información que entra y sale de la base de datos basándose en el código y arquitectura existente.
- **Constitución consultada**: `docs/constitution.md` (Línea base v1.0).
- **Aprobación**: Pendiente de revisión y aprobación explícita por parte del usuario/coordinador.

---

## 1. Problema y Objetivo

### 1.1 Contexto del Problema
SIRADIG Auto automatiza el procesamiento y la presentación de deducciones impositivas en el Formulario 572 Web de AFIP/ARCA a partir de comprobantes enviados por mensajería (Telegram) y procesados mediante IA (Gemini OCR). 

Para garantizar la integridad, consistencia, auditabilidad y aislamiento multiusuario de la información fiscal, se requiere definir de forma determinista y exhaustiva:
1. Qué entidades y atributos componen el esquema persistente.
2. Cuáles son los canales y puntos exactos de entrada (mutaciones/escrituras).
3. Cuáles son los canales y puntos exactos de salida (lecturas/consultas/proyecciones).
4. La máquina de estados finitos que gobierna el ciclo de vida del comprobante.
5. Las reglas de negocio, validaciones y restricciones de seguridad obligatorias establecidas en la constitución del proyecto.

### 1.2 Objetivo
Proporcionar una especificación técnica formal verificable (SDD) que describa exhaustivamente el modelo de datos, los contratos de persistencia, las operaciones CRUD por canal y los límites normativos del sistema.

---

## 2. Alcance

### 2.1 Incluido
1. **Modelo de Datos y Persistencia**:
   - Entidad `User` (`django.contrib.auth.models.User`).
   - Entidad `UserProfile` (`receipts.models.UserProfile`).
   - Entidad `Receipt` (`receipts.models.Receipt`).
   - Entidad `Token` (`rest_framework.authtoken.models.Token`).
2. **Puntos de Entrada y Mutación (Escrituras)**:
   - Registro y autenticación de usuarios (creación implícita de perfil y token vía señales `post_save`).
   - Vinculación de cuenta de Telegram (`/telegram/webhook/` con comando `/start <token>`).
   - Ingesta de archivos multimedia vía Webhook de Telegram (`photo` y `document`), almacenamiento binario y registro en base de datos.
   - Enriquecimiento asíncrono/síncrono post-OCR (mutación de metadatos de factura y persistencia de `raw_ocr_json`).
   - Actualización de estado y reporte de errores desde la extensión vía API DRF (`PATCH /api/receipts/<id>/`).
   - Gestión administrativa vía Django Admin y comando de inicialización CLI `ensure_superuser`.
3. **Puntos de Salida y Proyección (Lecturas)**:
   - Dashboard web (`/dashboard/`): conteo de métricas agregadas y listado histórico ordenado cronológicamente descendente.
   - API REST DRF (`GET /api/receipts/pending/`): filtrado de comprobantes pendientes para la extensión del navegador.
   - Notificaciones y respuestas automáticas de Telegram basadas en datos del comprobante y perfil del usuario.
4. **Ciclo de Vida y Estados de Comprobante**:
   - Transiciones permitidas: `pendiente_revision` → `pendiente_carga` → (`cargado_en_siradig` | `error_carga`).
5. **Reglas de Negocio y Seguridad Constitucionales**:
   - Aislamiento estricto entre usuarios (Row-Level Isolation).
   - Validación restrictiva de categoría SIRADIG (MVP indumentaria).
   - Principio de cero credenciales AFIP/ARCA.

### 2.2 Excluido
1. Modificación de código fuente o dependencias en esta fase.
2. Captura, almacenamiento o tránsito de credenciales fiscales (CUIT tributario personal o Clave Fiscal).
3. Soporte para canales de mensajería no incluidos en el MVP (WhatsApp, Slack, correo).
4. Categorías de deducción de SIRADIG ajenas a "Gastos de Adquisición de Indumentaria y Equipamiento".
5. Motores de base de datos distribuidos o esquemas multitenant no nativos de Django ORM.

---

## 3. Actores y Términos

- **Usuario Contribuyente**: Persona humana autenticada que consulta su dashboard web, vincula su Telegram y ejecuta la extensión.
- **Bot de Telegram**: Canal de mensajería que recibe imágenes/PDFs de comprobantes y comandos `/start`.
- **Servicio OCR (Gemini)**: Motor externo de extracción estructurada que consume binarios y retorna campos de factura.
- **Extensión de Navegador**: Cliente HTTP autenticado vía DRF `Token` que consulta comprobantes listos para inyección en AFIP y reporta el resultado de la carga.
- **Administrador de Sistema**: Usuario con privilegios `is_staff` / `is_superuser` que accede al Django Admin o ejecuta comandos CLI.
- **AFIP / ARCA**: Organismo tributario oficial. La interacción se realiza exclusivamente del lado del cliente en el navegador; nunca interactúa directamente con la base de datos de SIRADIG Auto.

---

## 4. Historias de Usuario

### HU-001 — Aprovisionamiento de Identidad y Credenciales de API
Como usuario nuevo del sistema, quiero que al registrarme se inicialice automáticamente mi perfil y un token de autenticación de API, para poder vincular mis canales y la extensión del navegador sin pasos manuales complejos.

### HU-002 — Ingesta y Persistencia de Comprobantes vía Telegram
Como usuario contribuyente, quiero enviar una foto o PDF de mi factura a través de Telegram, para que el sistema almacene el archivo original, extraiga los datos fiscales mediante OCR y deje registrado un comprobante estructurado en la base de datos.

### HU-003 — Consulta de Resumen y Comprobantes en Dashboard
Como usuario contribuyente, quiero acceder a mi panel web para visualizar el estado de mis comprobantes, totales deducibles acumulados y métricas operativas calculadas desde la base de datos.

### HU-004 — Consumo Seguro de Deducciones Pendientes desde la Extensión
Como extensión de navegador autenticada con token, quiero obtener únicamente los comprobantes de mi usuario en estado `pendiente_carga`, para poder inyectarlos ordenadamente en el formulario oficial de AFIP.

### HU-005 — Actualización del Resultado de Carga
Como extensión de navegador, quiero actualizar el estado de un comprobante procesado a `cargado_en_siradig` o `error_carga`, para mantener sincronizada la base de datos y evitar cargas duplicadas.

---

## 5. Modelo Entidad-Relación y Diccionario de Datos

### 5.1 Diagrama Entidad-Relación Conceptual

```
+-------------------------------------------------------------+
|              django.contrib.auth.models.User                |
+-------------------------------------------------------------+
| id                     : BigAutoField (PK)                  |
| username               : CharField (Unique)                 |
| email                  : EmailField                         |
| password               : CharField                          |
| is_staff               : BooleanField                       |
| is_superuser           : BooleanField                       |
| ...                                                         |
+-------------------------------------------------------------+
      | 1                       | 1                      | 1
      | 1                       | 1                      | 1..N
+-----v--------------+    +-----v---------------+   +----v--------------------------+
|    UserProfile     |    |   authtoken.Token   |   |           Receipt             |
+--------------------+    +---------------------+   +-------------------------------+
| id (PK)            |    | key (CharField 40 PK|   | id : BigAutoField (PK)        |
| user_id (FK Unique)|    | user_id (FK Unique) |   | user_id : ForeignKey          |
| trial_start_date   |    | created : DateTime  |   | archivo_original : FileField  |
| telegram_chat_id   |    +---------------------+   | fecha_emision : CharField(20) |
| telegram_link_token|                              | cuit_emisor : CharField(11)   |
+--------------------+                              | razon_social : CharField(255) |
                                                    | tipo_comprobante : Char(50)   |
                                                    | letra : CharField(5)          |
                                                    | numero_comprobante : Char(50) |
                                                    | punto_venta : CharField(5)    |
                                                    | numero_solo : CharField(8)    |
                                                    | importe_total : Decimal(12,2) |
                                                    | importe_iva : Decimal(12,2)   |
                                                    | categoria_gasto_siradig : C(100)
                                                    | origen : CharField(20)        |
                                                    | estado : CharField(20)        |
                                                    | mensaje_error : TextField     |
                                                    | raw_ocr_json : JSONField      |
                                                    | created_at : DateTimeField    |
                                                    +-------------------------------+
```

### 5.2 Diccionario de Datos Detallado

#### 5.2.1 Tabla: `receipts_userprofile` (Modelo `UserProfile`)
Extensión del usuario estándar de Django para vincular sesiones externas y onboarding.

| Columna | Tipo de Dato Físico | Nulo / Vacío | Restricciones / Índices | Descripción y Valores por Defecto |
|---|---|---|---|---|
| `id` | `BIGINT` | `NOT NULL` | `PRIMARY KEY AUTOINCREMENT` | Identificador único del perfil. |
| `user_id` | `BIGINT` | `NOT NULL` | `UNIQUE`, `FOREIGN KEY (auth_user.id) ON DELETE CASCADE` | Enlace 1 a 1 estricto con el usuario propietario. |
| `trial_start_date` | `TIMESTAMP WITH TIME ZONE` | `NOT NULL` | `INDEX` (implícito) | Marca temporal de creación del perfil (`auto_now_add=True`). |
| `telegram_chat_id` | `VARCHAR(64)` | `NULL`, `blank=True` | `UNIQUE` | Identificador numérico del chat de Telegram del usuario. Es nulo hasta que el usuario vincula su cuenta con `/start <token>`. |
| `telegram_link_token` | `VARCHAR(64)` | `NOT NULL` | `UNIQUE` | Token aleatorio URL-safe (24 bytes base64url ~32 caracteres) generado por defecto mediante `_generate_token()` para deep linking (`t.me/<bot>?start=<token>`). |

#### 5.2.2 Tabla: `receipts_receipt` (Modelo `Receipt`)
Registro maestro de comprobantes fiscales procesados.

| Columna | Tipo de Dato Físico | Nulo / Vacío | Restricciones / Índices | Descripción y Reglas de Negocio |
|---|---|---|---|---|
| `id` | `BIGINT` | `NOT NULL` | `PRIMARY KEY AUTOINCREMENT` | Identificador secuencial del comprobante. |
| `user_id` | `BIGINT` | `NOT NULL` | `INDEX`, `FOREIGN KEY (auth_user.id) ON DELETE CASCADE` | Usuario propietario. Garantiza el aislamiento multitenant. |
| `archivo_original`| `VARCHAR(100)` | `NOT NULL` | Ruta relativa | Archivo binario guardado en storage bajo patrón `receipts/%Y/%m/<filename>`. |
| `fecha_emision` | `VARCHAR(20)` | `NOT NULL`, `blank=True` | Ninguno | Fecha extraída por OCR o cargada manualmente (`DD/MM/AAAA`). |
| `cuit_emisor` | `VARCHAR(11)` | `NOT NULL`, `blank=True` | Ninguno | CUIT del emisor sin guiones (11 dígitos numéricos). |
| `razon_social` | `VARCHAR(255)` | `NOT NULL`, `blank=True` | Ninguno | Nombre comercial o razón social de la entidad emisora. |
| `tipo_comprobante`| `VARCHAR(50)` | `NOT NULL`, `blank=True` | Ninguno | Categoría de comprobante (ej: `Factura`, `Ticket`, `Recibo`). |
| `letra` | `VARCHAR(5)` | `NOT NULL`, `blank=True` | Ninguno | Letra fiscal (`A`, `B`, `C`, etc.). |
| `numero_comprobante` | `VARCHAR(50)` | `NOT NULL`, `blank=True` | Ninguno | Identificador combinado legible (`00005-00001234`). Mantenido por retrocompatibilidad. |
| `punto_venta` | `VARCHAR(5)` | `NOT NULL`, `blank=True` | Ninguno | Punto de venta estandarizado a 5 dígitos (`00005`). |
| `numero_solo` | `VARCHAR(8)` | `NOT NULL`, `blank=True` | Ninguno | Número secuencial estandarizado a 8 dígitos (`00001234`). |
| `importe_total` | `DECIMAL(12,2)`| `NULL`, `blank=True` | Ninguno | Importe bruto total del comprobante con 2 decimales. |
| `importe_iva` | `DECIMAL(12,2)`| `NULL`, `blank=True` | Ninguno | Importe discriminado de IVA o 0.00 si no aplica. |
| `categoria_gasto_siradig` | `VARCHAR(100)` | `NOT NULL`, `blank=True` | Ninguno | Subcategoría de deducción. En MVP debe ser exclusivamente `"Gastos de Adquisición de Indumentaria y Equipamiento"`. |
| `origen` | `VARCHAR(20)` | `NOT NULL` | `CHECK (origen IN ('telegram', 'upload_web'))` | Canal de ingreso del comprobante. |
| `estado` | `VARCHAR(20)` | `NOT NULL` | `CHECK (estado IN ('pendiente_revision', 'pendiente_carga', 'cargado_en_siradig', 'error_carga'))` | Estado en la máquina de estados. Valor por defecto: `'pendiente_revision'`. |
| `mensaje_error` | `TEXT` | `NOT NULL`, `blank=True` | Ninguno | Registro textual de fallas reportadas por la extensión o validaciones. |
| `raw_ocr_json` | `JSON` / `TEXT`| `NULL`, `blank=True` | Ninguno | Payload JSON completo retornado por la invocación de Gemini OCR. |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | `NOT NULL` | `INDEX` (implícito) | Marca temporal de inserción (`auto_now_add=True`). |

#### 5.2.3 Tabla: `authtoken_token` (Modelo `rest_framework.authtoken.models.Token`)
Credenciales delegadas para consumo de API headless.

| Columna | Tipo de Dato Físico | Nulo / Vacío | Restricciones / Índices | Descripción |
|---|---|---|---|---|
| `key` | `VARCHAR(40)` | `NOT NULL` | `PRIMARY KEY` | Token hexadecimal de 40 caracteres generado automáticamente al crearse el usuario. |
| `user_id` | `BIGINT` | `NOT NULL` | `UNIQUE`, `FOREIGN KEY (auth_user.id) ON DELETE CASCADE` | Enlace 1 a 1 con el usuario. |
| `created` | `TIMESTAMP WITH TIME ZONE` | `NOT NULL` | Ninguno | Timestamp de generación del token. |

---

## 6. Mapeo Integral de Flujos de I/O de la Base de Datos

### 6.1 Matriz de Flujos de Entrada (Mutaciones / Escrituras)

| ID Flujo | Canal / Endpoint | Evento Disparador | Operación DB | Tablas y Columnas Modificadas | Condiciones y Precondiciones |
|---|---|---|---|---|---|
| **IN-01** | `post_save` (Signal) | Creación de nuevo registro en `auth_user` | `INSERT` / `get_or_create` | `receipts_userprofile` (`user_id`, `telegram_link_token`, `trial_start_date`), `authtoken_token` (`key`, `user_id`, `created`) | Solo se ejecuta si `created=True`. Si ya existen, no sobrescribe. |
| **IN-02** | `/telegram/webhook/` (`_handle_start`) | Mensaje `/start <token>` | `SELECT` + `UPDATE` | `SELECT` en `receipts_userprofile` por `telegram_link_token`. `UPDATE` de `telegram_chat_id` en fila coincidente. | Requiere coincidencia exacta de `telegram_link_token`. Si no existe, no altera la base de datos y envía mensaje de error. |
| **IN-03** | `/telegram/webhook/` (`_handle_receipt_file`) | Recepción de `photo` o `document` | `SELECT` + `INSERT` | `SELECT` en `receipts_userprofile` por `telegram_chat_id`. `INSERT` en `receipts_receipt` (`user_id`, `origen='telegram'`, `estado='pendiente_revision'`, `archivo_original`). | Requiere que el remitente tenga `telegram_chat_id` registrado previamente. |
| **IN-04** | `/telegram/webhook/` (Post-OCR) | Inferencia exitosa de Gemini OCR | `UPDATE` | `UPDATE` en `receipts_receipt`: campos fiscales extraídos (`fecha_emision`, `cuit_emisor`, `razon_social`, `tipo_comprobante`, `letra`, `numero_comprobante`, `punto_venta`, `numero_solo`, `importe_total`, `importe_iva`, `categoria_gasto_siradig`), `raw_ocr_json=datos`, `estado='pendiente_carga'`. | Ocurre inmediatamente después de la respuesta 200 de Gemini. Si falla el OCR o levanta excepción, el registro permanece en `pendiente_revision` y no se muta. |
| **IN-05** | `PATCH /api/receipts/<id>/` | Inyección completada o fallida en AFIP por extensión | `SELECT` + `UPDATE` | `SELECT` por `id` filtrando por `user_id=request.user.id`. `UPDATE` de campo `estado` (`'cargado_en_siradig'` o `'error_carga'`). | Requiere `TokenAuthentication`. Solo permite modificar comprobantes pertenecientes al usuario autenticado. `ReceiptSerializer` restringe campos editables únicamente a `estado`. |
| **IN-06** | `CLI: ensure_superuser` | Ejecución de comando de despliegue/admin | `SELECT` + `INSERT` / `UPDATE` | `auth_user`: `get_or_create` de superusuario basado en variables de entorno. Actualiza contraseña (`password_hash`), `is_staff=True`, `is_superuser=True`. | Dispara indirectamente **IN-01** si el superusuario es creado nuevo. |
| **IN-07** | Django Admin (`/admin/`) | Edición manual por staff | `INSERT` / `UPDATE` / `DELETE` | `receipts_receipt`, `receipts_userprofile`, `auth_user`. | Requiere sesión con `is_staff=True` y permisos específicos de modelo. |

### 6.2 Matriz de Flujos de Salida (Lecturas / Consultas / Proyecciones)

| ID Flujo | Canal / Endpoint | Destinatario | Tipo de Consulta ORM | Tablas y Campos Leídos | Filtros y Ordenamiento |
|---|---|---|---|---|---|
| **OUT-01** | `GET /dashboard/` (`dashboard_home`) | Vista HTML Navegador | Agregaciones y lista | `receipts_userprofile` (`telegram_link_token`), `authtoken_token` (`key`), `receipts_receipt` (todos los campos para la tabla). | `receipts.filter(user=request.user).order_by('-created_at')`. Agregaciones en memoria y DB: `filter(estado='pendiente_carga').count()`, `filter(estado='cargado_en_siradig').count()`, `filter(estado='error_carga').count()`, `sum(importe_total)`. |
| **OUT-02** | `GET /api/receipts/pending/` | Extensión de Navegador | Lista serializada JSON | `receipts_receipt`: `id`, `fecha_emision`, `cuit_emisor`, `razon_social`, `tipo_comprobante`, `letra`, `numero_comprobante`, `punto_venta`, `numero_solo`, `importe_total`, `importe_iva`, `categoria_gasto_siradig`, `origen`, `estado`, `created_at`. | `Receipt.objects.filter(user=request.user, estado='pendiente_carga').order_by('created_at')`. |
| **OUT-03** | `/telegram/webhook/` | Notificaciones Telegram al chat del usuario | Consulta puntual | `receipts_receipt` (`razon_social`, `importe_total`). | Proyección de campos en mensaje de confirmación tras procesar el OCR. |
| **OUT-04** | Django Admin (`/admin/receipts/receipt/`) | Panel de Control Admin | Lista paginada | `receipts_receipt`: `user`, `razon_social`, `importe_total`, `estado`, `origen`, `created_at`. | Filtros laterales por `estado` y `origen`. Búsqueda por `razon_social`, `cuit_emisor`, `numero_comprobante`. |

---

## 7. Máquina de Estados de `Receipt`

### 7.1 Definición Formal de Estados
1. `pendiente_revision`: Estado inicial obligatorio al ingresar el archivo binario a la base de datos antes del procesamiento OCR o ante fallo/incompletitud de la extracción.
2. `pendiente_carga`: Estado alcanzado cuando el comprobante tiene los datos fiscales mínimos requeridos y está a la espera de ser consumido por la extensión web.
3. `cargado_en_siradig`: Estado terminal exitoso. El comprobante fue inyectado y confirmado en el F572 web de AFIP.
4. `error_carga`: Estado terminal de error o excepción operativa. Ocurre si la extensión detecta bloqueo, inconsistencia o error de validación en el formulario de AFIP.

### 7.2 Tabla de Transiciones de Estado

| Estado Origen | Evento Desencadenante | Precondición | Estado Destino | Mutación en DB | Criterio de Aceptación |
|---|---|---|---|---|---|
| `[NUEVO]` | Ingesta de archivo vía Telegram o Web | Archivo binario persistido en storage | `pendiente_revision` | `INSERT` con `estado='pendiente_revision'` | CA-002 |
| `pendiente_revision` | OCR exitoso | `datos` JSON válidos retornados por Gemini | `pendiente_carga` | `UPDATE` de campos fiscales y `estado='pendiente_carga'` | CA-003 |
| `pendiente_revision` | OCR fallido o timeout | Excepción en llamada o JSON no recuperable | `pendiente_revision` | `estado` permanece sin cambios | CA-004 |
| `pendiente_carga` | Extensión inyecta comprobante en AFIP con éxito | Respuesta afirmativa de DOM AFIP | `cargado_en_siradig` | `PATCH /api/receipts/<id>/` con `{"estado": "cargado_en_siradig"}` | CA-005 |
| `pendiente_carga` | Extensión reporta fallo en DOM AFIP | Fallo en inyección, campos no válidos o error AFIP | `error_carga` | `PATCH /api/receipts/<id>/` con `{"estado": "error_carga"}` | CA-006 |

### 7.3 Transiciones Prohibidas e Invariantes
- **Prohibido**: No está permitida la transición directa de `[NUEVO]` a `cargado_en_siradig` sin pasar por `pendiente_carga`.
- **Prohibido**: Un comprobante en estado `cargado_en_siradig` no debe ser devuelto jamás por el endpoint `/api/receipts/pending/`.
- **Principio de Zero Tolerance**: Todo cambio implementado o probado sobre estados debe validar unitariamente cada una de las transiciones declaradas.

---

## 8. Requisitos Funcionales (RF)

- **RF-001 (Aprovisionamiento Automático de Identidad)**: El sistema debe crear de forma automática un registro `UserProfile` con token único y un registro DRF `Token` cuando un usuario es persistido por primera vez en la tabla `auth_user`.
- **RF-002 (Vinculación Segura de Telegram)**: El sistema debe registrar el `telegram_chat_id` en el `UserProfile` correspondiente al recibir un comando `/start <token>` únicamente si el token coincide exactamente con un `telegram_link_token` existente.
- **RF-003 (Persistencia Inicial de Comprobante)**: El sistema debe crear un registro de `Receipt` con origen `telegram` y estado `pendiente_revision` inmediatamente tras descargar el binario desde Telegram, vinculándolo al usuario dueño del `telegram_chat_id`.
- **RF-004 (Enriquecimiento Post-OCR)**: El sistema debe actualizar el registro del comprobante con los datos extraídos (CUIT, razón social, fecha, importes, comprobante descompuesto en punto de venta y número) y mutar su estado a `pendiente_carga` si la extracción de Gemini fue exitosa.
- **RF-005 (Manejo de Fallas de Inferencia)**: El sistema debe registrar en logs la falla y conservar el comprobante en estado `pendiente_revision` sin corromper el registro si todos los modelos candidatos de Gemini fallan.
- **RF-006 (Aislamiento de Consultas de Comprobantes)**: Todas las consultas de lectura y actualización en el dashboard y en la API REST deben estar acotadas estrictamente a los registros cuyo `user_id` coincide con el usuario autenticado.
- **RF-007 (Consulta de Comprobantes Pendientes para Extensión)**: El endpoint `GET /api/receipts/pending/` debe retornar únicamente los comprobantes del usuario autenticado que posean el estado `pendiente_carga`, ordenados de forma ascendente por `created_at`.
- **RF-008 (Actualización de Estado vía API REST)**: El endpoint `PATCH /api/receipts/<id>/` debe admitir la actualización del campo `estado` (a `cargado_en_siradig` o `error_carga`) únicamente sobre comprobantes que pertenezcan al usuario autenticado, rechazando la modificación de cualquier otro campo fiscal del comprobante.
- **RF-009 (Restricción de Categoría SIRADIG - MVP)**: La persistencia y validación de comprobantes en el MVP debe admitir exclusivamente deducciones pertenecientes a `"Gastos de Adquisición de Indumentaria y Equipamiento"`. Cualquier otra categoría debe ser rechazada o marcada para revisión manual.

---

## 9. Reglas de Negocio (RN)

- **RN-001 (Aislamiento Multi-Tenant Estricto)**: Ningún usuario puede consultar, alterar ni inferir la existencia de comprobantes pertenecientes a otro usuario.
- **RN-002 (Prohibición de Almacenamiento de Credenciales AFIP)**: La base de datos bajo ninguna circunstancia debe contener campos o registros destinados a almacenar Clave Fiscal, CUIT tributario de acceso o contraseñas de AFIP/ARCA.
- **RN-003 (Normalización de Número de Comprobante)**: El número de comprobante debe estructurarse y persistirse dividido en `punto_venta` (5 dígitos rellenados con ceros a la izquierda) y `numero_solo` (8 dígitos rellenados con ceros a la izquierda) para cumplir con el contrato DOM del formulario de AFIP.
- **RN-004 (Inmutabilidad Fiscal en Actualizaciones de API)**: La extensión de navegador no tiene privilegios para mutar importes, CUIT, fechas o razones sociales vía API; únicamente puede notificar transiciones de estado (`cargado_en_siradig` o `error_carga`).

---

## 10. Criterios de Aceptación (CA)

### CA-001 — Aprovisionamiento de Perfil y Token (RF-001)
- **Dado** un nuevo usuario creado en el sistema (ej. vía admin o comando).
- **Cuando** se ejecuta la señal `post_save` en `auth_user`.
- **Entonces** se crea un registro en `receipts_userprofile` con un `telegram_link_token` único y no nulo.
- **Y** se crea un registro en `authtoken_token` asociado al usuario.

### CA-002 — Ingesta de Archivo desde Telegram (RF-003)
- **Dado** un usuario con `telegram_chat_id` vinculado en su `UserProfile`.
- **Cuando** envía un mensaje con una imagen o documento al bot de Telegram.
- **Entonces** se crea un registro en `receipts_receipt` con `origen='telegram'`, `estado='pendiente_revision'` y el archivo binario guardado en storage.

### CA-003 — Transición Exitosa a Pendiente de Carga (RF-004)
- **Dado** un comprobante en `pendiente_revision` con archivo binario guardado.
- **Cuando** el servicio OCR retorna un JSON válido con los campos requeridos (`fecha_emision`, `cuit_emisor`, `razon_social`, `importe_total`).
- **Entonces** el registro en la base de datos se actualiza con los campos extraídos, se persiste el JSON en `raw_ocr_json` y el `estado` muta a `pendiente_carga`.

### CA-004 — Retención en Revisión ante Fallo de OCR (RF-005)
- **Dado** un comprobante recién creado en `pendiente_revision`.
- **Cuando** la llamada a la cadena de modelos OCR levanta un error (ej. timeout, agotamiento o formato inválido).
- **Entonces** el comprobante permanece en base de datos en estado `pendiente_revision` con sus campos fiscales en blanco.
- **Y** se notifica al usuario por Telegram que el comprobante quedó para revisión manual.

### CA-005 — Transición de Carga Exitosa vía Extensión (RF-007, RF-008)
- **Dado** un usuario autenticado mediante su Token DRF y un comprobante en estado `pendiente_carga`.
- **Cuando** la extensión realiza un `PATCH /api/receipts/<id>/` con `{"estado": "cargado_en_siradig"}`.
- **Entonces** el registro en la base de datos se actualiza a `cargado_en_siradig`.
- **Y** las solicitudes posteriores a `GET /api/receipts/pending/` no incluyen dicho comprobante.

### CA-006 — Reporte de Error en Carga vía Extensión (RF-008)
- **Dado** un comprobante en estado `pendiente_carga`.
- **Cuando** la extensión reporta una imposibilidad de carga realizando `PATCH /api/receipts/<id>/` con `{"estado": "error_carga"}`.
- **Entonces** el registro en la base de datos se actualiza a `error_carga`.
- **Y** en el dashboard se contabiliza dentro del indicador de errores de carga.

### CA-007 — Rechazo de Acceso a Comprobantes Ajenos (RF-006)
- **Dado** un usuario A y un comprobante perteneciente al usuario B.
- **Cuando** el usuario A intenta consultar o modificar el comprobante mediante `/api/receipts/<id>/`.
- **Entonces** el sistema responde con error `404 Not Found`.
- **Y** no se produce ninguna modificación en la base de datos.

---

## 11. Requisitos No Funcionales (RNF)

- **RNF-001 (Consistencia Transaccional)**: Toda operación de escritura en base de datos debe ser consistente; fallos en servicios externos auxiliares no deben dejar registros en estados corruptos.
- **RNF-002 (Aislamiento de Datos - Seguridad)**: Las consultas SQL generadas por el ORM deben contener obligatoriamente el filtro de clave foránea `user_id = <authenticated_user>` para prevenir brechas de información entre inquilinos.
- **RNF-003 (Tiempo de Respuesta en API de Extensión)**: La consulta `GET /api/receipts/pending/` debe responder en menos de 250 ms en condiciones de carga nominal.
- **RNF-004 (Formato e Integridad de Tipos de Datos)**: Los montos deben usar campos decimales de punto fijo (`DECIMAL(12,2)`) para evitar imprecisiones de redondeo en importes tributarios.

---

## 12. Dependencias, Restricciones y Riesgos

### 12.1 Dependencias
- Base de datos relacional compatible con Django ORM (PostgreSQL en producción Render, SQLite3 para desarrollo local).
- Django REST Framework y paquete `rest_framework.authtoken`.
- Google GenAI SDK (`google-genai`) para la extracción OCR.
- API HTTP de Telegram para webhooks y descarga de archivos.

### 12.2 Restricciones Constitucionales
- Stack: Django 6.1 + DRF + Python 3.11.
- Cobertura mínima del 80% requerida en las rutas del webhook OCR y API receipts.
- Suite de tests obligatoria en `receipts/tests.py` usando `pytest-django`.
- Soporte exclusivo en MVP para la categoría "Gastos de Adquisición de Indumentaria y Equipamiento".

### 12.3 Riesgos y Hallazgos del Código Actual
1. **Falta de endpoint de edición manual (`/edit/<id>/`)**: En la petición original se mencionó `/edit/<id>/`, pero al auditar las URLs (`receipts/urls.py`) solo existen el dashboard, el webhook de Telegram y los dos endpoints de DRF. La edición manual de comprobantes actualmente no tiene vista web implementada.
2. **Validación de Categoría en BD**: Si bien la constitución exige rechazar en validación cualquier categoría distinta a "Gastos de Adquisición de Indumentaria y Equipamiento", el modelo actual (`Receipt.categoria_gasto_siradig`) es un `CharField(max_length=100, blank=True)` sin `choices` ni validación a nivel de modelo/serializer, permitiendo que el OCR guarde otras cadenas.
3. **Manejo del Campo `mensaje_error`**: La migración `0003_add_error_state.py` agregó el campo `mensaje_error` al modelo `Receipt`, pero el `ReceiptSerializer` no lo incluye en sus campos permitidos para actualización vía API.

---

## 13. Trazabilidad

| Historia de Usuario | Requisito Funcional | Regla de Negocio | Criterio de Aceptación | Verificación Prevista |
|---|---|---|---|---|
| HU-001 | RF-001 | RN-001 | CA-001 | Test unitario de señales (`receipts/tests.py`) |
| HU-002 | RF-002 | RN-001 | CA-001 | Test de integración de webhook `/start` |
| HU-002 | RF-003, RF-004, RF-005 | RN-003, RN-004 | CA-002, CA-003, CA-004 | Test de integración webhook + mock OCR |
| HU-003 | RF-006 | RN-001 | CA-007 | Test de vista de dashboard |
| HU-004 | RF-006, RF-007 | RN-001, RN-004 | CA-005, CA-007 | Test de API DRF con autenticación Token |
| HU-005 | RF-008 | RN-004 | CA-005, CA-006 | Test de API `PATCH` de estado |
| - | RF-009 | RN-002 | CA-003 | Test de modelo y validación de categoría |

---

## 14. Dudas y Decisiones

| ID | Pregunta o Decisión | Impacto | Estado |
|---|---|---|---|
| **DEC-001** | La base de datos nunca almacena credenciales de AFIP/ARCA; el usuario inicia sesión manualmente en el portal oficial. | Constitucional / Seguridad | Confirmada |
| **DEC-002** | El flujo de la extensión solo actualiza el estado (`cargado_en_siradig` o `error_carga`) y no muta campos fiscales vía API. | Integridad de Datos | Confirmada |
| **Q-001** | ¿Debe exponerse en la API DRF el campo `mensaje_error` para que la extensión guarde el detalle del motivo de fallo cuando marca `error_carga`? | Extensión / Trazabilidad de fallas | Pendiente de aclaración |
| **Q-002** | ¿Se implementará una vista web específica para edición manual (`/edit/<id>/`) de comprobantes en revisión, o se posterga para una fase posterior? | Alcance Dashboard Web | Pendiente de aclaración |

---

## 15. Control de Calidad y Checklist

- [x] Problema, actores y resultado esperado están definidos.
- [x] Alcance y exclusiones no se contradicen.
- [x] Los requisitos usan lenguaje inequívoco e identificadores estables (`RF-001` a `RF-009`).
- [x] Cada RF tiene criterios de aceptación verificables vinculados.
- [x] Las historias de usuario están enlazadas con sus requisitos.
- [x] Se cubren flujos de error, autorización y aislamiento multi-tenant.
- [x] Los estados y transiciones de la máquina de estados coinciden con la constitución.
- [x] Los RNF aplicables son medibles y claros.
- [x] Se contemplan privacidad, seguridad y principio de cero credenciales AFIP.
- [x] Se respetan estrictamente los límites de la constitución (indumentaria, Gemini fallback, pytest-django).
- [x] No hay modificaciones a código de aplicación ni pruebas ejecutadas indebidamente.

---

## 16. Historial de Cambios

| Revisión | Fecha | Resumen de Cambios | Requisitos Afectados | Estado |
|---|---|---|---|---|
| `REV-001` | 2026-10-17 | Creación inicial de la especificación técnica de flujos de I/O de base de datos (`SPEC-002`). | RF-001 a RF-009 | Pendiente de Aprobación |
