# AGENTS.md — SIRADIG Auto

## ¿Qué es este proyecto?

SIRADIG Auto es una aplicación web para automatizar la carga de deducciones en el **Formulario 572 web (SIRADIG)** de AFIP/ARCA. Los usuarios envían fotos de sus comprobantes por Telegram, un OCR con IA extrae los datos, y quedan disponibles en un dashboard para cargarlos en SIRADIG con ayuda de una extensión de navegador.

**Problema que busca resolver:** Los usuarios de AFIP deben completar manualmente formularios extensos (el F572) con datos de cada comprobante. Esto es lento, propenso a errores y consume mucho tiempo. SIRADIG Auto automatiza la extracción de datos mediante IA (Gemini OCR) y los estructura para que una extensión de navegador los inyecte directamente en el formulario, reduciendo drásticamente el tiempo de carga.

**Principio clave de seguridad:** esta app **nunca** maneja las credenciales de AFIP/ARCA. El usuario siempre inicia sesión manualmente en el sitio oficial.

## Inicio rápido

```powershell
python -m venv venv; .\venv\Scripts\Activate.ps1
pip install -r siradig_auto\requirements.txt
copy .env.example .env  # luego completar secretos (nunca hacer commit de .env)
python manage.py migrate
python manage.py ensuresuperuser  # comando personalizado
python manage.py runserver
```

## Archivos clave y límites

| Ruta | Qué hace |
|---|---|
| `core/settings.py` | Fuente única de verdad para variables de entorno (`django-environ` lee `.env`). Todas las claves viven aquí. |
| `core/urls.py` | Enrutador raíz de URL — las rutas están namespaced bajo `/api/`, `/telegram/webhook/`, etc. |
| `receipts/views.py` | Vista del dashboard, manejador de webhook de Telegram, ListAPIView y UpdateAPIView de DRF. |
| `receipts/models.py` | `Receipt` (comprobante) + `UserProfile` (vinculación de Telegram). |
| `receipts/serializers.py` | Serializadores de DRF usados por la extensión del navegador. |
| `receipts/services/ocr.py` | OCR de Gemini — reintentos entre modelos fallback con backoff exponencial. |
| `receipts/management/commands/` | `ensure_superuser` y `set_telegram_webhook` — comandos de admin/deploy personalizados. |
| `extension/manifest.json` | Manifest V3 de la extensión del navegador (en desarrollo). |

## Notas de arquitectura

- **Ninguna credencial de AFIP toca esta app.** El usuario siempre inicia sesión manualmente en el sitio oficial. Este backend solo almacena datos de comprobantes extraídos por OCR.
- **Cascada de modelos OCR** (`receipts/services/ocr.py`): prueba `gemini-3.6-flash` → `gemini-3.5-flash-lite` → `gemini-3.5-flash`. Un error 404 significa "modelo deprecado" (saltar al siguiente); 429/503 desencadenan reintentos con backoff exponencial.
- **Autenticación de la extensión**: usa TokenAuthentication de DRF (`rest_framework.authtoken`). El token se crea automáticamente en el primer login vía `receipts/signals.py`.
- **Máquina de estados de Receipt**: `pendiente_revision` → `pendiente_carga` → (`cargado_en_siradig` | `error_carga`).
- Solo una categoría de SIRADIG está soportada en el MVP: **"Gastos de Adquisición de Indumentaria y Equipamiento"** (campo `categoria_gasto_siradig`).

## Comandos y trampas

| Comando | Nota |
|---|---|
| `python manage.py migrate` | Ejecutar después de cada cambio de dependencia. |
| `python manage.py collectstatic --noinput` | Requerido antes de cualquier despliegue en producción (Render lo hace). |
| `python manage.py ensuresuperuser` | Comando personalizado de `receipts/management/commands/`. |
| `python manage.py set_telegram_webhook <url>` | Registra el webhook en Telegram; el paso de build de Render lo llama. |
| `gunicorn core.wsgi:application --timeout 120` | Comando de inicio de Render (timeout largo necesario para subidas de imágenes grandes). |

### Particularidades del desarrollo local

- La base de datos predetermina a `db.sqlite3` cuando `DATABASE_URL` no está establecida. Para paridad con producción, establezca `DATABASE_URL=postgresql://...`.
- Los archivos de medios van a `media/` (ignorados por git). Los archivos estáticos van a `staticfiles/` (también ignorados).
- Las plantillas viven en `receipts/templates/receipts/dashboard.html`.
- Los orígenes permitidos de CORS están controlados por la variable de entorno `CORS_ALLOWED_ORIGINS` (vacía por defecto).

## Despliegue (Render)

El despliegue ocurre automáticamente vía push a GitHub → Blueprint de Render (`render.yaml`). El paso de build se ejecuta en orden:

1. `pip install -r siradig_auto/requirements.txt`
2. `python manage.py collectstatic --noinput`
3. `python manage.py migrate`
4. `python manage.py ensure_superuser`
5. `python manage.py set_telegram_webhook https://siradig.onrender.com/telegram/webhook/`

Las variables de entorno se sincronizan desde el panel de Render o se generan aleatoriamente (`SECRET_KEY`). Nunca codificar secretos directamente.

## Estilo / convenciones (ninguna configurada)

No hay linter, formateador, verificador de tipos o framework de pruebas configurado actualmente. Cuando se añadan más tarde:
- Preferir **ruff** para linting/formateo (compatible con Django).
- Usar **pytest-django** para pruebas (no `manage.py test` — pytest tiene mejores fixtures y soporte para skip/xfail).
- Considerar **pre-commit** hooks una vez elegida la tooling.

```powershell
python -m venv venv; .\venv\Scripts\Activate.ps1
pip install -r siradig_auto\requirements.txt
copy .env.example .env  # then fill secrets (never commit .env)
python manage.py migrate
python manage.py ensuresuperuser  # custom command
python manage.py runserver
```

## Key files & boundaries

| Path | What it does |
|---|---|
| `core/settings.py` | Single source of truth for env vars (`django-environ` reads `.env`). All keys live here. |
| `core/urls.py` | Root URL router — routes are namespaced under `/api/`, `/telegram/webhook/`, etc. |
| `receipts/views.py` | Dashboard view, Telegram webhook handler, DRF ListAPIView & UpdateAPIView. |
| `receipts/models.py` | `Receipt` (comprobante) + `UserProfile` (Telegram linking). |
| `receipts/serializers.py` | DRF serializers used by the browser extension. |
| `receipts/services/ocr.py` | Gemini OCR — retries across fallback models with exponential backoff. |
| `receipts/management/commands/` | `ensure_superuser` and `set_telegram_webhook` — custom admin/deploy commands. |
| `extension/manifest.json` | Browser extension Manifest V3 (in development). |

## Architecture notes

- **No AFIP credentials touch this app.** User logs into AFIP manually in their browser. This backend only stores OCR-extracted receipt data.
- **OCR model cascade** (`receipts/services/ocr.py`): tries `gemini-3.6-flash` → `gemini-3.5-flash-lite` → `gemini-3.5-flash`. A 404 means "model deprecated" (skip to next); 429/503 trigger exponential backoff retry.
- **Extension auth**: uses DRF TokenAuthentication (`rest_framework.authtoken`). Token is auto-created on first login via `receipts/signals.py`.
- **Receipt state machine**: `pendiente_revision` → `pendiente_carga` → (`cargado_en_siradig` | `error_carga`).
- Only one SIRADIG category is supported in MVP: **"Gastos de Adquisición de Indumentaria y Equipamiento"** (`categoria_gasto_siradig` field).

## Commands & gotchas

| Command | Note |
|---|---|
| `python manage.py migrate` | Run after every dependency change. |
| `python manage.py collectstatic --noinput` | Required before any production deploy (Render does this). |
| `python manage.py ensuresuperuser` | Custom command from `receipts/management/commands/`. |
| `python manage.py set_telegram_webhook <url>` | Registers the webhook in Telegram; Render build step calls this. |
| `gunicorn core.wsgi:application --timeout 120` | Render start command (long timeout needed for large image uploads). |

### Local dev quirks

- Database defaults to `db.sqlite3` when `DATABASE_URL` is unset. For Prod parity, set `DATABASE_URL=postgresql://...`.
- Media files land in `media/` (ignored by git). Static files in `staticfiles/` (also ignored).
- Templates live in `receipts/templates/receipts/dashboard.html`.
- CORS allowed origins controlled by `CORS_ALLOWED_ORIGINS` env var (empty by default).

## Deploy (Render)

Deploy happens automatically via GitHub push → Render Blueprint (`render.yaml`). Build step runs in order:

1. `pip install -r siradig_auto/requirements.txt`
2. `python manage.py collectstatic --noinput`
3. `python manage.py migrate`
4. `python manage.py ensure_superuser`
5. `python manage.py set_telegram_webhook https://siradig.onrender.com/telegram/webhook/`

Env vars are synced from Render panel or generated at random (`SECRET_KEY`). Never hard-code secrets.

## Style / conventions (none configured)

No linter, formatter, typechecker, or test framework is currently configured. When adding them later:
- Prefer **ruff** for linting/formatting (Django-compatible).
- Use **pytest-django** for tests (not `manage.py test` — pytest has better fixtures and skip/xfail support).
- Consider **pre-commit** hooks once tooling is chosen.
