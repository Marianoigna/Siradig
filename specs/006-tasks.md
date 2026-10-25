# Tareas Técnicas: Rediseño del Dashboard, Avisos Legales y Páginas de Términos / Privacidad

- **Identificador de Especificación:** `specs/006-dashboard-rediseño-y-legales.md` (`006-dashboard-rediseño-y-legales`)
- **Revisión de Especificación Aprobada:** `REV-001`
- **Plan Técnico:** `specs/006-plan.md`
- **Estado de las Tareas:** `PENDIENTE_DE_APROBACION`
- **Fecha:** 2026-10-25

---

## Matriz de Tareas

| ID | Tarea | Requisitos Cubiertos | Archivos Principales | Dependencias |
|---|---|---|---|---|
| **T1** | Páginas legales públicas (`/terminos/` y `/privacidad/`) y enlaces en footer | RF-LEG-001, RF-LEG-002, RF-LEG-003, RF-LEG-007, RN-001, RN-002 | `receipts/urls.py`, `templates/legal/terminos.html`, `templates/legal/privacidad.html`, `templates/base.html` | Ninguna |
| **T2** | Formulario de registro con checkbox obligatorio y avisos legales en autenticación | RF-LEG-004, RF-LEG-005, RF-LEG-006, RN-003 | `receipts/forms.py`, `core/settings.py`, `templates/account/signup.html`, `templates/account/login.html` | T1 |
| **T3** | Rediseño integral de la plantilla del Dashboard con Bootstrap 5.3, KPIs y badges | RF-DSH-001, RF-DSH-002, RF-DSH-003, RF-DSH-004, RF-DSH-006, RF-DSH-007, RN-004, RN-005 | `receipts/templates/receipts/dashboard.html`, `receipts/views.py` | T1 |
| **T4** | Copiado interactivo de Token al portapapeles y verificación de Logout | RF-DSH-005, RF-DSH-008, RNF-DSH-004 | `receipts/templates/receipts/dashboard.html`, `core/settings.py` | T3 |
| **T5** | Suite integral de pruebas automatizadas con pytest-django y linters | Todos los RF y CA (CA-LEG-001..005, CA-DSH-001..006) | `receipts/tests.py` | T1, T2, T3, T4 |

---

## Detalle de Tareas

### Tarea T1: Páginas legales públicas (`/terminos/` y `/privacidad/`) y enlaces en footer
- **Objetivo:** Exponer las rutas públicas `/terminos/` y `/privacidad/` mediante `TemplateView`, creando sus plantillas con los textos oficiales acordados (deslinde de credenciales AFIP, contacto `marianoignaszewski@gmail.com`), e incorporar sus enlaces en el footer de `base.html`.
- **Requisitos cubiertos:** `RF-LEG-001`, `RF-LEG-002`, `RF-LEG-003`, `RF-LEG-007`, `RN-001`, `RN-002`.
- **Criterios de Aceptación:** `CA-LEG-001`, `CA-LEG-002`, `CA-LEG-005`.
- **Archivos afectados:**
  - `receipts/urls.py`
  - `templates/legal/terminos.html` (nuevo)
  - `templates/legal/privacidad.html` (nuevo)
  - `templates/base.html`
- **Cambios previstos:**
  1. En `receipts/urls.py`, agregar rutas:
     - `path("terminos/", TemplateView.as_view(template_name="legal/terminos.html"), name="terminos")`
     - `path("privacidad/", TemplateView.as_view(template_name="legal/privacidad.html"), name="privacidad")`
  2. Crear `templates/legal/terminos.html` extendiendo de `base.html`, detallando:
     - Finalidad de asistencia en deducciones F572.
     - Deslinde de responsabilidad tributaria frente a AFIP/ARCA.
     - Aclaración expresa de que no se almacenan contraseñas ni claves fiscales de AFIP/ARCA.
     - Canal de contacto y soporte: `marianoignaszewski@gmail.com`.
  3. Crear `templates/legal/privacidad.html` extendiendo de `base.html`, detallando:
     - Responsable del tratamiento y casilla `marianoignaszewski@gmail.com`.
     - Datos recolectados (email, fotos, CUIT y montos de comprobantes).
     - Procesamiento OCR mediante Google Gemini API sin uso de datos para entrenamiento de modelos públicos.
     - Mecanismo para solicitar rectificación y baja/supresión de datos.
  4. En `templates/base.html`, agregar en el `<footer>` los enlaces directos a `{% url 'terminos' %}` y `{% url 'privacidad' %}`.
- **Límites:** No modificar modelos ni agregar dependencias.
- **Pruebas y Verificaciones que añadirá/ejecutará el implementer:**
  - GET `/terminos/` responde HTTP 200 y contiene "marianoignaszewski@gmail.com" y deslinde de claves AFIP.
  - GET `/privacidad/` responde HTTP 200 y contiene "marianoignaszewski@gmail.com" y mención a Gemini OCR.
  - GET `/` responde HTTP 200 y contiene enlaces a `/terminos/` y `/privacidad/` en el HTML.
- **Criterio de finalización:** Ambas rutas responden HTTP 200 con contenido legal completo y el footer enlaza a ambas.

---

### Tarea T2: Formulario de registro con checkbox obligatorio y avisos legales en autenticación
- **Objetivo:** Forzar la aceptación obligatoria de los Términos y Condiciones y la Política de Privacidad en el formulario de registro (`/accounts/signup/`), agregar enlaces informativos en login y la cláusula legal requerida bajo el botón de Google OAuth.
- **Requisitos cubiertos:** `RF-LEG-004`, `RF-LEG-005`, `RF-LEG-006`, `RN-003`.
- **Criterios de Aceptación:** `CA-LEG-003`, `CA-LEG-004`.
- **Archivos afectados:**
  - `receipts/forms.py` (nuevo)
  - `core/settings.py`
  - `templates/account/signup.html`
  - `templates/account/login.html`
- **Cambios previstos:**
  1. Crear `receipts/forms.py` con `LegalSignupForm(SignupForm)` de `allauth.account.forms`:
     - Campo `terminos_y_privacidad = forms.BooleanField(required=True, label="Acepto los Términos y Condiciones y la Política de Privacidad", error_messages={'required': 'Debes aceptar los Términos y Condiciones y la Política de Privacidad para registrarte.'})`.
     - Método `save(request)` delegando en `super().save(request)`.
  2. En `core/settings.py`, configurar `ACCOUNT_FORMS = {"signup": "receipts.forms.LegalSignupForm"}`.
  3. En `templates/account/signup.html`:
     - Renderizar el checkbox de `terminos_y_privacidad` con hipervínculos funcionales a `{% url 'terminos' %}` y `{% url 'privacidad' %}` con `target="_blank"`.
     - Mostrar error de validación cuando el campo no se marque.
     - Debajo del botón de Google OAuth, agregar el texto explícito: *"Al continuar con Google aceptas los Términos y la Política de Privacidad"* con los enlaces respectivos.
  4. En `templates/account/login.html`:
     - Al pie del formulario de login tradicional, agregar enlace informativo a los términos y privacidad.
     - Debajo del botón de Google OAuth, agregar el texto explícito: *"Al continuar con Google aceptas los Términos y la Política de Privacidad"*.
- **Límites:** No romper la creación automática de `UserProfile` y `Token` DRF garantizada por la señal `post_save`.
- **Pruebas y Verificaciones que añadirá/ejecutará el implementer:**
  - POST `/accounts/signup/` con credenciales válidas pero checkbox desmarcado -> HTTP 200, no crea usuario en BD, formulario con error de validación.
  - POST `/accounts/signup/` con credenciales válidas y checkbox marcado -> HTTP 302 a `/dashboard/`, usuario creado con perfil y token.
  - Comprobar presencia del texto de Google OAuth en `signup.html` y `login.html`.
- **Criterio de finalización:** Registro bloqueado si no se aceptan los términos y textos informativos presentes en templates de autenticación.

---

### Tarea T3: Rediseño integral de la plantilla del Dashboard con Bootstrap 5.3, KPIs y badges
- **Objetivo:** Transformar `receipts/templates/receipts/dashboard.html` en un panel de control moderno que herede de `base.html`, con 4 tarjetas de métricas (KPIs), botones destacados de acción (Telegram, portal oficial AFIP), tabla responsiva con badges coloreados por estado y estado vacío amigable.
- **Requisitos cubiertos:** `RF-DSH-001`, `RF-DSH-002`, `RF-DSH-003`, `RF-DSH-004`, `RF-DSH-006`, `RF-DSH-007`, `RN-004`, `RN-005`.
- **Criterios de Aceptación:** `CA-DSH-001`, `CA-DSH-003`, `CA-DSH-004`, `CA-DSH-005`.
- **Archivos afectados:**
  - `receipts/templates/receipts/dashboard.html`
  - `receipts/views.py` (verificación/optimización de contexto si corresponde)
- **Cambios previstos:**
  1. Reemplazar la estructura legacy de `receipts/templates/receipts/dashboard.html` por:
     - `{% extends "base.html" %}`
     - Encabezado con bienvenida y acciones rápidas.
     - 4 Tarjetas KPI:
       - Pendientes de carga (`{{ pendientes }}`).
       - Cargados en SIRADIG (`{{ cargados }}`).
       - Errores de carga (`{{ errores_carga }}`).
       - Total deducible (`${{ total_deducible|floatformat:2 }}`).
     - Botón para vincular Telegram (`{{ telegram_link }}`) con icono `bi-telegram`.
     - Botón para acceder al portal de ARCA/AFIP (`https://auth.afip.gob.ar/contribuyente_/login.xhtml`) con `target="_blank"` y `rel="noopener noreferrer"`.
     - Tabla responsiva dentro de `.table-responsive` (`table table-hover align-middle`):
       - Badges semánticos para `r.estado`:
         - `pendiente_revision` -> `<span class="badge bg-secondary">Pendiente de Revisión</span>`
         - `pendiente_carga` -> `<span class="badge bg-warning text-dark">Pendiente de Carga</span>`
         - `cargado_en_siradig` -> `<span class="badge bg-success">Cargado en SIRADIG</span>`
         - `error_carga` -> `<span class="badge bg-danger">Error de Carga</span>`
     - Bloque para `{% if not receipts %}` con diseño de empty state guiando a vincular Telegram y subir la primera factura.
  2. En `receipts/views.py`: asegurar que el contexto entregue los datos de manera consistente y aislada por usuario (`request.user.receipts`).
- **Límites:** No modificar la máquina de estados de `Receipt` ni alterar los serializadores de DRF.
- **Pruebas y Verificaciones que añadirá/ejecutará el implementer:**
  - Test GET `/dashboard/` renderiza correctamente las 4 tarjetas de KPI con sus conteos.
  - Test GET `/dashboard/` muestra los badges semánticos adecuados según el estado del comprobante.
  - Test GET `/dashboard/` con usuario nuevo sin comprobantes muestra el empty state.
  - Test de aislamiento: comprobantes de otros usuarios no se contabilizan ni se listan.
- **Criterio de finalización:** El dashboard luce la interfaz moderna de Bootstrap 5.3 con KPIs, enlaces a Telegram/AFIP y tabla con badges.

---

### Tarea T4: Copiado interactivo de Token al portapapeles y verificación de Logout
- **Objetivo:** Incorporar en la sección de la extensión del dashboard un botón interactivo para copiar el Token API al portapapeles con feedback visual temporal ("¡Copiado!"), garantizando compatibilidad entre navegadores, y verificar que el cierre de sesión redirija consistentemente a `/`.
- **Requisitos cubiertos:** `RF-DSH-005`, `RF-DSH-008`, `RNF-DSH-004`.
- **Criterios de Aceptación:** `CA-DSH-002`, `CA-DSH-006`.
- **Archivos afectados:**
  - `receipts/templates/receipts/dashboard.html`
  - `core/settings.py` (verificación de `LOGOUT_REDIRECT_URL`)
- **Cambios previstos:**
  1. En `receipts/templates/receipts/dashboard.html`:
     - Mostrar el token DRF en un campo o bloque con id `extension-token-input` (o data-attribute).
     - Botón "Copiar Token" (`id="btn-copy-token"`) con icono `bi-clipboard`.
     - Script JS vanilla en `{% block extra_scripts %}`:
       - Escucha el clic en el botón.
       - Invoca `navigator.clipboard.writeText(...)` con fallback a selección y `document.execCommand('copy')`.
       - Cambia temporalmente (2 segundos) el texto e icono a "¡Copiado!" con `bi-check2` y clase `btn-success`.
     - Botón o enlace visible de cierre de sesión apuntando a `{% url 'account_logout' %}` con método POST o link según configuración.
  2. Verificar en `core/settings.py` que `LOGOUT_REDIRECT_URL = "/"` y `ACCOUNT_LOGOUT_REDIRECT_URL = "/"`.
- **Límites:** Cero librerías externas de JS (solo Vanilla JS estándar).
- **Pruebas y Verificaciones que añadirá/ejecutará el implementer:**
  - Test de contenido HTML asegurando la presencia del script/lógica de copiado y el token del usuario.
  - Test de logout verificando redirección HTTP 302 a `/` (landing).
- **Criterio de finalización:** Botón de copiado funcional en el DOM con feedback y logout redirigiendo a la raíz.

---

### Tarea T5: Suite integral de pruebas automatizadas con pytest-django y linters
- **Objetivo:** Consolidar todos los tests de las nuevas características en `receipts/tests.py` (o tests modularizados), verificar que se alcancen y superen los umbrales de cobertura constitucional (>80% en áreas críticas) y que `ruff` y `black` aprueben sin observaciones.
- **Requisitos cubiertos:** Todos los RF y CA (`CA-LEG-001` a `CA-LEG-005`, `CA-DSH-001` a `CA-DSH-006`), `RNF-001` a `RNF-005`.
- **Archivos afectados:**
  - `receipts/tests.py`
- **Comandos de Verificación:**
  - `pytest -v --cov=receipts --cov=core --cov-report=term-missing`
  - `ruff check .`
  - `black --check .`
- **Criterio de finalización:** 100% de los tests pasan, cero regresiones en tests de OCR/Telegram/API, cobertura crítica > 80% y linters limpios.
