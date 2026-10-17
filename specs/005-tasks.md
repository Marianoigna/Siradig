# Tareas Técnicas: Sistema de Autenticación Unificado y Landing Page Pública

- **Identificador de Especificación:** `specs/005-autenticacion-y-landing.md` (`005-autenticacion-y-landing`)
- **Revisión de Especificación Aprobada:** `REV-001`
- **Plan Técnico:** `specs/005-plan.md`
- **Estado de las Tareas:** `PENDIENTE_DE_APROBACION`
- **Fecha:** 2026-10-17

---

## Matriz de Tareas

| ID | Tarea | Requisitos Cubiertos | Archivos Principales | Dependencias |
|---|---|---|---|---|
| **T1** | Pinning de `django-allauth` y configuración de autenticación y correo | RF-AUTH-005, RF-AUTH-006, RNF-AUTH-003, RNF-AUTH-004, RNF-AUTH-005 | `siradig_auto/requirements.txt`, `core/settings.py`, `.env.example` | Ninguna |
| **T2** | Vista y plantilla de Landing Page pública y redirecciones de acceso | RF-AUTH-001, RF-AUTH-002, RF-AUTH-003, RF-AUTH-017 | `core/urls.py`, `receipts/views.py`, `templates/landing.html`, `templates/base.html` | T1 |
| **T3** | Configuración y plantillas de autenticación local (Signup, Login, Logout) y señales | RF-AUTH-004, RF-AUTH-005, RF-AUTH-006, RF-AUTH-007, RF-AUTH-016, RF-AUTH-018, RF-AUTH-019 | `templates/account/login.html`, `templates/account/signup.html`, `receipts/signals.py` | T1, T2 |
| **T4** | Flujo completo y plantillas de recuperación de contraseña | RF-AUTH-011, RF-AUTH-012, RF-AUTH-013, RF-AUTH-014, RF-AUTH-015 | `templates/account/password_reset*.html`, `core/settings.py` | T1, T3 |
| **T5** | Integración de Google OAuth 2.0 y soporte en plantillas de login/registro | RF-AUTH-008, RF-AUTH-009, RF-AUTH-010, RF-AUTH-019 | `core/settings.py`, `templates/account/login.html`, `templates/account/signup.html` | T3 |
| **T6** | Suite integral de pruebas pytest-django y verificación de linters | RNF-AUTH-001..006, Todos los CA (CA-AUTH-001..011) | `receipts/tests.py`, `pyproject.toml` | T1, T2, T3, T4, T5 |

---

## Detalle de Tareas

### Tarea T1: Pinning de dependencias y configuración de Settings y Email
- **Objetivo:** Fijar la versión exacta de `django-allauth` en `siradig_auto/requirements.txt`, ajustar la configuración de autenticación en `core/settings.py` (método de autenticación por email, redirecciones, expiración de tokens, backend y variables de correo) y actualizar `.env.example`.
- **Requisitos cubiertos:** `RF-AUTH-005`, `RF-AUTH-006`, `RNF-AUTH-003`, `RNF-AUTH-004`, `RNF-AUTH-005`.
- **Cambios previstos:**
  - `siradig_auto/requirements.txt`: Fijar `django-allauth==65.4.1` (o compatible fijada).
  - `core/settings.py`:
    - Incorporar `BASE_DIR / 'templates'` en `TEMPLATES[0]['DIRS']`.
    - Definir `ACCOUNT_AUTHENTICATION_METHOD = 'email'`.
    - Definir `ACCOUNT_EMAIL_REQUIRED = True`, `ACCOUNT_UNIQUE_EMAIL = True`, `ACCOUNT_USERNAME_REQUIRED = False`.
    - Definir `ACCOUNT_EMAIL_VERIFICATION = 'none'`.
    - Definir `LOGIN_REDIRECT_URL = '/dashboard/'` y `ACCOUNT_LOGOUT_REDIRECT_URL = '/'`.
    - Configurar variables SMTP para producción con fallbacks limpios para desarrollo (`EMAIL_HOST`, `EMAIL_PORT`, etc.).
  - `.env.example`: Documentar variables de correo y credenciales OAuth de Google.
- **Límites:** No modificar modelos ni eliminar apps de `INSTALLED_APPS`.
- **Pruebas y Verificaciones:**
  - Verificar sintaxis con `python -m py_compile core/settings.py`.
  - Comprobar que Django inicia settings correctamente: `python manage.py check`.

---

### Tarea T2: Vista y plantilla de Landing Page pública y redirecciones de acceso
- **Objetivo:** Implementar la vista y template de la Landing Page en la raíz `/`, permitiendo que usuarios anónimos conozcan SIRADIG Auto y redirigiendo automáticamente a `/dashboard/` a usuarios que ya cuenten con sesión activa.
- **Requisitos cubiertos:** `RF-AUTH-001`, `RF-AUTH-002`, `RF-AUTH-003`, `RF-AUTH-017`.
- **Criterios de Aceptación:** `CA-AUTH-001`, `CA-AUTH-002`, `CA-AUTH-011`.
- **Cambios previstos:**
  - `receipts/views.py`: Crear vista `landing_page_view(request)` que comprueba `request.user.is_authenticated`.
  - `core/urls.py`: Actualizar la ruta raíz `path('', views.landing_page_view, name='landing')`.
  - `templates/base.html`: Crear plantilla base con Bootstrap 5.3 + Bootstrap Icons (CDN), Navbar limpia y bloques `{% block content %}`.
  - `templates/landing.html`: Crear plantilla de aterrizaje con Hero, propuesta de valor (Telegram + OCR Gemini + Extensión F572), declaración estricta de no almacenamiento de credenciales AFIP y CTAs claros a Login y Registro.
- **Pruebas y Verificaciones:**
  - Test GET `/` anónimo -> HTTP 200, comprueba presencia de títulos y texto de seguridad AFIP.
  - Test GET `/` autenticado -> HTTP 302 hacia `/dashboard/`.
  - Test GET `/dashboard/` anónimo -> HTTP 302 hacia `/accounts/login/?next=/dashboard/`.

---

### Tarea T3: Autenticación local (Signup, Login, Logout) y garantía de señales
- **Objetivo:** Diseñar e integrar las plantillas personalizadas de registro, inicio de sesión y cierre de sesión con Bootstrap 5, asegurando que la creación de usuarios aprovisione de inmediato `UserProfile` y `Token` DRF.
- **Requisitos cubiertos:** `RF-AUTH-004`, `RF-AUTH-005`, `RF-AUTH-006`, `RF-AUTH-007`, `RF-AUTH-016`, `RF-AUTH-018`, `RF-AUTH-019`, `RNF-AUTH-001`, `RNF-AUTH-002`.
- **Criterios de Aceptación:** `CA-AUTH-003`, `CA-AUTH-004`, `CA-AUTH-005`, `CA-AUTH-010`.
- **Cambios previstos:**
  - `templates/account/login.html`: Formulario estilizado con campos email/password, CSRF token, feedback de errores, enlace a reseteo y botón a Google.
  - `templates/account/signup.html`: Formulario con email, password y confirmación, CSRF token, validaciones visibles y botón a Google.
  - `templates/account/logout.html`: Confirmación de cierre de sesión (o logout directo por configuración).
  - `receipts/signals.py`: Verificar la robustez de la señal `post_save` vinculada a `settings.AUTH_USER_MODEL`.
- **Pruebas y Verificaciones:**
  - Test POST `/accounts/signup/` exitoso -> HTTP 302 a `/dashboard/`, creación de `User`, `UserProfile` con `telegram_link_token` y `Token` DRF.
  - Test POST `/accounts/signup/` con email repetido o contraseña inválida -> HTTP 200, error visible.
  - Test POST `/accounts/login/` con credenciales válidas -> HTTP 302 a `/dashboard/`.
  - Test POST `/accounts/login/` inválido -> HTTP 200, error genérico.
  - Test logout -> destrucción de sesión y redirección a `/`.

---

### Tarea T4: Flujo completo de recuperación de contraseña
- **Objetivo:** Proveer las plantillas y verificar el flujo seguro de restablecimiento de contraseña vía correo electrónico con tokens de un solo uso y expiración temporal.
- **Requisitos cubiertos:** `RF-AUTH-011`, `RF-AUTH-012`, `RF-AUTH-013`, `RF-AUTH-014`, `RF-AUTH-015`, `RN-AUTH-004`.
- **Criterios de Aceptación:** `CA-AUTH-006`, `CA-AUTH-007`, `CA-AUTH-008`.
- **Cambios previstos:**
  - `templates/account/password_reset.html`: Formulario para solicitar enlace por correo.
  - `templates/account/password_reset_done.html`: Pantalla de confirmación con mensaje uniforme anti-enumeración.
  - `templates/account/password_reset_from_key.html`: Formulario para ingresar la nueva contraseña validada.
  - `templates/account/password_reset_from_key_done.html`: Confirmación de cambio exitoso con enlace a login.
- **Pruebas y Verificaciones:**
  - Test POST `/accounts/password/reset/` con usuario existente -> envío de correo con token, HTTP 302 a done.
  - Test POST `/accounts/password/reset/` con correo inexistente -> misma respuesta (anti-enumeración), cero correos enviados.
  - Test cambio de contraseña con token válido -> hash de contraseña actualizado, acceso permitido con nueva clave.
  - Test cambio con token inválido/expirado -> rechazo y mensaje de error.

---

### Tarea T5: Configuración y templates para Google OAuth 2.0
- **Objetivo:** Habilitar la acción "Continuar con Google" en las pantallas de acceso, permitiendo el registro y login federado con aprovisionamiento automático de `UserProfile` y `Token`.
- **Requisitos cubiertos:** `RF-AUTH-008`, `RF-AUTH-009`, `RF-AUTH-010`, `RF-AUTH-019`, `RN-AUTH-005`.
- **Criterios de Aceptación:** `CA-AUTH-009`.
- **Cambios previstos:**
  - `templates/account/login.html` y `templates/account/signup.html`: Botón de acción con estilo de Google invocando `{% provider_login_url 'google' %}` (o formulario POST correspondiente a la versión de allauth).
  - Pruebas mock con adaptador social de `allauth` para simular la recepción de un login exitoso de Google.
- **Pruebas y Verificaciones:**
  - Test unitario simulando el callback social de Google: verifica que el nuevo usuario es autenticado, que se crea su `UserProfile` y su `Token` de DRF.
  - Test verificando que la vinculación de cuenta social no resetea ni corrompe el `telegram_link_token` existente.

---

### Tarea T6: Suite integral de pruebas pytest-django y verificación de calidad
- **Objetivo:** Consolidar todos los tests de autenticación y landing page en `receipts/tests.py` (o suite de tests modular), verificar el umbral de cobertura (>80%) y ejecutar los linters obligatorios.
- **Requisitos cubiertos:** `RNF-AUTH-001`, `RNF-AUTH-002`, `RNF-AUTH-006`, y todos los `CA-AUTH-001` al `011`.
- **Comandos de Verificación:**
  - `pytest -v --ds core.settings --cov=receipts --cov=core --cov-report=term-missing`
  - `ruff check .`
  - `black --check .`
- **Criterio de finalización:** 100% de los tests de autenticación y landing aprobados, sin regresiones en las pruebas previas (webhook OCR, Telegram y API receipts), cobertura superior al 80% y linters limpios.
