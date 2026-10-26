# Registro de Seguimiento: Incremento 007 — Pasarela MercadoPago y Suscripciones

- **Identificador de Incremento:** `007-pasarela-mercadopago`
- **Especificación:** `specs/007-pasarela-mercadopago.md` (`REV-001`) — **Estado:** `APROBADA` (Aprobación formal del usuario)
- **Plan Técnico:** `specs/007-plan.md` — **Estado:** `PENDIENTE_DE_APROBACION`
- **Tareas Técnicas:** `specs/007-tasks.md` — **Estado:** `PENDIENTE_DE_APROBACION`
- **Fase Actual:** `Fase 2: Planificación y Tareas`
- **Última Actualización:** 2026-10-25

---

## 1. Historial de Fases y Aprobaciones

| Fecha | Fase | Evento / Hito | Responsable / Evidencia |
|---|---|---|---|
| 2026-10-25 | Fase 1: Especificación | Creación de especificación `007-pasarela-mercadopago.md` (`REV-001`) | Planner |
| 2026-10-25 | Fase 1: Especificación | **Aprobación formal de REV-001** | Usuario (Coordinador) |
| 2026-10-25 | Fase 2: Planificación | Redacción de `specs/007-plan.md` y `specs/007-tasks.md` | Planner |

---

## 2. Estado del Desglose de Tareas (Fase 3: Pendiente de inicio)

| Tarea | Descripción | Estado | Pruebas / Verificación |
|---|---|---|---|
| **T1** | Dependencias, settings y bootstrap de app `subscriptions` | `PENDIENTE` | `python manage.py check` |
| **T2** | Modelos `Plan`, `Suscripcion`, `Pago`, migraciones y admin | `PENDIENTE` | Migraciones aplicadas, admin verificado |
| **T3** | Servicio unificado de acceso (`trial` y suscripción activa) | `PENDIENTE` | Tests unitarios de acceso |
| **T4** | Integración del SDK MercadoPago (Preapproval API) | `PENDIENTE` | Tests con mocks de SDK MP |
| **T5** | Webhook con validación criptográfica HMAC e idempotencia | `PENDIENTE` | Tests de webhook con fixtures de firma |
| **T6** | Vistas y plantillas de planes, checkout y cancelación | `PENDIENTE` | Tests funcionales de vistas web |
| **T7** | Restricción de acceso en Telegram Webhook y API DRF | `PENDIENTE` | Tests de bloqueo en Telegram y DRF |
| **T8** | Banners de estado de suscripción/trial en Dashboard | `PENDIENTE` | Renderizado condicional en templates |
| **T9** | Suite integral de pruebas, cobertura >= 80% y linters | `PENDIENTE` | `pytest --cov`, `ruff check` |

---

## 3. Próximo Paso Recomendado

Presentar al usuario el plan técnico (`specs/007-plan.md`) y el desglose de tareas (`specs/007-tasks.md`) para su aprobación formal antes de dar inicio a la implementación (Fase 3).
