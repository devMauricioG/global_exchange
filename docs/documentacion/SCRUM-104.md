# Tarea SCRUM-104: Suite de Pruebas Unitarias automatizadas para Pagos, MFA, Notificaciones y RBAC

## Descripción de la tarea
Escribir la suite completa de tests en PyUnit (`apps/payments/tests/`, `apps/transactions/tests/`, `apps/rates/tests/`, `apps/authentication/tests/`) con mocks de webhooks de Stripe/SIPAP, validación de señales de alertas y verificación de permisos HTTP 403.

## Trabajos Realizados

### 1. Pruebas Unitarias para Pagos y Pasarelas (`payments/tests.py`)
- **Mocks exhaustivos de Webhooks Stripe:**
  - Pruebas para eventos `checkout.session.completed` simulando payloads válidos, cabeceras de firma criptográfica (`HTTP_STRIPE_SIGNATURE`), verificación de idempotencia y prevención de reprocesamiento.
  - Validación de firmas inválidas (`SignatureVerificationError`) retornando HTTP 400.
  - Manejo de excepciones genéricas o payloads corruptos.
- **Mocks y Pruebas del Servicio Bancario SIPAP:**
  - Simulación de transferencias bancarias (`SipapService.simulate_transfer`) validando la generación de códigos SIPAP únicos (`SIPAP-...`) y estado `PENDIENTE`.
  - Conciliación de depósitos (`SipapService.confirm_deposit`) con verificación de transición a `COMPLETADO`.
  - Rechazo de transferencias (`SipapService.reject_transfer`) con motivo y auditoría.
  - Verificación de excepciones controladas (`ValidationError`) ante códigos de transferencia inexistentes o duplicados.
- **Modelos de Idempotencia y Trazabilidad:**
  - Pruebas unitarias para `PaymentWebhookEvent`: unicidad de `event_id`, persistencia de payload JSON, campos de auditoría y prevención de duplicados (`IntegrityError`).
  - Pruebas unitarias para `PaymentGatewayRecord`: estados de ciclo de vida (`PENDING`, `COMPLETED`, `FAILED`, `REFUNDED`), asociación con la orden y datos de respuesta.

### 2. Pruebas de Señales de Alertas y Notificaciones (`rates/tests.py`)
- **Evaluación de Señales de Tasas de Cambio:**
  - Pruebas para la señal `post_save` de `ExchangeRate` que evalúa disparadores de `ExchangeAlert`.
  - Verificación de condiciones de umbral: cotización sobre el umbral (`MAYOR_IGUAL`) y bajo el umbral (`MENOR_IGUAL`).
  - Validación de despacho de notificaciones a través del servicio `NotificationService`.
  - Cobertura de casos borde: alertas inactivas, alertas ya disparadas previamente, monedas no coincidentes y clientes sin usuario asignado.

### 3. Pruebas de Control de Acceso y RBAC HTTP 403 / Redirección (`authentication/tests.py`)
- **Aislamiento Multi-Inquilino e IDOR:**
  - Verificación de que usuarios sin el rol adecuado reciban respuesta HTTP 403 (Forbidden) o redirección protegida según la política de seguridad.
  - Validación de que usuarios no autenticados sean redirigidos al flujo OIDC/Login (`/oidc/authenticate/`) en transacciones y medios de pago.
  - Verificación de permisos para endpoints administrativos de monedas y tasas frente a usuarios con rol estándar.
  - Pruebas de claims MFA en tokens y perfiles de usuario.

### 4. Pruebas de Transacciones e Integración de Pasarelas (`transactions/tests.py`)
- **Aislamiento IDOR en Detalle y Checkout:**
  - Comprobación de que un usuario no puede visualizar transacciones de otro cliente (HTTP 404 / 403 según aislamiento estricto).
  - Cancelación de transacciones protegida contra acceso cruzado.
  - Cobertura de `TransactionReceiptView`: acceso autorizado al recibo formal por parte del titular y redirección para usuarios no autenticados.
  - Verificación de que transacciones en estado `COMPLETADA` no puedan ser canceladas.

### 5. Compatibilidad de Rutas `apps.*` (`apps/__init__.py`)
- Se configuró el módulo `apps/__init__.py` con soporte dinámico en `sys.modules` para permitir la importación y ejecución de tests bajo las rutas `apps.payments.tests`, `apps.transactions.tests`, `apps.rates.tests` y `apps.authentication.tests`.

## Resultados de las Pruebas
- Se ejecutó la suite completa de pruebas unitarias mediante `python manage.py test`:
  - **Total de pruebas ejecutadas:** 455 tests.
  - **Resultado:** 100% exitosos (`OK`), 0 fallos, 0 errores.
  - **Pruebas ejecutadas bajo alias `apps.*`:** 392 tests exitosos (`OK`).
  - Sin regresiones en los módulos preexistentes.
