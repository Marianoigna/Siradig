# Especificación: Rediseño del Dashboard, Avisos Legales y Páginas de Términos / Privacidad

- **Identificador:** `006-dashboard-rediseño-y-legales` (SPEC-006)
- **Revisión:** `REV-001`
- **Estado:** `PENDIENTE_DE_APROBACION`
- **Fuente de la petición:** Respuestas y directivas del usuario para Fase 0:
  1. Checkbox en Registro + Enlaces informativos en Login.
  2. Rutas en español: `/terminos/` y `/privacidad/` (TemplateViews sirviendo documentos legales con contacto marianoignaszewski@gmail.com).
  3. Para Google OAuth: Texto legal explícito con enlaces debajo del botón ("Al continuar con Google aceptas los Términos y la Política de Privacidad").
  4. Logout desde el dashboard hacia la landing page (`/`).
  5. Mejora de la apariencia visual del dashboard (`receipts/templates/receipts/dashboard.html`), heredando de `base.html` con Bootstrap 5.3, KPIs/Cards de totales, copiado interactivo de token de la extensión, enlace al bot de Telegram y tabla responsive con badges de estado.
- **Constitución consultada:** `docs/constitution.md` (Revisión vigente: Django 6.1 + Python 3.11, Bootstrap 5.3 CDN, TokenAuthentication en `/api/receipts/`, no almacenar credenciales AFIP/ARCA, categoría exclusiva indumentaria y equipamiento).
- **Aprobación:** Sin aprobación registrada (Entregado al coordinador para presentación y aprobación explícita del usuario).

---

## 1. Problema y Objetivo

### 1.1 Contexto y Problema
En el ciclo de autenticación y landing pública (SPEC-005), se establecieron los flujos de acceso, pero subsisten carencias clave de cumplimiento normativo, transparencia legal y experiencia de usuario (UX):
1. **Ausencia de Términos y Condiciones y Política de Privacidad**: Los usuarios crean cuentas y envían facturas sin un marco legal explícito que defina la responsabilidad del usuario, la confidencialidad, el procesamiento de comprobantes y la exención explícita de relación con AFIP/ARCA.
2. **Falta de consentimiento informado**: El formulario de registro local no cuenta con consentimiento explícito (checkbox de aceptación de términos y privacidad), el formulario de login carece de enlaces de referencia y el flujo de Google OAuth no aclara que el inicio de sesión federado implica la adhesión a dichos términos.
3. **Dashboard legacy no integrado**: La plantilla actual `receipts/templates/receipts/dashboard.html` utiliza HTML básico sin estilos (tablas estándar con borde 1, listas con viñetas sin formateo, sin heredar de `base.html`), lo cual desentona visual y funcionalmente con la estética moderna de Bootstrap 5.3 de la landing y de las pantallas de autenticación.
4. **Fricción operativa en el Dashboard**: El token de la extensión se muestra en texto plano sin mecanismo de copiado con un clic (clipboard API), y la visualización de métricas (KPIs de comprobantes pendientes, cargados, con error y monto deducible) carece de jerarquía visual (Cards / badges).

### 1.2 Objetivo
- Publicar las páginas legales oficiales `/terminos/` y `/privacidad/` con contenido completo, identificando el correo de contacto (`marianoignaszewski@gmail.com`) y enfatizando que el servicio no es oficial de AFIP ni almacena credenciales fiscales.
- Integrar el consentimiento legal en los flujos de registro local (checkbox obligatorio), login tradicional (enlaces informativos) y Google OAuth (aviso explícito bajo el botón).
- Rediseñar integralmente el Dashboard (`receipts/templates/receipts/dashboard.html`) heredando de `base.html` con Bootstrap 5.3 y Bootstrap Icons:
  - KPIs visuales tipo cards para estados y montos acumulados.
  - Botón interactivo de copiado rápido del Token API con feedback visual ("¡Copiado!").
  - Botón/enlace destacado para vincular el bot de Telegram (`https://t.me/...`).
  - Botón de acceso directo al portal de ARCA/AFIP en pestaña nueva.
  - Tabla de comprobantes responsiva, con badges coloreados por estado y montos formateados.
  - Cierre de sesión visible y accesible que redirija a la raíz `/` (landing page).

---

## 2. Alcance

### 2.1 Incluido
- **Páginas Legales Públicas**:
  - Ruta `/terminos/` servida vía `TemplateView` con plantilla `legal/terminos.html` heredando de `base.html`.
  - Ruta `/privacidad/` servida vía `TemplateView` con plantilla `legal/privacidad.html` heredando de `base.html`.
  - Inclusión visible del correo de contacto `marianoignaszewski@gmail.com` para consultas, derechos de acceso y supresión de datos.
  - Enlaces a ambas páginas en el footer global de `base.html`.
- **Integración Legal en Autenticación**:
  - En `account/signup.html`: Checkbox obligatorio de aceptación de "Términos y Condiciones" y "Política de Privacidad" (validado en frontend y backend antes de registrar la cuenta).
  - En `account/login.html`: Enlaces al pie del formulario ("Al ingresar, recordá consultar nuestros Términos y Privacidad").
  - En `account/login.html` y `account/signup.html` (Google OAuth): Texto aclaratorio debajo del botón de Google: *"Al continuar con Google aceptas los Términos y la Política de Privacidad"*, con enlaces que abren en nueva pestaña o conducen a los documentos.
- **Rediseño del Dashboard (`receipts/dashboard.html`)**:
  - Herencia completa de `base.html` (`{% extends "base.html" %}`).
  - Encabezado con saludo al usuario y botón de cerrar sesión (o integrado en la barra de navegación que redirige a `/`).
  - Tarjetas de resumen (KPI Cards) con Bootstrap 5.3:
    1. *Pendientes de carga* (indicador de alerta/amarillo).
    2. *Cargados en SIRADIG* (indicador de éxito/verde).
    3. *Con error de carga* (indicador de peligro/rojo).
    4. *Total deducible acumulado* (formato moneda argentina `$ 1.234,56` o numérico claro).
  - Sección interactiva "Extensión del Navegador":
    - Campo con el Token DRF (o máscara) y botón interactivo *"Copiar Token"* con feedback visual temporal mediante JavaScript estándar.
  - Sección "Vincular Telegram":
    - Botón CTA directo con icono de Telegram para abrir el enlace profundo (`tg://resolve` o `https://t.me/...`).
  - Botón de acceso rápido oficial a ARCA / AFIP (`https://auth.afip.gob.ar/contribuyente_/login.xhtml`, `target="_blank"`).
  - Tabla responsiva de comprobantes (`table table-hover table-striped` en wrapper `.table-responsive`) con badges semánticos según estado (`pendiente_revision`, `pendiente_carga`, `cargado_en_siradig`, `error_carga`).
  - Estado vacío amigable (*empty state*) cuando el usuario aún no posee comprobantes cargados.

### 2.2 Exclusiones Explícitas
- **Almacenamiento de credenciales AFIP**: Prohibición constitucional absoluta. El sistema nunca solicita, procesa ni almacena CUIT ni Clave Fiscal.
- **Firma electrónica o contratos comerciales avanzados**: La aceptación se realiza por consentimiento digital / checkbox web.
- **Categorías adicionales de deducción**: Se mantiene la restricción del MVP exclusiva a *"Gastos de Adquisición de Indumentaria y Equipamiento"*.
- **Paginación del dashboard en servidor**: Para el volumen actual del MVP se renderizan los comprobantes del usuario; la paginación avanzada o filtrado asincrónico por AJAX se reserva para iteraciones posteriores.

---

## 3. Actores y Términos

### 3.1 Actores
- **Visitante Anónimo**: Puede consultar libremente `/terminos/` y `/privacidad/` desde el footer o enlaces de registro/login.
- **Usuario Registrante**: Debe aceptar explícitamente los términos antes de crear su cuenta en `/accounts/signup/`.
- **Usuario Autenticado**: Accede al dashboard `/dashboard/`, consulta sus KPIs, copia su Token API, accede a Telegram y cierra su sesión regresando a `/`.

### 3.2 Términos Clave
- **SIRADIG / F572 web**: Formulario web de AFIP/ARCA para la declaración jurada de deducciones de Ganancias.
- **Token API (DRF)**: Clave de autenticación (`Token.key`) empleada por la extensión de navegador para autenticar contra `/api/receipts/`.
- **Enlace Profundo de Telegram**: URL tipo `https://t.me/<bot_username>?start=<token>` que vincula el chat de Telegram del usuario con su `UserProfile`.

---

## 4. Historias de Usuario

### HU-LEG-001 — Consulta de Términos y Política de Privacidad
**Como** visitante o usuario de SIRADIG Auto,  
**quiero** acceder a páginas dedicadas en `/terminos/` y `/privacidad/`,  
**para** conocer mis derechos, el tratamiento de mis datos de facturación, la exención de responsabilidad fiscal y las vías de contacto con el responsable.

### HU-LEG-002 — Consentimiento Informado en Registro y Acceso Social
**Como** nuevo usuario que crea una cuenta (localmente o con Google OAuth),  
**quiero** ver claramente las condiciones legales y manifestar mi aceptación,  
**para** tener certeza de las reglas del servicio y la protección de mi privacidad antes de utilizarlo.

### HU-DSH-001 — Panel de Control Moderno con Métricas Claras (KPIs)
**Como** usuario con sesión iniciada,  
**quiero** visualizar un dashboard estético y ordenado con tarjetas de totales y estados de comprobantes,  
**para** saber de un vistazo cuántos comprobantes tengo pendientes, cargados o con error, y cuánto suma el total deducible.

### HU-DSH-002 — Copiado Rápido del Token de la Extensión
**Como** usuario que va a configurar la extensión de Chrome,  
**quiero** presionar un botón para copiar mi Token API al portapapeles sin tener que seleccionarlo manualmente,  
**para** pegarlo rápidamente en la extensión sin errores tipográficos.

### HU-DSH-003 — Vinculación Sencilla con Telegram y Acceso a AFIP
**Como** usuario del dashboard,  
**quiero** tener botones directos y visibles para abrir el bot de Telegram y el portal de ARCA/AFIP,  
**para** enviar comprobantes desde mi celular e ingresar al sitio fiscal oficial con un solo clic.

### HU-DSH-004 — Gestión Visual de Comprobantes con Badges de Estado
**Como** usuario que consulta su historial,  
**quiero** ver una tabla estilizada, adaptada a pantallas móviles o de escritorio, con badges coloreados que destaquen el estado de cada factura,  
**para** auditar visualmente mis gastos sin confusiones.

---

## 5. Requisitos Funcionales (RF)

### 5.1 Módulo Legal (RF-LEG-*)

- **RF-LEG-001 — Rutas Legales Públicas**: El sistema debe exponer las rutas públicas en español `/terminos/` y `/privacidad/`, accesibles sin autenticación previa mediante métodos HTTP GET (código 200).
- **RF-LEG-002 — Contenido de Términos y Condiciones**: La página `/terminos/` debe detallar explícitamente:
  1. Propósito de la herramienta: asistente tecnológico de extracción y precarga de deducciones F572.
  2. Deslinde fiscal: el servicio no certifica deducibilidad impositiva; la responsabilidad ante AFIP/ARCA es exclusiva del contribuyente.
  3. Declaración de seguridad: SIRADIG Auto no solicita ni guarda claves fiscales ni contraseñas de AFIP.
  4. Canal de soporte y contacto: dirección de correo electrónico `marianoignaszewski@gmail.com`.
- **RF-LEG-003 — Contenido de Política de Privacidad**: La página `/privacidad/` debe detallar explícitamente:
  1. Datos recolectados: email de usuario, fotos de comprobantes, datos fiscales extraídos (CUIT emisor, importe, fecha, categoría).
  2. Proveedor de OCR: procesamiento automatizado mediante Google Gemini API sin utilización de datos para entrenamiento de modelos públicos.
  3. Derechos del titular: derecho de acceso, rectificación y supresión de datos escribiendo a `marianoignaszewski@gmail.com`.
  4. Conservación de datos: almacenamiento exclusivo para la operatividad del usuario en la plataforma.
- **RF-LEG-004 — Checkbox Obligatorio en Formulario de Registro**: La vista de registro (`/accounts/signup/`) debe incorporar un campo de verificación (checkbox) obligatorio con la leyenda: *"Acepto los Términos y Condiciones y la Política de Privacidad"*, con hipervínculos funcionales a `/terminos/` y `/privacidad/`. Si el checkbox no está marcado, el registro debe ser bloqueado con mensaje de validación.
- **RF-LEG-005 — Enlaces Legales en Inicio de Sesión**: La vista de inicio de sesión (`/accounts/login/`) debe mostrar un texto informativo al pie del formulario con hipervínculos a los Términos y Condiciones y a la Política de Privacidad.
- **RF-LEG-006 — Cláusula Legal para Google OAuth**: En las pantallas de login y registro que presenten el botón de autenticación con Google, debe incluirse inmediatamente debajo del botón el texto explícito: *"Al continuar con Google aceptas los Términos y la Política de Privacidad"*, con enlaces accesibles a ambas páginas legales.
- **RF-LEG-007 — Enlaces en Footer Global**: La plantilla base `templates/base.html` debe incluir en el footer enlaces directos y visibles a `/terminos/` y `/privacidad/`.

### 5.2 Módulo Dashboard Rediseñado (RF-DSH-*)

- **RF-DSH-001 — Herencia Estructural de Base**: La vista `receipts/templates/receipts/dashboard.html` debe heredar de `base.html`, manteniendo consistente la barra de navegación superior, los recursos CSS/JS de Bootstrap 5.3 y el footer global.
- **RF-DSH-002 — Tarjetas de Métricas (KPI Cards)**: El dashboard debe presentar en la parte superior cuatro tarjetas informativas (Cards):
  - *Pendientes de carga*: Contador de comprobantes en estado `pendiente_carga` (estilo visual warning/amarillo o acorde).
  - *Cargados en SIRADIG*: Contador de comprobantes en estado `cargado_en_siradig` (estilo visual success/verde).
  - *Errores de carga*: Contador de comprobantes en estado `error_carga` (estilo visual danger/rojo).
  - *Total deducible*: Suma acumulada de importes en pesos argentinos, formateada legiblemente (`$ 123.456,78` o separador de miles con decimales).
- **RF-DSH-003 — Acceso Rápido a Portal Fiscal**: El dashboard debe ofrecer un botón de llamada a la acción hacia el portal oficial de ARCA/AFIP (`https://auth.afip.gob.ar/contribuyente_/login.xhtml`), configurado con atributo `target="_blank"` y `rel="noopener noreferrer"`.
- **RF-DSH-004 — Vinculación Interactiva con Telegram**: El dashboard debe contener un bloque destacado para Telegram con el enlace profundo (`telegram_link`), mostrando un botón de acceso directo *"Abrir bot en Telegram"* con icono correspondiente.
- **RF-DSH-005 — Copiado Rápido del Token API al Portapapeles**: El dashboard debe presentar el Token de autenticación de la extensión dentro de un campo de sólo lectura (o etiqueta de código) acompañado de un botón interactivo *"Copiar Token"*. Al hacer clic:
  - El token debe copiarse al portapapeles del navegador mediante la Clipboard API de JavaScript.
  - El botón o un badge adyacente debe proporcionar feedback visual inmediato (ej. texto *"¡Copiado!"* con icono de check durante al menos 2 segundos).
- **RF-DSH-006 — Tabla de Comprobantes Responsiva y Estilizada**: La lista de comprobantes del usuario debe renderizarse dentro de un contenedor `.table-responsive` utilizando las clases `table table-hover table-striped align-middle`. Cada fila debe reflejar:
  - Fecha de emisión (`r.fecha_emision` o `-`).
  - Razón social del emisor (`r.razon_social`).
  - Importe total formateado en moneda.
  - Categoría de gasto (`r.categoria_gasto_siradig`).
  - Canal de origen (`r.get_origen_display`).
  - Estado del comprobante representado mediante un Badge de Bootstrap:
    - `pendiente_revision`: Badge color secundario/gris (`badge bg-secondary`).
    - `pendiente_carga`: Badge color advertencia/amarillo (`badge bg-warning text-dark`).
    - `cargado_en_siradig`: Badge color éxito/verde (`badge bg-success`).
    - `error_carga`: Badge color peligro/rojo (`badge bg-danger`).
- **RF-DSH-007 — Manejo de Estado Vacío (Empty State)**: Si el usuario no tiene comprobantes registrados, en lugar de una tabla vacía sin datos, debe mostrarse una tarjeta amigable que informe que aún no hay comprobantes y anime a vincular Telegram para enviar la primera foto.
- **RF-DSH-008 — Redirección de Cierre de Sesión hacia la Landing Page**: Al ejecutar el cierre de sesión desde el navbar o el dashboard, el usuario debe ser redirigido a la raíz `/` (`landing`).

---

## 6. Reglas de Negocio (RN)

- **RN-001 — Prohibición Estricta de Gestión de Credenciales Fiscales**: SIRADIG Auto jamás solicitará, recolectará, procesará ni almacenará Clave Fiscal, CUIT o datos de autenticación de AFIP/ARCA. Esta regla es mandato constitucional irrevocable y debe constar en los Términos y Condiciones.
- **RN-002 — Contacto Legal Unificado**: Toda comunicación referida a privacidad, términos, bajas de cuenta o ejercicio de derechos ARCO (Acceso, Rectificación, Cancelación y Oposición) debe centralizarse en la casilla oficial `marianoignaszewski@gmail.com`.
- **RN-003 — Obligatoriedad de Aceptación Legal**: No se permitirá la creación de cuentas locales si el usuario no ha marcado afirmativamente la casilla de consentimiento de términos y privacidad.
- **RN-004 — Aislamiento Estricto de Datos en Dashboard**: Un usuario autenticado solo puede visualizar sus propios comprobantes, métricas y token de perfil (`request.user.receipts` y `request.user.userprofile`). Ningún dato de otro usuario puede ser visible en el dashboard.
- **RN-005 — Categoría Exclusiva del MVP**: Se mantiene vigente que la única categoría admitida para carga y visualización operativa es *"Gastos de Adquisición de Indumentaria y Equipamiento"*.

---

## 7. Interfaces, Vistas y Rutas Afectadas

| Ruta | Nombre URL | Vista / Handler | Plantilla | Comportamiento |
|---|---|---|---|---|
| `/terminos/` | `terminos` | `TemplateView.as_view(...)` | `legal/terminos.html` | Pública (GET 200). Renderiza términos y condiciones completos con contacto `marianoignaszewski@gmail.com`. |
| `/privacidad/` | `privacidad` | `TemplateView.as_view(...)` | `legal/privacidad.html` | Pública (GET 200). Renderiza política de privacidad y tratamiento de datos con contacto oficial. |
| `/dashboard/` | `dashboard` | `receipts.views.dashboard_home` | `receipts/dashboard.html` | Protegida (`@login_required`). Dashboard moderno con KPIs, botón de copiado de token, tabla estilizada y badges. |
| `/accounts/signup/` | `account_signup` | `allauth.account.views.SignupView` | `account/signup.html` | Pública. Incorpora checkbox de aceptación legal y cláusula de Google OAuth. |
| `/accounts/login/` | `account_login` | `allauth.account.views.LoginView` | `account/login.html` | Pública. Incorpora enlaces informativos a términos/privacidad y cláusula de Google OAuth. |
| `/accounts/logout/` | `account_logout` | `allauth.account.views.LogoutView` | - | Redirige a `/` tras cerrar sesión (según `LOGOUT_REDIRECT_URL = '/'`). |

---

## 8. Criterios de Aceptación (CA)

### CA-LEG-001 — Visualización de Términos y Condiciones (RF-LEG-001, RF-LEG-002)
- **Dado** cualquier usuario (anónimo o autenticado),
- **Cuando** navega hacia la ruta `/terminos/`,
- **Entonces** el servidor responde HTTP 200 con la página de Términos y Condiciones heredada de `base.html`,
- **Y** la página contiene la aclaración de no almacenamiento de credenciales AFIP y la dirección de contacto `marianoignaszewski@gmail.com`.

### CA-LEG-002 — Visualización de Política de Privacidad (RF-LEG-001, RF-LEG-003)
- **Dado** cualquier usuario (anónimo o autenticado),
- **Cuando** navega hacia la ruta `/privacidad/`,
- **Entonces** el servidor responde HTTP 200 con la página de Política de Privacidad heredada de `base.html`,
- **Y** la página detalla el tratamiento de comprobantes e identifica el correo `marianoignaszewski@gmail.com` para solicitudes de baja o supresión de datos.

### CA-LEG-003 — Obligatoriedad del Checkbox Legal en Registro (RF-LEG-004)
- **Dado** un visitante en el formulario de registro `/accounts/signup/`,
- **Cuando** completa email y contraseña válidos pero deja desmarcado el checkbox de aceptación de Términos y Privacidad,
- **Entonces** el formulario no se envía (o es rechazado en validación con mensaje de error claro),
- **Y** la cuenta no es creada hasta que el usuario marque la casilla.

### CA-LEG-004 — Cláusula Legal en Botón de Google OAuth (RF-LEG-006)
- **Dado** un visitante en `/accounts/login/` o `/accounts/signup/`,
- **Cuando** observa la sección de inicio de sesión con Google,
- **Entonces** visualiza inmediatamente debajo del botón el texto *"Al continuar con Google aceptas los Términos y la Política de Privacidad"*,
- **Y** los términos y la política cuentan con enlaces operativos hacia `/terminos/` y `/privacidad/`.

### CA-LEG-005 — Enlaces Legales en Footer Global (RF-LEG-007)
- **Dado** cualquier usuario navegando por cualquier página que herede de `base.html`,
- **Cuando** inspecciona el pie de página (footer),
- **Entonces** visualiza enlaces directos a "Términos y Condiciones" y "Política de Privacidad".

### CA-DSH-001 — Visualización de KPIs en el Dashboard (RF-DSH-001, RF-DSH-002)
- **Dado** un usuario autenticado con comprobantes en diversos estados,
- **Cuando** accede a `/dashboard/`,
- **Entonces** visualiza cuatro tarjetas con el recuento exacto de comprobantes pendientes de carga, cargados, con error de carga y el monto total acumulado,
- **Y** el diseño mantiene el estilo coherente de Bootstrap 5.3 heredado de `base.html`.

### CA-DSH-002 — Copiado Interactivo del Token al Portapapeles (RF-DSH-005)
- **Dado** un usuario autenticado en `/dashboard/`,
- **Cuando** hace clic en el botón *"Copiar Token"* junto a su token de la extensión,
- **Entonces** el valor del token es copiado exitosamente al portapapeles del sistema,
- **Y** el botón muestra una confirmación visual temporal (*"¡Copiado!"* con icono de check).

### CA-DSH-003 — Acceso a Telegram y Sitio Oficial de AFIP (RF-DSH-003, RF-DSH-004)
- **Dado** un usuario en `/dashboard/`,
- **Cuando** presiona el botón de Telegram,
- **Entonces** se abre el enlace directo al bot con el token de vinculación,
- **Y** si presiona el botón de AFIP/ARCA, se abre en una pestaña nueva la página de login oficial de ARCA/AFIP sin solicitar credenciales intermedias.

### CA-DSH-004 — Badges y Tabla Responsiva de Comprobantes (RF-DSH-006)
- **Dado** un usuario con comprobantes registrados en su cuenta,
- **Cuando** revisa la tabla del dashboard,
- **Entonces** cada fila presenta sus datos alineados dentro de un contenedor responsive,
- **Y** la columna de estado exhibe un badge visual acorde al estado (`badge bg-warning`, `badge bg-success`, `badge bg-danger`, etc.).

### CA-DSH-005 — Estado Vacío (Empty State) para Nuevos Usuarios (RF-DSH-007)
- **Dado** un usuario recién registrado sin comprobantes aún subidos,
- **Cuando** accede a `/dashboard/`,
- **Entonces** visualiza un mensaje ilustrativo indicando que aún no hay comprobantes y guiándolo a enviar su primera foto por Telegram.

### CA-DSH-006 — Cierre de Sesión Hacia la Landing Page (RF-DSH-008)
- **Dado** un usuario autenticado en `/dashboard/`,
- **Cuando** presiona el botón de "Cerrar Sesión",
- **Entonces** su sesión se invalida y es redirigido inmediatamente a la raíz `/` (`landing`).

---

## 9. Requisitos No Funcionales (RNF)

- **RNF-001 — Responsividad Móvil (Layout)**: Tanto las páginas legales como el dashboard deben adaptarse fluidamente a dispositivos móviles (ancho mínimo 320px) y de escritorio utilizando el sistema de grillas y componentes de Bootstrap 5.3.
- **RNF-002 — Rendimiento de Carga**: El tiempo de renderizado de las páginas legales y del dashboard en el backend debe ser inferior a 150 ms para un conjunto típico de 50 comprobantes por usuario.
- **RNF-003 — Accesibilidad y Usabilidad**: Los contrastes de color en badges y botones deben cumplir las directrices WCAG 2.1 AA. Los campos interactivos de copiado deben funcionar tanto con ratón como con foco de teclado.
- **RNF-004 — Compatibilidad de Navegadores para Portapapeles**: El script de copiado del token debe utilizar `navigator.clipboard.writeText` con degradación elegante (*fallback* a `document.execCommand('copy')` o selección manual) en caso de que el navegador no soporte o restrinja la API del portapapeles.
- **RNF-005 — Seguridad y Privacidad**: Ningún secreto, token de Telegram interno de webhook o datos de otros usuarios debe exponerse en el código HTML renderizado.

---

## 10. Dependencias y Restricciones Constitucionales

- **Compatibilidad con Stack Existente**: No se agregarán librerías externas ni dependencias pesadas de frontend. Se utiliza estrictamente el CDN de Bootstrap 5.3 y Bootstrap Icons ya configurado en `templates/base.html`.
- **Arquitectura de URLs**: Las rutas legales se incorporan limpiamente a nivel de aplicación (`receipts/urls.py` o `core/urls.py`) respetando la convención de rutas en español acordada (`/terminos/`, `/privacidad/`).
- **No Invasión de Lógica Fiscal**: El dashboard no calculará deducciones estimativas de Ganancias ni determinará deducibilidad jurídica; únicamente totaliza sumas de los importes extraídos de los comprobantes.
- **Calidad de Código**: Las nuevas vistas, tests y templates deberán ajustarse a las convenciones de Ruff, Black y `pytest-django` fijadas por la constitución.

---

## 11. Trazabilidad

| Historia de Usuario | Requisito Funcional | Regla de Negocio | Criterio de Aceptación | Tipo de Verificación Previsto |
|---|---|---|---|---|
| HU-LEG-001 | RF-LEG-001, RF-LEG-002, RF-LEG-003 | RN-001, RN-002 | CA-LEG-001, CA-LEG-002 | Test HTTP (pytest / Client GET 200, contenido clave) |
| HU-LEG-002 | RF-LEG-004, RF-LEG-005, RF-LEG-006 | RN-003 | CA-LEG-003, CA-LEG-004 | Test de integración de formulario y verificación de templates |
| HU-LEG-001 | RF-LEG-007 | RN-002 | CA-LEG-005 | Test de renderizado de base.html y navegación |
| HU-DSH-001 | RF-DSH-001, RF-DSH-002 | RN-004, RN-005 | CA-DSH-001 | Test de vista `dashboard_home` con fixtures y totales |
| HU-DSH-002 | RF-DSH-005 | RN-004 | CA-DSH-002 | Verificación visual / prueba de DOM y Clipboard JS |
| HU-DSH-003 | RF-DSH-003, RF-DSH-004 | RN-001 | CA-DSH-003 | Test de contexto de template (`telegram_link`, enlace AFIP) |
| HU-DSH-004 | RF-DSH-006 | RN-004 | CA-DSH-004 | Test de renderizado de badges de estado en tabla |
| HU-DSH-001 | RF-DSH-007 | RN-004 | CA-DSH-005 | Test de estado vacío sin comprobantes |
| HU-DSH-001 | RF-DSH-008 | RN-004 | CA-DSH-006 | Test de redirección tras logout (`LOGOUT_REDIRECT_URL`) |

---

## 12. Registro de Dudas y Decisiones

| ID | Pregunta o Decisión | Impacto | Estado y Evidencia |
|---|---|---|---|
| DEC-001 | Checkbox obligatorio en registro y enlaces informativos en login | Aprobado | Decisión confirmada del usuario (Respuesta 1). Bloquea registro si no se acepta. |
| DEC-002 | Nombres de rutas legales en español (`/terminos/` y `/privacidad/`) | Aprobado | Decisión confirmada del usuario (Respuesta 2). Servidos mediante `TemplateView`. |
| DEC-003 | Casilla oficial de contacto legal: `marianoignaszewski@gmail.com` | Aprobado | Decisión confirmada del usuario (Respuesta 2). Consignada en ambas páginas legales. |
| DEC-004 | Cláusula explícita para Google OAuth bajo el botón social | Aprobado | Decisión confirmada del usuario (Respuesta 3). *"Al continuar con Google aceptas los Términos y la Política de Privacidad"*. |
| DEC-005 | Redirección de Logout hacia la landing page (`/`) | Aprobado | Decisión confirmada del usuario (Respuesta 4). Alineado con `LOGOUT_REDIRECT_URL = '/'`. |
| DEC-006 | Rediseño integral de `dashboard.html` con Bootstrap 5.3 heredando de `base.html` | Aprobado | Decisión confirmada del usuario (Respuesta 5). Cards para KPIs, badges de estado, portapapeles JS interactivo y botón Telegram. |

---

## 13. Control de Calidad y Checklist

- [x] Problema, actores y resultado esperado están definidos.
- [x] Alcance y exclusiones no se contradicen.
- [x] Los requisitos usan lenguaje inequívoco e identificadores estables (`RF-LEG-*`, `RF-DSH-*`).
- [x] Cada RF tiene criterios de aceptación verificables estilo Dado/Cuando/Entonces (`CA-LEG-*`, `CA-DSH-*`).
- [x] Las historias de usuario están enlazadas con los requisitos que las satisfacen.
- [x] Se cubren errores, validación y estados (ej. validación de checkbox, empty state de tabla).
- [x] La constitución está respetada (no almacenamiento de credenciales AFIP, Bootstrap 5.3 CDN, Token DRF, aislamiento de datos).
- [x] No hay decisiones técnicas nuevas disfrazadas de requisitos ni supuestos no aprobados.
- [x] Las decisiones del usuario (Fase 0) están documentadas con evidencia explícita en `DEC-001` a `DEC-006`.
- [x] La revisión está identificada como `REV-001` con estado `PENDIENTE_DE_APROBACION`.

---

## 14. Historial de Cambios

| Revisión | Cambio | Requisitos afectados | Estado de aprobación |
|---|---|---|---|
| `REV-001` | Creación de especificación formal basada en las respuestas del usuario sobre Fase 0 (Legales + Rediseño de Dashboard). | Todos (`RF-LEG-001` a `007`, `RF-DSH-001` a `008`) | PENDIENTE_DE_APROBACION |
