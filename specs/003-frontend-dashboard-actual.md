# SPEC-003: Especificación de Línea Base del Frontend Actual (Dashboard Web)

- **Identificador**: `SPEC-003`
- **Revisión**: `REV-001 (Borrador Inicial - As-Is y Brechas)`
- **Título**: Especificación de Línea Base del Frontend Actual (Dashboard Web) y Matriz de Brechas para Rediseño
- **Estado**: `PENDIENTE_DE_APROBACION`
- **Fuente de la petición**: Solicitud del usuario para documentar formalmente la especificación del frontend web actual (`receipts/templates/receipts/dashboard.html` y vistas asociadas), caracterizado como muy básico, para establecer la línea base formal antes de acometer su mejora/rediseño tras consolidar el flujo de datos.
- **Constitución consultada**: `docs/constitution.md` (Línea base v1.0).
- **Aprobación**: Pendiente de revisión y confirmación explícita por parte del usuario y coordinador.

---

## 1. Problema y Objetivo

### 1.1 Contexto del Problema
Actualmente, el sistema SIRADIG Auto cuenta con una única plantilla HTML de servidor para la interacción del usuario final (`receipts/templates/receipts/dashboard.html`), renderizada por la vista Django `dashboard_home` (`receipts/views.py`). 

Dicha interfaz fue concebida como un prototipo funcional mínimo (*scaffolding*) sin hojas de estilo CSS (ni locales ni CDNs), sin scripts interactivos de cliente (JavaScript), sin diseño responsive, sin paginación y con capacidades estrictamente de solo lectura. Los usuarios no disponen de mecanismos visuales para previsualizar el archivo original (imagen o PDF de la factura), corregir datos erróneos inferidos por el OCR, filtrar comprobantes, observar el progreso de cargas en tiempo real ni interactuar con las notificaciones de Telegram/WebSockets contempladas en la arquitectura constitucional.

### 1.2 Objetivo
1. **Establecer la línea base formal (As-Is)**: Documentar de forma rigurosa y exhaustiva el comportamiento, estructura DOM, contratos de datos y reglas operativas del frontend web actual.
2. **Definir la matriz de brechas y oportunidades de mejora (To-Be)**: Servir como especificación canónica de referencia para la posterior fase de rediseño y modernización de la UI, asegurando coherencia con el flujo de datos (`SPEC-002`), la extensión de navegador (`SPEC-001`) y la constitución del proyecto (`docs/constitution.md`).

---

## 2. Alcance

### 2.1 Incluido
1. **Plantilla HTML del Dashboard**: `receipts/templates/receipts/dashboard.html`.
2. **Controlador y Vista de Backend**: `dashboard_home` en `receipts/views.py` y ruta `/dashboard/` en `receipts/urls.py`.
3. **Contrato de Contexto de Plantilla**: Estructura de datos inyectada por el motor de plantillas de Django (`DjangoTemplates`), incluyendo perfil, usuario, conteos de estado, totales y enlaces de integración.
4. **Flujo de Autenticación y Autorización Web**: Control de acceso vía decorador `@login_required`, sesión de usuario Django y soporte AllAuth.
5. **Inventario Exhaustivo de Brechas y Limitaciones**: Análisis dimensional (UX/UI, interactividad, tiempo real, accesibilidad, responsividad, seguridad).

### 2.2 Excluido
1. **Interfaz de la Extensión de Navegador**: `extension/popup.html` y `extension/popup.js` (cubiertos en `SPEC-001`).
2. **Modificación de Código Fuente**: Esta especificación no modifica templates, vistas ni añade paquetes al entorno.
3. **Interfaces Administrativas de Terceros**: Django Admin (`/admin/`) y vistas internas del proveedor de autenticación AllAuth (`/accounts/`).
4. **Canales de Mensajería Externos**: La interfaz de chat nativa de Telegram o WhatsApp.

---

## 3. Actores y Términos

- **Usuario Contribuyente**: Persona humana autenticada mediante sesión web en Django que consulta el estado de sus deducciones impositivas y gestiona su vinculación.
- **Dashboard Web**: Vista HTML renderizada del lado del servidor (SSR) expuesta bajo la ruta `/dashboard/`.
- **Token DRF**: Clave hexadecimal de 40 caracteres perteneciente a `rest_framework.authtoken.models.Token`, expuesta en el dashboard para ser copiada a la extensión del navegador.
- **Deep Link de Telegram**: URL en formato `https://t.me/<bot>?start=<token>` utilizada para enlazar la sesión de chat con el usuario de la aplicación.
- **As-Is (Estado Actual)**: Comportamiento y presentación vigentes en el repositorio a la fecha de esta especificación.
- **To-Be (Estado Deseado/Futuro)**: Capacidades de diseño, interactividad y componentes identificados para el próximo ciclo de mejora.

---

## 4. Historias de Usuario (Frontend Actual)

### HU-FE-001 — Visualización de Bienvenida e Identificación de Sesión
Como usuario autenticado, quiero ver mi nombre o nombre de usuario en el encabezado del panel, para tener certeza de qué cuenta fiscal estoy administrando.

### HU-FE-002 — Consulta de Métricas de Resumen Operativo
Como usuario contribuyente, quiero visualizar un resumen cuantitativo con la cantidad de comprobantes por estado y el monto deducible total acumulado, para evaluar de un vistazo el volumen de gastos cargados y pendientes.

### HU-FE-003 — Acceso Rápido al Portal Oficial de AFIP/ARCA
Como usuario contribuyente, quiero contar con un hipervínculo directo hacia el login oficial de AFIP/ARCA, para iniciar sesión manualmente en el portal fiscal antes de utilizar la extensión de autocompletado.

### HU-FE-004 — Obtención del Enlace de Vinculación de Telegram
Como usuario contribuyente, quiero acceder a mi link personalizado de Telegram, para iniciar la conversación con el bot y habilitar la recepción de fotos y documentos desde mi celular.

### HU-FE-005 — Copia de Token para la Extensión del Navegador
Como usuario contribuyente, quiero disponer en pantalla de mi token de API personal, para pegarlo en la extensión de Chrome y permitir que interactúe con mis comprobantes pendientes.

### HU-FE-006 — Visualización del Histórico de Comprobantes
Como usuario contribuyente, quiero consultar una tabla con la lista cronológica de mis comprobantes procesados (fecha, razón social, importe, categoría, origen y estado legible), para controlar la información capturada por el sistema.

---

## 5. Requisitos Funcionales (RF - Estado Actual)

- **RF-FE-001 (Control de Acceso Web)**: El sistema debe restringir el acceso a la ruta `/dashboard/` únicamente a usuarios autenticados, redirigiendo a los usuarios anónimos al formulario de autenticación correspondiente (`settings.LOGIN_URL`).
- **RF-FE-002 (Aprovisionamiento Implícito de Perfil)**: Al acceder al dashboard, la vista debe asegurar la existencia de una instancia `UserProfile` asociada al usuario activo (`get_or_create`), garantizando la disponibilidad del `telegram_link_token`.
- **RF-FE-003 (Cálculo Agregado de Métricas en Servidor)**: La vista debe computar en servidor y proveer al contexto:
  - Cantidad de comprobantes con estado `pendiente_carga`.
  - Cantidad de comprobantes con estado `cargado_en_siradig`.
  - Cantidad de comprobantes con estado `error_carga`.
  - Suma acumulada de `importe_total` de todos los comprobantes del usuario.
- **RF-FE-004 (Construcción de Enlace de Vinculación Telegram)**: La vista debe construir y entregar en el contexto una URL al formato `https://t.me/<TELEGRAM_BOT_USERNAME>?start=<telegram_link_token>` consumiendo la variable de entorno configurada.
- **RF-FE-005 (Proyección de Clave de Token de Extensión)**: La plantilla debe proyectar la clave `key` del token de autenticación DRF asociado al usuario mediante la navegación relacional `profile.user.auth_token.key`.
- **RF-FE-006 (Renderizado de Tabla Histórica de Comprobantes)**: La plantilla debe iterar y desplegar en una tabla HTML estándar (`<table border="1">`) el conjunto completo de comprobantes pertenecientes al usuario ordenados descendentemente por fecha de creación (`-created_at`), mostrando:
  - Fecha de emisión (`r.fecha_emision`).
  - Razón social (`r.razon_social`).
  - Importe total (`r.importe_total`).
  - Categoría de gasto (`r.categoria_gasto_siradig`).
  - Nombre legible del origen vía `r.get_origen_display` (`Telegram` o `Carga manual (web)`).
  - Nombre legible del estado vía `r.get_estado_display` (`Pendiente de revisión`, `Pendiente de carga en SIRADIG`, `Cargado en SIRADIG`, `Error en carga en SIRADIG`).
- **RF-FE-007 (Enlace Saliente a Portal Fiscal)**: La plantilla debe proveer un enlace saliente seguro a `https://auth.afip.gob.ar/contribuyente_/login.xhtml` configurado con atributo `target="_blank"`.

---

## 6. Reglas de Negocio del Frontend (RN)

- **RN-FE-001 (Aislamiento Visual Estricto)**: El dashboard debe listar única y exclusivamente los comprobantes vinculados al `user_id` de la sesión actual; ningún usuario podrá visualizar comprobantes, tokens ni métricas ajenas.
- **RN-FE-002 (No Captura de Credenciales en UI)**: El dashboard no debe presentar en ningún momento campos de formulario destinados a solicitar, capturar o persistir Clave Fiscal o CUIT tributario de AFIP.
- **RN-FE-003 (Solo Lectura en Dashboard Actual)**: En el estado As-Is, el dashboard es puramente informativo y de solo lectura; no contiene formularios HTML de mutación (`<form method="POST">`), botones de edición ni endpoints de borrado directo desde la página.

---

## 7. Contrato de Datos de la Vista (`dashboard_home`)

### 7.1 Objeto de Contexto Django (`context`)

| Clave de Contexto | Tipo / Origen | Expresión / Cálculo en `receipts/views.py` | Uso en Plantilla |
|---|---|---|---|
| `profile` | `UserProfile` | `UserProfile.objects.get_or_create(user=request.user)[0]` | Acceso indirecto a `profile.user.auth_token.key` para el token de extensión. |
| `receipts` | `QuerySet[Receipt]` | `request.user.receipts.order_by('-created_at')` | Iteración `{% for r in receipts %}` en la tabla de comprobantes. |
| `pendientes` | `int` | `receipts.filter(estado='pendiente_carga').count()` | Elemento de lista en Resumen: "Comprobantes pendientes de carga en SIRADIG". |
| `cargados` | `int` | `receipts.filter(estado='cargado_en_siradig').count()` | Elemento de lista en Resumen: "Comprobantes ya cargados". |
| `errores_carga` | `int` | `receipts.filter(estado='error_carga').count()` | Elemento de lista en Resumen: "Comprobantes con error en carga". |
| `total_deducible` | `Decimal` / `float` | `sum(r.importe_total or 0 for r in receipts)` | Elemento de lista en Resumen: "Total deducible acumulado: ${{ total_deducible }}". |
| `telegram_link` | `str` | `f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={profile.telegram_link_token}"` | Hipervínculo y texto visible en sección "Vincular Telegram". |

### 7.2 Variables Globales Disponibles en Template (Context Processors)
- `request.user`: Instancia `django.contrib.auth.models.User` activa en la sesión.
  - Usado en: `{{ request.user.first_name|default:request.user.username }}`.
- `messages`: Mensajes flash del framework de Django (actualmente no renderizados en la plantilla).

---

## 8. Arquitectura y Componentes de UI Actuales

### 8.1 Jerarquía Estructural del DOM
El documento `receipts/templates/receipts/dashboard.html` es completamente monolítico y autónomo (no hereda de ningún `base.html` ni incluye partials):

```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>SIRADIG Auto - Dashboard</title>
</head>
<body>
    <!-- 1. Encabezado de Identidad -->
    <h1>Hola, {{ request.user.first_name|default:request.user.username }}</h1>

    <!-- 2. Tarjeta / Lista de Resumen de KPIs -->
    <h2>Resumen</h2>
    <ul>...</ul>

    <!-- 3. Acceso AFIP Oficial -->
    <p><a href="https://auth.afip.gob.ar/contribuyente_/login.xhtml" target="_blank">Ir a ARCA / AFIP</a></p>

    <!-- 4. Bloque de Onboarding Telegram -->
    <h2>Vincular Telegram</h2>
    <p>...<a href="{{ telegram_link }}">...</a></p>

    <!-- 5. Credencial de Extensión -->
    <h2>Token para la extensión del navegador</h2>
    <p>...<code>{{ profile.user.auth_token.key }}</code></p>

    <!-- 6. Grilla de Comprobantes -->
    <h2>Comprobantes</h2>
    <table border="1" cellpadding="4">
        <!-- Thead / Tbody unificados en trs planos -->
    </table>
</body>
</html>
```

### 8.2 Dependencias de Estilos y Scripts (Inventario Actual)
- **Hojas de estilo CSS**: `0` (Ninguna). No hay Bootstrap, Tailwind, Bulma ni archivo CSS local vinculado vía `<link rel="stylesheet">`.
- **Estilos en línea / Inline CSS**: `0` (Ninguno). El estilizado depende exclusivamente de los estilos por defecto del agente de usuario (navegador) y atributos HTML legados (`border="1"`, `cellpadding="4"`).
- **Scripts JavaScript**: `0` (Ninguno). No hay scripts locales ni librerías externas (Alpine.js, HTMX, jQuery, React, etc.).
- **Fuentes / Iconos**: No utiliza fuentes web ni iconografías (ej. FontAwesome, Lucide, SVG).

---

## 9. Criterios de Aceptación (CA - Estado Actual)

### CA-FE-001 — Acceso Restringido a Usuarios Autenticados (RF-FE-001)
- **Dado** un visitante no autenticado en el sistema.
- **Cuando** intenta realizar una petición `GET /dashboard/`.
- **Entonces** es redirigido a `/accounts/login/?next=/dashboard/` (o URL de login configurada) con código HTTP 302.

### CA-FE-002 — Saludo Personalizado al Usuario (RF-FE-001)
- **Dado** un usuario autenticado con `first_name="Martín"` y `username="mignasze"`.
- **Cuando** visita `/dashboard/`.
- **Entonces** el título `<h1>` muestra exactamente `"Hola, Martín"`.
- **Y** si `first_name` está en blanco, muestra `"Hola, mignasze"`.

### CA-FE-003 — Exactitud en Métricas del Resumen (RF-FE-003)
- **Dado** un usuario que posee:
  - 2 comprobantes en `pendiente_carga`.
  - 3 comprobantes en `cargado_en_siradig`.
  - 1 comprobante en `error_carga`.
  - 1 comprobante en `pendiente_revision`.
  - Importes totales que suman `$45000.50`.
- **Cuando** carga la página del dashboard.
- **Entonces** la lista de resumen muestra:
  - `Comprobantes pendientes de carga en SIRADIG: 2`
  - `Comprobantes ya cargados: 3`
  - `Comprobantes con error en carga: 1`
  - `Total deducible acumulado: $45000.50`

### CA-FE-004 — Disponibilidad y Formato del Deep Link de Telegram (RF-FE-004)
- **Dado** un usuario con `telegram_link_token="abc123token"` y `TELEGRAM_BOT_USERNAME="SiradigBot"`.
- **Cuando** se renderiza la sección de Telegram.
- **Entonces** el enlace `<a>` contiene el atributo `href="https://t.me/SiradigBot?start=abc123token"`.

### CA-FE-005 — Exposición del Token de Extensión (RF-FE-005)
- **Dado** un usuario que posee un token DRF asignado con valor `"9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"`.
- **Cuando** se visualiza la sección de extensión.
- **Entonces** el contenido dentro de la etiqueta `<code>` coincide exactamente con dicho token.

### CA-FE-006 — Visualización Completa y Ordenada de la Tabla (RF-FE-006)
- **Dado** un usuario con comprobantes registrados en la base de datos.
- **Cuando** se genera la tabla de comprobantes.
- **Entonces** se muestran las columnas: Fecha, Razón Social, Importe, Categoría, Origen y Estado.
- **Y** las filas se ordenan desde el comprobante más reciente al más antiguo según `created_at`.

---

## 10. Requisitos No Funcionales (RNF - Estado Actual y Deseado)

- **RNF-FE-001 (Tiempo de Renderizado SSR)**: El tiempo de procesamiento y renderizado en servidor de la plantilla `dashboard.html` debe ser inferior a 150 ms para un volumen nominal de hasta 100 comprobantes por usuario.
- **RNF-FE-002 (Compatibilidad de Navegadores)**: Al no depender de JavaScript ni CSS propietario, la plantilla debe renderizarse sin anomalías funcionales en cualquier navegador moderno compatible con HTML5 (Chrome, Firefox, Safari, Edge).
- **RNF-FE-003 (Aislamiento de Seguridad CSP y Enlaces Salientes)**: Los enlaces salientes hacia dominios de terceros (`t.me` y `afip.gob.ar`) deben incorporar buenas prácticas de seguridad (como `rel="noopener noreferrer"`) para evitar ataques de tab-napping.
- **RNF-FE-004 (Accesibilidad Semántica Básica)**: El documento debe mantener una jerarquía de encabezados válida (`h1`, `h2`) y etiquetas semánticas de tabla (`thead`, `tbody`, `th`, `td`) para no degradar la navegación por lectores de pantalla.

---

## 11. Inventario de Brechas, Limitaciones y Oportunidades de Mejora (Matriz As-Is vs. To-Be)

Esta sección consolida las carencias identificadas en la implementación actual frente a las necesidades reales del producto y la arquitectura prevista en la constitución.

| Dimensión | Estado Actual (As-Is - Prototipo) | Limitación / Problema Generado | Estado Futuro Deseado (To-Be - Rediseño) | Prioridad |
|---|---|---|---|---|
| **Diseño y Estilos** | HTML puro sin CSS ni frameworks. Estructura basada en `table border="1"`. | Aspecto visual tosco y poco profesional; experiencia precaria para el usuario. | Adopción de framework moderno o utilidad CSS (ej. Tailwind CSS o Bootstrap limpio) con diseño limpio y sobrio. | **ALTA** |
| **Responsividad Móvil** | No posee meta-viewport (`<meta name="viewport" content="...">`) ni estilos responsive. | La tabla se desborda en dispositivos móviles y smartphones, requiriendo scroll horizontal incómodo. | Layout responsivo *mobile-first* con tarjetas colapsables o tabla con scroll horizontal optimizado en smartphones. | **ALTA** |
| **Previsualización de Comprobante** | No hay enlaces ni modales para ver `archivo_original`. | El usuario no puede cotejar si los datos leídos por el OCR coinciden con la foto/PDF subido. | Modal o visor lateral que permita abrir y hacer zoom a la imagen original o PDF del comprobante. | **ALTA** |
| **Edición y Corrección de Datos OCR** | No existe formulario ni vista de edición (`/edit/<id>/`). | Si Gemini confunde un CUIT, fecha o monto, el comprobante queda erróneo sin posibilidad de subsanación web por el usuario. | Formulario inline o modal de edición para corregir campos fiscales antes del autocompletado en AFIP. | **CRÍTICA** |
| **Paginación y Filtrado** | Carga `request.user.receipts` completo sin `Paginator` ni filtros de estado/fecha. | Con más de 50 facturas la página se vuelve lenta y la navegación inmanejable. | Paginación estándar (ej. 20 items/página), filtros rápidos por estado (Pendientes, Cargados, Errores) y buscador. | **MEDIA** |
| **Feedback de Carga en Tiempo Real** | Requiere recarga manual completa (`F5`) para verificar si un comprobante fue subido por Telegram o inyectado por la extensión. | El usuario no sabe en qué momento el OCR terminó de procesar o la extensión finalizó la carga sin recargar la página. | Conexión WebSocket mediante Django Channels (declarado en constitución) para actualizar el estado de comprobantes en vivo. | **MEDIA** |
| **Acciones de Copia y Usabilidad (UX)** | El token de extensión y el link de Telegram se presentan como texto plano para selección manual. | El usuario debe seleccionar manualmente con el mouse strings largos, propiciando errores de copiado. | Botones interactivos con un click: `"Copiar Token"` y `"Copiar Enlace"` con toast de confirmación visual. | **BAJA** |
| **Gestión de Errores Detallados** | Solo muestra el conteo total de `errores_carga`. La tabla no expone el campo `mensaje_error`. | Si un comprobante falla en AFIP, el usuario no sabe cuál fue la causa del rechazo (ej. CUIT no habilitado, importe inválido). | Columna o tooltip de detalle que exponga `mensaje_error` para comprobantes en estado `error_carga`. | **MEDIA** |
| **Eliminación / Descarte de Comprobantes** | No hay opción para descartar comprobantes duplicados o ilegibles. | Comprobantes erróneos o fotos accidentales quedan acumulados permanentemente en el dashboard. | Acción de descarte / archivado de comprobante con confirmación previa. | **MEDIA** |
| **Layout Base y Reutilización** | No existe `base.html`. No hay barra de navegación, logout visible ni enlaces a términos. | El usuario no puede cerrar sesión de forma intuitiva ni navegar entre secciones si la app crece. | Arquitectura de plantillas modular con `base.html`, navbar de sesión con botón de logout y pie de página. | **ALTA** |

---

## 12. Dependencias y Restricciones Constitucionales

1. **Stack Técnico**: Basado en Django 6.1 y Python 3.11 (`core/settings.py` y `requirements.txt`).
2. **Uso de Django Channels**: La constitución establece: *"Los canales WebSocket (`channels`) se usan para notificaciones de mensajería; el MVP usa Telegram pero la arquitectura es agnóstica"*. El rediseño del frontend deberá prever la integración de WebSockets para notificar eventos de recepción de comprobantes y cambios de estado.
3. **Principio de Cero Credenciales**: Bajo ningún aspecto el frontend rediseñado incorporará inputs para CUIT de autenticación o Clave Fiscal de AFIP.
4. **Categoría Exclusiva del MVP**: El frontend debe reforzar la restricción constitucional de soporte exclusivo para `"Gastos de Adquisición de Indumentaria y Equipamiento"`.

---

## 13. Trazabilidad

| Necesidad / Brecha | Requisito Funcional | Criterio de Aceptación | Tipo de Verificación Prevista |
|---|---|---|---|
| Acceso y Seguridad | RF-FE-001 | CA-FE-001 | Test de integración HTTP con cliente Django (`pytest-django`) |
| Identidad de Sesión | RF-FE-002 | CA-FE-002 | Test de renderizado de contexto en vista de dashboard |
| Métricas Agregadas | RF-FE-003 | CA-FE-003 | Test unitario de cálculo de agregaciones en `dashboard_home` |
| Deep Linking Telegram | RF-FE-004 | CA-FE-004 | Test de formato de URL con token |
| Token de Extensión | RF-FE-005 | CA-FE-005 | Verificación de clave DRF en contexto |
| Tabla Histórica | RF-FE-006 | CA-FE-006 | Test de renderizado de filas y `order_by` descendente |
| Enlace AFIP | RF-FE-007 | CA-FE-007 | Inspección de atributos en plantilla HTML |

---

## 14. Dudas Abiertas y Decisiones

| ID | Pregunta o Decisión | Impacto | Estado |
|---|---|---|---|
| **DEC-FE-001** | El dashboard actual (`receipts/templates/receipts/dashboard.html`) se mantiene temporalmente intacto como línea base funcional hasta aprobar la especificación del rediseño. | Estabilidad operativa | Confirmada |
| **DEC-FE-002** | No se introducen archivos de código ni dependencias en esta llamada de especificación SDD. | Gobernanza SDD | Confirmada |
| **Q-FE-001** | ¿Cuál será la tecnología preferida para la UI mejorada? (Opciones: Django Templates + Tailwind CSS + HTMX, o Bootstrap 5 estándar, o SPA independiente). | Planificación y dependencias | Pendiente de decisión del usuario |
| **Q-FE-002** | ¿La edición de comprobantes erróneos se realizará en una página dedicada (`/receipts/<id>/edit/`) o mediante modales en el mismo dashboard? | Arquitectura de vistas | Pendiente de aclaración |
| **Q-FE-003** | ¿Se requiere permitir la subida manual de comprobantes directamente desde la web (formulario drag-and-drop) además de Telegram en la próxima versión? | Alcance de ingestión | Pendiente de aclaración |

---

## 15. Control de Calidad y Checklist de la Especificación

- [x] Problema, actores y resultado esperado están delimitados formalmente.
- [x] Alcance y exclusiones separan claramente la UI web de la extensión de navegador.
- [x] Requisitos Funcionales con IDs estables (`RF-FE-001` a `RF-FE-007`) modelan con precisión lo que hace el frontend actual.
- [x] Reglas de Negocio (`RN-FE-001` a `RN-FE-003`) y RNF documentados objetivamente.
- [x] Criterios de Aceptación verificables en formato Dado/Cuando/Entonces para cada funcionalidad.
- [x] Contrato de datos del contexto de la vista exhaustivamente auditado desde el código real de `views.py`.
- [x] Matriz de brechas y limitaciones (As-Is vs. To-Be) detallada para orientar el futuro rediseño.
- [x] Cumplimiento de restricciones constitucionales (Cero credenciales AFIP, Django Channels para tiempo real, MVP indumentaria).
- [x] Dudas y decisiones categorizadas con su impacto.

---

## 16. Historial de Cambios

| Revisión | Fecha | Resumen de Cambios | Requisitos Afectados | Estado |
|---|---|---|---|---|
| `REV-001` | 2026-10-17 | Redacción inicial de la especificación de línea base del frontend actual (`SPEC-003`) y análisis de brechas para mejora futura. | RF-FE-001 a RF-FE-007 | Pendiente de Aprobación |
