# SPEC-004: Integración del Canal de Mensajería Telegram y Flujo de Ingesta

- **Identificador**: `SPEC-004`
- **Revisión**: `REV-001 (Borrador Inicial - Integración Telegram)`
- **Título**: Especificación Integral de la Conexión con Telegram Bot API, Vinculación de Cuentas e Ingesta de Comprobantes
- **Estado**: `PENDIENTE_DE_APROBACION`
- **Fuente de la petición**: Solicitud del usuario para especificar formalmente todo lo relacionado con la conexión a Telegram (configuración, servicios, webhooks, vinculación de cuenta, descarga de archivos, pipeline OCR, persistencia, manejo de errores y compatibilidad arquitectónica agnóstica).
- **Constitución consultada**: `docs/constitution.md` (Línea base v1.0, Principios #1, #2, #4, #5, #6, #7, #8 y #9).
- **Aprobación**: Pendiente de revisión y aprobación explícita por parte del usuario y coordinador.

---

## 1. Problema y Objetivo

### 1.1 Contexto del Problema
SIRADIG Auto busca eliminar la fricción en la recopilación de comprobantes de deducciones impositivas (F572 Web) permitiendo a los contribuyentes enviar directamente fotos o documentos de sus facturas desde su teléfono móvil vía mensajería instantánea.

En el MVP, **Telegram** es el canal exclusivo de mensajería implementado para la recepción de comprobantes y notificaciones operativas al usuario. Dicha integración abarca:
1. Configuración de credenciales y registro del webhook ante los servidores de Telegram Bot API.
2. Vinculación criptográfica determinista entre una cuenta de usuario web (`User` / `UserProfile`) y un chat individual de Telegram (`telegram_chat_id`).
3. Recepción segura y asíncrona/síncrona de actualizaciones HTTP POST (`Update`).
4. Extracción de binarios multimedia (fotos en alta resolución y documentos PDF/JPEG) mediante Telegram Bot API (`getFile` y descarga de stream).
5. Persistencia del archivo y creación del comprobante (`Receipt`) en estado inicial.
6. Disparo del pipeline de OCR de IA (Gemini) y retroalimentación interactiva por chat al contribuyente informando el resultado del procesamiento.

### 1.2 Objetivo
Definir la especificación técnica formal bajo Spec-Driven Development (SDD) para todo el subsistema de integración con Telegram, estableciendo con precisión:
- El comportamiento funcional y los flujos conversacionales.
- Los contratos de datos, modelos y persistencia involucrados.
- Las garantías de seguridad, validación y fiabilidad.
- La preservación estricta de la abstracción arquitectónica que permita incorporar WhatsApp u otros canales en el futuro sin acoplar la lógica de dominio fiscal ni violar la constitución.

---

## 2. Alcance

### 2.1 Incluido
1. **Configuración y Gestión de Variables de Entorno**:
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`.
   - Comando de administración y despliegue `set_telegram_webhook`.
2. **Endpoint de Webhook HTTP**:
   - Ruta `/telegram/webhook/` en `receipts/views.py`.
   - Deserialización de payloads JSON provenientes de Telegram Bot API.
   - Verificación de tipos de mensaje (`text`, `photo`, `document`).
3. **Flujo de Vinculación de Cuenta (Deep Linking)**:
   - Generación de token único `telegram_link_token` en `UserProfile`.
   - Construcción del enlace profundo `https://t.me/<bot_username>?start=<token>` en el dashboard web.
   - Procesamiento del comando `/start <token>` en el webhook y asociación persistente del `telegram_chat_id`.
4. **Flujo de Ingesta Multimedia y Descarga**:
   - Selección de la variante de mayor resolución en colecciones de `photo` (`PhotoSize[-1]`).
   - Soporte de archivos adjuntos enviados como `document` (PDF, JPEG, PNG, etc.).
   - Llamadas a la Bot API: `getFile` (obtención de `file_path`) y descarga binaria vía `https://api.telegram.org/file/bot<token>/<file_path>`.
   - Persistencia física y de base de datos en `Receipt.archivo_original`.
5. **Orquestación con Pipeline OCR y Notificaciones de Usuario**:
   - Disparo de `ocr_service.extraer_datos_factura`.
   - Manejo de transiciones de estado de `Receipt`: `pendiente_revision` → `pendiente_carga`.
   - Envíos de mensajes interactivos a través de `sendMessage` informando éxito, revisión manual, cuenta no vinculada o formatos no reconocidos.
6. **Manejo de Errores y Casos Negativos**:
   - Mensajes de usuarios no registrados/no vinculados.
   - Formatos o tipos de mensaje no admitidos (audios, stickers, videos, texto suelto sin comando).
   - Fallas de red, timeouts o respuestas HTTP erróneas al invocar la API de Telegram.

### 2.2 Excluido
1. **Implementación de WhatsApp u otros Canales**:
   - Conforme al Principio #2 y #7 de la Constitución, WhatsApp **no** se implementa en el MVP. La especificación exige diseñar contratos desacoplados, pero sin introducir código ni dependencias anticipadas de proveedores de WhatsApp (Twilio, Meta Cloud API, etc.).
2. **Interfaz de la Extensión Web**:
   - La extensión de navegador interactúa exclusivamente con la API REST (`/api/receipts/`), documentada en `SPEC-001`.
3. **Lógica Interna del Modelo Gemini OCR**:
   - Las reglas heurísticas de extracción de campos, prompts y reintentos OCR están delimitadas en `receipts/services/ocr.py` y `SPEC-002`. Aquí solo se especifica la invocación del servicio y la respuesta ante su retorno.
4. **Interacción con Portales de AFIP/ARCA**:
   - Sin credenciales de AFIP y sin interacción externa (Principio #9 de la Constitución).

---

## 3. Actores y Términos

- **Usuario Contribuyente**: Titular de la cuenta en SIRADIG Auto que interactúa vía chat de Telegram enviando comprobantes.
- **Telegram Bot API**: Servicio REST proporcionado por Telegram (`https://api.telegram.org`) para la interacción con bots mediante webhooks y peticiones HTTP.
- **Deep Link (`/start <token>`)**: Mecanismo nativo de Telegram que permite transferir parámetros al bot cuando el usuario inicia la conversación desde un enlace web externo.
- **Update**: Objeto JSON estructurado enviado por Telegram mediante HTTP POST al webhook registrado con información de eventos (mensajes, fotos, comandos).
- **PhotoSize**: Estructura de Telegram que representa una versión redimensionada de una imagen enviada por el usuario.
- **Document**: Estructura de Telegram que representa un archivo general adjunto, con metadatos de nombre (`file_name`) y tipo MIME (`mime_type`).
- **Canal Agnóstico (`Channel`)**: Patrón arquitectónico donde el canal de mensajería (Telegram hoy, WhatsApp mañana) es un adaptador perimetral que transforma eventos externos en modelos de dominio desacoplados (`Receipt`).

---

## 4. Historias de Usuario

### HU-TG-001 — Vinculación rápida de cuenta Telegram
- **Como** usuario contribuyente registrado en SIRADIG Auto,
- **quiero** hacer click en el enlace de Telegram disponible en mi dashboard web para abrir el bot con mi token único,
- **para** asociar de forma inmediata y segura mi chat de Telegram con mi perfil y habilitar la recepción de mis facturas.

### HU-TG-002 — Ingesta de comprobante por foto
- **Como** usuario vinculado en Telegram,
- **quiero** fotografiar y enviar un ticket o factura desde la aplicación de Telegram en mi teléfono móvil,
- **para** que el sistema almacene el archivo original, procese automáticamente sus datos tributarios y me confirme en el mismo chat que quedó pendiente de carga.

### HU-TG-003 — Ingesta de comprobante en formato documento/PDF
- **Como** usuario vinculado en Telegram,
- **quiero** reenviar o adjuntar un archivo PDF o imagen sin compresión desde Telegram,
- **para** que SIRADIG Auto procese comprobantes electrónicos digitales recibidos por correo sin perder calidad.

### HU-TG-004 — Retroalimentación ante estados de excepción
- **Como** usuario que interactúa con el bot de Telegram,
- **quiero** recibir mensajes claros y orientativos si no he vinculado mi cuenta, si el archivo no pudo ser leído o si envié un contenido incompatible,
- **para** saber con precisión qué acción debo tomar en el sistema o en el dashboard.

---

## 5. Requisitos Funcionales

- **RF-TG-001: Configuración y Registro del Webhook**:
  El sistema debe permitir configurar la URL pública del webhook en Telegram Bot API mediante la función `set_webhook(url)` y el comando de gestión `python manage.py set_telegram_webhook <url>`, validando que `TELEGRAM_BOT_TOKEN` esté definido en el entorno.

- **RF-TG-002: Ingesta de Updates mediante HTTP POST**:
  El sistema debe exponer la ruta pública `/telegram/webhook/` libre de protección CSRF (`@csrf_exempt`), aceptando exclusivamente peticiones `POST` (`@require_POST`). Debe responder siempre con código HTTP `200 OK` a Telegram para evitar reintentos continuos e inundación del webhook, incluso cuando el procesamiento interno encuentre errores de validación.

- **RF-TG-003: Vinculación de Cuenta por Deep Link (`/start <token>`)**:
  Cuando el webhook reciba un mensaje cuyo campo `text` comience con `/start`, el sistema debe extraer el token parámetro. Si coincide con un `telegram_link_token` existente en `UserProfile`, debe actualizar `telegram_chat_id` con el ID del chat emisor y responder con un mensaje de éxito. Si el token no existe o está vacío, debe rechazar la vinculación y enviar un mensaje indicando que el token es inválido.

- **RF-TG-004: Restricción de Ingesta a Cuentas Vinculadas**:
  Ante cualquier envío de archivo (`photo` o `document`), el sistema debe verificar que el `chat_id` emisor coincida con un `UserProfile.telegram_chat_id` registrado. Si el remitente no está vinculado, el sistema debe abortar la ingesta, no crear ningún registro `Receipt` y notificar al remitente que debe vincular primero su cuenta con el enlace de su dashboard.

- **RF-TG-005: Procesamiento de Imágenes (`photo`)**:
  Si el mensaje recibido contiene el array `photo`, el sistema debe seleccionar la última posición del arreglo (`photo[-1]`), garantizando la máxima resolución disponible provista por Telegram, asignar el tipo MIME `image/jpeg` y derivar el nombre de archivo a partir de su `file_id`.

- **RF-TG-006: Procesamiento de Documentos Adjuntos (`document`)**:
  Si el mensaje recibido contiene un objeto `document`, el sistema debe extraer su `file_id`, su `mime_type` (con valor por defecto `application/octet-stream` si no se declara) y su `file_name` original.

- **RF-TG-007: Obtención y Descarga Binaria desde Telegram API**:
  El sistema debe consultar el endpoint `getFile` de Telegram Bot API enviando el `file_id` para obtener el `file_path` relativo, y a continuación descargar la totalidad de los bytes del archivo desde `https://api.telegram.org/file/bot<token>/<file_path>`.

- **RF-TG-008: Creación y Persistencia del Comprobante (`Receipt`)**:
  Antes de procesar la extracción de datos, el sistema debe crear un registro `Receipt` asociado al `User` del perfil vinculado, con `origen='telegram'`, `estado='pendiente_revision'` y almacenar los bytes descargados en `archivo_original`.

- **RF-TG-009: Invocación OCR y Notificación de Éxito**:
  El sistema debe remitir los bytes y el tipo MIME del archivo al servicio OCR. Si la extracción es exitosa y produce campos estructurados válidos, el sistema debe poblar los atributos fiscales de `Receipt`, almacenar el payload en `raw_ocr_json`, transicionar el estado a `pendiente_carga` y enviar un mensaje al usuario con el formato: `Comprobante procesado: <razon_social> - $<importe_total>. Ya está pendiente de carga en SIRADIG.`.

- **RF-TG-010: Degradación Elegante y Notificación ante Falla OCR**:
  Si el servicio OCR retorna `None` o genera una excepción no recuperable, el sistema debe mantener el comprobante en su estado inicial `pendiente_revision`, registrar el error en logs del servidor y notificar al usuario de Telegram: `No pude leer los datos del comprobante, quedó guardado para revisión manual.`.

- **RF-TG-011: Manejo de Contenidos No Soportados**:
  Si un usuario vinculado envía un mensaje que no contenga comando `/start`, ni array `photo`, ni objeto `document` (por ejemplo: stickers, mensajes de audio/voz, ubicaciones, contactos o texto arbitrario), el sistema debe responder informando: `Enviame una foto o PDF de tu comprobante.`.

- **RF-TG-012: Enlace de Vinculación en Dashboard**:
  El dashboard web (`/dashboard/`) debe generar y mostrar dinámicamente la URL completa de vinculación `https://t.me/<TELEGRAM_BOT_USERNAME>?start=<telegram_link_token>` para facilitar el enrolamiento en un solo click.

---

## 6. Reglas de Negocio

- **RN-TG-001 (Unicidad de Vinculación de Chat)**:
  Un `telegram_chat_id` solo puede estar vinculado a un único `UserProfile` en la base de datos a la vez (`unique=True` en modelo). Si un chat reenvía `/start` con un token nuevo, se actualiza el perfil correspondiente al nuevo token.
- **RN-TG-002 (Preservación del Archivo Físico)**:
  Ninguna falla en la capa de OCR o en el parsing de datos debe causar la pérdida o eliminación del archivo binario descargado desde Telegram. Todo archivo recibido de un usuario vinculado debe quedar respaldado en `media/receipts/%Y/%m/`.
- **RN-TG-003 (Aislamiento Multi-inquilino estricto)**:
  Los comprobantes recibidos a través de un chat de Telegram solo se asignan al usuario propietario del perfil que registró dicho `telegram_chat_id`. Bajo ninguna circunstancia un comprobante puede quedar huérfano (`user=None`) ni asociado a un tercero.
- **RN-TG-004 (Transiciones de Estado de Comprobante)**:
  Todo comprobante ingresado vía Telegram nace en `pendiente_revision`. Solo si el OCR extrae satisfactoriamente los datos mínimos requeridos transiciona a `pendiente_carga`. No se admiten transiciones directas a `cargado_en_siradig` desde el canal Telegram.
- **RN-TG-005 (Restricción de Categoría MVP)**:
  El comprobante debe recibir en su campo `categoria_gasto_siradig` el valor asignado por el pipeline fiscal, respetando la única categoría habilitada en el MVP ("Gastos de Adquisición de Indumentaria y Equipamiento") conforme al Principio #7 de la Constitución.
- **RN-TG-006 (Arquitectura de Canales Agnóstica)**:
  El diseño de dominio no debe depender de atributos propios de Telegram más allá de la capa de adaptación (`UserProfile.telegram_chat_id`, `receipts/services/telegram.py` y `telegram_webhook`). La lógica de creación de `Receipt` debe utilizar la abstracción `origen` (`telegram`, `upload_web`, y futuro `whatsapp`).

---

## 7. Datos y Contratos Observables

### 7.1 Variables de Entorno del Canal Telegram
| Variable | Descripción | Tipo | Obligatorio | Valor por Defecto / Ejemplo |
|---|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Token secreto de autenticación emitido por `@BotFather`. | String | Sí | `""` (Debe suministrarse en `.env`) |
| `TELEGRAM_BOT_USERNAME` | Username público del bot (sin `@`) para deep-linking. | String | Sí | `""` (Ej: `MiSiradigBot`) |

### 7.2 Entidades de Persistencia y Campos Involucrados
- **`UserProfile` (`receipts/models.py`)**:
  - `user`: Clave foránea `OneToOneField` a `auth.User`.
  - `telegram_chat_id`: `CharField(max_length=64, blank=True, null=True, unique=True)`. Almacena el identificador numérico de chat provisto por Telegram en formato cadena.
  - `telegram_link_token`: `CharField(max_length=64, unique=True)`. Generado criptográficamente vía `secrets.token_urlsafe(24)` al crear el perfil.
- **`Receipt` (`receipts/models.py`)**:
  - `user`: Clave foránea al `User` autenticado y vinculado.
  - `archivo_original`: `FileField(upload_to='receipts/%Y/%m/')`. Archivo binario JPG/PDF.
  - `origen`: `CharField(max_length=20)` con valor `'telegram'`.
  - `estado`: `CharField(max_length=20)`. Inicia en `'pendiente_revision'`; transiciona a `'pendiente_carga'` si el OCR es satisfactorio.
  - `raw_ocr_json`: `JSONField(null=True, blank=True)`. Respuesta íntegra del motor OCR.
  - Campos tributarios: `fecha_emision`, `cuit_emisor`, `razon_social`, `tipo_comprobante`, `letra`, `numero_comprobante`, `punto_venta`, `numero_solo`, `importe_total`, `importe_iva`, `categoria_gasto_siradig`.

### 7.3 Contratos de API de Telegram Utilizados (`receipts/services/telegram.py`)
1. **`sendMessage`**:
   - URL: `POST https://api.telegram.org/bot<token>/sendMessage`
   - Payload JSON: `{"chat_id": <int|str>, "text": "<mensaje>"}`
   - Timeout de red: `10` segundos.
2. **`getFile`**:
   - URL: `GET https://api.telegram.org/bot<token>/getFile?file_id=<file_id>`
   - Retorno esperado: `{"ok": true, "result": {"file_id": "...", "file_path": "photos/file_1.jpg", "file_size": 12345}}`
   - Timeout de red: `10` segundos.
3. **`download_file`**:
   - URL: `GET https://api.telegram.org/file/bot<token>/<file_path>`
   - Retorno: Flujo binario de bytes (`bytes`).
   - Timeout de red: `30` segundos.
4. **`setWebhook`**:
   - URL: `POST https://api.telegram.org/bot<token>/setWebhook`
   - Payload JSON: `{"url": "<url_publica_webhook>"}`
   - Timeout de red: `10` segundos.

---

## 8. Diagrama de Secuencia y Flujo de Comunicación

### 8.1 Flujo A: Configuración y Despliegue del Webhook
```
Deploy (Render / CLI)               SIRADIG Auto (Django)            Telegram Bot API
       |                                      |                              |
       |--- python manage.py set_telegram_webhook <url> --->                |
       |                                      |--- POST /setWebhook -------->|
       |                                      |    {"url": "<url>"}          |
       |                                      |<-- 200 OK {"ok": true} ------|
       |<-- Imprime resultado en stdout ------|                              |
```

### 8.2 Flujo B: Vinculación de Usuario vía Deep Link (`/start <token>`)
```
Usuario Telegram                  Telegram Server            SIRADIG Webhook (/telegram/webhook/)       Base de Datos
      |                                  |                                     |                              |
      |-- Abre t.me/<bot>?start=<token> -|                                     |                              |
      |-- Presiona "Iniciar" ------------|                                     |                              |
      |                                  |-- POST /telegram/webhook/ --------->|                              |
      |                                  |   {"message": {"text": "/start T"}} |                              |
      |                                  |                                     |-- UserProfile.objects.filter(|
      |                                  |                                     |   telegram_link_token=T) --->|
      |                                  |                                     |<-- Retorna UserProfile ------|
      |                                  |                                     |-- profile.telegram_chat_id = |
      |                                  |                                     |   chat_id; profile.save() -->|
      |                                  |<-- POST /sendMessage --------------|                              |
      |                                  |    "¡Cuenta vinculada!"             |                              |
      |<-- "¡Cuenta vinculada!" ---------|                                     |                              |
      |                                  |<-- 200 OK HTTP Response ------------|                              |
```

### 8.3 Flujo C: Ingesta de Foto/Documento, Descarga y Pipeline OCR
```
Usuario Telegram                  Telegram Server            SIRADIG Webhook (/telegram/webhook/)    Servicio OCR (Gemini)    Base de Datos
      |                                  |                                     |                              |                     |
      |-- Envía Foto / Factura PDF ----->|                                     |                              |                     |
      |                                  |-- POST /telegram/webhook/ --------->|                              |                     |
      |                                  |   {"photo": [...], "chat": {...}}   |                              |                     |
      |                                  |                                     |-- Valida telegram_chat_id -->|                     |
      |                                  |                                     |<-- Perfil existe ------------|                     |
      |                                  |<-- GET /getFile?file_id=... --------|                              |                     |
      |                                  |-- 200 OK {"file_path": "..."} ----->|                              |                     |
      |                                  |<-- GET /file/bot<token>/<path> -----|                              |                     |
      |                                  |-- 200 OK (Stream binario de bytes)->|                              |                     |
      |                                  |                                     |-- Receipt.objects.create(...)--------------------->|
      |                                  |                                     |   (estado='pendiente_revision')                    |
      |                                  |                                     |-- extraer_datos_factura(bytes)-->|                 |
      |                                  |                                     |                              |-- Model Cascade --->|
      |                                  |                                     |<-- Retorna dict con datos ---|                     |
      |                                  |                                     |-- Actualiza Receipt ------------------------------>|
      |                                  |                                     |   (estado='pendiente_carga')                       |
      |                                  |<-- POST /sendMessage ---------------|                                                    |
      |                                  |    "Comprobante procesado: ..."     |                                                    |
      |<-- "Comprobante procesado: ..." -|                                     |                                                    |
      |                                  |<-- 200 OK HTTP Response ------------|                                                    |
```

---

## 9. Criterios de Aceptación (Dado / Cuando / Entonces)

### CA-TG-001: Vinculación exitosa mediante deep linking — RF-TG-003
- **Dado** un usuario registrado con `UserProfile` cuyo `telegram_link_token` es `ABC123XYZ` y `telegram_chat_id` es nulo,
- **Cuando** Telegram envía un `Update` tipo mensaje con `chat.id = 987654` y `text = "/start ABC123XYZ"`,
- **Entonces** el webhook actualiza `UserProfile.telegram_chat_id` a `"987654"`,
- **Y** envía por Telegram el mensaje `"¡Cuenta vinculada! Ya podés enviarme fotos de tus comprobantes."`,
- **Y** retorna una respuesta HTTP con código `200`.

### CA-TG-002: Rechazo de vinculación por token inexistente — RF-TG-003
- **Dado** una base de datos donde ningún perfil posee el token `TOKEN_FALSO`,
- **Cuando** Telegram envía un `Update` con `text = "/start TOKEN_FALSO"`,
- **Entonces** ningún `UserProfile` sufre modificaciones en la base de datos,
- **Y** el sistema envía por Telegram `"Token inválido. Generá el link desde tu dashboard."`,
- **Y** la petición HTTP retorna status `200`.

### CA-TG-003: Recepción y procesamiento exitoso de foto de comprobante — RF-TG-005, RF-TG-007, RF-TG-008, RF-TG-009
- **Dado** un usuario con cuenta vinculada (`telegram_chat_id = "555123"`),
- **Cuando** el usuario envía una imagen con 3 tamaños de foto (`photo` array de 3 elementos),
- **Entonces** el webhook selecciona el `file_id` del último elemento (`photo[-1]`),
- **Y** descarga el archivo binario utilizando `getFile` y `download_file`,
- **Y** crea un `Receipt` con `origen = "telegram"`, `estado = "pendiente_revision"` y guarda el archivo en disco,
- **Y** al retornar el servicio OCR datos válidos de factura, actualiza el `Receipt` a `estado = "pendiente_carga"` con `raw_ocr_json` persistido,
- **Y** envía por Telegram la confirmación de comprobante procesado con razón social e importe.

### CA-TG-004: Intento de envío de comprobante por usuario no vinculado — RF-TG-004
- **Dado** un `chat_id = 999888` que no existe en ningún registro de `UserProfile`,
- **Cuando** el remitente envía una imagen o documento PDF,
- **Entonces** el sistema no ejecuta la descarga del archivo ni invoca el servicio OCR,
- **Y** no crea ningún registro en el modelo `Receipt`,
- **Y** responde al chat: `"Primero vinculá tu cuenta con el link del dashboard (/start <token>)."`.

### CA-TG-005: Tolerancia a fallo o ilegibilidad de OCR — RF-TG-010
- **Dado** un usuario vinculado que envía un comprobante,
- **Cuando** la descarga del archivo es exitosa pero el servicio OCR lanza una excepción (ej. agotamiento de modelos, cuota superada) o no logra extraer datos estructurados,
- **Entonces** el `Receipt` permanece almacenado en la base de datos con `estado = "pendiente_revision"` y su archivo original intacto,
- **Y** el bot envía el mensaje: `"No pude leer los datos del comprobante, quedó guardado para revisión manual."`.

### CA-TG-006: Manejo de tipos de mensaje incompatibles (Texto suelto, stickers, audio) — RF-TG-011
- **Dado** un usuario con cuenta vinculada que envía un mensaje de texto plano `"Hola bot"`,
- **Cuando** el webhook procesa la solicitud,
- **Entonces** detecta la ausencia de `/start`, `photo` y `document`,
- **Y** no altera la base de datos de comprobantes,
- **Y** responde con el recordatorio: `"Enviame una foto o PDF de tu comprobante."`.

### CA-TG-007: Resiliencia del webhook ante payloads vacíos o sin chat_id — RF-TG-002
- **Dado** una llamada al webhook con un payload JSON malformado o sin el bloque `chat.id` (como eventos de canales o updates de estado interno de Telegram),
- **Cuando** la vista procesa el payload,
- **Entonces** no arroja un error no controlado (HTTP 500),
- **Y** devuelve inmediatamente un código HTTP `200 OK`.

---

## 10. Requisitos No Funcionales

- **RNF-TG-001 (Timeouts en Llamadas a la API de Telegram)**:
  Las consultas a endpoints de control (`sendMessage`, `getFile`, `setWebhook`) deben tener un timeout máximo estricto de **10 segundos**. La descarga de streams binarios pesados (`download_file`) debe tener un timeout máximo de **30 segundos**, evitando que workers de Gunicorn se bloqueen indefinidamente.

- **RNF-TG-002 (Inmunidad contra Reintentos en Bucle de Telegram)**:
  El endpoint `/telegram/webhook/` debe retornar status HTTP `200` en un plazo menor al timeout estándar de Telegram (5 segundos en la recepción de la petición o procesamiento diferido), evitando que Telegram asuma caída del servidor y reenvíe repetitivamente el mismo `Update`.

- **RNF-TG-003 (Manejo de Secretos y Tokens)**:
  El `TELEGRAM_BOT_TOKEN` nunca debe ser versionado en el repositorio de código Git, expuesto en respuestas HTTP, plantillas de frontend ni registrado en archivos de logging (Principio #9 de la Constitución).

- **RNF-TG-004 (Cobertura de Pruebas de Integración)**:
  Toda la ruta crítica del webhook de Telegram (`receipts/views.py` y `receipts/services/telegram.py`) debe mantener una cobertura de pruebas automatizadas superior al **80%** ejecutadas con `pytest-django` mediante dobles de prueba (mocks) deterministas sin llamadas reales a la red de Telegram (Principio #4 y #5 de la Constitución).

---

## 11. Seguridad y Confiabilidad

### 11.1 Validación de Remitente e Integridad del Webhook (Análisis de Brecha)
- **Estado Actual (As-Is)**:
  Actualmente, el endpoint `/telegram/webhook/` no valida la cabecera `X-Telegram-Bot-Api-Secret-Token`. Cualquier actor malicioso que descubra la URL del webhook en Render (`https://siradig.onrender.com/telegram/webhook/`) podría emitir peticiones HTTP `POST` falsificando el `chat_id` de una víctima o enviando enlaces arbitrarios.
- **Requisito de Seguridad Propuesto (To-Be / Hardening)**:
  Se debe contemplar el soporte para `secret_token` al registrar el webhook (`setWebhook(url, secret_token=...)`) y verificar dicha cabecera `X-Telegram-Bot-Api-Secret-Token` en la vista Django antes de deserializar el payload.

### 11.2 Límites de Tamaño y Restricciones de Telegram
- Telegram Bot API impone un límite máximo de descarga de archivos para bots estándar de **20 MB**. Archivos que superen este tamaño recibirán un error en `getFile` que debe ser manejado adecuadamente.
- El servidor web de producción (Gunicorn en Render) cuenta con `--timeout 120`, lo que garantiza margen para subidas y descargas de comprobantes pesados.

### 11.3 Aislamiento de Errores y Tolerancia a Fallas
- Si la API de Telegram sufre degradación o intermitencia durante `sendMessage`, el error de red no debe impedir que el comprobante quede salvaguardado en la base de datos si ya fue descargado.
- La ejecución sincrónica actual del OCR dentro del request del webhook representa un cuello de botella potencial bajo alto volumen o demoras en la API de Gemini (riesgo documentado en Sección 13).

---

## 12. Trazabilidad

| Historia de Usuario | Requisito Funcional | Regla de Negocio | Criterio de Aceptación | Tipo de Verificación Previsto |
|---|---|---|---|---|
| HU-TG-001 | RF-TG-003, RF-TG-012 | RN-TG-001, RN-TG-003 | CA-TG-001, CA-TG-002 | Integración (`pytest-django`, `Client.post`) |
| HU-TG-002 | RF-TG-005, RF-TG-007, RF-TG-008, RF-TG-009 | RN-TG-002, RN-TG-004, RN-TG-005 | CA-TG-003 | Integración con mocks de Telegram y Gemini |
| HU-TG-003 | RF-TG-006, RF-TG-007, RF-TG-008, RF-TG-009 | RN-TG-002, RN-TG-004, RN-TG-005 | CA-TG-003 | Integración con mock de documento PDF |
| HU-TG-004 | RF-TG-004, RF-TG-010, RF-TG-011 | RN-TG-002, RN-TG-003 | CA-TG-004, CA-TG-005, CA-TG-006 | Unitaria e integración de flujos alternativos |
| Transversal | RF-TG-001, RF-TG-002 | RN-TG-006 | CA-TG-007 | Unitaria del comando y webhook base |

---

## 13. Dudas, Brechas y Riesgos Técnicos

| ID | Aspecto / Pregunta | Impacto | Estado | Recomendación / Mitigación |
|---|---|---|---|---|
| **Q-TG-001** | **Autenticación del Webhook**: Actualmente no se valida el `secret_token` de Telegram (`X-Telegram-Bot-Api-Secret-Token`). | Seguridad / Exposición de endpoint público. | Pendiente de Decisión | Incorporar `TELEGRAM_WEBHOOK_SECRET` en settings, configurarlo en `set_webhook` y validarlo en `telegram_webhook`. |
| **Q-TG-002** | **Procesamiento Síncrono vs Cola de Tareas**: La vista del webhook procesa en el mismo hilo HTTP la llamada a Telegram (`getFile` + descarga) y la llamada a Gemini OCR (que tiene reintentos y sleep de backoff). Si Gemini demora 10s, el webhook puede demorar 15-20s en responderle a Telegram. | Rendimiento / Timeout de Telegram (reintentos automáticos de Telegram). | Mitigado parcialmente en MVP por volumen bajo; riesgo para escalabilidad. | A futuro evaluar pasaje a worker asíncrono (Celery/RQ o background tasks) preservando la respuesta inmediata 200 OK a Telegram. |
| **Q-TG-003** | **Límite de tamaño de archivo (20 MB)**: Si un usuario envía un PDF escaneado > 20MB, la Bot API de Telegram arroja error en `getFile`. | Experiencia de Usuario. | Identificado | Atrapar `HTTPError` de `getFile` y avisar al usuario: "El archivo es demasiado grande (máximo 20 MB permitido por Telegram)". |
| **Q-TG-004** | **Abstracción Multicanal (WhatsApp)**: ¿Cómo garantizar que añadir WhatsApp futuro no rompa el modelo actual? | Arquitectura / Principio #2 de la Constitución. | Resuelto en diseño | La entidad `Receipt` ya posee el campo `origen` (`telegram`, `upload_web`, etc.). La lógica de parsing debe delegarse en adaptadores específicos de canal (`receipts/services/telegram.py` vs `receipts/services/whatsapp.py`). |

---

## 14. Control de Calidad y Checklist

- [x] Problema, actores y resultado esperado están completamente definidos.
- [x] Alcance y exclusiones delimitados (Telegram activo en MVP; WhatsApp agnóstico pero explícitamente no implementado aún).
- [x] Los requisitos usan lenguaje inequívoco e identificadores estables (`RF-TG-001` a `RF-TG-012`, `RNF-TG-001` a `RNF-TG-004`).
- [x] Cada RF cuenta con criterios de aceptación verificables en formato Dado/Cuando/Entonces (`CA-TG-001` a `CA-TG-007`).
- [x] Las historias de usuario están enlazadas con los requisitos funcionales en la matriz de trazabilidad.
- [x] Se cubren escenarios negativos, límites de resolución (`photo[-1]`), timeouts y usuarios no vinculados.
- [x] Se respetan las normas de la Constitución (`docs/constitution.md`): cero credenciales AFIP, máquina de estados respetada, no implementación prematura de WhatsApp.
- [x] No se alteró código fuente de la aplicación durante esta fase.

---

## 15. Historial de Revisiones

| Revisión | Fecha | Resumen de Cambios | Requisitos Afectados | Estado de Aprobación |
|---|---|---|---|---|
| `REV-001` | 2026-10-17 | Creación inicial de la especificación SDD formal para la integración de Telegram en SIRADIG Auto. | Todos (`RF-TG-001` a `RF-TG-012`) | `PENDIENTE_DE_APROBACION` |
