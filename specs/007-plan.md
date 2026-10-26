# Plan Técnico: Integración de Pasarela de Pagos MercadoPago y Gestión de Suscripciones

- **Identificador de Especificación:** `specs/007-pasarela-mercadopago.md` (`007-pasarela-mercadopago`)
- **Revisión de Especificación Aprobada:** `REV-001` (Aprobada formalmente por el usuario)
- **Estado del Plan:** `PENDIENTE_DE_APROBACION`
- **Fecha:** 2026-10-25

---

## 1. Enfoque Técnico y Arquitectura

El objetivo principal es dotar a **SIRADIG Auto** de un esquema de monetización formal y automatizado mediante una aplicación desacoplada `subscriptions`, basada en el modelo probado de `Monitorea/CORE/SUSCRIPCIONES`. 

El esquema combina:
1. **Período de Prueba (Trial por tiempo)**: 15 días corridos evaluados sobre `UserProfile.trial_start_date` (configurable con `TRIAL_DURATION_DAYS`).
2. **Suscripción Recurrente Automática**: Débito automático mensual o anual en ARS implementado a través de la API **MercadoPago Preapproval** (`/preapproval`).
3. **Control de Acceso Unificado**: Servicio transversal `usuario_tiene_acceso_activo(user)` que bloquea el procesamiento en el Bot de Telegram (`telegram_webhook`), la API REST consumida por la extensión (`/api/receipts/pending/` y actualización), y muestra advertencias/banners en el Dashboard.
4. **Webhook Seguro e Idempotente**: Validación criptográfica HMAC-SHA256 con headers `x-signature` y `x-request-id`, y registro transaccional idempotente mediante `referencia_gateway` única.
5. **Autoservicio de Cancelación**: Revocación de suscripción ante MercadoPago (`PUT /preapproval/{id}` con `{"status": "cancelled"}`) conservando el acceso hasta la fecha de expiración pagada.

---

## 2. Decisiones Técnicas Confirmadas y Justificación

| ID | Decisión | Justificación Técnica |
|---|---|---|
| **ARQ-01** | Nueva app Django `subscriptions` | Modularidad limpia, separación de responsabilidades con `receipts` y facilidad de mantenimiento o sustitución a futuro. |
| **ARQ-02** | Dependencia oficial `mercadopago==2.2.0` | Versión testeada y estable del SDK oficial de MercadoPago para Python 3.11, permitiendo llamadas nativas a preapproval y gestión de endpoints de pago. |
| **ARQ-03** | Servicio de Acceso Centralizado (`subscriptions.services.access`) | Un solo punto de verdad para determinar si un usuario puede usar el bot o la extensión: `usuario_tiene_acceso_activo(user)`. Evita duplicación de lógica de fechas. |
| **ARQ-04** | DRF Permission Class `HasActiveSubscriptionOrTrial` | Permite proteger `PendingReceiptListAPIView` y `ReceiptUpdateAPIView` respondiendo `HTTP 403 Forbidden` (`{"detail": "...", "code": "subscription_required"}`) sin acoplar vistas a la base de datos de pagos. |
| **ARQ-05** | Validación HMAC-SHA256 en Webhooks | Cumplimiento estricto de seguridad para mitigar ataques man-in-the-middle y replay attacks. Extrae `ts` y `v1` de `x-signature`, genera digest con `MERCADOPAGO_WEBHOOK_SECRET` y valida con `hmac.compare_digest`. |
| **ARQ-06** | Idempotencia en Pagos | `Pago.referencia_gateway` con restricción de unicidad (`unique=True`). Uso de `transaction.atomic()` y `select_for_update()` para evitar dobles acreditaciones ante reintentos de MercadoPago. |

---

## 3. Componentes Afectados y Estructura Propuesta

### 3.1 Nueva App: `subscriptions`

```text
subscriptions/
├── __init__.py
├── admin.py                  # Administración de Plan, Suscripcion y Pago
├── apps.py                   # AppConfig con name='subscriptions'
├── models.py                 # Plan, Suscripcion, Pago
├── urls.py                   # /suscripciones/...
├── views.py                  # PlanesView, SuscribirView, WebhookView, CancelarView, Retornos
├── forms.py                  # Formulario o confirmación de cancelación
├── permissions.py            # HasActiveSubscriptionOrTrial (para DRF)
├── services/
│   ├── __init__.py
│   ├── access.py             # usuario_tiene_acceso_activo, dias_restantes_trial, estado_cuenta
│   ├── mercadopago.py        # Wrapper SDK MP (crear preapproval, cancelar preapproval, consultar pago)
│   └── webhook.py            # Verificación de firma HMAC y lógica de procesamiento de eventos
└── templates/
    └── subscriptions/
        ├── planes.html       # Selector de planes mensual / anual
        ├── pago_exitoso.html # Retorno exitoso / pendiente de acreditación
        ├── pago_fallido.html # Retorno tras rechazo
        └── cancelar.html     # Confirmación de cancelación
```

### 3.2 Modelos de Datos (`subscriptions/models.py`)

1. **`Plan`**:
   - `nombre`: CharField(max_length=50, unique=True) — valores (`gratuito`, `mensual`, `anual`).
   - `precio_mensual`: DecimalField(max_digits=10, decimal_places=2, default=0).
   - `descripcion`: TextField(blank=True).
   - `dias_duracion`: PositiveIntegerField(default=30).

2. **`Suscripcion`**:
   - `usuario`: OneToOneField(`settings.AUTH_USER_MODEL`, on_delete=models.CASCADE, related_name='suscripcion').
   - `plan`: ForeignKey(`Plan`, on_delete=models.PROTECT).
   - `estado`: CharField(max_length=20, choices=[('activa', 'Activa'), ('vencida', 'Vencida'), ('cancelada', 'Cancelada'), ('trial', 'Prueba')]).
   - `fecha_inicio`: DateTimeField(auto_now_add=True).
   - `fecha_vencimiento`: DateTimeField().
   - `gateway_subscription_id`: CharField(max_length=100, blank=True, null=True, db_index=True).
   - `codigo_cancelacion`: CharField(max_length=6, blank=True, null=True).

3. **`Pago`**:
   - `suscripcion`: ForeignKey(`Suscripcion`, on_delete=models.CASCADE, related_name='pagos').
   - `monto`: DecimalField(max_digits=10, decimal_places=2).
   - `fecha`: DateTimeField(auto_now_add=True).
   - `metodo`: CharField(max_length=50, default='mercadopago').
   - `referencia_gateway`: CharField(max_length=200, unique=True).
   - `exitoso`: BooleanField(default=True).

### 3.3 Integración en `receipts` y `core`

1. **`core/settings.py`**:
   - Agregar `'subscriptions'` a `INSTALLED_APPS`.
   - Variables de entorno:
     ```python
     MERCADOPAGO_ACCESS_TOKEN = env("MERCADOPAGO_ACCESS_TOKEN", default="")
     MERCADOPAGO_PUBLIC_KEY = env("MERCADOPAGO_PUBLIC_KEY", default="")
     MERCADOPAGO_WEBHOOK_SECRET = env("MERCADOPAGO_WEBHOOK_SECRET", default="")
     MERCADOPAGO_BACK_URL = env("MERCADOPAGO_BACK_URL", default="http://localhost:8000")
     PRECIO_MENSUAL = env.decimal("PRECIO_MENSUAL", default="15000.00")
     TRIAL_DURATION_DAYS = env.int("TRIAL_DURATION_DAYS", default=15)
     ```
2. **`core/urls.py`**:
   - Registrar `path("suscripciones/", include("subscriptions.urls"))`.
3. **`receipts/views.py` (`telegram_webhook` y `_handle_receipt_file`)**:
   - Al recibir archivo/foto, invocar `usuario_tiene_acceso_activo(profile.user)`.
   - Si retorna `False`, no descargar archivo, no llamar a OCR, y responder con mensaje de bloqueo y enlace a planes.
4. **`receipts/views.py` (`PendingReceiptListAPIView` y `ReceiptUpdateAPIView`)**:
   - Añadir `permission_classes = [permissions.IsAuthenticated, HasActiveSubscriptionOrTrial]`.
5. **`receipts/templates/receipts/dashboard.html` & `dashboard_home`**:
   - Proveer datos de estado de suscripción (`dias_trial_restantes`, `estado_suscripcion`, `suscripcion_activa`).
   - Mostrar banner informativo en Bootstrap:
     - Trial activo: Badge informativo con días restantes.
     - Suscripción activa: Badge verde con vencimiento.
     - Vencido: Banner de alerta con botón destacado hacia `/suscripciones/planes/`.

---

## 4. Dependencias Propuestas y Compatibilidad

- **`mercadopago==2.2.0`**:
  - Compatible con Python 3.11 y Django 5.x/6.x.
  - SDK ligero basado en `requests` que implementa la capa de comunicación y firma para APIs V1 y V2 de MercadoPago.
- Se agregará formalmente a `siradig_auto/requirements.txt` en la tarea correspondiente.

---

## 5. Seguridad, Webhooks e Idempotencia

### 5.1 Verificación de Firma HMAC-SHA256 (`subscriptions/services/webhook.py`)
MercadoPago envía el encabezado `x-signature` con formato: `ts=<timestamp>,v1=<hash_hex>` y `x-request-id: <uuid>`.
1. Si `MERCADOPAGO_WEBHOOK_SECRET` está configurado:
   - Se parsea `ts` y `v1` de `x-signature`.
   - Se obtiene el `data_id` de la query string o payload.
   - Se crea el manifest de validación: `id:{data_id};request-id:{x_request_id};ts:{ts};`.
   - Se computa `hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()`.
   - Se valida con `hmac.compare_digest(hash_calculado, v1)`.
   - Si no coincide o falta la firma: retornar `HttpResponse(status=401)`.
2. Si `MERCADOPAGO_WEBHOOK_SECRET` no está configurado (solo en entorno local/test): registrar advertencia en logs y permitir procesamiento si `DEBUG=True`.

### 5.2 Idempotencia y Transaccionalidad
1. Los eventos recibidos (`payment`, `subscription_authorized_payment`, `preapproval`) contienen un `id` único.
2. Cada pago se registra con `Pago.objects.get_or_create(referencia_gateway=str(resource_id), defaults=...)`.
3. Si el pago ya existía (`created == False`), el webhook responde `HTTP 200` de inmediato sin alterar fechas de vencimiento.
4. Si es nuevo, dentro de `transaction.atomic()` se actualiza la `Suscripcion` del usuario correspondiente (obtenido vía `external_reference = "<user_id>:<tipo>"`) extendiendo el vencimiento en +30 o +365 días.

---

## 6. Estrategia de Pruebas y Cobertura

- Se utilizará `pytest-django`.
- **Mocks estrictos de MercadoPago**: Se implementarán fixtures y mocks para `mercadopago.SDK` (o `requests.post`/`requests.put`) para evitar llamadas HTTP externas en CI y tests locales.
- **Suite de Pruebas**:
  1. `subscriptions/tests.py`:
     - Test unitarios de modelos (`Plan`, `Suscripcion`, `Pago`).
     - Test del servicio `access.py` (cálculo de trial, días restantes, prioridad de suscripción activa).
     - Test de verificación de firma HMAC en `webhook.py` (firmas válidas, inválidas, ausentes).
     - Test del endpoint de webhook (idempotencia ante reintentos, extensión de vigencia).
     - Test de vista de checkout y redirección al `init_point`.
     - Test de flujo de cancelación y llamada mockeada a MercadoPago.
  2. `receipts/tests.py` (actualización de integración):
     - Test de `telegram_webhook` con usuario en trial activo (procesa OCR normal).
     - Test de `telegram_webhook` con usuario en trial vencido (bloquea OCR y responde mensaje de suscripción).
     - Test de `PendingReceiptListAPIView` con trial vencido (retorna HTTP 403 Forbidden con código `subscription_required`).
     - Test de `dashboard_home` con contexto de trial y suscripción.
- **Cobertura**: Medición con `pytest --cov=subscriptions --cov=receipts` garantizando que las rutas críticas (`subscriptions.services`, `subscriptions.views`, `receipts.views`) alcancen o superen el umbral constitucional del 80%.

---

## 7. Plan de Rollback y Riesgos

- **Riesgo:** Webhook de MercadoPago no accesible en desarrollo local sin túnel.
  - *Mitigación:* Configuración de `MERCADOPAGO_BACK_URL` y soporte de mocks para tests automatizados.
- **Riesgo:** Usuario sin `trial_start_date` previo.
  - *Mitigación:* La migración y la señal `post_save` garantizan que `UserProfile.trial_start_date` tenga un valor válido (por defecto `auto_now_add=True`).
