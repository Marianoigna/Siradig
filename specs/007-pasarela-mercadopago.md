# Especificación: Integración de Pasarela de Pagos MercadoPago y Gestión de Suscripciones

- **Identificador:** `007-pasarela-mercadopago` (SPEC-007)
- **Revisión:** `REV-002`
- **Estado:** `PENDIENTE_DE_APROBACION`
- **Fuente de la petición:** Directivas del usuario y actualización conforme a documentación oficial de Mercado Pago:
  1. Esquema de cobro: Suscripción recurrente automática mensual vía Mercado Pago Preapproval / Planes recurrentes (`preapproval_plan` y `preapproval`).
  2. Tarifa y plan: Mensualidad oficial establecida en **8.999 ARS** (`$8999.00 ARS/mes`).
  3. Provisión del plan: Soporte para provisión y vinculación de plan recurrente en Mercado Pago (`POST /preapproval_plan` con `reason="SIRADIG Auto - Plan Mensual"`, `frequency: 1`, `frequency_type: "months"`, `transaction_amount: 8999.00`, `currency_id: "ARS"`), más comando Django de aprovisionamiento/sincronización (`ensure_mercadopago_plan` o `crear_plan_mercadopago`).
  4. Flujo de Checkout recurrente / suscripción: Soporte dual documentado por Mercado Pago:
     a) Creación de suscripción asociada a plan (`POST /preapproval` con `preapproval_plan_id` o uso del `init_point` provisto por MP para el plan).
     b) Creación directa de suscripción recurrente (`POST /preapproval` con `auto_recurring`: `frequency: 1`, `frequency_type: "months"`, `transaction_amount: 8999.00`, `currency_id: "ARS"`, `payer_email`, `back_url`, `external_reference`), obteniendo `init_point` para redirección del pagador.
  5. Webhooks y tópicos oficiales de Suscripciones: `subscription_preapproval` (vinculación/cambios de suscripción), `subscription_authorized_payment` (cobros periódicos y renovaciones), `subscription_preapproval_plan` (cambios en el plan) y `payment` (pagos procesados).
  6. Validación de firma criptográfica oficial: Header `x-signature` (`ts`, `v1`), header `x-request-id`, y manifest `id:[data.id_url];request-id:[x-request-id_header];ts:[ts_header];` validado con HMAC-SHA256 y secreto de webhook.
  7. Condición de acceso: Trial por tiempo (usando el campo preexistente `trial_start_date` en `UserProfile`), bloqueando el procesamiento de comprobantes (subida/extracción/extensión) al expirar el trial sin suscripción activa.
  8. Estructura Django: Nueva app dedicada `subscriptions`.
  9. Referencia de arquitectura: Adaptación e importación conceptual de `Monitorea/CORE/SUSCRIPCIONES` enriquecida con los estándares oficiales de Mercado Pago.
- **Constitución consultada:** `docs/constitution.md` (Revisión vigente: Django + DRF + Python 3.11, dependencias fijadas en `requirements.txt`, no almacenar credenciales AFIP/ARCA, TokenAuthentication en `/api/receipts/`, tests obligatorios de transiciones).
- **Aprobación:** `REV-001` aprobada previamente; `REV-002` pendiente de aprobación por el usuario.

---

## 1. Problema y Objetivo

### 1.1 Contexto y Problema
En el estado actual de **SIRADIG Auto**:
1. Todo usuario registrado cuenta con un campo `trial_start_date` en su `UserProfile`, pero el sistema no realiza ninguna validación de caducidad ni restringe el procesamiento de comprobantes tras un periodo de prueba.
2. Los usuarios pueden enviar fotos ilimitadas por Telegram, subirlas por la web (o interactuar vía la extensión de navegador) sin ningún mecanismo de monetización o cobro recurrente.
3. No existe un módulo de facturación, pasarela de pagos ni integración con procesadores de cobro en Argentina (MercadoPago).
4. El proyecto hermano de referencia (`Monitorea/CORE/SUSCRIPCIONES`) implementa un esquema funcional en Django con MercadoPago que combina suscripciones recurrentes automáticas (Preapproval), validación estricta de webhooks con firma HMAC-SHA256, y trazabilidad de pagos.
5. Se requiere alinear la integración con la documentación oficial de Mercado Pago para suscripciones recurrentes, estandarizando la tarifa a **8.999 ARS/mes** y soportando tanto la definición de un `preapproval_plan` recurrente como el flujo de suscripción por `init_point` y validación canónica de webhooks.

### 1.2 Objetivo
- Implementar una aplicación desacoplada y modular denominada `subscriptions` en SIRADIG Auto.
- Definir un modelo de acceso basado en **Período de Prueba (Trial por tiempo)** de **15 días** (configurable por entorno) a partir de `trial_start_date`.
- Implementar el esquema de **Suscripción Recurrente Automática** mensual mediante la API de **Mercado Pago Preapproval / Planes Recurrentes** con una tarifa exacta de **8.999 ARS ($8999.00 ARS/mes)**.
- Proveer un comando de gestión (Django management command `ensure_mercadopago_plan`) para crear o sincronizar automáticamente el plan mensual en Mercado Pago (`POST /preapproval_plan`) y asociar su `preapproval_plan_id`.
- Restringir el procesamiento de comprobantes cuando un usuario tenga el trial vencido y no posea una suscripción activa con pago vigente:
  - En Telegram Webhook: rechazar el procesamiento del comprobante y notificar al usuario con enlace a planes.
  - En DRF `/api/receipts/pending/` y actualización: responder con error de autorización/suscripción requerida (HTTP 403 Forbidden con código `subscription_required`).
  - En Dashboard: mostrar banner de aviso de suscripción/trial con días restantes y bloqueo de acciones de carga.
- Implementar un endpoint de Webhook seguro e idempotente que procese notificaciones oficiales de Mercado Pago (`subscription_preapproval`, `subscription_authorized_payment`, `subscription_preapproval_plan`, `payment`), valide firmas criptográficas con la plantilla HMAC-SHA256 oficial y mantenga el estado de suscripción del usuario.
- Proveer un flujo de autoservicio de cancelación de suscripción ante Mercado Pago (`PUT /preapproval/{id}` con status `cancelled`).

---

## 2. Alcance

### 2.1 Incluido
- **App Django `subscriptions`**:
  - Modelos de datos: `Plan`, `Suscripcion` y `Pago` (adaptados de `Monitorea`).
  - Vistas web para presentación de planes (`/suscripciones/planes/`), redirección al checkout de MP (`/suscripciones/suscribirse/<tipo>/`), páginas de retorno (`/suscripciones/pago-exitoso/`, `/suscripciones/pago-fallido/`, etc.).
  - Servicio de webhook (`/suscripciones/webhook/`) para eventos de Mercado Pago.
  - Flujo de cancelación de suscripción con revocación en Mercado Pago vía API de Preapproval.
- **Tarifa Oficial y Planes**:
  - Tarifa mensual fijada por defecto en **$8999.00 ARS** (variable de entorno `PRECIO_MENSUAL=8999.00`).
  - Comando Django `ensure_mercadopago_plan` para asegurar la existencia del plan recurrente mensual en la cuenta del vendedor de Mercado Pago y almacenar el `gateway_plan_id` (`preapproval_plan_id`).
- **Lógica de Acceso y Estado de Cuenta (Trial + Premium)**:
  - Helper / Servicio unificado de verificación de estado: `usuario_tiene_acceso_activo(user)` que evalúa:
    1. Si está dentro del periodo de prueba (`trial_dias_restantes > 0`).
    2. O si posee una `Suscripcion` en estado `activa` con `fecha_vencimiento > now()`.
  - Duración del trial configurable por variable de entorno `TRIAL_DURATION_DAYS` (valor por defecto: 15 días).
- **Restricción de Servicios al Expirar**:
  - **Telegram Bot**: Si el usuario no tiene acceso activo, el bot descarta la extracción de la factura y responde amigablemente indicando que su período de prueba finalizó, adjuntando el enlace al dashboard/planes.
  - **API REST (`/api/receipts/`)**: Endpoint consumido por la extensión de navegador valida que el usuario propietario del token tenga acceso activo; caso contrario retorna HTTP 403 Forbidden con payload `{ "detail": "...", "code": "subscription_required" }`.
  - **Dashboard Web**: Renderizado de banner informativo indicando días restantes de prueba o estado de suscripción ("Prueba activa: X días restantes", "Plan Mensual Activo", "Suscripción Vencida").
- **Integración con Mercado Pago (Preapproval & Preapproval Plan API)**:
  - Creación de plan recurrente (`/preapproval_plan`) mensual por $8999.00 ARS.
  - Creación de intención de suscripción recurrente (`/preapproval`) con `auto_recurring` (frecuencia mensual por $8999.00 ARS), `preapproval_plan_id` opcional/asociado, `payer_email`, `back_url` y `notification_url`.
  - Parámetro `external_reference = "<user_id>:<tipo_plan>"` para correlación inequívoca e idempotente.
  - Redirección al `init_point` devuelto por Mercado Pago (Checkout con medios de pago guardados/tarjetas).
  - Validación de firma oficial de webhooks de Mercado Pago (`x-signature` con `ts` y `v1`, `x-request-id`, y el template `id:[data.id_url];request-id:[x-request-id_header];ts:[ts_header];` con hash HMAC-SHA256 usando `MERCADOPAGO_WEBHOOK_SECRET`).
  - Procesamiento idempotente de pagos mediante `Pago.referencia_gateway` único.
- **Cancelación de Suscripciones**:
  - Cancelación vía interfaz con confirmación, actualizando el estado local a `cancelada` y llamando al endpoint de actualización de Preapproval de Mercado Pago (`PUT /preapproval/{id}` con `{"status": "cancelled"}`).

### 2.2 Exclusiones Explícitas
- **Credenciales AFIP/ARCA**: Ninguna parte de la app de suscripciones interactúa con credenciales fiscales (Principio Constitucional #9).
- **Procesamiento de tarjetas propio / Tokenización directa**: Todos los datos de tarjetas y medios de pago son procesados exclusivamente en los servidores certificados PCI-DSS de Mercado Pago a través de su `init_point` (Checkout Pro / Preapproval).
- **Múltiples pasarelas de pago simultáneas**: En esta versión solo se integra Mercado Pago.
- **Facturación electrónica automática (AFIP Factura A/B para la suscripción)**: La emisión de comprobantes fiscales por el cobro del servicio de SIRADIG Auto se gestionará externamente o en un módulo administrativo futuro.

---

## 3. Actores y Términos

### 3.1 Actores
- **Usuario en Trial**: Usuario registrado que aún cuenta con días disponibles en su periodo de prueba de 15 días desde `trial_start_date`.
- **Usuario Suscriptor**: Usuario con una suscripción de pago activa recurrente en Mercado Pago ($8.999 ARS/mes).
- **Usuario Bloqueado/Expirado**: Usuario cuyo trial finalizó y no cuenta con suscripción activa ni pago vigente.
- **Mercado Pago (Gateway)**: Plataforma de pagos que debita los importes recurrentes periódicos, administra los métodos de pago y notifica eventos vía webhooks.
- **Bot de Telegram**: Canal de ingesta de comprobantes que debe consultar la elegibilidad de suscripción antes de procesar archivos.
- **Extensión de Navegador**: Cliente API que solicita comprobantes pendientes para inyectar en SIRADIG.

### 3.2 Términos Clave
- **Preapproval Plan (`preapproval_plan`)**: Objeto de la API de Mercado Pago que define las condiciones estándar de recurrencia (título, frecuencia mensual, moneda ARS, monto $8.999 ARS).
- **Preapproval (`preapproval`)**: Objeto de la API de Mercado Pago que representa una suscripción y autorización de débito recurrente programada para un pagador específico.
- **Init Point**: URL provista por Mercado Pago hacia la cual se redirige al cliente para autorizar e ingresar los datos de cobro recurrente.
- **External Reference**: Identificador unívoco (`<user_id>:<tipo>`) provisto en el payload de creación para asociar eventos asíncronos del webhook con el usuario local.
- **x-signature**: Header HTTP enviado por Mercado Pago con formato `ts=...,v1=...` para verificar criptográficamente la autenticidad e integridad del webhook recibido.

---

## 4. Historias de Usuario

### HU-SUB-001 — Visualización de Planes y Estado de Suscripción
**Como** usuario autenticado,  
**quiero** ver claramente cuántos días de prueba me quedan o el estado de mi suscripción activa en el dashboard y en la sección de planes, con el valor mensual oficial de $8.999 ARS,  
**para** saber cuándo debo suscribirme y tener certeza de la continuidad del servicio.

### HU-SUB-002 — Contratación de Suscripción Recurrente Mensual ($8.999 ARS)
**Como** usuario cuyo período de prueba está por vencer o ya venció,  
**quiero** seleccionar el plan mensual ($8.999 ARS) y ser redirigido a Mercado Pago para autorizar el débito automático,  
**para** continuar utilizando la extracción automática de comprobantes y la carga con la extensión.

### HU-SUB-003 — Activación Inmediata vía Webhook Oficial
**Como** usuario que acaba de autorizar una suscripción en Mercado Pago,  
**quiero** que mi cuenta se active automáticamente e instantáneamente sin intervención manual tras el procesamiento del webhook,  
**para** poder subir comprobantes de inmediato.

### HU-SUB-004 — Bloqueo de Procesamiento por Trial Vencido
**Como** administrador del sistema,  
**quiero** que un usuario sin suscripción activa y con trial vencido no pueda procesar nuevos comprobantes por Telegram ni descargarlos con la extensión,  
**para** proteger la infraestructura y garantizar el modelo de negocio.

### HU-SUB-005 — Cancelación de Suscripción
**Como** usuario suscriptor,  
**quiero** cancelar mi débito automático en cualquier momento desde mi panel,  
**para** no recibir cargos futuros en Mercado Pago, manteniendo el acceso hasta la fecha ya abonada.

---

## 5. Requisitos Funcionales

- **RF-001:** El sistema debe registrar un modelo `Plan` con planes tipificados (`gratuito`, `mensual`, `anual`), su precio asociado (fijado por defecto en **$8.999 ARS** para el plan mensual), y opcionalmente su `gateway_plan_id` (`preapproval_plan_id` de Mercado Pago).
- **RF-002:** El sistema debe registrar un modelo `Suscripcion` vinculado unívocamente a `User` con campos `plan`, `estado` (`activa`, `vencida`, `cancelada`, `trial`), `fecha_inicio`, `fecha_vencimiento`, `gateway_subscription_id` y `codigo_cancelacion`.
- **RF-003:** El sistema debe registrar un modelo `Pago` con `suscripcion`, `monto`, `fecha`, `metodo`, `referencia_gateway` único y bandera `exitoso`.
- **RF-004:** El sistema debe calcular el estado de acceso de cada usuario:
  - Tiene acceso si `now() <= user.profile.trial_start_date + timedelta(days=settings.TRIAL_DURATION_DAYS)`.
  - O si posee `Suscripcion` activa con `fecha_vencimiento > now()`.
- **RF-005:** La vista `/suscripciones/planes/` debe mostrar las opciones de contratación destacando el Plan Mensual por **$8.999 ARS**, el estado actual del usuario y los días restantes de prueba o suscripción.
- **RF-006:** La vista `/suscripciones/suscribirse/<tipo>/` debe comunicarse con la API de Mercado Pago (`POST /preapproval`), crear la suscripción recurrente con el monto configurado ($8.999 ARS para mensual), `currency_id: "ARS"`, `external_reference = "<user_id>:<tipo>"`, asociar el plan correspondiente si está aprovisionado, y redirigir al usuario al `init_point`.
- **RF-007:** El webhook `/suscripciones/webhook/` debe procesar notificaciones oficiales de Mercado Pago de tópicos `subscription_authorized_payment`, `subscription_preapproval`, `subscription_preapproval_plan` y `payment`.
- **RF-008:** El webhook debe validar la firma digital en el header `x-signature` utilizando la clave `MERCADOPAGO_WEBHOOK_SECRET` mediante HMAC-SHA256 y el template oficial `id:[data.id_url];request-id:[x-request-id_header];ts:[ts_header];` cuando dicha variable esté configurada; si la firma es inválida, debe responder con HTTP 401.
- **RF-009:** El procesamiento del webhook debe ser estrictamente idempotente: registrar el `Pago` con `update_or_create` usando `referencia_gateway` y extender la vigencia de la suscripción sin duplicar días ante reintentos de la misma notificación.
- **RF-010:** En la recepción de fotos/documentos en `telegram_webhook`:
  - Si el usuario remitente no posee acceso activo (trial vencido y sin suscripción activa), el bot NO debe procesar la imagen ni invocar el servicio de OCR.
  - El bot debe enviar un mensaje explicativo informando la finalización del periodo de prueba y facilitando el enlace para suscribirse.
- **RF-011:** En la API DRF (`PendingReceiptListAPIView` y `ReceiptUpdateAPIView`):
  - Si el usuario autenticado por token no posee acceso activo, la API debe rechazar la petición con código HTTP 403 Forbidden y payload con código `subscription_required`, impidiendo que la extensión descargue o modifique comprobantes.
- **RF-012:** El sistema debe permitir la cancelación de suscripción:
  - Se debe ofrecer un flujo de confirmación.
  - El sistema debe invocar la API de Mercado Pago (`PUT /preapproval/{id}` con `{"status": "cancelled"}`).
  - El estado local de `Suscripcion` debe actualizarse a `cancelada`. El usuario mantiene el acceso hasta `fecha_vencimiento`.
- **RF-013:** La plantilla de Dashboard (`receipts/templates/receipts/dashboard.html`) debe incluir una alerta/badge informando el estado de la cuenta (Días de trial restantes, o Suscripción activa hasta fecha X, o Aviso de cuenta suspendida con botón directo a planes).
- **RF-014:** El sistema debe proveer un comando de gestión (`ensure_mercadopago_plan`) para crear o sincronizar en Mercado Pago el `preapproval_plan` recurrente mensual de $8.999 ARS vía `POST /preapproval_plan`, guardando su ID en la base de datos o configuración.

---

## 6. Reglas de Negocio

- **RN-001 (Duración de Período de Prueba):** El período de prueba gratuito es de **15 días corridos** contados a partir del timestamp exacto de `trial_start_date` del `UserProfile`. Puede sobreescribirse mediante la variable `TRIAL_DURATION_DAYS`.
- **RN-002 (Cálculo de Días Restantes):** Los días restantes de trial se calculan como `max(0, ceil((trial_start_date + 15 días - now()).total_seconds() / 86400))`. Al llegar a 0, el trial se considera expirado.
- **RN-003 (Prevalencia de Suscripción Activa):** Si un usuario contrata un plan pago durante su período de prueba, la suscripción de pago toma precedencia inmediata sobre el trial. La fecha de vencimiento inicial se computará sumando el período contratado (30 días para mensual) a partir del momento del cobro.
- **RN-004 (Renovaciones Recurrentes):** Cuando Mercado Pago notifica un cobro recurrente aprobado (`subscription_authorized_payment` con `status == 'approved'`), si la suscripción aún está vigente, se extienden `+30 días` a partir de la fecha de vencimiento previa; si ya estaba vencida, se extienden a partir de `now()`.
- **RN-005 (Cancelación sin Pérdida Inmediata):** Cuando el usuario cancela su suscripción, se revoca el débito automático futuro en Mercado Pago, pero el usuario conserva acceso activo hasta que se cumpla su `fecha_vencimiento`.
- **RN-006 (Idempotencia de Pagos):** Cada evento de pago reportado con un ID de transacción de Mercado Pago (`data.id` o `resource_id`) solo puede procesarse y acreditarse una única vez. Intentos duplicados deben retornar HTTP 200 sin extender nuevamente la fecha.
- **RN-007 (Aislamiento Multi-usuario):** El webhook debe identificar fehacientemente al usuario local a través de `external_reference` (`<user_id>:<tipo>`). Bajo ninguna circunstancia se debe acreditar un pago a un usuario no verificado.
- **RN-008 (Tolerancia Cero en Fallas de Validación):** Si una solicitud de webhook no contiene `data.id`/`resource_id` o falla la verificación criptográfica HMAC de Mercado Pago, debe rechazarse inmediatamente con HTTP 401 sin ejecutar transacciones de base de datos.
- **RN-009 (Precio y Moneda):** El precio de la suscripción mensual es de **8.999 ARS** (`transaction_amount: 8999.00`, `currency_id: "ARS"`). Salvo sobreescritura explícita en variable de entorno `PRECIO_MENSUAL`, este valor es mandatorio.

---

## 7. Datos y Contratos Observables

### 7.1 Modelo de Datos (Nueva app `subscriptions`)

#### Plan
- `nombre`: CharField con opciones (`gratuito`, `mensual`, `anual`), único.
- `precio_mensual`: DecimalField(max_digits=10, decimal_places=2, default=8999.00).
- `descripcion`: TextField(blank=True).
- `dias_duracion`: PositiveIntegerField(default=30).
- `gateway_plan_id`: CharField(max_length=100, blank=True, null=True, help_text="ID del preapproval_plan en Mercado Pago").

#### Suscripcion
- `usuario`: OneToOneField(`settings.AUTH_USER_MODEL`, on_delete=CASCADE, related_name='suscripcion').
- `plan`: ForeignKey(`Plan`, on_delete=models.PROTECT).
- `estado`: CharField(max_length=20, choices=[`activa`, `vencida`, `cancelada`, `trial`]).
- `fecha_inicio`: DateTimeField(auto_now_add=True).
- `fecha_vencimiento`: DateTimeField().
- `gateway_subscription_id`: CharField(max_length=100, blank=True, null=True, db_index=True).
- `codigo_cancelacion`: CharField(max_length=6, blank=True, null=True).

#### Pago
- `suscripcion`: ForeignKey(`Suscripcion`, on_delete=CASCADE, related_name='pagos').
- `monto`: DecimalField(max_digits=10, decimal_places=2).
- `fecha`: DateTimeField(auto_now_add=True).
- `metodo`: CharField(max_length=50, default='mercadopago').
- `referencia_gateway`: CharField(max_length=200, unique=True).
- `exitoso`: BooleanField(default=True).

### 7.2 Variables de Entorno Requeridas
- `MERCADOPAGO_ACCESS_TOKEN`: Token de acceso de producción o sandbox de Mercado Pago.
- `MERCADOPAGO_PUBLIC_KEY`: Clave pública de Mercado Pago (para frontend o Checkout).
- `MERCADOPAGO_WEBHOOK_SECRET`: Secreto provisto por Mercado Pago en la configuración de Webhooks para validación de firma HMAC-SHA256.
- `MERCADOPAGO_BACK_URL`: URL base pública (ej. `https://siradig.onrender.com` o ngrok en desarrollo) para componer los retornos del checkout.
- `MERCADOPAGO_PREAPPROVAL_PLAN_ID`: (Opcional) ID preconfigurado del plan recurrente mensual de Mercado Pago.
- `PRECIO_MENSUAL`: Monto numérico en ARS para la tarifa mensual (default: `8999.00`).
- `TRIAL_DURATION_DAYS`: Cantidad de días de prueba para nuevos usuarios (default: `15`).

### 7.3 Contrato de Endpoints API y Webhook

#### Webhook: `POST /suscripciones/webhook/`
- Query params evaluados: `data.id`, `type`, `topic`.
- Headers evaluados: `x-signature` (`ts=...,v1=...`), `x-request-id`.
- Template de validación de firma oficial:
  `id:[data.id_url];request-id:[x-request-id_header];ts:[ts_header];`
- Respuestas:
  - `HTTP 200 OK`: Notificación recibida y procesada correctamente (o evento ignorado intencionalmente).
  - `HTTP 401 Unauthorized`: Firma inválida o ausente.

#### API Receipts: `GET /api/receipts/pending/`
- Si usuario con acceso activo: `HTTP 200 OK` con listado de comprobantes JSON.
- Si usuario con trial expirado y sin suscripción: `HTTP 403 Forbidden` con:
  ```json
  {
    "detail": "Acceso restringido: Período de prueba vencido. Se requiere una suscripción activa.",
    "code": "subscription_required"
  }
  ```

---

## 8. Estados y Transiciones de Suscripción

| Origen | Evento y precondición | Destino | Efectos observables | Criterio |
| --- | --- | --- | --- | --- |
| Sin suscripción (Trial activo) | Transcurren > 15 días desde `trial_start_date` sin pago | Trial Vencido | Bloqueo de bot de Telegram y API DRF; banner de suscripción en dashboard | CA-001 |
| Trial activo / Vencido | Webhook recibe `subscription_preapproval` autorizado o `subscription_authorized_payment` | `activa` | Se crea/actualiza `Suscripcion`, `fecha_vencimiento` = `now() + 30d`, se registra `Pago` de $8999, se desbloquea acceso | CA-002 |
| `activa` | Webhook recibe cobro recurrente periódico aprobado (`subscription_authorized_payment`) | `activa` | `fecha_vencimiento` se extiende +30 días; se crea nuevo registro `Pago` con `referencia_gateway` único | CA-003 |
| `activa` | Usuario solicita y confirma cancelación | `cancelada` | Se invoca Mercado Pago API (`PUT /preapproval/{id}` con `status: cancelled`); `estado` local pasa a `cancelada`; acceso se mantiene hasta `fecha_vencimiento` | CA-004 |
| `cancelada` / `activa` | Se alcanza `fecha_vencimiento` sin nuevos cobros aprobados | `vencida` | Al vencer, el usuario pierde el acceso a OCR en Telegram y a la extensión DRF | CA-005 |

---

## 9. Criterios de Aceptación

### CA-001 — Bloqueo de subida por Telegram con trial vencido (RF-010)
- **Dado** un usuario cuyo `trial_start_date` es de hace 16 días y no posee una suscripción activa de pago,
- **Cuando** dicho usuario envía una foto o documento de un comprobante a través de Telegram,
- **Entonces** el sistema NO almacena el archivo ni ejecuta la llamada al servicio OCR,
- **Y** el bot responde un mensaje: *"Tu período de prueba de 15 días ha finalizado. Para seguir procesando comprobantes y cargarlos en SIRADIG, suscribite al Plan Mensual ($8.999 ARS) en: `<URL_PLANES>`"*.

### CA-002 — Bloqueo de consulta de comprobantes en extensión API DRF (RF-011)
- **Dado** un usuario autenticado mediante su `Token` DRF cuyo período de prueba expiró sin suscripción activa,
- **Cuando** la extensión de navegador realiza una petición `GET` a `/api/receipts/pending/`,
- **Entonces** la API responde con código `HTTP 403 Forbidden`,
- **Y** el cuerpo JSON contiene `{"detail": "Acceso restringido: Período de prueba vencido. Se requiere una suscripción activa.", "code": "subscription_required"}`.

### CA-003 — Acceso permitido para usuario en período de prueba activo (RF-004, RF-010, RF-011)
- **Dado** un usuario registrado hace 5 días (`trial_start_date` dentro de los 15 días permitidos),
- **Cuando** envía un comprobante por Telegram o consulta `/api/receipts/pending/` vía DRF,
- **Entonces** la petición se procesa con normalidad (el OCR extrae los datos y la API retorna HTTP 200 con los comprobantes).

### CA-004 — Creación de suscripción mensual por $8.999 ARS y redirección a Mercado Pago (RF-006, RF-014)
- **Dado** un usuario autenticado en la plataforma web en `/suscripciones/planes/`,
- **Cuando** hace clic en el botón de suscripción mensual (`/suscripciones/suscribirse/mensual/`),
- **Entonces** el backend envía el payload `preapproval` a la API de Mercado Pago con importe `8999.00`, moneda `ARS`, recurrencia mensual, `external_reference="<user_id>:mensual"`,
- **Y** redirige al usuario mediante `HTTP 302` hacia el `init_point` retornado por Mercado Pago.

### CA-005 — Acreditación automática vía Webhook oficial e idempotencia (RF-007, RF-009)
- **Dado** una notificación de webhook válida enviada por Mercado Pago para tópicos `subscription_authorized_payment` o `subscription_preapproval`,
- **Cuando** el endpoint `/suscripciones/webhook/` procesa la petición con firma criptográfica válida,
- **Entonces** se crea o actualiza la `Suscripcion` en estado `activa` con fecha de vencimiento adecuada (+30 días),
- **Y** se registra el `Pago` asociado por $8999.00;
- **Y** ante el reenvío de la misma notificación con el mismo ID de transacción, el endpoint responde HTTP 200 sin duplicar el pago ni sumar días adicionales.

### CA-006 — Rechazo de Webhook con firma inválida según manifest oficial (RF-008)
- **Dado** un requerimiento al webhook con header `x-signature` alterado, timestamp expirado o hash discrepante del template `id:[data.id_url];request-id:[x-request-id_header];ts:[ts_header];`,
- **Cuando** la petición llega a `/suscripciones/webhook/` y `MERCADOPAGO_WEBHOOK_SECRET` está configurado,
- **Entonces** el sistema registra una advertencia en el log y responde inmediatamente con código `HTTP 401 Unauthorized` sin alterar la base de datos.

### CA-007 — Cancelación de suscripción en Mercado Pago (RF-012)
- **Dado** un usuario con suscripción recurrente activa (`gateway_subscription_id` presente),
- **Cuando** confirma la cancelación de su suscripción en la plataforma,
- **Entonces** el sistema envía una petición `PUT` a Mercado Pago (`/preapproval/{id}`) con `{"status": "cancelled"}`,
- **Y** actualiza localmente el estado a `cancelada`, manteniendo el acceso activo hasta `fecha_vencimiento`.

### CA-008 — Creación y aprovisionamiento de Plan de Suscripción en Mercado Pago (RF-014)
- **Dado** el comando de gestión Django `ensure_mercadopago_plan`,
- **Cuando** se ejecuta en un entorno configurado con `MERCADOPAGO_ACCESS_TOKEN`,
- **Entonces** consulta si ya existe un plan registrado o envía `POST /preapproval_plan` con `reason="SIRADIG Auto - Plan Mensual"`, `frequency=1`, `frequency_type="months"`, `transaction_amount=8999.00`, `currency_id="ARS"`,
- **Y** guarda el `gateway_plan_id` retornado en la base de datos para el `Plan` mensual.

---

## 10. Requisitos No Funcionales y Seguridad

- **RNF-001 (Seguridad Criptográfica en Webhooks):** Validación canónica obligatoria según documentación de Mercado Pago: extraer `ts` y `v1` de `x-signature`, procesar `x-request-id`, generar el manifest `id:[data.id];request-id:[x-request-id];ts:[ts];` y validar HMAC-SHA256 con `MERCADOPAGO_WEBHOOK_SECRET`.
- **RNF-002 (Aislamiento de Datos):** Ningún usuario puede visualizar, consultar ni cancelar la suscripción o los comprobantes de otro usuario.
- **RNF-003 (Resiliencia ante Caídas del Gateway):** Si la API de Mercado Pago se encuentra fuera de servicio al intentar crear una suscripción o cancelarla, el sistema debe registrar el error detallado en los logs y mostrar una vista de error amigable sin exponer stack traces ni secrets.
- **RNF-004 (Transaccionalidad Atómica):** Todas las actualizaciones de suscripción, asignación de fechas de vencimiento y registro de pagos dentro del webhook o de la cancelación deben ejecutarse dentro de bloques `transaction.atomic()` para garantizar consistencia.
- **RNF-005 (Cero Credenciales Fiscales):** El módulo de suscripciones no maneja, solicita ni almacena claves de AFIP ni datos de tarjetas de crédito.
- **RNF-006 (Calidad y Cobertura):** La nueva app `subscriptions` debe contar con tests unitarios y de integración con mocks en `pytest-django`, cubriendo con un mínimo de 80% de cobertura el servicio de webhook, la validación de firmas y el servicio de control de acceso (trial y suscripción).

---

## 11. Dependencias, Restricciones y Riesgos

### 11.1 Dependencias
- SDK oficial `mercadopago` (agregado y fijado en `siradig_auto/requirements.txt`, ej. `mercadopago==2.2.0` o `2.3.0` compatible con Python 3.11).
- Biblioteca `requests` (ya presente en `requirements.txt`).

### 11.2 Restricciones Constitucionales
- Cumplimiento de `docs/constitution.md`: stack en Django + Python 3.11, dependencias fijadas y pruebas en `pytest-django`.
- La extensión debe continuar funcionando sin cambios estructurales en su protocolo, simplemente recibiendo el código HTTP 403 Forbidden (`subscription_required`) cuando el acceso esté vencido.

### 11.3 Riesgos y Mitigaciones
- **Riesgo:** Webhooks de Mercado Pago en entorno local (desarrollo/staging).
  - *Mitigación:* Documentar el uso de herramientas como `ngrok` o la variable `MERCADOPAGO_BACK_URL` para desarrollo local, y permitir omitir la validación de firma únicamente si `MERCADOPAGO_WEBHOOK_SECRET` está explícitamente vacío durante pruebas iniciales.
- **Riesgo:** Desfase horario o latencia entre el cobro de Mercado Pago y el webhook.
  - *Mitigación:* Al redirigir a la página de retorno (`pago_exitoso`), mostrar un mensaje informativo que aclare que la activación puede demorar unos instantes hasta la recepción de la confirmación bancaria.

---

## 12. Trazabilidad

| Historia o necesidad | Requisito | Regla relacionada | Criterios | Tipo de verificación previsto |
| --- | --- | --- | --- | --- |
| HU-SUB-001 | RF-001, RF-005, RF-013 | RN-001, RN-002, RN-009 | CA-003 | Test funcional de vistas y templates |
| HU-SUB-002 | RF-006, RF-014 | RN-003, RN-009 | CA-004, CA-008 | Test unitario con mock de SDK Mercado Pago y management command |
| HU-SUB-003 | RF-007, RF-008, RF-009 | RN-004, RN-006, RN-008 | CA-005, CA-006 | Test de integración de Webhook con fixtures oficiales |
| HU-SUB-004 | RF-004, RF-010, RF-011 | RN-001, RN-002 | CA-001, CA-002 | Tests en `telegram_webhook` y `PendingReceiptListAPIView` |
| HU-SUB-005 | RF-012 | RN-005 | CA-007 | Test de flujo de cancelación con mock de API MP |

---

## 13. Dudas y Decisiones

| ID | Pregunta o decisión | Impacto | Estado y evidencia |
| --- | --- | --- | --- |
| DEC-001 | Cobro recurrente: Preapproval & Preapproval Plan | Integra `/preapproval_plan` y `/preapproval` conforme a la doc oficial de MP | Confirmado por el usuario y verificado en docs oficiales de MP |
| DEC-002 | Período de prueba (Trial) de 15 días | Define el período inicial gratuito evaluado sobre `UserProfile.trial_start_date` | Confirmado según directiva del usuario (configurable vía `TRIAL_DURATION_DAYS`) |
| DEC-003 | Tarifa oficial: $8.999 ARS/mes | Fija el monto estándar de la suscripción mensual en `8999.00` | Confirmado por el usuario |
| DEC-004 | Comando Django de aprovisionamiento de plan | `ensure_mercadopago_plan` asegura el `preapproval_plan` en Mercado Pago | Confirmado para simplificar despliegue y configuración |
| DEC-005 | Validación de firma HMAC oficial con `x-signature` y `x-request-id` | Plantilla `id:[data.id];request-id:[x-request-id];ts:[ts];` | Confirmado según documentación oficial de Webhooks de MP |

---

## 14. Control de Calidad y Aprobación

- [x] Problema, actores y resultado esperado están definidos.
- [x] Tarifa oficial de 8.999 ARS y endpoints oficiales de suscripción integrados.
- [x] Requisitos y criterios de aceptación verificables en formato Dado/Cuando/Entonces.
- [x] Validación criptográfica de Webhooks alineada con el estándar de Mercado Pago.
- [x] Invariantes de seguridad fiscal y aislamiento garantizados.
- [x] Identificador de revisión `REV-002` listo para aprobación del usuario.

---

## 15. Historial de Cambios

| Revisión | Cambio | Requisitos afectados | Estado de aprobación |
| --- | --- | --- | --- |
| REV-001 | Creación inicial de especificación basada en Monitorea y directivas acordadas | Todos (RF-001 a RF-013) | APROBADA (Usuario) |
| REV-002 | Actualización con documentación oficial de Mercado Pago: tarifa de 8.999 ARS/mes, provisión de `preapproval_plan`, comando Django de gestión, tópicos oficiales de webhooks (`subscription_preapproval`, `subscription_authorized_payment`), y firma HMAC canónica. | RF-001, RF-005, RF-006, RF-007, RF-008, RF-014, RN-008, RN-009, CA-004, CA-005, CA-006, CA-008 | PENDIENTE_DE_APROBACION |

