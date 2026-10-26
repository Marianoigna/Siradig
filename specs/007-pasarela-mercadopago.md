# Especificación: Integración de Pasarela de Pagos MercadoPago y Gestión de Suscripciones

- **Identificador:** `007-pasarela-mercadopago` (SPEC-007)
- **Revisión:** `REV-001`
- **Estado:** `APROBADA`
- **Fuente de la petición:** Directivas del usuario:
  1. Esquema de cobro: Suscripción recurrente automática (MercadoPago Preapproval / Planes recurrentes).
  2. Condición de acceso: Trial por tiempo (usando el campo preexistente `trial_start_date` en `UserProfile`), bloqueando el procesamiento de comprobantes (subida/extracción/extensión) al expirar el trial sin suscripción activa.
  3. Estructura Django: Nueva app dedicada `subscriptions`.
  4. Referencia de arquitectura: Adaptación e importación conceptual de `Monitorea/CORE/SUSCRIPCIONES` (modelos `Plan`, `Suscripcion`, `Pago`, servicios de webhook, endpoints y cancelación).
- **Constitución consultada:** `docs/constitution.md` (Revisión vigente: Django + DRF + Python 3.11, dependencias fijadas en `requirements.txt`, no almacenar credenciales AFIP/ARCA, TokenAuthentication en `/api/receipts/`, tests obligatorios de transiciones).
- **Aprobación:** Aprobada formalmente por el usuario para la Fase 2 (Planificación).

---

## 1. Problema y Objetivo

### 1.1 Contexto y Problema
En el estado actual de **SIRADIG Auto**:
1. Todo usuario registrado cuenta con un campo `trial_start_date` en su `UserProfile`, pero el sistema no realiza ninguna validación de caducidad ni restringe el procesamiento de comprobantes tras un periodo de prueba.
2. Los usuarios pueden enviar fotos ilimitadas por Telegram, subirlas por la web (o interactuar vía la extensión de navegador) sin ningún mecanismo de monetización o cobro recurrente.
3. No existe un módulo de facturación, pasarela de pagos ni integración con procesadores de cobro en Argentina (MercadoPago).
4. El proyecto hermano de referencia (`Monitorea/CORE/SUSCRIPCIONES`) ya implementa un esquema funcional en Django con MercadoPago que combina suscripciones recurrentes automáticas (Preapproval directo), validación estricta de webhooks con firma HMAC-SHA256, y trazabilidad de pagos.

### 1.2 Objetivo
- Implementar una aplicación desacoplada y modular denominada `subscriptions` en SIRADIG Auto.
- Definir un modelo de acceso basado en **Período de Prueba (Trial por tiempo)** de **15 días** (configurable por entorno) a partir de `trial_start_date`.
- Implementar el esquema de **Suscripción Recurrente Automática** mediante la API de **MercadoPago Preapproval** (débito automático mensual o anual en ARS).
- Restringir el procesamiento de comprobantes cuando un usuario tenga el trial vencido y no posea una suscripción activa con pago vigente:
  - En Telegram Webhook: rechazar el procesamiento del comprobante y notificar al usuario con enlace a planes.
  - En DRF `/api/receipts/pending/` y actualización: responder con error de autorización/suscripción requerida (HTTP 402 Payment Required o HTTP 403 Forbidden).
  - En Dashboard: mostrar banner de aviso de suscripción/trial con días restantes y bloqueo de acciones de carga.
- Implementar un endpoint de Webhook seguro e idempotente que procese notificaciones de MercadoPago (`subscription_authorized_payment`, `preapproval`, `payment`), valide firmas criptográficas y mantenga el estado de suscripción del usuario.
- Proveer un flujo de autoservicio de cancelación de suscripción.

---

## 2. Alcance

### 2.1 Incluido
- **App Django `subscriptions`**:
  - Modelos de datos: `Plan`, `Suscripcion` y `Pago` (adaptados de `Monitorea`).
  - Vistas web para presentación de planes (`/suscripciones/planes/`), redirección al checkout de MP (`/suscripciones/suscribirse/<tipo>/`), páginas de retorno (`/suscripciones/pago-exitoso/`, `/suscripciones/pago-fallido/`, etc.).
  - Servicio de webhook (`/suscripciones/webhook/`) para eventos de MercadoPago.
  - Flujo de cancelación de suscripción con revocación en MercadoPago vía API de Preapproval.
- **Lógica de Acceso y Estado de Cuenta (Trial + Premium)**:
  - Helper / Servicio unificado de verificación de estado: `usuario_tiene_acceso_activo(user)` que evalúa:
    1. Si está dentro del periodo de prueba (`trial_dias_restantes > 0`).
    2. O si posee una `Suscripcion` en estado `activa` con `fecha_vencimiento > now()`.
  - Duración del trial configurable por variable de entorno `TRIAL_DURATION_DAYS` (valor por defecto: 15 días).
- **Restricción de Servicios al Expirar**:
  - **Telegram Bot**: Si el usuario no tiene acceso activo, el bot descarta la extracción de la factura y responde amigablemente indicando que su período de prueba finalizó, adjuntando el enlace al dashboard/planes.
  - **API REST (`/api/receipts/`)**: Endpoint consumido por la extensión de navegador valida que el usuario propietario del token tenga acceso activo; caso contrario retorna HTTP 403 Forbidden o HTTP 402 Payment Required con payload `{ "detail": "Suscripción requerida." }`.
  - **Dashboard Web**: Renderizado de banner informativo indicando días restantes de prueba o estado de suscripción ("Prueba activa: X días restantes", "Plan Mensual Activo", "Suscripción Vencida").
- **Integración con MercadoPago (Preapproval API)**:
  - Creación de intención de suscripción recurrente con `auto_recurring` (mensual o anual).
  - Configuración de `back_url` y `notification_url`.
  - Parámetro `external_reference = "<user_id>:<tipo_plan>"` para correlación inequívoca e idempotente.
  - Validación de firma de webhooks de MercadoPago (`x-signature`, HMAC-SHA256 con `x-request-id` y `ts`).
  - Procesamiento idempotente de pagos mediante `Pago.referencia_gateway` único.
- **Cancelación de Suscripciones**:
  - Cancelación vía interfaz con confirmación o código de seguridad, actualizando el estado local a `cancelada` y llamando al endpoint de actualización de Preapproval de MercadoPago (`{"status": "cancelled"}`).

### 2.2 Exclusiones Explícitas
- **Credenciales AFIP/ARCA**: Ninguna parte de la app de suscripciones interactúa con credenciales fiscales (Principio Constitucional #9).
- **Procesamiento de tarjetas propio / Tokenización directa**: Todos los datos de tarjetas y medios de pago son procesados exclusivamente en los servidores certificados PCI-DSS de MercadoPago a través de su `init_point`.
- **Múltiples pasarelas de pago simultáneas**: En esta versión solo se integra MercadoPago (Stripe u otras quedan para fases posteriores).
- **Facturación electrónica automática (AFIP Factura A/B para la suscripción)**: La emisión de comprobantes fiscales por el cobro del servicio de SIRADIG Auto se gestionará externamente o en un módulo administrativo futuro.

---

## 3. Actores y Términos

### 3.1 Actores
- **Usuario en Trial**: Usuario registrado que aún cuenta con días disponibles en su periodo de prueba de 15 días desde `trial_start_date`.
- **Usuario Suscriptor**: Usuario con una suscripción de pago activa recurrente en MercadoPago.
- **Usuario Bloqueado/Expirado**: Usuario cuyo trial finalizó y no cuenta con suscripción activa ni pago vigente.
- **MercadoPago (Gateway)**: Plataforma de pagos que debita los importes recurrentes, administra los métodos de pago y notifica eventos vía webhooks.
- **Bot de Telegram**: Canal de ingesta de comprobantes que debe consultar la elegibilidad de suscripción antes de procesar archivos.
- **Extensión de Navegador**: Cliente API que solicita comprobantes pendientes para inyectar en SIRADIG.

### 3.2 Términos Clave
- **Preapproval**: Objeto de la API de MercadoPago que representa un débito recurrente programado sobre la tarjeta del pagador.
- **Init Point**: URL segura provista por MercadoPago a la cual se redirige al usuario para autorizar la suscripción recurrente.
- **External Reference**: Identificador unívoco provisto en el payload de creación (`<user_id>:<tipo>`) utilizado para asociar eventos asíncronos del webhook con el usuario local.
- **x-signature**: Header HTTP enviado por MercadoPago para verificar criptográficamente la autenticidad e integridad del webhook recibido.

---

## 4. Historias de Usuario

### HU-SUB-001 — Visualización de Planes y Estado de Suscripción
**Como** usuario autenticado,  
**quiero** ver claramente cuántos días de prueba me quedan o el estado de mi suscripción activa en el dashboard y en la sección de planes,  
**para** saber cuándo debo suscribirme y tener certeza de la continuidad del servicio.

### HU-SUB-002 — Contratación de Suscripción Recurrente
**Como** usuario cuyo período de prueba está por vencer o ya venció,  
**quiero** seleccionar un plan mensual o anual y ser redirigido a MercadoPago para activar el débito automático,  
**para** continuar utilizando la extracción automática de comprobantes y la carga con la extensión.

### HU-SUB-003 — Activación Inmediata vía Webhook
**Como** usuario que acaba de autorizar una suscripción en MercadoPago,  
**quiero** que mi cuenta se active automáticamente e instantáneamente sin intervención manual,  
**para** poder subir comprobantes de inmediato.

### HU-SUB-004 — Bloqueo de Procesamiento por Trial Vencido
**Como** administrador del sistema,  
**quiero** que un usuario sin suscripción activa y con trial vencido no pueda procesar nuevos comprobantes por Telegram ni descargarlos con la extensión,  
**para** proteger la infraestructura y garantizar el modelo de negocio.

### HU-SUB-005 — Cancelación de Suscripción
**Como** usuario suscriptor,  
**quiero** cancelar mi débito automático en cualquier momento desde mi panel,  
**para** no recibir cargos futuros en MercadoPago, manteniendo el acceso hasta la fecha ya abonada.

---

## 5. Requisitos Funcionales

- **RF-001:** El sistema debe registrar un modelo `Plan` con planes tipificados (`gratuito`, `mensual`, `anual`) y sus montos asociados.
- **RF-002:** El sistema debe registrar un modelo `Suscripcion` vinculado unívocamente a `User` con campos `plan`, `estado` (`activa`, `vencida`, `cancelada`, `trial`), `fecha_inicio`, `fecha_vencimiento`, `gateway_subscription_id` y `codigo_cancelacion`.
- **RF-003:** El sistema debe registrar un modelo `Pago` con `suscripcion`, `monto`, `fecha`, `metodo`, `referencia_gateway` único y bandera `exitoso`.
- **RF-004:** El sistema debe calcular el estado de acceso de cada usuario:
  - Tiene acceso si `now() <= user.profile.trial_start_date + timedelta(days=settings.TRIAL_DURATION_DAYS)`.
  - O si posee `Suscripcion` activa con `fecha_vencimiento > now()`.
- **RF-005:** La vista `/suscripciones/planes/` debe mostrar las opciones de contratación (mensual y anual), el estado actual del usuario y los días restantes de prueba o suscripción.
- **RF-006:** La vista `/suscripciones/suscribirse/<tipo>/` debe comunicarse con la API de MercadoPago (`/preapproval`), crear la suscripción recurrente con `external_reference = "<user_id>:<tipo>"`, y redirigir al usuario al `init_point`.
- **RF-007:** El webhook `/suscripciones/webhook/` debe procesar notificaciones de tipo `subscription_authorized_payment`, `preapproval` y `payment`.
- **RF-008:** El webhook debe validar la firma digital en el header `x-signature` utilizando la clave `MERCADOPAGO_WEBHOOK_SECRET` mediante HMAC-SHA256 cuando dicha variable esté configurada; si la firma es inválida, debe responder con HTTP 401.
- **RF-009:** El procesamiento del webhook debe ser estrictamente idempotente: registrar el `Pago` con `update_or_create` usando `referencia_gateway` y extender la vigencia de la suscripción sin duplicar días ante reintentos de la misma notificación.
- **RF-010:** En la recepción de fotos/documentos en `telegram_webhook`:
  - Si el usuario remitente no posee acceso activo (trial vencido y sin suscripción activa), el bot NO debe procesar la imagen ni invocar el servicio de OCR.
  - El bot debe enviar un mensaje explicativo informando la finalización del periodo de prueba y facilitando el enlace para suscribirse.
- **RF-011:** En la API DRF (`PendingReceiptListAPIView` y `ReceiptUpdateAPIView`):
  - Si el usuario autenticado por token no posee acceso activo, la API debe rechazar la petición con código HTTP 403 Forbidden o HTTP 402 Payment Required, impidiendo que la extensión descargue o modifique comprobantes.
- **RF-012:** El sistema debe permitir la cancelación de suscripción:
  - Se debe ofrecer un flujo de confirmación.
  - El sistema debe invocar la API de MercadoPago (`PUT /preapproval/{id}` con `{"status": "cancelled"}`).
  - El estado local de `Suscripcion` debe actualizarse a `cancelada`. El usuario mantiene el acceso hasta `fecha_vencimiento`.
- **RF-013:** La plantilla de Dashboard (`receipts/templates/receipts/dashboard.html`) debe incluir una alerta/badge informando el estado de la cuenta (Días de trial restantes, o Suscripción activa hasta fecha X, o Aviso de cuenta suspendida con botón directo a planes).

---

## 6. Reglas de Negocio

- **RN-001 (Duración de Período de Prueba):** El período de prueba gratuito es de **15 días corridos** contados a partir del timestamp exacto de `trial_start_date` del `UserProfile`. Puede sobreescribirse mediante la variable `TRIAL_DURATION_DAYS`.
- **RN-002 (Cálculo de Días Restantes):** Los días restantes de trial se calculan como `max(0, ceil((trial_start_date + 15 días - now()).total_seconds() / 86400))`. Al llegar a 0, el trial se considera expirado.
- **RN-003 (Prevalencia de Suscripción Activa):** Si un usuario contrata un plan pago durante su período de prueba, la suscripción de pago toma precedencia inmediata sobre el trial. La fecha de vencimiento inicial se computará sumando el período contratado (30 días para mensual, 365 días para anual) a partir del momento del cobro.
- **RN-004 (Renovaciones Recurrentes):** Cuando MercadoPago notifica un cobro recurrente aprobado (`subscription_authorized_payment` con `status == 'approved'`), si la suscripción aún está vigente, se extienden `+30 días` (o `+365 días`) a partir de la fecha de vencimiento previa; si ya estaba vencida, se extienden a partir de `now()`.
- **RN-005 (Cancelación sin Pérdida Inmediata):** Cuando el usuario cancela su suscripción, se revoca el débito automático futuro en MercadoPago, pero el usuario conserva acceso activo hasta que se cumpla su `fecha_vencimiento`.
- **RN-006 (Idempotencia de Pagos):** Cada evento de pago reportado con un ID de transacción de MercadoPago (`resource_id` o `payment.id`) solo puede procesarse y acreditarse una única vez. Intentos duplicados deben retornar HTTP 200 sin extender nuevamente la fecha.
- **RN-007 (Aislamiento Multi-usuario):** El webhook debe identificar fehacientemente al usuario local a través de `external_reference` (`<user_id>:<tipo>`). Bajo ninguna circunstancia se debe acreditar un pago a un usuario no verificado.
- **RN-008 (Tolerancia Cero en Fallas de Validación):** Si una solicitud de webhook no contiene `resource_id` o falla la verificación criptográfica HMAC de MercadoPago, debe rechazarse inmediatamente con HTTP 401 sin ejecutar transacciones de base de datos.

---

## 7. Datos y Contratos Observables

### 7.1 Modelo de Datos (Nueva app `subscriptions`)

#### Plan
- `nombre`: CharField con opciones (`gratuito`, `mensual`, `anual`), único.
- `precio_mensual`: DecimalField(max_digits=10, decimal_places=2, default=0).
- `descripcion`: TextField(blank=True).

#### Suscripcion
- `usuario`: OneToOneField(`settings.AUTH_USER_MODEL`, on_delete=CASCADE, related_name='suscripcion').
- `plan`: ForeignKey(`Plan`, on_delete=models.PROTECT).
- `estado`: CharField(max_length=20, choices=[`activa`, `vencida`, `cancelada`, `trial`]).
- `fecha_inicio`: DateTimeField(auto_now_add=True).
- `fecha_vencimiento`: DateTimeField().
- `gateway_subscription_id`: CharField(max_length=100, blank=True, null=True).
- `codigo_cancelacion`: CharField(max_length=6, blank=True, null=True).

#### Pago
- `suscripcion`: ForeignKey(`Suscripcion`, on_delete=CASCADE, related_name='pagos').
- `monto`: DecimalField(max_digits=10, decimal_places=2).
- `fecha`: DateTimeField(auto_now_add=True).
- `metodo`: CharField(max_length=50, default='mercadopago').
- `referencia_gateway`: CharField(max_length=200, unique=True).
- `exitoso`: BooleanField(default=True).

### 7.2 Variables de Entorno Requeridas
- `MERCADOPAGO_ACCESS_TOKEN`: Token de acceso de producción o sandbox de MercadoPago.
- `MERCADOPAGO_WEBHOOK_SECRET`: Secreto provisto por MercadoPago para la validación de firmas HMAC-SHA256 de notificaciones.
- `MERCADOPAGO_BACK_URL`: URL base pública del frontend/backend (ej. `https://siradig.onrender.com` o ngrok en desarrollo local) para componer los retornos del checkout.
- `PRECIO_MENSUAL`: Monto numérico en ARS para la tarifa mensual (ej. `30000`).
- `TRIAL_DURATION_DAYS`: Cantidad de días de prueba para nuevos usuarios (por defecto: `15`).

### 7.3 Contrato de Endpoints API y Webhook

#### Webhook: `POST /suscripciones/webhook/` (o GET según esquema de MP)
- Headers evaluados: `x-signature`, `x-request-id`.
- Parámetros: `type` / `action`, `data.id` / `resource_id`.
- Respuestas:
  - `HTTP 200 OK`: Notificación recibida y procesada correctamente (o evento irrelevante/ignorado intencionalmente).
  - `HTTP 401 Unauthorized`: Firma inválida o adulterada.

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
| Trial activo / Vencido | Webhook recibe `preapproval` autorizado o `subscription_authorized_payment` | `activa` | Se crea/actualiza `Suscripcion`, `fecha_vencimiento` = `now() + 30/365d`, se registra `Pago`, se desbloquea acceso | CA-002 |
| `activa` | Webhook recibe cobro recurrente periódico aprobado | `activa` | `fecha_vencimiento` se extiende +30 o +365 días; se crea nuevo registro `Pago` con `referencia_gateway` único | CA-003 |
| `activa` | Usuario solicita y confirma cancelación | `cancelada` | Se invoca MercadoPago API (`status: cancelled`); `estado` local pasa a `cancelada`; acceso se mantiene hasta `fecha_vencimiento` | CA-004 |
| `cancelada` / `activa` | Se alcanza `fecha_vencimiento` sin nuevos cobros aprobados | `vencida` | Al vencer, el usuario pierde el acceso a OCR en Telegram y a la extensión DRF | CA-005 |

---

## 9. Criterios de Aceptación

### CA-001 — Bloqueo de subida por Telegram con trial vencido (RF-010)
- **Dado** un usuario cuyo `trial_start_date` es de hace 16 días y no posee una suscripción activa de pago,
- **Cuando** dicho usuario envía una foto o documento de un comprobante a través de Telegram,
- **Entonces** el sistema NO almacena el archivo ni ejecuta la llamada al servicio OCR,
- **Y** el bot responde un mensaje: *"Tu período de prueba de 15 días ha finalizado. Para seguir procesando comprobantes y cargarlos en SIRADIG, suscribite a un plan en: `<URL_PLANES>`"*.

### CA-002 — Bloqueo de consulta de comprobantes en extensión API DRF (RF-011)
- **Dado** un usuario autenticado mediante su `Token` DRF cuyo período de prueba expiró sin suscripción activa,
- **Cuando** la extensión de navegador realiza una petición `GET` a `/api/receipts/pending/`,
- **Entonces** la API responde con código `HTTP 403 Forbidden` (o `402 Payment Required`),
- **Y** el cuerpo JSON contiene `{"detail": "Acceso restringido: Período de prueba vencido. Se requiere una suscripción activa.", "code": "subscription_required"}`.

### CA-003 — Acceso permitido para usuario en período de prueba activo (RF-004, RF-010, RF-011)
- **Dado** un usuario registrado hace 5 días (`trial_start_date` dentro de los 15 días permitidos),
- **Cuando** envía un comprobante por Telegram o consulta `/api/receipts/pending/` vía DRF,
- **Entonces** la petición se procesa con normalidad (el OCR extrae los datos y la API retorna HTTP 200 con los comprobantes).

### CA-004 — Creación de suscripción y redirección a MercadoPago (RF-006)
- **Dado** un usuario autenticado en la plataforma web en `/suscripciones/planes/`,
- **Cuando** hace clic en el botón de suscripción mensual (`/suscripciones/suscribirse/mensual/`),
- **Entonces** el backend envía el payload `preapproval` a la API de MercadoPago con `external_reference="<user_id>:mensual"` y `auto_recurring`,
- **Y** redirige al usuario mediante `HTTP 302` hacia el `init_point` retornado por MercadoPago.

### CA-005 — Acreditación automática vía Webhook e idempotencia (RF-007, RF-009)
- **Dado** una notificación de webhook válida enviada por MercadoPago correspondiente a una suscripción autorizada o pago aprobado,
- **Cuando** el endpoint `/suscripciones/webhook/` procesa la petición con firma criptográfica válida,
- **Entonces** se crea o actualiza la `Suscripcion` en estado `activa` con fecha de vencimiento adecuada,
- **Y** se registra el `Pago` asociado;
- **Y** ante el reenvío de la misma notificación con el mismo ID de transacción, el endpoint responde HTTP 200 sin duplicar el pago ni sumar días adicionales.

### CA-006 — Rechazo de Webhook con firma inválida (RF-008)
- **Dado** un requerimiento al webhook con header `x-signature` alterado o inexistente cuando `MERCADOPAGO_WEBHOOK_SECRET` está configurado,
- **Cuando** la petición llega a `/suscripciones/webhook/`,
- **Entonces** el sistema registra una advertencia en el log y responde inmediatamente con código `HTTP 401 Unauthorized` sin alterar la base de datos.

### CA-007 — Cancelación de suscripción en MercadoPago (RF-012)
- **Dado** un usuario con suscripción recurrente activa (`gateway_subscription_id` presente),
- **Cuando** confirma la cancelación de su suscripción en la plataforma,
- **Entonces** el sistema envía una petición `PUT` o `PATCH` a MercadoPago para cancelar el débito recurrente (`{"status": "cancelled"}`),
- **Y** actualiza localmente el estado a `cancelada`, manteniendo el acceso activo hasta `fecha_vencimiento`.

---

## 10. Requisitos No Funcionales y Seguridad

- **RNF-001 (Seguridad Criptográfica en Webhooks):** Todo webhook en producción debe validar el encabezado `x-signature` utilizando HMAC-SHA256 con el `request-id` y el timestamp `ts` para prevenir ataques de suplantación o replay attacks.
- **RNF-002 (Aislamiento de Datos):** Ningún usuario puede visualizar, consultar ni cancelar la suscripción o los comprobantes de otro usuario.
- **RNF-003 (Resiliencia ante Caídas del Gateway):** Si la API de MercadoPago se encuentra fuera de servicio al intentar crear una suscripción o cancelarla, el sistema debe registrar el error detallado en los logs y mostrar una vista de error amigable sin exponer stack traces ni secrets.
- **RNF-004 (Transaccionalidad Atómica):** Todas las actualizaciones de suscripción, asignación de fechas de vencimiento y registro de pagos dentro del webhook o de la cancelación deben ejecutarse dentro de bloques `transaction.atomic()` para garantizar consistencia.
- **RNF-005 (Cero Credenciales Fiscales):** El módulo de suscripciones no maneja, solicita ni almacena claves de AFIP ni datos de tarjetas de crédito.
- **RNF-006 (Calidad y Cobertura):** La nueva app `subscriptions` debe contar con tests unitarios y de integración con mocks en `pytest-django`, cubriendo con un mínimo de 80% de cobertura el servicio de webhook, la validación de firmas y el servicio de control de acceso (trial y suscripción).

---

## 11. Dependencias, Restricciones y Riesgos

### 11.1 Dependencias
- SDK oficial `mercadopago` (agregado y fijado en `siradig_auto/requirements.txt`, ej. `mercadopago==2.3.0` o versión compatible probada).
- Biblioteca `requests` (ya presente en `requirements.txt`).

### 11.2 Restricciones Constitucionales
- Cumplimiento de `docs/constitution.md`: el stack se mantiene en Django + Python 3.11, dependencias fijadas y pruebas en `pytest-django`.
- La extensión debe continuar funcionando sin cambios estructurales en su protocolo, simplemente recibiendo el código HTTP de suscripción requerida cuando el acceso esté vencido.

### 11.3 Riesgos y Mitigaciones
- **Riesgo:** Webhooks de MercadoPago en entorno local (desarrollo/staging).
  - *Mitigación:* Documentar el uso de herramientas como `ngrok` o la variable `MERCADOPAGO_BACK_URL` para desarrollo local, y permitir omitir la validación de firma únicamente si `MERCADOPAGO_WEBHOOK_SECRET` está explícitamente vacío durante pruebas iniciales.
- **Riesgo:** Desfase horario o latencia entre el cobro de MercadoPago y el webhook.
  - *Mitigación:* Al redirigir a la página de retorno (`pago_exitoso`), mostrar un mensaje informativo que aclare que la activación puede demorar unos instantes hasta la recepción de la confirmación bancaria.

---

## 12. Trazabilidad

| Historia o necesidad | Requisito | Regla relacionada | Criterios | Tipo de verificación previsto |
| --- | --- | --- | --- | --- |
| HU-SUB-001 | RF-001, RF-005, RF-013 | RN-001, RN-002 | CA-003 | Test funcional de vistas y templates |
| HU-SUB-002 | RF-006 | RN-003 | CA-004 | Test unitario con mock de SDK MercadoPago |
| HU-SUB-003 | RF-007, RF-008, RF-009 | RN-004, RN-006, RN-008 | CA-005, CA-006 | Test de integración de Webhook con fixtures |
| HU-SUB-004 | RF-004, RF-010, RF-011 | RN-001, RN-002 | CA-001, CA-002 | Tests en `telegram_webhook` y `PendingReceiptListAPIView` |
| HU-SUB-005 | RF-012 | RN-005 | CA-007 | Test de flujo de cancelación con mock de API MP |

---

## 13. Dudas y Decisiones

| ID | Pregunta o decisión | Impacto | Estado y evidencia |
| --- | --- | --- | --- |
| DEC-001 | Cobro recurrente: Preapproval directo | Define la integración con la API de MercadoPago (`/preapproval`) en vez de pagos manuales únicos | Confirmado por el usuario y verificado en `Monitorea` |
| DEC-002 | Período de prueba (Trial) de 15 días | Define el período inicial gratuito evaluado sobre `UserProfile.trial_start_date` | Confirmado según directiva del usuario (configurable vía `TRIAL_DURATION_DAYS`) |
| DEC-003 | Nueva app `subscriptions` | Modularidad limpia sin contaminar el modelo de `receipts` | Confirmado por el usuario |
| DEC-004 | Código HTTP ante bloqueo en API DRF | La extensión recibirá HTTP 403 Forbidden con código `subscription_required` | Confirmado |
| Q-001 | ¿El flujo de cancelación requerirá código de seguridad de 6 dígitos por email (como en Monitorea) o confirmación simple en el panel web? | Afecta complejidad del template y envío de correo | Pendiente de confirmación menor (propuesta: confirmación modal directa en web, extensible a email) |

---

## 14. Control de Calidad y Aprobación

- [x] Problema, actores y resultado esperado están definidos.
- [x] Alcance y exclusiones no se contradicen.
- [x] Los requisitos usan lenguaje inequívoco e identificadores estables.
- [x] Cada RF tiene criterios de aceptación verificables en formato Dado/Cuando/Entonces.
- [x] Las historias están enlazadas con los requisitos que las satisfacen.
- [x] Se cubren errores, autorización, expiración e idempotencia.
- [x] Los estados y transiciones son consistentes con el ciclo de cobro.
- [x] Los RNF son medibles y respetan la constitución del proyecto.
- [x] Privacidad y ausencia absoluta de credenciales AFIP garantizadas.
- [x] Revisión identificada y lista para aprobación.

---

## 15. Historial de Cambios

| Revisión | Cambio | Requisitos afectados | Estado de aprobación |
| --- | --- | --- | --- |
| REV-001 | Creación inicial de especificación basada en Monitorea y directivas acordadas | Todos (RF-001 a RF-013) | APROBADA (Usuario) |
