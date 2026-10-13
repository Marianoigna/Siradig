# Constitución del Proyecto SIRADIG Auto

## Stack & Arquitectura

1. **Stack base**: Django 6.1 + DRF + Python 3.11. Todas las dependencias deben estar pinned en `requirements.txt`; sin paquetes anónimos.
2. **Comunicación**: La extensión navegador consume la API DRF (`/api/receipts/`) mediante `TokenAuthentication`. Los canales WebSocket (`channels`) se usan para notificaciones de mensajería; el MVP usa Telegram pero la arquitectura es agnóstica (preparada para añadir WhatsApp futuramente).

## Calidad

3. **Herramientas**: Ruff + Black como linter/formateador obligatorios en CI. El archivo `pyproject.toml` es la única fuente de verdad para configuración de herramientas.
4. **Cobertura**: Mínimo 80% de cobertura en rutas críticas (webhook OCR, API receipts). Framework de pruebas: `pytest-django` (no `manage.py test`).

## Tests

5. **Alcance**: Tests unitarios en `receipts/tests.py` para modelos y servicios OCR; tests de integración para webhook y flujo de estados.
6. **Zero tolerance**: Todo cambio de estado en `Receipt` debe ir acompañado de un test que cubra la transición correspondiente (`pendiente_revision` → `pendiente_carga` → `cargado_en_siradig` | `error_carga`).

## Límites

7. **MVP**: Soporte exclusivo para la categoría "Gastos de Adquisición de Indumentaria y Equipamiento" (campo `categoria_gasto_siradig`). Otras categorías serán rechazadas en capa de validación.
8. **OCR**: Cadena de fallback configurable vía `MODELOS_CANDIDATOS` en `receipts/services/ocr.py`. Permite añadir modelos mejores/pagos futuros. Reglas: HTTP 404 = skip modelo; HTTP 429/503 = retry con backoff exponencial. MVP actual: `gemini-3.6-flash` → `gemini-3.5-flash-lite` → `gemini-3.5-flash`.
9. **Seguridad**: Sin credenciales AFIP/ARCA se almacenan ni se transmiten. El usuario siempre inicia sesión manualmente en el sitio oficial.
