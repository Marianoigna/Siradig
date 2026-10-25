# Plan Técnico: Rediseño del Dashboard, Avisos Legales y Páginas de Términos / Privacidad

- **Identificador de Especificación:** `specs/006-dashboard-rediseño-y-legales.md` (`006-dashboard-rediseño-y-legales`)
- **Revisión de Especificación Aprobada:** `REV-001` (Aprobada formalmente por el usuario)
- **Estado del Plan:** `PENDIENTE_DE_APROBACION`
- **Fecha:** 2026-10-25

---

## 1. Enfoque Técnico y Arquitectura

El propósito de este incremento es dotar a SIRADIG Auto de un marco legal explícito y unificado, brindar transparencia y cumplimiento normativo en los flujos de autenticación, y modernizar integralmente el Dashboard de usuario heredando de la plantilla maestra Bootstrap 5.3 (`templates/base.html`).

### 1.1 Decisiones Técnicas Confirmadas
1. **Páginas Legales en Español (`/terminos/` y `/privacidad/`):**
   - Servidas vía `TemplateView.as_view()` desde `receipts/urls.py` (o `core/urls.py`).
   - Plantillas dedicadas `templates/legal/terminos.html` y `templates/legal/privacidad.html` extendiendo de `base.html`.
   - Incluyen explícitamente el correo oficial de contacto `marianoignaszewski@gmail.com` y deslinde respecto de credenciales AFIP/ARCA.
2. **Consentimiento en Autenticación (`django-allauth`):**
   - Creación de un formulario personalizado de registro que hereda de `allauth.account.forms.SignupForm` (ubicado en `receipts/forms.py`), agregando un campo `terminos_y_privacidad = forms.BooleanField(required=True)`.
   - Configuración en `core/settings.py` de `ACCOUNT_FORMS = {'signup': 'receipts.forms.LegalSignupForm'}`.
   - Actualización de `templates/account/signup.html` para renderizar el checkbox de aceptación con hipervínculos funcionales y feedback de validación.
   - Enlaces informativos al pie de `templates/account/login.html`.
   - Cláusula explícita para Google OAuth debajo del botón social tanto en login como en signup: *"Al continuar con Google aceptas los Términos y la Política de Privacidad"*.
3. **Footer Global:**
   - Adición de enlaces directos a `/terminos/` y `/privacidad/` en `templates/base.html`.
4. **Rediseño del Dashboard (`receipts/templates/receipts/dashboard.html`):**
   - Herencia de `base.html` (`{% extends "base.html" %}`).
   - Grid responsive con 4 tarjetas KPI:
     - Pendientes de carga (`badge bg-warning` / alerta).
     - Cargados en SIRADIG (`badge bg-success` / éxito).
     - Con error de carga (`badge bg-danger` / peligro).
     - Total deducible acumulado (formato con filtro `floatformat:2` y prefijo `$`).
   - Botón interactivo para copiar el Token DRF mediante la Web Clipboard API con fallback a `document.execCommand` y feedback visual en botón ("¡Copiado!").
   - Botón CTA directo para abrir el bot de Telegram (`telegram_link`).
   - Botón directo para ingresar al portal de ARCA/AFIP en pestaña nueva (`target="_blank" rel="noopener noreferrer"`).
   - Tabla responsiva (`table-responsive`) con badges por estado y formateo visual de moneda y fecha.
   - Estado vacío (*empty state*) amigable cuando `receipts` esté vacío.
5. **Redirección de Logout:**
   - Confirmar que `LOGOUT_REDIRECT_URL = "/"` y `ACCOUNT_LOGOUT_REDIRECT_URL = "/"` redirigen consistentemente a la landing page.

---

## 2. Componentes Afectados y Cambios Previstos

### 2.1 Enrutamiento (`receipts/urls.py` / `core/urls.py`)
- Agregar rutas para páginas legales:
  - `path("terminos/", TemplateView.as_view(template_name="legal/terminos.html"), name="terminos")`
  - `path("privacidad/", TemplateView.as_view(template_name="legal/privacidad.html"), name="privacidad")`

### 2.2 Configuración del Proyecto (`core/settings.py`)
- Registrar formulario personalizado de signup de `allauth`:
  ```python
  ACCOUNT_FORMS = {
      "signup": "receipts.forms.LegalSignupForm",
  }
  ```
- Mantener intactas las directivas existentes de sesión y redirección:
  - `LOGIN_REDIRECT_URL = "/dashboard/"`
  - `LOGOUT_REDIRECT_URL = "/"`
  - `ACCOUNT_LOGOUT_REDIRECT_URL = "/"`

### 2.3 Formularios (`receipts/forms.py`)
- Crear `receipts/forms.py` con `LegalSignupForm(SignupForm)`:
  - Campo `terminos_y_privacidad = forms.BooleanField(required=True, error_messages={'required': 'Debes aceptar los Términos y Condiciones y la Política de Privacidad para registrarte.'})`.
  - Sobreescribir `save(request)` delegando en `super().save(request)`.

### 2.4 Vistas (`receipts/views.py`)
- Verificar el contexto de `dashboard_home(request)`:
  - `pendientes`: `receipts.filter(estado="pendiente_carga").count()`
  - `cargados`: `receipts.filter(estado="cargado_en_siradig").count()`
  - `errores_carga`: `receipts.filter(estado="error_carga").count()`
  - `total_deducible`: cálculo acumulado de importes.
  - `telegram_link`: enlace profundo de vinculación.
  - Asegurar aislamiento estricto por usuario (`request.user.receipts`).

### 2.5 Plantillas Frontend (`templates/` y `receipts/templates/receipts/`)
1. **`templates/base.html`**:
   - Agregar en el `<footer>` los enlaces a `{% url 'terminos' %}` y `{% url 'privacidad' %}`.
2. **`templates/legal/terminos.html`**:
   - Crear plantilla extendiendo `base.html`.
   - Secciones: Propósito y alcance del servicio, Deslinde explícito de responsabilidad tributaria frente a AFIP/ARCA, Prohibición estricta y deslinde de credenciales de AFIP, Limitación de responsabilidad, Propiedad intelectual, Modificaciones y Canal de soporte y contacto (`marianoignaszewski@gmail.com`).
3. **`templates/legal/privacidad.html`**:
   - Crear plantilla extendiendo `base.html`.
   - Secciones: Responsable del tratamiento (`marianoignaszewski@gmail.com`), Información recolectada (datos de cuenta, imágenes y metadatos de comprobantes), Finalidad del tratamiento, Proveedores terceros y procesamiento OCR (Google Gemini API sin entrenamiento con datos de usuario), Conservación y seguridad de la información, Ejercicio de derechos ARCO (acceso, rectificación y supresión) y Ausencia de cesión de datos a terceros.
4. **`templates/account/signup.html`**:
   - Agregar el campo checkbox de `terminos_y_privacidad` en el formulario con enlaces a `/terminos/` y `/privacidad/` abriendo en pestaña nueva (`target="_blank"`).
   - Renderizar mensaje de error si el campo no fue marcado.
   - Agregar leyenda bajo el botón de Google: *"Al continuar con Google aceptas los Términos y la Política de Privacidad"*, con enlaces correspondientes.
5. **`templates/account/login.html`**:
   - Agregar al pie del formulario enlace informativo a términos y privacidad.
   - Agregar la leyenda bajo el botón de Google OAuth: *"Al continuar con Google aceptas los Términos y la Política de Privacidad"*.
6. **`receipts/templates/receipts/dashboard.html`**:
   - Reemplazar completamente el HTML antiguo. Extender `base.html`.
   - Header con saludo de bienvenida (`{{ request.user.first_name|default:request.user.username }}`) y botón de cierre de sesión accesible.
   - 4 Tarjetas KPI superiores:
     - Pendientes de carga (estilo card borde warning / icono).
     - Cargados en SIRADIG (estilo card borde success / icono).
     - Errores de carga (estilo card borde danger / icono).
     - Total deducible acumulado (formateado en ARS).
   - Card "Extensión del Navegador":
     - Muestra `profile.user.auth_token.key` en un input o badge monoespaciado.
     - Botón "Copiar Token" con evento JS: `navigator.clipboard.writeText(...)` y cambio temporal de texto e icono a "¡Copiado!".
   - Card "Vincular Telegram":
     - Botón CTA prominente con icono de Telegram para abrir `telegram_link`.
   - Card / Botón de Acceso a ARCA / AFIP:
     - Botón para abrir `https://auth.afip.gob.ar/contribuyente_/login.xhtml` en pestaña nueva (`target="_blank"`).
   - Card con Tabla de Comprobantes:
     - Contenedor `.table-responsive`.
     - Columnas: Fecha, Razón Social, Importe, Categoría, Origen, Estado.
     - Badges de Bootstrap para estados:
       - `pendiente_revision` -> `badge bg-secondary`
       - `pendiente_carga` -> `badge bg-warning text-dark`
       - `cargado_en_siradig` -> `badge bg-success`
       - `error_carga` -> `badge bg-danger`
     - Empty state cuando no existan comprobantes: ilustración/icono y texto de invitación a enviar el primer comprobante por Telegram.

---

## 3. Contratos de Rutas, Vistas y Respuestas

| Ruta | Nombre de URL | Auth Requerida | Método | Respuesta / Redirección |
|---|---|---|---|---|
| `/terminos/` | `terminos` | Anónimo / Pública | GET | HTTP 200 `legal/terminos.html` |
| `/privacidad/` | `privacidad` | Anónimo / Pública | GET | HTTP 200 `legal/privacidad.html` |
| `/dashboard/` | `dashboard` | Requerida (`@login_required`) | GET | HTTP 200 `receipts/dashboard.html` (o 302 a login) |
| `/accounts/signup/` | `account_signup` | Anónimo / Pública | GET, POST | GET: HTTP 200 con checkbox. POST sin checkbox: HTTP 200 con error. POST con checkbox: HTTP 302 a `/dashboard/`. |
| `/accounts/login/` | `account_login` | Anónimo / Pública | GET, POST | HTTP 200 con enlaces legales y leyenda Google OAuth. |
| `/accounts/logout/` | `account_logout` | Requerida | POST / GET | Invalida sesión y redirige (HTTP 302) a `/`. |

---

## 4. Seguridad y Cumplimiento Constitucional

1. **Principio Clave de Seguridad (No almacenar credenciales AFIP/ARCA):**
   - Toda la documentación legal (`/terminos/`, `/privacidad/`) y el dashboard refuerzan explícitamente que la app no intermedia credenciales tributarias ni clave fiscal.
2. **Protección CSRF:**
   - Todos los formularios (registro, login, logout) cuentan con token `{% csrf_token %}`.
3. **Aislamiento Multiusuario (RN-004):**
   - El dashboard y sus KPIs operan exclusivamente sobre `request.user.receipts` y `request.user.userprofile`.
4. **Token DRF Seguro:**
   - Se preserva la señal `post_save` que genera tokens DRF únicos por usuario.
5. **Calidad de Código y Linters:**
   - Todo código y plantilla debe pasar validaciones de `ruff` y `black`.

---

## 5. Estrategia de Pruebas con `pytest-django`

Se incorporarán pruebas completas en `receipts/tests.py` o módulo de tests correspondiente cubriendo todos los Criterios de Aceptación:

### 5.1 Matriz de Casos de Prueba
1. **Páginas Legales Públicas (`CA-LEG-001`, `CA-LEG-002`, `CA-LEG-005`):**
   - GET `/terminos/` -> HTTP 200, comprueba presencia de texto de deslinde AFIP y correo `marianoignaszewski@gmail.com`.
   - GET `/privacidad/` -> HTTP 200, comprueba presencia de tratamiento de datos y correo `marianoignaszewski@gmail.com`.
   - GET `/` (landing) y GET `/dashboard/` -> comprueba presencia de enlaces a `/terminos/` y `/privacidad/` en el footer.
2. **Formulario de Registro y Checkbox Obligatorio (`CA-LEG-003`, `CA-LEG-004`):**
   - POST `/accounts/signup/` con email y clave válidos pero `terminos_y_privacidad` ausente o `False`:
     - Retorna HTTP 200 (formulario inválido).
     - No crea usuario en la base de datos.
     - Contiene mensaje de validación de aceptación requerida.
   - POST `/accounts/signup/` con email, clave y `terminos_y_privacidad='on'` (o `True`):
     - Crea usuario, `UserProfile` y `Token` DRF.
     - Retorna HTTP 302 a `/dashboard/`.
   - GET `/accounts/signup/` y GET `/accounts/login/` -> verifica en el HTML la presencia del texto de Google OAuth: *"Al continuar con Google aceptas los Términos y la Política de Privacidad"*.
3. **Dashboard Rediseñado y KPIs (`CA-DSH-001`, `CA-DSH-003`, `CA-DSH-004`, `CA-DSH-005`):**
   - GET `/dashboard/` anónimo -> HTTP 302 a `/accounts/login/?next=/dashboard/`.
   - GET `/dashboard/` con usuario sin comprobantes -> HTTP 200, muestra empty state, métricas en 0 y token DRF.
   - GET `/dashboard/` con usuario con comprobantes (distintos estados: `pendiente_carga`, `cargado_en_siradig`, `error_carga`):
     - Verifica conteos exactos en el HTML (`pendientes`, `cargados`, `errores_carga`).
     - Verifica suma de `total_deducible`.
     - Verifica renderizado de badges semánticos (`badge bg-warning`, `badge bg-success`, `badge bg-danger`).
     - Verifica presencia de enlaces a Telegram (`telegram_link`), portal oficial AFIP y botón de copiado de token.
   - Aislamiento multiusuario: Comprobantes de otro usuario no aparecen en el conteo ni en la tabla.
4. **Cierre de Sesión (`CA-DSH-006`):**
   - POST `/accounts/logout/` -> HTTP 302 hacia `/` (landing page).

### 5.2 Medición de Cobertura de Áreas Críticas
- Cobertura ejecutada mediante:
  `pytest -v --cov=receipts --cov=core --cov-report=term-missing`
- Verificar que las áreas críticas (vistas, formularios, webhook, OCR y API receipts) superen holgadamente el umbral constitucional del 80%.

---

## 6. Riesgos y Mitigaciones

| Riesgo Técnico | Impacto | Mitigación |
|---|---|---|
| Incompatibilidad de `allauth.account.forms.SignupForm` con el flujo de signup | Error en renderizado o falla al registrarse | Extender de `allauth.account.forms.SignupForm` y configurar `ACCOUNT_FORMS = {'signup': '...'}` respetando la documentación de django-allauth. |
| La Clipboard API puede fallar en navegadores sin contexto seguro (HTTP o browsers antiguos) | El botón de copiado no funciona | Implementar degradación progresiva en JS (`navigator.clipboard` con fallback a `document.execCommand('copy')`). |
| Discrepancia en el cálculo de totales si hay montos nulos | Excepción `TypeError` en el template o vista | Asegurar en `dashboard_home` y template el uso de fallbacks (`r.importe_total or 0`). |
| Invasión visual de estilos ajenos a Bootstrap 5.3 | Ruptura de consistencia estética | Utilizar exclusivamente clases de Bootstrap 5.3 ya importadas en `base.html`. |
