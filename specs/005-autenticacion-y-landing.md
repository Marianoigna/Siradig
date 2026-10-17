# Especificación: Sistema de Autenticación Unificado y Landing Page Pública

- **Identificador:** `005-autenticacion-y-landing` (SPEC-005)
- **Revisión:** `REV-001`
- **Estado:** `PENDIENTE_DE_APROBACION`
- **Fuente de la petición:** Solicitud del usuario: *"Vamos a crear una nueva feature para el Loging de la pagina. Quiero que pueda loguearse con OAuth 2.0 o colocando una mail y contraseña. que se pueda recuperar la contraseña. Ademas que exista una landing page muy basica por ahora."*
- **Constitución consultada:** `docs/constitution.md` (Revisión vigente: Stack base Django 6.1 + DRF + Python 3.11, dependencias fijadas en requirements.txt, cero paquetes anónimos, pruebas pytest-django, no almacenar credenciales AFIP).
- **Aprobación:** Sin aprobación registrada (Entregado al coordinador para revisión explícita del usuario).

---

## 1. Resumen Ejecutivo, Problema y Objetivo

### 1.1 Contexto y Problema
Actualmente, el backend de **SIRADIG Auto** protege el panel de control (`/dashboard/`) mediante `@login_required` y redirige la ruta raíz (`/`) directamente a `dashboard/` sin ofrecer una página de presentación pública previa. Asimismo, el acceso depende de usuarios preexistentes o creados vía Django Admin / scripts CLI (`ensuresuperuser`), careciendo de:
1. Una página de aterrizaje (Landing Page) que explique el propósito de la herramienta (automatización de deducciones F572 en AFIP sin manejo de credenciales fiscales).
2. Interfaz web pública para registro e inicio de sesión local mediante correo electrónico y contraseña.
3. Inicio de sesión federado mediante OAuth 2.0 (Google como proveedor principal del MVP, con base lista en `allauth.socialaccount`).
4. Flujo de autoservicio para la recuperación y restablecimiento seguro de contraseñas olvidadas por correo electrónico.

### 1.2 Objetivo
Proveer una experiencia de acceso completa, moderna y segura para usuarios web, consistente en:
- Una **Landing Page** pública y responsiva en la raíz `/` para usuarios anónimos.
- Un sistema de autenticación híbrido (Credenciales locales: Email/Contraseña + OAuth 2.0 con Google).
- Un flujo completo de restablecimiento de contraseña vía correo electrónico con tokens de un solo uso.
- Preservación estricta de la integridad de datos: asegurar que la creación de usuarios por cualquiera de las vías dispare la señal `post_save` en `receipts/signals.py`, aprovisionando de inmediato el `UserProfile` (con su token de Telegram) y el `Token` DRF para la extensión de navegador.

---

## 2. Alcance

### 2.1 Incluido
- **Landing Page pública (`/`)**:
  - Vista visible para usuarios no autenticados con explicación clara de la propuesta de valor y del principio de seguridad ("Tus credenciales de AFIP nunca tocan nuestros servidores").
  - Botones de llamada a la acción (CTA) hacia "Iniciar Sesión" y "Registrarse".
  - Redirección automática a `/dashboard/` si el visitante ya cuenta con una sesión web activa.
- **Autenticación local (Email y Contraseña)**:
  - Registro de nuevos usuarios solicitando Email y Contraseña (con confirmación). El email se utiliza como credencial primaria de inicio de sesión (`ACCOUNT_AUTHENTICATION_METHOD = 'email'` en `django-allauth` o username derivado unívocamente del email).
  - Inicio de sesión con Email y Contraseña.
  - Validación de robustez de contraseñas según los validadores estándar configurados en Django (`AUTH_PASSWORD_VALIDATORS`).
- **Autenticación Social / OAuth 2.0**:
  - Soporte para inicio de sesión y registro con un clic mediante **Google OAuth 2.0** utilizando la infraestructura ya declarada en `allauth.socialaccount.providers.google`.
  - Vinculación segura de cuenta por email coincidente si está verificado por el proveedor social.
- **Recuperación de Contraseña**:
  - Formulario de solicitud de restablecimiento mediante ingreso de email registrado.
  - Generación de enlace seguro con token de un solo uso y expiración temporal (Django `default_token_generator`).
  - Envío de correo electrónico (backend consola en entorno local/desarrollo, SMTP configurable vía variables de entorno en producción).
  - Formulario para establecer la nueva contraseña y confirmación de cambio exitoso.
- **Ciclo de Sesión y Navegación**:
  - Cierre de sesión explícito (`/accounts/logout/`) con confirmación o redirección inmediata a la landing page.
  - Redirecciones configuradas: post-login hacia `/dashboard/`, post-logout hacia `/`.
  - Protección de `/dashboard/` para requerir sesión activa (`login_required`), redirigiendo a `/accounts/login/` con parámetro `?next=/dashboard/`.
- **Garantía de Señales**:
  - Asegurar que la creación de usuarios (sea por email/password o por OAuth 2.0 de `allauth`) ejecute `receipts/signals.py` (`create_user_profile`), garantizando que todo usuario tenga `UserProfile` y `Token` de DRF creados sin intervención manual.

### 2.2 Exclusiones Explícitas
- **Credenciales AFIP/ARCA**: Ninguna parte de la landing, login o backend solicitará o almacenará CUIT ni Clave Fiscal de AFIP (Mandato Constitucional, Principio de Seguridad #9).
- **Múltiples factores de autenticación (2FA / MFA)**: Fuera del alcance del MVP.
- **Proveedores OAuth secundarios**: En este incremento solo se habilita Google OAuth 2.0. Proveedores adicionales (GitHub, Apple, etc.) quedan para iteraciones futuras.
- **Edición de perfil de usuario / Cambio de email**: Fuera del alcance de este incremento (se cubre solo login, logout, registro y recuperación de contraseña).
- **Verificación obligatoria de email para login inicial**: Para evitar fricción en el MVP, se mantiene `ACCOUNT_EMAIL_VERIFICATION = 'optional'` o `'none'` para el acceso inmediato, reservando el email principalmente para login y reseteo de contraseña.

---

## 3. Actores y Términos

### 3.1 Actores
- **Visitante Anónimo**: Persona no autenticada que ingresa a la aplicación. Puede explorar la landing, iniciar sesión, registrarse o solicitar recuperación de contraseña.
- **Usuario Autenticado**: Persona con sesión web activa. Puede acceder al dashboard, ver sus comprobantes y vincular su cuenta con Telegram.
- **Extensión de Navegador (Cliente API)**: Software cliente que consume la API REST de comprobantes utilizando el token DRF (`TokenAuthentication`) asignado al usuario.
- **Proveedor OAuth (Google Identity)**: Proveedor externo de identidad que autentica al usuario y entrega claims verificados (email, profile) mediante OAuth 2.0.

### 3.2 Términos Clave
- **F572 web**: Formulario oficial de deducciones de AFIP/ARCA (Sistema SIRADIG).
- **Token DRF**: Token criptográfico generado en `rest_framework.authtoken.models.Token`, necesario para que la extensión de Chrome consulte `/api/receipts/pending/`.
- **django-allauth**: Conjunto de aplicaciones estándar de Django para gestionar flujos de registro, login local y social accounts.
- **Token de Recuperación**: Token criptográfico generado por Django con expiración temporal basado en la sal del usuario y timestamp para un solo uso.

---

## 4. Historias de Usuario

### HU-AUTH-001 — Visualización de Landing Page y Propuesta de Valor
**Como** visitante no registrado o no autenticado,  
**quiero** visualizar una página de presentación clara al ingresar a la raíz del sitio (`/`),  
**para** comprender qué es SIRADIG Auto, saber que mis credenciales de AFIP nunca están en riesgo, y acceder fácilmente a los formularios de inicio de sesión o registro.

### HU-AUTH-002 — Registro de Cuenta con Email y Contraseña
**Como** nuevo usuario,  
**quiero** crear una cuenta ingresando mi correo electrónico y una contraseña segura,  
**para** disponer de un espacio personal donde gestionar mis deducciones y obtener mi token para la extensión.

### HU-AUTH-003 — Inicio de Sesión con Email y Contraseña
**Como** usuario registrado,  
**quiero** iniciar sesión con mi correo electrónico y contraseña,  
**para** acceder a mi dashboard privado de comprobantes.

### HU-AUTH-004 — Inicio de Sesión / Registro con Google OAuth 2.0
**Como** usuario que prefiere no recordar nuevas contraseñas,  
**quiero** iniciar sesión o registrarme con un solo clic usando mi cuenta de Google,  
**para** acceder de manera rápida y segura al sistema.

### HU-AUTH-005 — Recuperación de Contraseña Olvidada
**Como** usuario que olvidó su contraseña de acceso local,  
**quiero** solicitar un enlace de restablecimiento a mi correo electrónico,  
**para** definir una nueva contraseña de manera segura y recuperar el acceso a mi cuenta.

### HU-AUTH-006 — Cierre de Sesión Seguro
**Como** usuario autenticado,  
**quiero** cerrar mi sesión desde el dashboard,  
**para** proteger mi cuenta al utilizar un dispositivo compartido.

### HU-AUTH-007 — Sincronización Automática de Perfil y Token API
**Como** usuario autenticado (indistintamente de si me registré por email o por Google),  
**quiero** que mi perfil de Telegram y mi Token DRF para la extensión se creen automáticamente de inmediato,  
**para** poder configurar la extensión de Chrome y vincular el bot de Telegram sin pasos manuales de soporte.

---

## 5. Requisitos Funcionales (RF)

### Landing Page Pública
- **RF-AUTH-001 (Landing Pública)**: El sistema debe exponer en la ruta raíz (`/`) una página de aterrizaje (landing page) pública cuando la solicitud provenga de un usuario anónimo (no autenticado).
- **RF-AUTH-002 (Contenido de Landing)**: La landing page debe incluir:
  1. Identidad visual y nombre de la aplicación (SIRADIG Auto).
  2. Descripción clara de la propuesta de valor: carga automática de deducciones de indumentaria y equipamiento en el F572 web a partir de comprobantes enviados por Telegram.
  3. Declaración explícita de seguridad: *"SIRADIG Auto nunca solicita ni almacena tus claves de AFIP/ARCA; el inicio de sesión en AFIP se realiza exclusivamente en el portal oficial"*.
  4. Botones de acción directa hacia "Iniciar Sesión" (`/accounts/login/`) y "Crear Cuenta" (`/accounts/signup/`).
- **RF-AUTH-003 (Redirección de Usuario Autenticado en `/`)**: Si un usuario autenticado accede a la raíz (`/`), el sistema debe redirigirlo automáticamente con código HTTP 302 a `/dashboard/`.

### Autenticación Local (Email y Contraseña)
- **RF-AUTH-004 (Formulario de Registro)**: El sistema debe ofrecer una página de registro (`/accounts/signup/`) solicitando: correo electrónico, contraseña y confirmación de contraseña.
- **RF-AUTH-005 (Autenticación por Email)**: El sistema debe permitir iniciar sesión en `/accounts/login/` utilizando el correo electrónico y la contraseña como credenciales de acceso. Si el modelo subyacente `User` de Django utiliza `username`, el sistema debe gestionar automáticamente que el email sea único y actúe como identificador primario de autenticación (vía configuración de `allauth`: `ACCOUNT_AUTHENTICATION_METHOD = 'email'`, `ACCOUNT_EMAIL_REQUIRED = True`, `ACCOUNT_UNIQUE_EMAIL = True`).
- **RF-AUTH-006 (Validación de Robustez)**: La contraseña ingresada en el registro o reseteo debe ser validada contra los validadores estándar configurados en `AUTH_PASSWORD_VALIDATORS` (longitud mínima, no similitud con atributos, no numérica pura, no contraseña común). Ante incumplimiento, debe mostrar mensajes de error específicos en español.
- **RF-AUTH-007 (Rechazo de Credenciales Inválidas)**: Ante un intento de inicio de sesión con credenciales erróneas o cuenta inexistente, el sistema debe responder con un mensaje genérico de error de autenticación sin revelar si el correo existe o no en la base de datos.

### Autenticación Social (OAuth 2.0)
- **RF-AUTH-008 (Botón Google OAuth)**: En las pantallas de inicio de sesión (`/accounts/login/`) y registro (`/accounts/signup/`), el sistema debe presentar un botón accesible para "Continuar con Google".
- **RF-AUTH-009 (Flujo OAuth 2.0 Google)**: Al pulsar el botón de Google, el sistema debe iniciar el flujo de autorización OAuth 2.0 redirigiendo al endpoint oficial de Google con `scope` profile y email. Tras la autorización exitosa en Google, el callback debe autenticar al usuario en el sistema.
- **RF-AUTH-010 (Aprovisionamiento por Social Login)**: Si un usuario inicia sesión por primera vez mediante Google OAuth y su correo electrónico no existe en la base de datos, el sistema debe crear un nuevo registro de usuario vinculado a dicha identidad social. Si el correo ya existía (creado previamente de forma local), debe vincular la cuenta social sin duplicar usuarios ni generar errores de clave primaria.

### Recuperación de Contraseña
- **RF-AUTH-011 (Solicitud de Reseteo)**: El sistema debe proveer una ruta (`/accounts/password/reset/`) donde el usuario pueda ingresar su correo electrónico registrado para solicitar el restablecimiento de su contraseña.
- **RF-AUTH-012 (Generación y Envío de Enlace)**: Si el correo electrónico corresponde a una cuenta activa, el sistema debe generar un token criptográfico de un solo uso y enviar un correo electrónico con un enlace único hacia el formulario de restablecimiento (`/accounts/password/reset/key/<uidb64>-<token>/`).
- **RF-AUTH-013 (Anti-Enumeración de Emails)**: Al enviar el formulario de solicitud de reseteo, la interfaz debe mostrar un mensaje uniforme de confirmación (ej. *"Si el correo ingresado se encuentra registrado, recibirás las instrucciones en tu bandeja de entrada"*), impidiendo ataques de enumeración de cuentas.
- **RF-AUTH-014 (Establecimiento de Nueva Contraseña)**: Al ingresar al enlace con un token válido y no expirado, el sistema debe presentar un formulario para ingresar y confirmar la nueva contraseña. Al enviarla exitosamente, la contraseña debe ser actualizada y el token invalidado para futuros usos.
- **RF-AUTH-015 (Token Inválido o Expirado)**: Si el enlace contiene un token vencido o ya utilizado, el sistema debe rechazar la operación y mostrar un mensaje claro con opción de solicitar un nuevo enlace.

### Ciclo de Sesión y Protección de Rutas
- **RF-AUTH-016 (Cierre de Sesión)**: El sistema debe permitir al usuario autenticado cerrar su sesión actual vía `/accounts/logout/` (o POST con CSRF), invalidando la sesión de Django y redirigiéndolo a `/`.
- **RF-AUTH-017 (Protección de Dashboard)**: El acceso a `/dashboard/` y a cualquier subrecurso privado debe requerir autenticación obligatoria (`@login_required`). Si un visitante no autenticado intenta acceder, debe ser redirigido a `/accounts/login/?next=/dashboard/`.
- **RF-AUTH-018 (Redirección Post-Login)**: Al iniciar sesión exitosamente (vía local o Google OAuth), el sistema debe redirigir al usuario a la ruta indicada en el parámetro `next`, o por defecto a `/dashboard/`.

### Integración de Señales de Modelo
- **RF-AUTH-019 (Disparo de Señal de Creación)**: Ante cualquier creación de usuario (`post_save` con `created=True` en `settings.AUTH_USER_MODEL`), el receptor en `receipts/signals.py` debe ejecutarse garantizando la creación de una instancia de `UserProfile` (con `telegram_link_token` unívoco) y una instancia de `rest_framework.authtoken.models.Token`.

---

## 6. Reglas de Negocio (RN)

- **RN-AUTH-001 (Unicidad de Correo Electrónico)**: Dos cuentas de usuario no pueden compartir la misma dirección de correo electrónico.
- **RN-AUTH-002 (Aislamiento de Usuarios)**: Cada usuario solo puede ver y gestionar comprobantes asociados a su propia cuenta (`receipts = request.user.receipts.all()`). El token de DRF pertenece exclusivamente al usuario titular.
- **RN-AUTH-003 (Principio de No Almacenamiento Fiscal)**: Ni los formularios de registro ni los de login solicitarán campos relacionados con Clave Fiscal o CUIT de AFIP.
- **RN-AUTH-004 (Expiración de Tokens de Reseteo)**: Los tokens de recuperación de contraseña caducan tras el tiempo configurado en Django (por defecto 3 días / `PASSWORD_RESET_TIMEOUT = 259200` segundos, o configurable a 86400 segundos / 24 hs para mayor seguridad).
- **RN-AUTH-005 (Inmutabilidad de Token de Telegram tras Login Social)**: La vinculación o login con Google no debe alterar el `telegram_link_token` asignado en `UserProfile` ni regenerar el token DRF existente.

---

## 7. Contratos de Rutas, Vistas y Plantillas

### 7.1 Matriz de Rutas Web (URLs)
| Ruta URL | Nombre de URL | Método | Auth Requerida | Función / Vista | Redirección / Respuesta |
|---|---|---|---|---|---|
| `/` | `landing` | GET | Anónimo | Vista pública de Landing Page | Muestra `landing.html` (o 302 a `/dashboard/` si ya está autenticado) |
| `/dashboard/` | `dashboard` | GET | Requerida | `receipts.views.dashboard_home` | Muestra `receipts/dashboard.html` (o 302 a `/accounts/login/?next=/dashboard/`) |
| `/accounts/login/` | `account_login` | GET, POST | Anónimo | `allauth.account.views.LoginView` | Muestra formulario; POST válido redirige a `next` o `/dashboard/` |
| `/accounts/signup/` | `account_signup` | GET, POST | Anónimo | `allauth.account.views.SignupView` | Muestra formulario; POST válido crea usuario y redirige a `/dashboard/` |
| `/accounts/logout/` | `account_logout` | GET, POST | Requerida | `allauth.account.views.LogoutView` | Invalida sesión y redirige a `/` |
| `/accounts/password/reset/` | `account_reset_password` | GET, POST | Anónimo | `allauth.account.views.PasswordResetView` | Envía email con token; muestra confirmación |
| `/accounts/password/reset/done/` | `account_reset_password_done` | GET | Anónimo | `allauth.account.views.PasswordResetDoneView` | Vista informativa anti-enumeración |
| `/accounts/password/reset/key/<key>/` | `account_reset_password_from_key` | GET, POST | Anónimo | `allauth.account.views.PasswordResetFromKeyView` | Valida token y permite fijar nueva contraseña |
| `/accounts/password/reset/key/done/` | `account_reset_password_from_key_done` | GET | Anónimo | `allauth.account.views.PasswordResetFromKeyDoneView` | Informa reseteo exitoso con botón a login |
| `/accounts/google/login/` | `google_login` | POST | Anónimo | `allauth.socialaccount.providers.google.views.oauth2_login` | Inicia redirección al consentimiento de Google |
| `/accounts/google/login/callback/` | `google_callback` | GET | Anónimo | `allauth.socialaccount.providers.google.views.oauth2_callback` | Procesa código de autorización de Google |

### 7.2 Estructura de Plantillas Requeridas
1. `templates/landing.html`: Página pública moderna, estilizada con CSS responsivo (Bootstrap 5 o diseño limpio Tailwind/CSS nativo coherente con el dashboard), con sección Hero, 3 características destacadas (Telegram bot, OCR IA, Extensión F572), aviso de seguridad AFIP y barra de navegación con botones Login / Registro.
2. `templates/account/login.html`: Template personalizado para login que integra formulario email/contraseña, botón OAuth de Google y enlace a recuperación de contraseña.
3. `templates/account/signup.html`: Template para registro con email/contraseña y botón de registro con Google.
4. `templates/account/password_reset.html`: Formulario limpio para solicitar enlace de reseteo.
5. `templates/account/password_reset_done.html`: Pantalla de confirmación de envío.
6. `templates/account/password_reset_from_key.html`: Formulario para nueva contraseña.
7. `templates/account/password_reset_from_key_done.html`: Confirmación final de cambio.

---

## 8. Estados y Transiciones

### 8.1 Máquina de Estado del Usuario y Sesión
```
[Visitante Anónimo] 
       │
       ├── (Visita `/`) ──────────────> [Visualiza Landing Page]
       │
       ├── (POST `/accounts/signup/` exitoso) 
       │   o (Google OAuth Callback nuevo usuario)
       │         │
       │         └── [Disparo post_save: Crea UserProfile + Token DRF]
       │                   │
       │                   ▼
       ├── (POST `/accounts/login/` exitoso)
       │   o (Google OAuth Callback usuario existente)
       │         │
       │         ▼
       └───> [Usuario Autenticado (Sesión Activa)]
                   │
                   ├── (Visita `/` o `/dashboard/`) ──> [Visualiza Dashboard]
                   │
                   └── (POST `/accounts/logout/`) ────> [Visitante Anónimo] (Sesión destruida)
```

### 8.2 Ciclo de Vida del Token de Recuperación de Contraseña
| Origen | Evento y Precondición | Destino | Efectos Observables | Criterio |
|---|---|---|---|---|
| Contraseña Olvidada | Usuario solicita reseteo en `/accounts/password/reset/` con email válido. | Token Generado y Enviado | Se despacha correo con URL que contiene `uidb64` y `token`. Se muestra mensaje anti-enumeración. | CA-AUTH-006 |
| Token Generado | Usuario abre enlace antes de su expiración. | Formulario Habilitado | HTTP 200, muestra formulario de nueva contraseña. | CA-AUTH-007 |
| Formulario Habilitado | Usuario envía contraseña válida cumpliendo `AUTH_PASSWORD_VALIDATORS`. | Contraseña Actualizada | Password hash actualizado en BD. Token invalidado. Sesiones previas cerradas si aplica. Redirección a confirmación. | CA-AUTH-008 |
| Token Generado | Enlace abierto tras expiración o token manipulado. | Token Inválido / Rechazado | Muestra error informativo de enlace expirado; no permite cambio de clave. | CA-AUTH-009 |

---

## 9. Criterios de Aceptación (Dado / Cuando / Entonces)

### CA-AUTH-001 — Acceso a Landing Page para Visitantes Anónimos (RF-AUTH-001, RF-AUTH-002)
- **Dado** que un visitante no se encuentra autenticado en el sistema,
- **Cuando** navega a la URL raíz `GET /`,
- **Entonces** el servidor responde con código HTTP 200 y renderiza la landing page (`landing.html`),
- **Y** la página contiene la explicación de la herramienta, el aviso explícito de no manipulación de credenciales AFIP y enlaces visibles a `/accounts/login/` y `/accounts/signup/`.

### CA-AUTH-002 — Redirección Automática de Usuario Autenticado en la Raíz (RF-AUTH-003)
- **Dado** que un usuario ya ha iniciado sesión en el sistema,
- **Cuando** ingresa a la URL raíz `GET /`,
- **Entonces** el servidor responde con una redirección HTTP 302 hacia `/dashboard/`.

### CA-AUTH-003 — Registro Local Exitoso y Disparo de Señales (RF-AUTH-004, RF-AUTH-005, RF-AUTH-019)
- **Dado** un visitante no autenticado en la página de registro `/accounts/signup/`,
- **Cuando** completa el formulario con un email no registrado previamente y una contraseña que satisface los validadores de Django,
- **Entonces** el sistema crea un nuevo registro en `auth_user`,
- **Y** se ejecutan las señales de `receipts/signals.py` creando automáticamente su `UserProfile` (con un token de Telegram) y su `rest_framework.authtoken.models.Token`,
- **Y** el usuario queda con sesión iniciada y es redirigido a `/dashboard/`.

### CA-AUTH-004 — Inicio de Sesión Local con Email y Contraseña (RF-AUTH-005, RF-AUTH-018)
- **Dado** un usuario registrado con email `juan@ejemplo.com` y contraseña válida,
- **Cuando** ingresa sus credenciales en `/accounts/login/` y envía el formulario,
- **Entonces** el servidor valida las credenciales, inicia la sesión HTTP del usuario y responde con redirección HTTP 302 a `/dashboard/`.

### CA-AUTH-005 — Rechazo de Credenciales Inválidas (RF-AUTH-007)
- **Dado** un visitante en `/accounts/login/`,
- **Cuando** ingresa un email inexistente o una contraseña errónea y envía el formulario,
- **Entonces** el servidor responde con código HTTP 200 recargando el formulario,
- **Y** muestra un mensaje de error visible indicando que las credenciales son incorrectas, sin crear sesión.

### CA-AUTH-006 — Solicitud de Reseteo de Contraseña y Anti-Enumeración (RF-AUTH-011, RF-AUTH-012, RF-AUTH-013)
- **Dado** un usuario registrado en el sistema con email `pedro@ejemplo.com`,
- **Cuando** ingresa dicho email en `/accounts/password/reset/` y presiona "Restablecer contraseña",
- **Entonces** el sistema envía un correo electrónico (observable en la consola en dev o vía SMTP en prod) conteniendo la URL con el token de restablecimiento,
- **Y** la interfaz web responde mostrando la plantilla de confirmación genérica,
- **Y** si se ingresa un correo no registrado, se muestra exactamente la misma plantilla de confirmación sin disparar ningún envío.

### CA-AUTH-007 — Restablecimiento Exitoso de Contraseña (RF-AUTH-014, RF-AUTH-006)
- **Dado** que se generó un token válido de reseteo para el usuario,
- **Cuando** el usuario navega a la URL `/accounts/password/reset/key/<key>/` e ingresa una nueva contraseña válida que cumple los requisitos de longitud y complejidad,
- **Entonces** el sistema actualiza el hash de la contraseña en la base de datos,
- **Y** muestra la confirmación de restablecimiento exitoso con enlace a iniciar sesión con la nueva contraseña.

### CA-AUTH-008 — Rechazo de Token de Reseteo Inválido o Expirado (RF-AUTH-015)
- **Dado** un enlace de restablecimiento con un token previamente consumido o adulterado,
- **Cuando** el usuario intenta acceder a dicha URL o enviar una nueva contraseña,
- **Entonces** el sistema detecta la invalidez del token y presenta un mensaje indicando que el enlace es inválido o ha caducado, impidiendo cualquier alteración de la contraseña.

### CA-AUTH-009 — Registro / Login con Google OAuth 2.0 y Señales (RF-AUTH-008, RF-AUTH-009, RF-AUTH-010, RF-AUTH-019)
- **Dado** un usuario que selecciona "Continuar con Google" y autoriza la aplicación en Google,
- **Cuando** Google retorna el callback exitoso con un perfil verificado,
- **Entonces** el sistema autentica al usuario en Django,
- **Y** si era su primer ingreso, se verifica en base de datos la creación de su `User`, su `UserProfile` asociado y su `Token` de DRF vía `receipts/signals.py`,
- **Y** el usuario es redirigido a `/dashboard/`.

### CA-AUTH-010 — Cierre de Sesión (RF-AUTH-016)
- **Dado** un usuario autenticado en la plataforma,
- **Cuando** envía una solicitud de cierre de sesión a `/accounts/logout/`,
- **Entonces** la sesión es destruida en el backend,
- **Y** el usuario es redirigido a `/` (landing page pública).

### CA-AUTH-011 — Protección de Dashboard frente a Accesos Anónimos (RF-AUTH-017)
- **Dado** un usuario anónimo sin sesión activa,
- **Cuando** intenta acceder directamente a `GET /dashboard/`,
- **Entonces** el servidor intercepta la petición y responde con código HTTP 302 redirigiendo a `/accounts/login/?next=/dashboard/`.

---

## 10. Requisitos No Funcionales (RNF)

- **RNF-AUTH-001 (Seguridad Criptográfica y Contraseñas)**: Las contraseñas deben almacenarse utilizando el algoritmo hashing predeterminado de Django (`PBKDF2SHA256` con salt). Bajo ninguna circunstancia se almacenará texto plano.
- **RNF-AUTH-002 (Protección CSRF Obligatoria)**: Todos los formularios de autenticación (login, signup, logout, password reset) deben incluir de manera obligatoria la directiva `{% csrf_token %}` y ser validados por `django.middleware.csrf.CsrfViewMiddleware`.
- **RNF-AUTH-003 (Gestión Segura de Secretos OAuth)**: Las credenciales de Google OAuth (`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`) deben leerse exclusivamente desde variables de entorno (`.env` local, panel de Render en producción). Queda estrictamente prohibido commitear credenciales en el repositorio.
- **RNF-AUTH-004 (Configuración de Correo Electrónico por Entornos)**: El backend de correo debe ser desacoplado mediante la variable de entorno `EMAIL_BACKEND`:
  - Desarrollo local: `django.core.mail.backends.console.EmailBackend` (no requiere servidor SMTP real; imprime el email con el token directamente en la consola).
  - Producción: Configurable a backend SMTP (`django.core.mail.backends.smtp.EmailBackend`) con variables de entorno estándar (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`).
- **RNF-AUTH-005 (Compatibilidad de Dependencias y Pinning)**: La dependencia `django-allauth` ya se encuentra presente en `siradig_auto/requirements.txt` y en `INSTALLED_APPS` de `core/settings.py`. Para cumplir con el Principio #1 de la Constitución ("Todas las dependencias deben estar pinned en `requirements.txt`; sin paquetes anónimos"), debe fijarse una versión exacta compatible con Django 6.1 / Python 3.11 (ejemplo: `django-allauth==65.4.1` o la versión probada en el entorno).
- **RNF-AUTH-006 (Rendimiento y Usabilidad)**: La landing page debe cargar en menos de 1 segundo en conexiones estándar sin dependencias pesadas de Javascript externo. Debe ser completamente responsiva en dispositivos móviles y de escritorio.

---

## 11. Dependencias, Restricciones y Riesgos

### 11.1 Análisis del Repositorio Actual
- **`core/settings.py`**:
  - Ya incluye en `INSTALLED_APPS`: `'allauth'`, `'allauth.account'`, `'allauth.socialaccount'`, `'allauth.socialaccount.providers.google'`.
  - Ya incluye en `MIDDLEWARE`: `'allauth.account.middleware.AccountMiddleware'`.
  - Ya define `SITE_ID = 1`, `LOGIN_REDIRECT_URL = '/dashboard/'` y `AUTHENTICATION_BACKENDS`.
  - Configuración actual de `SOCIALACCOUNT_PROVIDERS['google']` ya lee `GOOGLE_OAUTH_CLIENT_ID` y `GOOGLE_OAUTH_CLIENT_SECRET`.
  - Configuración actual de email ya soporta `EMAIL_BACKEND` por variable de entorno defaulting a `console.EmailBackend`.
- **`core/urls.py`**:
  - Ya tiene mapeado `path('accounts/', include('allauth.urls'))`.
  - La ruta raíz actual es: `path('', RedirectView.as_view(url='dashboard/', permanent=False))`. **Impacto**: Esta ruta debe modificarse para que apunte a una vista inteligente de Landing Page (`landing_page_view`) que devuelva la plantilla si es anónimo o redirija a `dashboard/` si está autenticado.
- **`siradig_auto/requirements.txt`**:
  - Actualmente tiene `django-allauth` sin versión fija (`django-allauth`). Debe fijarse (pinned) conforme a la Constitución.

### 11.2 Riesgos Identificados
1. **Configuración de Sites (`django.contrib.sites`)**: `allauth` requiere que la entrada en la tabla `django_site` coincida con el dominio del servidor (ej. `localhost:8000` o el dominio de Render `siradig.onrender.com`). Si la tabla de Sites tiene por defecto `example.com`, el redirect de OAuth en Google puede fallar con `redirect_uri_mismatch`. Se debe contemplar la inicialización adecuada del Site o el uso de `SOCIALACCOUNT_ADAPTER` / comando de inicialización.
2. **Entrega de Emails en Producción**: Si en producción no se configuran variables SMTP, el reseteo de contraseña fallará silenciosamente o generará HTTP 500 al intentar enviar el email si el backend configurado no puede conectarse. Se mitigará documentando las variables en `.env.example`.

---

## 12. Trazabilidad de Requisitos

| Historia de Usuario | Requisito Funcional | Criterio de Aceptación | Componente / Archivo Previsto | Tipo de Verificación |
|---|---|---|---|---|
| HU-AUTH-001 | RF-AUTH-001, RF-AUTH-002 | CA-AUTH-001 | `receipts/views.py`, `templates/landing.html` | Test integración HTTP GET `/` (anónimo) |
| HU-AUTH-001 | RF-AUTH-003 | CA-AUTH-002 | `receipts/views.py`, `core/urls.py` | Test integración HTTP GET `/` (autenticado) |
| HU-AUTH-002 | RF-AUTH-004, RF-AUTH-005, RF-AUTH-006 | CA-AUTH-003 | `allauth`, `templates/account/signup.html` | Test integración POST `/accounts/signup/` |
| HU-AUTH-003 | RF-AUTH-005, RF-AUTH-007 | CA-AUTH-004, CA-AUTH-005 | `allauth`, `templates/account/login.html` | Test integración POST `/accounts/login/` |
| HU-AUTH-004 | RF-AUTH-008, RF-AUTH-009, RF-AUTH-010 | CA-AUTH-009 | `allauth.socialaccount`, mock OAuth | Test unitario / mock callback Google |
| HU-AUTH-005 | RF-AUTH-011, RF-AUTH-012, RF-AUTH-013 | CA-AUTH-006 | `allauth`, `templates/account/password_reset.html` | Test integración reseteo email + consola |
| HU-AUTH-005 | RF-AUTH-014, RF-AUTH-015 | CA-AUTH-007, CA-AUTH-008 | `allauth`, `templates/account/password_reset_from_key.html` | Test integración cambio de clave con token |
| HU-AUTH-006 | RF-AUTH-016 | CA-AUTH-010 | `core/settings.py`, `allauth` | Test integración POST `/accounts/logout/` |
| HU-AUTH-007 | RF-AUTH-019 | CA-AUTH-003, CA-AUTH-009 | `receipts/signals.py`, `receipts/models.py` | Test unitario post_save User -> UserProfile & Token |
| N/A (Seguridad) | RF-AUTH-017 | CA-AUTH-011 | `receipts/views.py` (`@login_required`) | Test integración GET `/dashboard/` anónimo |

---

## 13. Dudas Abiertas y Decisiones

| ID | Pregunta o Decisión | Impacto | Estado y Evidencia |
|---|---|---|---|
| **DEC-001** | Utilizar `django-allauth` como motor estándar de autenticación local, social y reseteo de claves. | Acelera desarrollo, mantiene consistencia con lo ya instalado en `core/settings.py` y minimiza código ad-hoc. | **Confirmada** (ya presente en `settings.py` y `urls.py`). |
| **DEC-002** | Google OAuth 2.0 como proveedor inicial para el MVP. | Define el alcance de integración social sin dispersión a otros proveedores no solicitados. | **Confirmada** (basada en la configuración existente en `settings.py`). |
| **DEC-003** | Mantener el disparo inmutable de `receipts/signals.py`. | Garantiza que cualquier usuario disponga de `UserProfile` y `Token` DRF para la extensión de inmediato. | **Confirmada** (verificado en `receipts/signals.py`). |
| **Q-AUTH-001** | ¿Se desea que el registro local requiera verificación de correo obligatoria antes de ingresar (`ACCOUNT_EMAIL_VERIFICATION = 'mandatory'`), o se prefiere permitir el ingreso inmediato para agilizar el MVP (`'optional'` o `'none'`)? | Si es obligatorio, el usuario no puede entrar hasta hacer clic en el email. Recomendación para MVP: `'none'` o `'optional'`, reservando el email para login y password reset. | **Pendiente de Aclaración** (Propuesta por defecto: `'none'` o `'optional'`). |
| **Q-AUTH-002** | Para el servicio de envío de correos en producción (Render), ¿se utilizará un proveedor transaccional SMTP específico (ej. Resend, SendGrid, Brevo, Gmail SMTP) o basta con dejar documentadas las variables de entorno genéricas `EMAIL_*` en `.env.example`? | Afecta configuración de despliegue en producción; en desarrollo local se usa `console.EmailBackend`. | **Pendiente de Aclaración** (Propuesta por defecto: variables SMTP genéricas). |
| **Q-AUTH-003** | En la Landing Page, ¿se prefiere mantener el estilo visual actual con Bootstrap 5 (mismo framework de `dashboard.html`) o se prefiere CSS personalizado puro / Tailwind CDN? | Coherencia visual con `receipts/templates/receipts/dashboard.html` que ya usa Bootstrap 5.3 y Bootstrap Icons. | **Pendiente de Aclaración** (Propuesta por defecto: Bootstrap 5.3 para paridad estética). |

---

## 14. Control de Calidad y Checklist

- [x] Problema, actores y resultado esperado están definidos.
- [x] Alcance y exclusiones no se contradicen (AFIP credentials explícitamente excluidas).
- [x] Los requisitos usan lenguaje inequívoco e identificadores estables (`RF-AUTH-*`, `RNF-AUTH-*`).
- [x] Cada RF tiene criterios de aceptación verificables en formato Dado/Cuando/Entonces (`CA-AUTH-*`).
- [x] Las historias de usuario están enlazadas con los requisitos y criterios correspondientes.
- [x] Se cubren errores (credenciales inválidas, tokens expirados), autorización y protección CSRF.
- [x] Los estados y transiciones son coherentes con las señales existentes (`receipts/signals.py`).
- [x] La constitución de SIRADIG Auto está respetada (Stack Django + DRF, cero credenciales AFIP, cobertura con pytest-django, pinning de dependencias).
- [x] No hay implementación de código realizada en esta fase (solo artefacto SDD).
- [x] La revisión está identificada (`REV-001`) y en estado `PENDIENTE_DE_APROBACION`.

---

## 15. Historial de Cambios

| Revisión | Fecha | Resumen de Cambios | Requisitos Afectados | Estado |
|---|---|---|---|---|
| `REV-001` | 2026-10-17 | Redacción inicial de la especificación SDD para Landing Page, Autenticación Local, Google OAuth 2.0 y Recuperación de Contraseña. | Todos (`RF-AUTH-001` a `019`) | `PENDIENTE_DE_APROBACION` |
