# Desglose de Tareas: Integración de Pasarela de Pagos MercadoPago y Gestión de Suscripciones

- **Identificador de Especificación:** `specs/007-pasarela-mercadopago.md` (`007-pasarela-mercadopago`)
- **Revisión de Especificación:** `REV-002`
- **Plan Técnico:** `specs/007-plan.md`
- **Estado de las Tareas:** `PENDIENTE_DE_APROBACION`
- **Fecha:** 2026-10-29

---

## Matriz de Tareas

| ID | Tarea | Requisitos Cubiertos | Archivos Principales | Dependencias |
|---|---|---|---|---|
| **T1** | Dependencias, configuración de settings con tarifa $8999 y bootstrap de app `subscriptions` | RF-001, RF-002, RF-003, RNF-005, RN-009 | `siradig_auto/requirements.txt`, `core/settings.py`, `subscriptions/apps.py` | Ninguna |
| **T2** | Modelos `Plan` (con `gateway_plan_id` y default 8999 ARS), `Suscripcion`, `Pago`, migraciones y Admin | RF-001, RF-002, RF-003, RN-003, RN-009 | `subscriptions/models.py`, `subscriptions/admin.py`, migraciones | T1 |
| **T3** | Servicio unificado de acceso (`trial` de 15 días y suscripción activa) y tests unitarios | RF-004, RN-001, RN-002, RN-003 | `subscriptions/services/access.py`, `subscriptions/tests.py` | T2 |
| **T4** | Integración del SDK Mercado Pago (Preapproval mensual $8999 ARS y cancelación) | RF-006, RF-012, RN-007, RN-009 | `subscriptions/services/mercadopago.py` | T1 |
| **T5** | Comando de gestión `ensure_mercadopago_plan` para creación de plan recurrente en Mercado Pago | RF-014, RN-009 | `subscriptions/management/commands/ensure_mercadopago_plan.py` | T2, T4 |
| **T6** | Webhook oficial de Mercado Pago con validación criptográfica HMAC canónica e idempotencia | RF-007, RF-008, RF-009, RN-004, RN-006, RN-008, RNF-001, RNF-004 | `subscriptions/services/webhook.py`, `subscriptions/views.py` | T2, T4 |
| **T7** | Vistas y plantillas de autoservicio: Planes ($8.999 ARS), checkout, retornos y cancelación | RF-005, RF-006, RF-012, RN-005 | `subscriptions/views.py`, `subscriptions/urls.py`, `subscriptions/templates/` | T4, T6 |
| **T8** | Restricción de acceso en Telegram Webhook y API DRF de comprobantes | RF-010, RF-011, RNF-002 | `receipts/views.py`, `subscriptions/permissions.py` | T3 |
| **T9** | Visualización de estado de suscripción y banner de trial en Dashboard Web | RF-013, RN-001 | `receipts/views.py`, `receipts/templates/receipts/dashboard.html` | T3 |
| **T10** | Suite integral de pruebas automatizadas, cobertura >= 80% y verificación de linters | Todos los RF y CA (CA-001 a CA-008, RNF-006) | `subscriptions/tests.py`, `receipts/tests.py` | T1 a T9 |

---

## Detalle de Tareas

### Tarea T1: Dependencias, configuración de settings con tarifa $8999 y bootstrap de app `subscriptions`
- **Objetivo:** Incorporar la dependencia `mercadopago==2.2.0` en `requirements.txt`, configurar variables de entorno para credenciales, `PRECIO_MENSUAL="8999.00"` y parámetros de suscripción en `core/settings.py`, registrar la app `subscriptions` en `INSTALLED_APPS` y vincular sus rutas en `core/urls.py`.
- **Requisitos cubiertos:** `RF-001`, `RF-002`, `RF-003`, `RNF-005`, `RN-009`.
- **Criterios de Aceptación:** Base técnica para todos los CA.
- **Archivos afectados:**
  - `siradig_auto/requirements.txt`
  - `core/settings.py`
  - `core/urls.py`
  - `subscriptions/apps.py` (nuevo)
  - `subscriptions/__init__.py` (nuevo)
- **Cambios previstos:**
  1. Agregar `mercadopago==2.2.0` a `siradig_auto/requirements.txt`.
  2. En `core/settings.py`, agregar `"subscriptions"` a `INSTALLED_APPS`.
  3. Configurar variables de entorno con fallback en `core/settings.py`:
     - `MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_PUBLIC_KEY`, `MERCADOPAGO_WEBHOOK_SECRET`, `MERCADOPAGO_BACK_URL`, `MERCADOPAGO_PREAPPROVAL_PLAN_ID`, `PRECIO_MENSUAL` (default `8999.00`), `TRIAL_DURATION_DAYS` (default `15`).
  4. En `core/urls.py`, incluir `path("suscripciones/", include("subscriptions.urls"))`.
- **Límites:** No modificar modelos ni vistas existentes de `receipts`.
- **Pruebas y Verificaciones:** `python manage.py check`.

---

### Tarea T2: Modelos `Plan` (con `gateway_plan_id` y default 8999 ARS), `Suscripcion`, `Pago`, migraciones y Admin
- **Objetivo:** Definir los modelos de datos de suscripción adaptados de Monitorea con el campo `gateway_plan_id` en `Plan` y precio default `8999.00`, generar migraciones consistentes y exponerlos en Django Admin para auditoría.
- **Requisitos cubiertos:** `RF-001`, `RF-002`, `RF-003`, `RN-003`, `RN-009`.
- **Criterios de Aceptación:** `CA-005`, `CA-008`.
- **Archivos afectados:**
  - `subscriptions/models.py` (nuevo)
  - `subscriptions/admin.py` (nuevo)
  - `subscriptions/migrations/0001_initial.py` (nuevo)
- **Cambios previstos:**
  1. Implementar modelo `Plan` con `nombre` (`gratuito`, `mensual`, `anual`), `precio_mensual` (default `8999.00`), `descripcion`, `dias_duracion`, `gateway_plan_id` (`preapproval_plan_id`).
  2. Implementar modelo `Suscripcion` con `OneToOneField` a `User`, `plan`, `estado` (`activa`, `vencida`, `cancelada`, `trial`), `fecha_inicio`, `fecha_vencimiento`, `gateway_subscription_id`, `codigo_cancelacion`.
  3. Implementar modelo `Pago` con `ForeignKey` a `Suscripcion`, `monto`, `fecha`, `metodo`, `referencia_gateway` (`unique=True`), `exitoso`.
  4. Registrar los tres modelos en `subscriptions/admin.py`.
  5. Ejecutar `python manage.py makemigrations subscriptions`.
- **Límites:** No modificar la tabla `Receipt` ni alterar la definición existente de `UserProfile`.
- **Pruebas y Verificaciones:** `python manage.py migrate --check` y tests unitarios de creación de instancias de modelo.

---

### Tarea T3: Servicio unificado de acceso (`trial` de 15 días y suscripción activa) y tests unitarios
- **Objetivo:** Desarrollar el servicio centralizado `subscriptions/services/access.py` que calcula los días restantes de prueba gratuita y evalúa si un usuario posee acceso activo para operar.
- **Requisitos cubiertos:** `RF-004`, `RN-001`, `RN-002`, `RN-003`.
- **Criterios de Aceptación:** `CA-003`.
- **Archivos afectados:**
  - `subscriptions/services/__init__.py` (nuevo)
  - `subscriptions/services/access.py` (nuevo)
  - `subscriptions/tests.py` (nuevo)
- **Cambios previstos:**
  1. Crear función `dias_restantes_trial(user) -> int`:
     - Calcula `max(0, ceil((profile.trial_start_date + timedelta(days=TRIAL_DURATION_DAYS) - now()).total_seconds() / 86400))`.
  2. Crear función `usuario_tiene_acceso_activo(user) -> bool`:
     - Retorna `True` si tiene suscripción activa con `fecha_vencimiento > now()`.
     - Retorna `True` si `dias_restantes_trial(user) > 0`.
     - Caso contrario retorna `False`.
  3. Crear función auxiliar `obtener_estado_cuenta(user) -> dict` con información para vistas y templates.
- **Límites:** Mantener la función pura, desacoplada del protocolo HTTP.
- **Pruebas y Verificaciones:** Tests unitarios en `subscriptions/tests.py` probando usuarios con 0 días, 5 días, suscripción activa, y suscripción expirada.

---

### Tarea T4: Integración del SDK Mercado Pago (Preapproval mensual $8999 ARS y cancelación)
- **Objetivo:** Encapsular la comunicación con Mercado Pago en `subscriptions/services/mercadopago.py` para la creación de suscripciones recurrentes (`/preapproval`) con el monto oficial de $8999 ARS y su cancelación vía API.
- **Requisitos cubiertos:** `RF-006`, `RF-012`, `RN-007`, `RN-009`.
- **Criterios de Aceptación:** `CA-004`, `CA-007`.
- **Archivos afectados:**
  - `subscriptions/services/mercadopago.py` (nuevo)
- **Cambios previstos:**
  1. Inicializar cliente `mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)`.
  2. Implementar `crear_preapproval(user, plan) -> str`:
     - Prepara payload con `payer_email`, `back_url`, `reason="SIRADIG Auto - Plan Mensual"`, `auto_recurring`: `frequency=1`, `frequency_type="months"`, `transaction_amount=float(plan.precio_mensual)` ($8999), `currency_id="ARS"`, `external_reference = f"{user.id}:mensual"`.
     - Si `plan.gateway_plan_id` está presente, incluir `preapproval_plan_id`.
     - Llama a `sdk.preapproval().create(payload)` y retorna `init_point`.
  3. Implementar `cancelar_preapproval(gateway_subscription_id) -> bool`:
     - Llama a `sdk.preapproval().update(gateway_subscription_id, {"status": "cancelled"})`.
- **Límites:** Manejo de excepciones robusto ante caídas de red o respuestas de error de Mercado Pago sin exponer tokens ni credenciales.
- **Pruebas y Verificaciones:** Tests unitarios con mocks de `mercadopago.SDK` verificando payloads y URLs devueltas.

---

### Tarea T5: Comando de gestión `ensure_mercadopago_plan` para creación de plan recurrente en Mercado Pago
- **Objetivo:** Crear el Django management command `ensure_mercadopago_plan` que provisiona automáticamente el `preapproval_plan` mensual en Mercado Pago con la tarifa de 8.999 ARS y almacena su ID en la base de datos.
- **Requisitos cubiertos:** `RF-014`, `RN-009`.
- **Criterios de Aceptación:** `CA-008`.
- **Archivos afectados:**
  - `subscriptions/management/__init__.py` (nuevo)
  - `subscriptions/management/commands/__init__.py` (nuevo)
  - `subscriptions/management/commands/ensure_mercadopago_plan.py` (nuevo)
- **Cambios previstos:**
  1. Definir comando que busca el `Plan` mensual (`nombre='mensual'`).
  2. Si `gateway_plan_id` está vacío o flag `--force`:
     - Invoca SDK de Mercado Pago o endpoint `/preapproval_plan` con `reason="SIRADIG Auto - Plan Mensual"`, `frequency: 1`, `frequency_type: "months"`, `transaction_amount: 8999.00`, `currency_id: "ARS"`, `back_url`.
     - Guarda el `preapproval_plan_id` retornado en `plan.gateway_plan_id`.
     - Emite mensaje de éxito informando el ID generado.
- **Límites:** No modificar planes inexistentes ni requerir intervención manual en el panel de Mercado Pago.
- **Pruebas y Verificaciones:** Test unitario ejecutando `call_command('ensure_mercadopago_plan')` con mock de la API de Mercado Pago.

---

### Tarea T6: Webhook oficial de Mercado Pago con validación criptográfica HMAC canónica e idempotencia
- **Objetivo:** Implementar el endpoint del webhook y su servicio de procesamiento seguro para los tópicos oficiales de suscripciones de Mercado Pago (`subscription_authorized_payment`, `subscription_preapproval`, `subscription_preapproval_plan`, `payment`).
- **Requisitos cubiertos:** `RF-007`, `RF-008`, `RF-009`, `RN-004`, `RN-006`, `RN-008`, `RNF-001`, `RNF-004`.
- **Criterios de Aceptación:** `CA-005`, `CA-006`.
- **Archivos afectados:**
  - `subscriptions/services/webhook.py` (nuevo)
  - `subscriptions/views.py` (nuevo)
- **Cambios previstos:**
  1. En `subscriptions/services/webhook.py`:
     - `validar_firma_mercadopago(request) -> bool`: parsea `x-signature` (`ts`, `v1`), toma `x-request-id` y `data.id` (en minúsculas), ensambla el manifest `id:[data.id];request-id:[x-request-id];ts:[ts];`, computa HMAC-SHA256 con `MERCADOPAGO_WEBHOOK_SECRET` y compara de forma segura (`hmac.compare_digest`).
     - `procesar_notificacion_mp(data, topic) -> bool`: dentro de `transaction.atomic()`, parsea eventos de cobro (`subscription_authorized_payment` o `payment`), registra el `Pago` con `get_or_create(referencia_gateway=...)`, y si es un cobro nuevo y aprobado, extiende la vigencia de la `Suscripcion` en +30 días.
  2. En `subscriptions/views.py`:
     - Vista `@csrf_exempt` `mercadopago_webhook(request)`: valida firma (HTTP 401 si falla), procesa notificación y responde HTTP 200.
- **Límites:** Estricta idempotencia ante llamadas duplicadas.
- **Pruebas y Verificaciones:** Tests de webhook con firmas válidas, inválidas, manipulación de encabezados y eventos duplicados.

---

### Tarea T7: Vistas y plantillas de autoservicio: Planes ($8.999 ARS), checkout, retornos y cancelación
- **Objetivo:** Desarrollar las interfaces de usuario para consultar planes con la tarifa destacada de $8.999 ARS, iniciar el checkout de Mercado Pago, visualizar páginas de retorno y gestionar la cancelación de suscripciones.
- **Requisitos cubiertos:** `RF-005`, `RF-006`, `RF-012`, `RN-005`.
- **Criterios de Aceptación:** `CA-004`, `CA-007`.
- **Archivos afectados:**
  - `subscriptions/views.py`
  - `subscriptions/urls.py` (nuevo)
  - `subscriptions/templates/subscriptions/planes.html` (nuevo)
  - `subscriptions/templates/subscriptions/pago_exitoso.html` (nuevo)
  - `subscriptions/templates/subscriptions/pago_fallido.html` (nuevo)
  - `subscriptions/templates/subscriptions/cancelar.html` (nuevo)
- **Cambios previstos:**
  1. `planes_view`: renderiza el plan mensual con precio de $8.999 ARS, indicando estado de prueba/suscripción actual.
  2. `suscribir_view`: redirige a `init_point` de Mercado Pago vía `HTTP 302`.
  3. `cancelar_suscripcion_view`: confirma la cancelación, invoca `cancelar_preapproval`, cambia estado a `cancelada` y preserva acceso hasta vencimiento.
  4. Vistas estáticas de retorno `pago_exitoso` y `pago_fallido`.
- **Límites:** Mantener diseño consistente con Bootstrap 5.3 heredando de `base.html`.
- **Pruebas y Verificaciones:** Tests de vistas HTTP con `client` de Django autenticado.

---

### Tarea T8: Restricción de acceso en Telegram Webhook y API DRF de comprobantes
- **Objetivo:** Bloquear la ingesta y extracción por OCR en Telegram y restringir el acceso a los endpoints de comprobantes consumidos por la extensión cuando el usuario tenga el trial vencido y no posea suscripción activa.
- **Requisitos cubiertos:** `RF-010`, `RF-011`, `RNF-002`.
- **Criterios de Aceptación:** `CA-001`, `CA-002`.
- **Archivos afectados:**
  - `subscriptions/permissions.py` (nuevo)
  - `receipts/views.py`
- **Cambios previstos:**
  1. Crear permiso DRF `HasActiveSubscriptionOrTrial` en `subscriptions/permissions.py`:
     - Retorna `True` si `usuario_tiene_acceso_activo(request.user)`.
     - Caso contrario lanza `PermissionDenied` con detalle explicativo y código `subscription_required`.
  2. En `receipts/views.py`:
     - Agregar `HasActiveSubscriptionOrTrial` a `PendingReceiptListAPIView` y `ReceiptUpdateAPIView`.
     - En `_handle_receipt_file` (Telegram webhook): antes de descargar el archivo y llamar al OCR, verificar `usuario_tiene_acceso_activo(profile.user)`.
     - Si es `False`, no procesar archivo y enviar mensaje informando que el trial finalizó con el link a `/suscripciones/planes/`.
- **Límites:** No modificar la lógica de extracción de comprobantes cuando el acceso esté activo.
- **Pruebas y Verificaciones:** Tests específicos en `receipts/tests.py` simulando solicitudes con usuarios activos y usuarios vencidos.

---

### Tarea T9: Visualización de estado de suscripción y banner de trial en Dashboard Web
- **Objetivo:** Enriquecer el Dashboard de usuario con un badge y banner informativo que muestre con claridad los días restantes de prueba, estado de suscripción mensual ($8.999 ARS) y alertas visuales cuando la cuenta esté vencida.
- **Requisitos cubiertos:** `RF-013`, `RN-001`.
- **Criterios de Aceptación:** `CA-003`.
- **Archivos afectados:**
  - `receipts/views.py` (`dashboard_home`)
  - `receipts/templates/receipts/dashboard.html`
- **Cambios previstos:**
  1. En `dashboard_home`: inyectar en el contexto los datos de `obtener_estado_cuenta(request.user)`.
  2. En `receipts/templates/receipts/dashboard.html`:
     - Si está en trial: Badge informativo `"Período de prueba: X días restantes"`.
     - Si tiene suscripción activa: Badge verde `"Suscripción Mensual Activa ($8.999 ARS - Vence: DD/MM/AAAA)"`.
     - Si está vencido: Alerta Bootstrap destacada `"Tu período de prueba ha finalizado. Suscribite al Plan Mensual para continuar cargando comprobantes"` con botón a `/suscripciones/planes/`.
- **Límites:** Conservar las métricas de KPIs y tabla de comprobantes existentes.
- **Pruebas y Verificaciones:** Comprobar renderizado de textos y alertas según estado del usuario.

---

### Tarea T10: Suite integral de pruebas automatizadas, cobertura >= 80% y verificación de linters
- **Objetivo:** Ejecutar la suite completa de pruebas con `pytest-django`, verificar mocks de Mercado Pago (preapproval, preapproval_plan, webhooks oficiales, management command), medir cobertura sobre `subscriptions` y `receipts` superando el umbral de 80%, y validar formato y linters con Ruff.
- **Requisitos cubiertos:** Todos los RF y CA (`CA-001` a `CA-008`, `RNF-006`).
- **Criterios de Aceptación:** Verificación exhaustiva de todos los criterios.
- **Archivos afectados:**
  - `subscriptions/tests.py`
  - `receipts/tests.py`
- **Comandos de verificación:**
  - `pytest --cov=subscriptions --cov=receipts --cov-report=term-missing`
  - `ruff check .`
  - `ruff format --check .`
- **Criterio de finalización:** 100% de tests pasando, cobertura >= 80% en módulos críticos y cero errores de linter.


---

## Detalle de Tareas

### Tarea T1: Dependencias, configuración en `settings.py` y creación de la app `subscriptions`
- **Objetivo:** Incorporar la dependencia `mercadopago==2.2.0` en `requirements.txt`, configurar variables de entorno para credenciales y parámetros de suscripción en `core/settings.py`, registrar la app `subscriptions` en `INSTALLED_APPS` y vincular sus rutas en `core/urls.py`.
- **Requisitos cubiertos:** `RF-001`, `RF-002`, `RF-003`, `RNF-005`.
- **Criterios de Aceptación:** Base técnica para todos los CA.
- **Archivos afectados:**
  - `siradig_auto/requirements.txt`
  - `core/settings.py`
  - `core/urls.py`
  - `subscriptions/apps.py` (nuevo)
  - `subscriptions/__init__.py` (nuevo)
- **Cambios previstos:**
  1. Agregar `mercadopago==2.2.0` a `siradig_auto/requirements.txt`.
  2. En `core/settings.py`, agregar `"subscriptions"` a `INSTALLED_APPS`.
  3. Configurar variables de entorno con fallback en `core/settings.py`:
     - `MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_PUBLIC_KEY`, `MERCADOPAGO_WEBHOOK_SECRET`, `MERCADOPAGO_BACK_URL`, `PRECIO_MENSUAL`, `TRIAL_DURATION_DAYS`.
  4. En `core/urls.py`, incluir `path("suscripciones/", include("subscriptions.urls"))`.
- **Límites:** No modificar modelos ni vistas existentes.
- **Pruebas y Verificaciones:** `python manage.py check`.

---

### Tarea T2: Modelos `Plan`, `Suscripcion`, `Pago`, migraciones y registro en Admin
- **Objetivo:** Definir los modelos de datos de suscripción adaptados de Monitorea, generar migraciones consistentes y exponerlos en Django Admin para auditoría.
- **Requisitos cubiertos:** `RF-001`, `RF-002`, `RF-003`, `RN-003`.
- **Criterios de Aceptación:** `CA-005`.
- **Archivos afectados:**
  - `subscriptions/models.py` (nuevo)
  - `subscriptions/admin.py` (nuevo)
  - `subscriptions/migrations/0001_initial.py` (nuevo)
- **Cambios previstos:**
  1. Implementar modelo `Plan` con `nombre` (`gratuito`, `mensual`, `anual`), `precio_mensual`, `descripcion`, `dias_duracion`.
  2. Implementar modelo `Suscripcion` con `OneToOneField` a `User`, `plan`, `estado` (`activa`, `vencida`, `cancelada`, `trial`), `fecha_inicio`, `fecha_vencimiento`, `gateway_subscription_id`, `codigo_cancelacion`.
  3. Implementar modelo `Pago` con `ForeignKey` a `Suscripcion`, `monto`, `fecha`, `metodo`, `referencia_gateway` (`unique=True`), `exitoso`.
  4. Registrar los tres modelos en `subscriptions/admin.py`.
  5. Ejecutar `python manage.py makemigrations subscriptions`.
- **Límites:** No modificar la tabla `Receipt` ni alterar la definición existente de `UserProfile`.
- **Pruebas y Verificaciones:** `python manage.py migrate --check` y tests unitarios de creación de instancias de modelo.

---

### Tarea T3: Servicio unificado de acceso (`trial` y suscripción activa) y tests unitarios
- **Objetivo:** Desarrollar el servicio centralizado `subscriptions/services/access.py` que calcula los días restantes de prueba gratuita y evalúa si un usuario posee acceso activo para operar.
- **Requisitos cubiertos:** `RF-004`, `RN-001`, `RN-002`, `RN-003`.
- **Criterios de Aceptación:** `CA-003`.
- **Archivos afectados:**
  - `subscriptions/services/__init__.py` (nuevo)
  - `subscriptions/services/access.py` (nuevo)
  - `subscriptions/tests.py` (nuevo)
- **Cambios previstos:**
  1. Crear función `dias_restantes_trial(user) -> int`:
     - Calcula `max(0, ceil((profile.trial_start_date + timedelta(days=TRIAL_DURATION_DAYS) - now()).total_seconds() / 86400))`.
  2. Crear función `usuario_tiene_acceso_activo(user) -> bool`:
     - Retorna `True` si tiene suscripción activa con `fecha_vencimiento > now()`.
     - Retorna `True` si `dias_restantes_trial(user) > 0`.
     - Caso contrario retorna `False`.
  3. Crear función auxiliar `obtener_estado_cuenta(user) -> dict` con información para vistas y templates.
- **Límites:** Mantener la función pura, desacoplada del protocolo HTTP.
- **Pruebas y Verificaciones:** Tests unitarios en `subscriptions/tests.py` probando usuarios con 0 días, 5 días, suscripción activa, y suscripción expirada.

---

### Tarea T4: Integración del SDK MercadoPago (creación y cancelación de Preapproval)
- **Objetivo:** Encapsular la comunicación con MercadoPago en `subscriptions/services/mercadopago.py` para la creación de suscripciones recurrentes (`preapproval`) y su cancelación vía API.
- **Requisitos cubiertos:** `RF-006`, `RF-012`, `RN-007`.
- **Criterios de Aceptación:** `CA-004`, `CA-007`.
- **Archivos afectados:**
  - `subscriptions/services/mercadopago.py` (nuevo)
- **Cambios previstos:**
  1. Inicializar cliente `mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)`.
  2. Implementar `crear_preapproval(user, tipo_plan) -> str`:
     - Prepara payload con `payer_email`, `back_url`, `reason`, `auto_recurring` (mensual o anual en ARS), `external_reference = f"{user.id}:{tipo_plan}"`.
     - Llama a `sdk.preapproval().create(payload)` y retorna `init_point`.
  3. Implementar `cancelar_preapproval(gateway_subscription_id) -> bool`:
     - Llama a `sdk.preapproval().update(gateway_subscription_id, {"status": "cancelled"})`.
- **Límites:** Manejo de excepciones robusto ante caídas de red o respuestas de error de MercadoPago sin exponer tokens ni credenciales.
- **Pruebas y Verificaciones:** Tests unitarios con mocks de `mercadopago.SDK` verificando payloads y URLs devueltas.

---

### Tarea T5: Webhook de MercadoPago con verificación criptográfica HMAC e idempotencia
- **Objetivo:** Implementar el endpoint del webhook y su servicio de procesamiento seguro para notificaciones de pago y preapproval de MercadoPago.
- **Requisitos cubiertos:** `RF-007`, `RF-008`, `RF-009`, `RN-004`, `RN-006`, `RN-008`, `RNF-001`, `RNF-004`.
- **Criterios de Aceptación:** `CA-005`, `CA-006`.
- **Archivos afectados:**
  - `subscriptions/services/webhook.py` (nuevo)
  - `subscriptions/views.py` (nuevo)
- **Cambios previstos:**
  1. En `subscriptions/services/webhook.py`:
     - `validar_firma_mercadopago(request) -> bool`: parsea `x-signature` (`ts`, `v1`), valida digest HMAC-SHA256 con `MERCADOPAGO_WEBHOOK_SECRET` y `x-request-id`.
     - `procesar_notificacion_mp(data) -> bool`: dentro de `transaction.atomic()`, parsea eventos de cobro (`subscription_authorized_payment` o `payment`), registra el `Pago` con `update_or_create(referencia_gateway=...)`, y si es un cobro nuevo y aprobado, extiende la vigencia de la `Suscripcion` en +30 o +365 días.
  2. En `subscriptions/views.py`:
     - Vista `@csrf_exempt` `mercadopago_webhook(request)`: valida firma (HTTP 401 si falla), procesa notificación y responde HTTP 200.
- **Límites:** Estricta idempotencia ante llamadas duplicadas.
- **Pruebas y Verificaciones:** Tests de webhook con firmas válidas, inválidas, eventos nuevos y eventos duplicados.

---

### Tarea T6: Vistas y plantillas de autoservicio: Planes, suscripción, retornos y cancelación
- **Objetivo:** Desarrollar las interfaces de usuario para consultar planes, iniciar el checkout de MercadoPago, visualizar páginas de retorno y gestionar la cancelación de suscripciones.
- **Requisitos cubiertos:** `RF-005`, `RF-006`, `RF-012`, `RN-005`.
- **Criterios de Aceptación:** `CA-004`, `CA-007`.
- **Archivos afectados:**
  - `subscriptions/views.py`
  - `subscriptions/urls.py` (nuevo)
  - `subscriptions/templates/subscriptions/planes.html` (nuevo)
  - `subscriptions/templates/subscriptions/pago_exitoso.html` (nuevo)
  - `subscriptions/templates/subscriptions/pago_fallido.html` (nuevo)
  - `subscriptions/templates/subscriptions/cancelar.html` (nuevo)
- **Cambios previstos:**
  1. `planes_view`: renderiza opciones mensual y anual, indicando estado de prueba/suscripción actual.
  2. `suscribir_view`: redirige a `init_point` de MercadoPago vía `HTTP 302`.
  3. `cancelar_suscripcion_view`: confirma la cancelación, invoca `cancelar_preapproval`, cambia estado a `cancelada` y preserva acceso hasta vencimiento.
  4. Vistas estáticas de retorno `pago_exitoso` y `pago_fallido`.
- **Límites:** Mantener diseño consistente con Bootstrap 5.3 heredando de `base.html`.
- **Pruebas y Verificaciones:** Tests de vistas HTTP con `client` de Django autenticado.

---

### Tarea T7: Restricción de acceso en Telegram Webhook y API DRF de comprobantes
- **Objetivo:** Bloquear la ingesta y extracción por OCR en Telegram y restringir el acceso a los endpoints de comprobantes consumidos por la extensión cuando el usuario tenga el trial vencido y no posea suscripción activa.
- **Requisitos cubiertos:** `RF-010`, `RF-011`, `RNF-002`.
- **Criterios de Aceptación:** `CA-001`, `CA-002`.
- **Archivos afectados:**
  - `subscriptions/permissions.py` (nuevo)
  - `receipts/views.py`
- **Cambios previstos:**
  1. Crear permiso DRF `HasActiveSubscriptionOrTrial` en `subscriptions/permissions.py`:
     - Retorna `True` si `usuario_tiene_acceso_activo(request.user)`.
     - Caso contrario lanza `PermissionDenied` con detalle explicativo y código `subscription_required`.
  2. En `receipts/views.py`:
     - Agregar `HasActiveSubscriptionOrTrial` a `PendingReceiptListAPIView` y `ReceiptUpdateAPIView`.
     - En `_handle_receipt_file` (Telegram webhook): antes de descargar el archivo y llamar al OCR, verificar `usuario_tiene_acceso_activo(profile.user)`.
     - Si es `False`, no procesar archivo y enviar mensaje informando que el trial finalizó con el link a `/suscripciones/planes/`.
- **Límites:** No modificar la lógica de extracción de comprobantes cuando el acceso esté activo.
- **Pruebas y Verificaciones:** Tests específicos en `receipts/tests.py` simulando solicitudes con usuarios activos y usuarios vencidos.

---

### Tarea T8: Visualización de estado de suscripción y banner de trial en Dashboard Web
- **Objetivo:** Enriquecer el Dashboard de usuario con un badge y banner informativo que muestre con claridad los días restantes de prueba, estado de suscripción y alertas visuales cuando la cuenta esté vencida.
- **Requisitos cubiertos:** `RF-013`, `RN-001`.
- **Criterios de Aceptación:** `CA-003`.
- **Archivos afectados:**
  - `receipts/views.py` (`dashboard_home`)
  - `receipts/templates/receipts/dashboard.html`
- **Cambios previstos:**
  1. En `dashboard_home`: inyectar en el contexto los datos de `obtener_estado_cuenta(request.user)`.
  2. En `receipts/templates/receipts/dashboard.html`:
     - Si está en trial: Badge informativo `"Período de prueba: X días restantes"`.
     - Si tiene suscripción activa: Badge verde `"Suscripción Mensual Activa (Vence: DD/MM/AAAA)"`.
     - Si está vencido: Alerta Bootstrap destacada `"Tu período de prueba ha finalizado. Suscribite para continuar cargando comprobantes"` con botón a `/suscripciones/planes/`.
- **Límites:** Conservar las métricas de KPIs y tabla de comprobantes existentes.
- **Pruebas y Verificaciones:** Comprobar renderizado de textos y alertas según estado del usuario.

---

### Tarea T9: Suite integral de pruebas automatizadas, cobertura >= 80% y verificación de linters
- **Objetivo:** Ejecutar la suite completa de pruebas con `pytest-django`, verificar mocks de MercadoPago, medir cobertura sobre `subscriptions` y `receipts` superando el umbral de 80%, y validar formato y linters con Ruff.
- **Requisitos cubiertos:** Todos los RF y CA (`CA-001` a `CA-007`, `RNF-006`).
- **Criterios de Aceptación:** Verificación exhaustiva de todos los criterios.
- **Archivos afectados:**
  - `subscriptions/tests.py`
  - `receipts/tests.py`
- **Comandos de verificación:**
  - `pytest --cov=subscriptions --cov=receipts --cov-report=term-missing`
  - `ruff check .`
  - `ruff format --check .`
- **Criterio de finalización:** 100% de tests pasando, cobertura >= 80% en módulos críticos y cero errores de linter.
