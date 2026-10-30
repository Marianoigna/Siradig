# Registro de Seguimiento: Incremento 007 — Pasarela MercadoPago y Suscripciones

- **Identificador de Incremento:** `007-pasarela-mercadopago`
- **Especificación:** `specs/007-pasarela-mercadopago.md` (`REV-002`) — **Estado:** `APROBADO`
- **Plan Técnico:** `specs/007-plan.md` — **Estado:** `APROBADO`
- **Tareas Técnicas:** `specs/007-tasks.md` — **Estado:** `APROBADO`
- **Fase Actual:** `Fase 6: Cierre del Incremento`
- **Estado General:** `COMPLETADO`
- **Última Actualización:** 2026-10-29

---

## 1. Historial de Fases y Aprobaciones

| Fecha | Fase | Evento / Hito | Responsable / Evidencia |
|---|---|---|---|
| 2026-10-25 | Fase 1: Especificación | Creación de especificación `007-pasarela-mercadopago.md` (`REV-001`) | Planner |
| 2026-10-25 | Fase 1: Especificación | **Aprobación formal de REV-001** | Usuario (Coordinador) |
| 2026-10-25 | Fase 2: Planificación | Redacción de `specs/007-plan.md` y `specs/007-tasks.md` | Planner |
| 2026-10-29 | Fase 1 / Fase 2: Actualización SDD | Actualización a `REV-002`: Tarifa oficial fijada en **8.999 ARS**, provisión de plan con `POST /preapproval_plan`, comando Django `ensure_mercadopago_plan`, suscripción a tópicos canónicos de MP (`subscription_preapproval`, `subscription_authorized_payment`, `subscription_preapproval_plan`) y verificación estricta de firma HMAC según manifest oficial (`id:[data.id];request-id:[x-request-id];ts:[ts];`). | Planner |
| 2026-10-29 | Fase 3: Implementación | Ejecución y culminación de tareas T1 a T10 | Implementer |
| 2026-10-29 | Fase 4: Revisión Independiente | Revisión técnica independiente: **APROBADO** (121 tests passed, 85% cobertura global, ruff en verde) | Reviewer |
| 2026-10-29 | Fase 6: Cierre | Cierre formal del incremento 007 | Planner / Coordinador |

---

## 2. Estado del Desglose de Tareas

| Tarea | Descripción | Estado | Pruebas / Verificación |
|---|---|---|---|
| **T1** | Dependencias, settings con tarifa $8999 y bootstrap de app `subscriptions` | `COMPLETADA` | `python manage.py check` |
| **T2** | Modelos `Plan` (con `gateway_plan_id` y default $8999), `Suscripcion`, `Pago`, migraciones y admin | `COMPLETADA` | Migraciones aplicadas, admin verificado |
| **T3** | Servicio unificado de acceso (`trial` de 15 días y suscripción activa) | `COMPLETADA` | Tests unitarios de acceso |
| **T4** | Integración del SDK Mercado Pago (Preapproval mensual $8999 ARS y cancelación) | `COMPLETADA` | Tests con mocks de SDK MP |
| **T5** | Management command `ensure_mercadopago_plan` para provisionar plan en Mercado Pago | `COMPLETADA` | Tests de ejecución de comando con mocks de MP |
| **T6** | Webhook oficial de Mercado Pago con validación HMAC canónica e idempotencia | `COMPLETADA` | Tests de webhook con fixtures de firma oficial |
| **T7** | Vistas y plantillas de planes ($8.999 ARS), checkout, retornos y cancelación | `COMPLETADA` | Tests funcionales de vistas web |
| **T8** | Restricción de acceso en Telegram Webhook y API DRF | `COMPLETADA` | Tests de bloqueo en Telegram y DRF |
| **T9** | Banners de estado de suscripción/trial en Dashboard | `COMPLETADA` | Renderizado condicional en templates |
| **T10** | Suite integral de pruebas, cobertura >= 80% y linters | `COMPLETADA` | `pytest --cov` (121 tests, 85% cov), `ruff check` OK |

---

## 3. Próximo Paso Recomendado

Incremento finalizado y verificado con éxito. Listo para despliegue / integración en la rama principal o definición del siguiente incremento funcional por parte del Coordinador.

