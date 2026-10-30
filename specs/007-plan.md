# Plan Técnico: Integración de Pasarela de Pagos MercadoPago y Gestión de Suscripciones

- **Identificador de Especificación:** `specs/007-pasarela-mercadopago.md` (`007-pasarela-mercadopago`)
- **Revisión de Especificación Aprobada:** `REV-002` (Propuesta actualizada conforme a docs oficiales de Mercado Pago)
- **Estado del Plan:** `PENDIENTE_DE_APROBACION`
- **Fecha:** 2026-10-29

---

## 1. Enfoque Técnico y Arquitectura

El objetivo principal es dotar a **SIRADIG Auto** de un esquema de monetización formal y automatizado mediante una aplicación desacoplada `subscriptions`, alineada estrictamente con la **documentación oficial de Mercado Pago para suscripciones recurrentes** y el modelo conceptual probado de `Monitorea/CORE/SUSCRIPCIONES`.

El esquema combina:
1. **Período de Prueba (Trial por tiempo)**: 15 días corridos evaluados sobre `UserProfile.trial_start_date` (configurable con `TRIAL_DURATION_DAYS`).
2. **Definición y Aprovisionamiento del Plan de Suscripción en Mercado Pago**:
   - Tarifa oficial mensual de **$8.999 ARS** (`8999.00`).
   - Modelo `Plan` con `gateway_plan_id` (`preapproval_plan_id`).
   - Comando de gestión Django (`ensure_mercadopago_plan`) que invoca `POST /preapproval_plan` con `reason="SIRADIG Auto - Plan Mensual"`, `auto_recurring`: `frequency: 1`, `frequency_type: "months"`, `transaction_amount: 8999.00`, `currency_id: "ARS"`, y `back_url`.
3. **Flujo de Suscripción y Checkout Recurrente (Preapproval)**:
   - Creación de la suscripción vía API de Mercado Pago (`POST /preapproval`) asociando el plan o recurrencia directa mensual por $8.999 ARS con `external_reference="<user_id>:mensual"`, obteniendo el `init_point` seguro para la redirección del pagador.
4. **Control de Acceso Unificado**: Servicio transversal `usuario_tiene_acceso_activo(user)` que bloquea el procesamiento en el Bot de Telegram (`telegram_webhook`), la API REST consumida por la extensión (`/api/receipts/pending/` y actualización con HTTP 403 Forbidden `subscription_required`), y muestra advertencias/banners en el Dashboard.
5. **Webhook Canónico Oficial e Idempotente**:
   - Suscripción y recepción de tópicos oficiales de Mercado Pago: `subscription_preapproval`, `subscription_authorized_payment`, `subscription_preapproval_plan` y `payment`.
   - Validación criptográfica HMAC-SHA256 según estándar oficial de Mercado Pago: extracción de `ts` y `v1` desde `x-signature`, `x-request-id`, y digest sobre el manifest `id:[data.id];request-id:[x-request-id];ts:[ts];`.
   - Registro transaccional idempotente mediante `referencia_gateway` única (`Pago.referencia_gateway`) dentro de `transaction.atomic()`.
6. **Autoservicio de Cancelación**: Revocación de suscripción ante Mercado Pago (`PUT /preapproval/{id}` con `{"status": "cancelled"}`) conservando el acceso hasta la fecha de expiración pagada.

---

## 2. Decisiones Técnicas Confirmadas y Justificación

| ID | Decisión | Justificación Técnica |
|---|---|---|
| **ARQ-01** | Nueva app Django `subscriptions` | Modularidad limpia, separación de responsabilidades con `receipts` y facilidad de mantenimiento o sustitución a futuro. |
| **ARQ-02** | Dependencia oficial `mercadopago==2.2.0` (o `2.3.0`) | Versión testeada y estable del SDK oficial de Mercado Pago para Python 3.11, permitiendo llamadas nativas a preapproval, preapproval_plan y consulta de cobros. |
| **ARQ-03** | Servicio de Acceso Centralizado (`subscriptions.services.access`) | Un solo punto de verdad para determinar si un usuario puede usar el bot o la extensión: `usuario_tiene_acceso_activo(user)`. Evita duplicación de lógica de fechas. |
| **ARQ-04** | DRF Permission Class `HasActiveSubscriptionOrTrial` | Permite proteger `PendingReceiptListAPIView` y `ReceiptUpdateAPIView` respondiendo `HTTP 403 Forbidden` (`{"detail": "...", "code": "subscription_required"}`) sin acoplar vistas a la base de datos de pagos. |
| **ARQ-05** | Validación HMAC-SHA256 Oficial en Webhooks | Cumplimiento canónico con la documentación de Mercado Pago: template `id:[data.id];request-id:[x-request-id];ts:[ts];` con `MERCADOPAGO_WEBHOOK_SECRET` y `hmac.compare_digest`. |
| **ARQ-06** | Tarifa Mensual Fija: 8.999 ARS | Valor oficial del servicio definido en `$8999.00 ARS/mes`, con fallback configurable en entorno `PRECIO_MENSUAL`. |
| **ARQ-07** | Provisión de Plan vía Management Command | `ensure_mercadopago_plan` asegura la creación del `preapproval_plan` en Mercado Pago de forma determinista y reproducible entre entornos (dev, staging, producción). |
| **ARQ-08** | Idempotencia en Pagos | `Pago.referencia_gateway` con restricción de unicidad (`unique=True`). Uso de `transaction.atomic()` y `select_for_update()` para evitar dobles acreditaciones ante reintentos de Mercado Pago. |

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
├── management/
│   ├── __init__.py
│   └── commands/
│       ├── __init__.py
│       └── ensure_mercadopago_plan.py  # Comando para crear/verificar el preapproval_plan en MP ($8999 ARS)
├── services/
│   ├── __init__.py
│   ├── access.py             # usuario_tiene_acceso_activo, dias_restantes_trial, estado_cuenta
│   ├── mercadopago.py        # Wrapper SDK MP (crear plan, crear preapproval, cancelar preapproval, consultar pago)
│   └── webhook.py            # Verificación de firma HMAC oficial y lógica de procesamiento de eventos
└── templates/
    └── subscriptions/
        ├── planes.html       # Selector de plan mensual ($8.999 ARS)
        ├── pago_exitoso.html # Retorno exitoso / pendiente de acreditación
        ├── pago_fallido.html # Retorno tras rechazo
        └── cancelar.html     # Confirmación de cancelación
```

### 3.2 Modelos de Datos (`subscriptions/models.py`)

1. **`Plan`**:
   - `nombre`: CharField(max_length=50, unique=True) — valores (`gratuito`, `mensual`, `anual`).
   - `precio_mensual`: DecimalField(max_digits=10, decimal_places=2, default=8999.00).
   - `descripcion`: TextField(blank=True).
   - `dias_duracion`: PositiveIntegerField(default=30).
   - `gateway_plan_id`: CharField(max_length=100, blank=True, null=True, help_text="ID del preapproval_plan en Mercado Pago").

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
     MERCADOPAGO_PREAPPROVAL_PLAN_ID = env("MERCADOPAGO_PREAPPROVAL_PLAN_ID", default="")
     PRECIO_MENSUAL = env.decimal("PRECIO_MENSUAL", default="8999.00")
     TRIAL_DURATION_DAYS = env.int("TRIAL_DURATION_DAYS", default=15)
     ```
2. **`core/urls.py`**:
   - Registrar `path("suscripciones/", include("subscriptions.urls"))`.
3. **`receipts/views.py` (`telegram_webhook` y `_handle_receipt_file`)**:
   - Al recibir archivo/foto, invocar `usuario_tiene_acceso_activo(profile.user)`.
   - Si retorna `False`, no descargar archivo, no llamar a OCR, y responder con mensaje amigable informando que el trial finalizó con el link a planes.
4. **`receipts/views.py` (`PendingReceiptListAPIView` y `ReceiptUpdateAPIView`)**:
   - Añadir `permission_classes = [permissions.IsAuthenticated, HasActiveSubscriptionOrTrial]`.
5. **`receipts/templates/receipts/dashboard.html` & `dashboard_home`**:
   - Proveer datos de estado de suscripción (`dias_trial_restantes`, `estado_suscripcion`, `suscripcion_activa`).
   - Mostrar banner informativo en Bootstrap con indicación de estado y acceso directo al plan de $8.999 ARS.

---

## 4. Dependencias Propuestas y Compatibilidad

- **`mercadopago==2.2.0`** (o versión compatible `2.3.0`):
  - Totalmente compatible con Python 3.11 y Django.
  - SDK oficial que implementa clientes para `/preapproval`, `/preapproval_plan` y consulta de entidades asociadas.
- Se agregará fijado en `siradig_auto/requirements.txt`.

---

## 5. Seguridad, Webhooks e Idempotencia

### 5.1 Verificación de Firma HMAC-SHA256 Oficial (`subscriptions/services/webhook.py`)
Conforme a la documentación oficial de Mercado Pago:
1. El header `x-signature` contiene: `ts=<timestamp>,v1=<hash_hex>`.
2. El header `x-request-id` contiene un UUID o identificador de trazabilidad.
3. El ID de la entidad notificada se encuentra en `data.id` (o query param `data.id` / `id`).
4. Si `data.id` contiene mayúsculas, se convierte a minúsculas (`data_id.lower()`).
5. Se arma el template estricto:
   ```text
   id:[data.id_url];request-id:[x-request-id_header];ts:[ts_header];
   ```
6. Con la clave secreta `MERCADOPAGO_WEBHOOK_SECRET`, se genera el hash:
   `hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()`.
7. Se compara de forma constante con `hmac.compare_digest(hash_calculado, v1)`.
8. Si no coincide: `HttpResponse(status=401)`.
9. Si no está configurado el secreto en entorno local/test: registrar advertencia y admitir solo si `DEBUG=True`.

### 5.2 Idempotencia y Transaccionalidad
1. Los tópicos oficiales recibidos (`subscription_authorized_payment`, `subscription_preapproval`, `payment`) informan la transacción.
2. Cada cobro se asocia a su ID único de Mercado Pago (`data.id` / `resource_id`).
3. Se ejecuta `Pago.objects.get_or_create(referencia_gateway=str(resource_id), defaults=...)`.
4. Si ya existía (`created == False`), el webhook responde `HTTP 200` de inmediato sin volver a modificar fechas ni duplicar pagos.
5. Si es nuevo y con estado `approved`, dentro de `transaction.atomic()` se actualiza la `Suscripcion` extendiendo la fecha de vencimiento +30 días a partir del vencimiento actual (o desde `now()` si estaba vencida).

---

## 6. Comando de Provisión del Plan: `ensure_mercadopago_plan`

Para evitar configuración manual propensa a errores en el panel de Mercado Pago:
1. Comando Django: `python manage.py ensure_mercadopago_plan`.
2. Flujo:
   - Verifica si el plan mensual en base de datos ya tiene un `gateway_plan_id`.
   - Si no lo tiene, o si se invoca con `--force`:
     - Invoca la API de MP `POST /preapproval_plan`:
       ```json
       {
         "reason": "SIRADIG Auto - Plan Mensual",
         "auto_recurring": {
           "frequency": 1,
           "frequency_type": "months",
           "transaction_amount": 8999.00,
           "currency_id": "ARS"
         },
         "back_url": "https://siradig.onrender.com/suscripciones/pago-exitoso/"
       }
       ```
     - Recupera el `id` retornado (`preapproval_plan_id`) y lo guarda en `Plan.gateway_plan_id`.
3. Esto garantiza que todos los entornos queden sincronizados con la tarifa de 8.999 ARS.

---

## 7. Estrategia de Pruebas y Cobertura

- **Framework**: `pytest-django`.
- **Mocks estrictos de Mercado Pago**: Fixtures de tests que simulan las respuestas de `POST /preapproval_plan`, `POST /preapproval`, `PUT /preapproval/{id}` y los webhooks oficiales con encabezados `x-signature` válidos e inválidos.
- **Suite de Pruebas**:
  1. `subscriptions/tests.py`:
     - Test unitario de modelos (`Plan` con precio $8999, `Suscripcion`, `Pago`).
     - Test del servicio `access.py` (trial de 15 días, días restantes, prioridad de suscripción activa).
     - Test de verificación de firma HMAC oficial en `webhook.py` (según plantilla canónica de MP).
     - Test del endpoint de webhook (idempotencia ante reintentos, extensión de vigencia para $8999 ARS).
     - Test de vista de checkout y redirección al `init_point`.
     - Test de comando `ensure_mercadopago_plan`.
     - Test de flujo de cancelación y llamada mockeada a Mercado Pago.
  2. `receipts/tests.py`:
     - Test de `telegram_webhook` con usuario en trial activo vs. vencido (bloqueo amigable con enlace a planes).
     - Test de `PendingReceiptListAPIView` con trial vencido (retorna HTTP 403 Forbidden con código `subscription_required`).
     - Test de `dashboard_home` con contexto de trial y suscripción.
- **Cobertura**: Medición con `pytest --cov=subscriptions --cov=receipts` garantizando que las rutas críticas alcancen o superen el umbral constitucional del 80%.

---

## 8. Plan de Rollback y Riesgos

- **Riesgo:** Webhook de Mercado Pago no accesible en desarrollo local sin túnel.
  - *Mitigación:* Configuración de `MERCADOPAGO_BACK_URL` y soporte de mocks para tests automatizados.
- **Riesgo:** Usuario sin `trial_start_date` previo.
  - *Mitigación:* `UserProfile.trial_start_date` garantizado por señal `post_save` con valor por defecto.

