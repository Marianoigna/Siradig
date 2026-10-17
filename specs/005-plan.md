# Plan Técnico: Sistema de Autenticación Unificado y Landing Page Pública

- **Identificador de Especificación:** `specs/005-autenticacion-y-landing.md` (`005-autenticacion-y-landing`)
- **Revisión de Especificación Aprobada:** `REV-001` (Aprobada formalmente por el usuario)
- **Estado del Plan:** `PENDIENTE_DE_APROBACION`
- **Fecha:** 2026-10-17

---

## 1. Enfoque Técnico y Arquitectura

El objetivo del incremento es transformar el acceso a **SIRADIG Auto**, pasando de una redirección directa y acceso administrativo a una plataforma web autoservicio compuesta por:
1. Una **Landing Page pública** (`/`) que comunica la propuesta de valor y el principio de seguridad ("cero credenciales AFIP/ARCA").
2. Un sistema de **autenticación híbrida** (Email/Contraseña local + Google OAuth 2.0) basado en `django-allauth`.
3. Flujo completo de **recuperación de contraseñas** por correo electrónico seguro (backend `console.EmailBackend` en local y SMTP genérico configurable en producción).
4. Preservación automática de las señales de aprovisionamiento de perfil (`UserProfile` + token DRF en `receipts/signals.py`).

### 1.1 Decisiones Técnicas Confirmadas
- **Motor de Autenticación:** `django-allauth` (aplicación madura ya integrada parcialmente en `INSTALLED_APPS`).
- **Email Verification:** `'optional'` o `'none'` para el MVP (sin bloqueo ni fricción para el primer login; se preserva el correo para login y reseteo).
- **Backend de Correo:** Configurado con `EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')` y soporte para variables SMTP estándar (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`).
- **Estilo UI:** Bootstrap 5.3 + Bootstrap Icons vía CDN en base limpia, garantizando responsividad, consistencia con el dashboard y cero dependencias pesadas de JS de build.

---

## 2. Componentes Afectados y Cambios Previstos

### 2.1 Dependencias (`siradig_auto/requirements.txt`)
- **Pinning de `django-allauth`:**
  - Versión actual: `django-allauth` (sin versión fija, incumple el Principio #1 de la Constitución).
  - Versión propuesta fijada: `django-allauth==65.4.1` (o la versión exacta probada en el entorno Python 3.11/Django 6.1).
- **Dependencias de test y cobertura:**
  - `pytest-django`, `pytest-cov`, `ruff`, `black` (ya contempladas en `pyproject.toml`).

### 2.2 Configuración del Proyecto (`core/settings.py`)
- **Directorio de Templates:**
  - Actualizar `TEMPLATES[0]['DIRS'] = [BASE_DIR / 'templates']` para permitir sobreescribir templates de `allauth` (`templates/account/`) y ubicar la landing page (`templates/landing.html`).
- **Ajustes de `django-allauth`:**
  - `ACCOUNT_AUTHENTICATION_METHOD = 'email'` (permite iniciar sesión con correo electrónico).
  - `ACCOUNT_EMAIL_REQUIRED = True` (el correo es obligatorio).
  - `ACCOUNT_UNIQUE_EMAIL = True` (no se admiten cuentas duplicadas con el mismo correo).
  - `ACCOUNT_USERNAME_REQUIRED = False` (el usuario no requiere memorizar un username separado).
  - `ACCOUNT_EMAIL_VERIFICATION = 'none'` (MVP sin fricción, confirmado por el usuario).
  - `LOGIN_REDIRECT_URL = '/dashboard/'` (post-login).
  - `ACCOUNT_LOGOUT_REDIRECT_URL = '/'` (post-logout hacia la landing pública).
  - `ACCOUNT_LOGOUT_ON_GET = True` (o soporte para logout vía POST con CSRF).
  - `PASSWORD_RESET_TIMEOUT = 86400` (24 horas de validez para el token de reseteo).
- **Variables de Email:**
  - `EMAIL_HOST = env('EMAIL_HOST', default='localhost')`
  - `EMAIL_PORT = env.int('EMAIL_PORT', default=25)`
  - `EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')`
  - `EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')`
  - `EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=False)`
  - `DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='no-reply@siradigauto.com')`

### 2.3 Variables de Entorno (`.env.example`)
- Documentar las variables genéricas de SMTP y OAuth:
  ```env
  EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
  EMAIL_HOST=
  EMAIL_PORT=587
  EMAIL_HOST_USER=
  EMAIL_HOST_PASSWORD=
  EMAIL_USE_TLS=True
  DEFAULT_FROM_EMAIL=SIRADIG Auto <no-reply@siradigauto.com>
  GOOGLE_OAUTH_CLIENT_ID=
  GOOGLE_OAUTH_CLIENT_SECRET=
  ```

### 2.4 Enrutamiento (`core/urls.py` y `receipts/urls.py`)
- **Ruta Raíz (`/`)**:
  - Reemplazar `RedirectView.as_view(url='dashboard/', permanent=False)` por una vista controlada: `landing_page_view`.
  - Comportamiento de `landing_page_view`:
    - Si `request.user.is_authenticated`: Redirección HTTP 302 a `dashboard`.
    - Si `not request.user.is_authenticated`: Renderiza `templates/landing.html` con HTTP 200.
- **Rutas de Cuentas (`/accounts/`)**:
  - Ya gestionadas mediante `include('allauth.urls')`.

### 2.5 Vistas y Señales (`receipts/views.py` y `receipts/signals.py`)
- Agregar la función `landing_page_view(request)` en `receipts/views.py` (o en `core/views.py`).
- Verificar que el decorador `@receiver(post_save, sender=settings.AUTH_USER_MODEL)` en `receipts/signals.py` mantenga su ejecución idempotente tanto para `create_user` estándar como para usuarios creados por los adaptadores de `django-allauth`.

### 2.6 Plantillas y Frontend (`templates/`)
- Crear `templates/base.html` con importación de Bootstrap 5.3 + Bootstrap Icons (CDN), mensajes flash (`django.contrib.messages`) y contenedor principal.
- Crear `templates/landing.html`:
  - Barra de navegación con logo SIRADIG Auto y botones a `/accounts/login/` y `/accounts/signup/`.
  - Hero section destacando la propuesta de valor.
  - Bloque explicativo de 3 pasos: (1) Enviar factura por Telegram, (2) Extracción OCR con Gemini, (3) Inyección en F572 web con la extensión.
  - Disclaimer destacado de seguridad: *"SIRADIG Auto nunca solicita ni almacena tus claves fiscales ni CUIT de AFIP/ARCA; el login se realiza exclusivamente en el sitio oficial"*.
- Crear templates de `allauth` en `templates/account/`:
  - `login.html`: Formulario con email, contraseña, enlace "¿Olvidaste tu contraseña?", botón "Continuar con Google" y enlace a registro.
  - `signup.html`: Formulario con email, contraseña y confirmación, botón Google y enlace a login.
  - `password_reset.html`: Formulario para solicitar enlace indicando correo electrónico.
  - `password_reset_done.html`: Pantalla informativa anti-enumeración.
  - `password_reset_from_key.html`: Formulario para ingresar la nueva contraseña validada.
  - `password_reset_from_key_done.html`: Confirmación de restablecimiento exitoso.

---

## 3. Contratos de Rutas, Vistas y Respuestas

| Ruta | Nombre de URL | Auth Requerida | Método | Respuesta / Redirección |
|---|---|---|---|---|
| `/` | `landing` | Anónimo | GET | HTTP 200 `landing.html` (o 302 a `/dashboard/` si `is_authenticated`) |
| `/dashboard/` | `dashboard` | Requerida | GET | HTTP 200 `receipts/dashboard.html` (o 302 a `/accounts/login/?next=/dashboard/`) |
| `/accounts/login/` | `account_login` | Anónimo | GET, POST | HTTP 200 `login.html`; POST exitoso -> HTTP 302 a `next` o `/dashboard/` |
| `/accounts/signup/` | `account_signup` | Anónimo | GET, POST | HTTP 200 `signup.html`; POST exitoso -> HTTP 302 a `/dashboard/` |
| `/accounts/logout/` | `account_logout` | Requerida | GET, POST | Invalida sesión -> HTTP 302 a `/` |
| `/accounts/password/reset/` | `account_reset_password` | Anónimo | GET, POST | HTTP 200 `password_reset.html`; POST -> HTTP 302 a done |
| `/accounts/password/reset/done/` | `account_reset_password_done` | Anónimo | GET | HTTP 200 `password_reset_done.html` |
| `/accounts/password/reset/key/<uidb64>-<token>/` | `account_reset_password_from_key` | Anónimo | GET, POST | HTTP 200 `password_reset_from_key.html`; POST -> HTTP 302 a key/done |
| `/accounts/password/reset/key/done/` | `account_reset_password_from_key_done` | Anónimo | GET | HTTP 200 `password_reset_from_key_done.html` |
| `/accounts/google/login/` | `google_login` | Anónimo | POST | Redirección 302 a Google Identity OAuth |

---

## 4. Seguridad y Cumplimiento Constitucional

1. **Protección de Credenciales AFIP/ARCA (Mandato #9):**
   - Ni en la landing ni en los formularios de autenticación se definen campos para CUIT o Clave Fiscal.
   - El disclaimer legal y de privacidad estará visible permanentemente en la landing page y en los formularios de registro/login.
2. **Protección CSRF (RNF-AUTH-002):**
   - Todo formulario incluye el token `{% csrf_token %}`.
   - Las pruebas automatizadas verificarán que peticiones POST sin token CSRF sean rechazadas.
3. **Manejo Seguro de Secretos OAuth y SMTP (RNF-AUTH-003, RNF-AUTH-004):**
   - Las variables sensibles residen exclusivamente en `.env` (ignorado en git) y se documentan vacías o con placeholders en `.env.example`.
4. **Anti-Enumeración de Cuentas (RF-AUTH-013):**
   - El formulario de reseteo de contraseña renderiza la misma vista de confirmación (`password_reset_done.html`), indistintamente de si el email está registrado o no.
5. **Validadores de Contraseña (RF-AUTH-006):**
   - Se activan los 4 validadores nativos de Django en `AUTH_PASSWORD_VALIDATORS`.

---

## 5. Estrategia de Pruebas con `pytest-django`

Para cumplir con la Constitución (>80% de cobertura en áreas críticas y verificación de regresiones):
- Se crearán tests organizados en `receipts/tests.py` o módulo `receipts/test_auth.py` utilizando `pytest-django`.

### 5.1 Matriz de Casos de Prueba
1. **Landing y Redirección de Raíz (`CA-AUTH-001`, `CA-AUTH-002`):**
   - Test GET `/` anónimo -> HTTP 200 y contenido de propuesta de valor + disclaimer AFIP.
   - Test GET `/` con usuario autenticado (`client.force_login`) -> HTTP 302 a `/dashboard/`.
2. **Protección de Dashboard (`CA-AUTH-011`):**
   - Test GET `/dashboard/` anónimo -> HTTP 302 a `/accounts/login/?next=/dashboard/`.
3. **Registro Local y Señales (`CA-AUTH-003`, `RF-AUTH-019`):**
   - Test POST `/accounts/signup/` con email y contraseña válidos -> Creación de `User`, creación de `UserProfile`, creación de `Token` DRF, sesión iniciada, HTTP 302 a `/dashboard/`.
   - Test POST `/accounts/signup/` con email duplicado o contraseña débil -> HTTP 200, mensaje de error en formulario, no crea usuario.
4. **Inicio de Sesión y Cierre de Sesión (`CA-AUTH-004`, `CA-AUTH-005`, `CA-AUTH-010`):**
   - Test POST `/accounts/login/` con credenciales válidas -> HTTP 302 a `/dashboard/`.
   - Test POST `/accounts/login/` con contraseña errónea o email inexistente -> HTTP 200, error visible.
   - Test GET/POST `/accounts/logout/` -> HTTP 302 a `/`, usuario desautenticado (`_auth_user_id` no en sesión).
5. **Recuperación de Contraseña (`CA-AUTH-006`, `CA-AUTH-007`, `CA-AUTH-008`):**
   - Test POST `/accounts/password/reset/` con email registrado -> Mensaje en `mail.outbox`, HTTP 302 a done.
   - Test POST `/accounts/password/reset/` con email no registrado -> Cero mensajes en `mail.outbox`, HTTP 302 a done (anti-enumeración).
   - Test de cambio de clave utilizando el token generado en `mail.outbox[0]` -> actualización del password en base de datos.
   - Test con token inválido o manipulado -> Rechazo y visualización de error.
6. **Autenticación Social / Google OAuth Mock (`CA-AUTH-009`):**
   - Mock del callback o adapter de `allauth.socialaccount` simulando login de Google -> Creación de usuario, creación de `UserProfile` y `Token`, redirección a `/dashboard/`.

### 5.2 Verificación de Calidad y Formato
- Ejecución de `ruff check .` y `black --check .` según mandatos constitucionales.
- Cobertura ejecutada mediante `pytest --ds core.settings --cov=receipts --cov=core --cov-report=term-missing`.

---

## 6. Riesgos y Mitigaciones

| Riesgo Técnico | Impacto | Mitigación |
|---|---|---|
| Incompatibilidad de versión de `django-allauth` con Django 6.1 | Errores en imports o templates al arrancar | Pinning explícito a versión verificada (`django-allauth==65.4.1` o compatible) y testeo con `pytest`. |
| Sobreescritura incorrecta de templates de `allauth` | Formularios feos o rotos si Django no encuentra `templates/` | Configurar `TEMPLATES[0]['DIRS'] = [BASE_DIR / 'templates']` en `core/settings.py`. |
| Fallo en la señal `post_save` ante usuarios creados por Social Login | Usuarios sin `UserProfile` o sin Token DRF | Verificar en test que la señal `create_user_profile` no dependa del método de creación. |
| Inyección de credenciales AFIP por confusión de diseño | Violación de la Constitución | Mensajes explícitos en la interfaz y revisión estricta de plantillas. |
