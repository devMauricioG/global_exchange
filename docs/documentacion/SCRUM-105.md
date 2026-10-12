# Tarea SCRUM-105: Actualización de Documentación de Diseño UML (Clases, Paquetes, Casos de Prueba) y ERS v3.4

## Descripción de la tarea
Actualizar los documentos formales de ingeniería: diagrama de clases (`DIS_CLA_01`), diagrama de paquetes (`DIS_PAQ_01`), casos de prueba (`DIS_CPR_01`) y especificación ERS incorporando los módulos de pasarelas de pago, MFA, alertas y RBAC.

## Trabajos Realizados

### 1. Actualización de la Especificación de Requerimientos de Software (ERS v3.4)
- **Documento:** `docs/documentacion/Proyecto/EQUIPO_08_A_ERS.md`
- **Cambios Incorporados:**
  - **Acrónimos y Definiciones (1.2):** Incorporación de términos formales: Stripe, SIPAP (BCP), MFA/TOTP, Webhooks e Idempotencia.
  - **Requerimientos Funcionales (4.2):**
    - **RF-39 (Pasarela de Pago Internacional Stripe):** Generación de Checkout Sessions y verificación criptográfica de Webhooks.
    - **RF-40 (Conciliación Bancaria Local SIPAP):** Simulación, confirmación y rechazo auditado de transferencias interbancarias.
    - **RF-41 (Orquestación Transaccional y Liquidación Atómica):** Centralización de transiciones de pago en `TransactionService`.
    - **RF-42 (Vistas de Checkout y Pago en Línea):** Pantalla interactiva `TransactionPaymentCheckoutView` con temporizador de 5 minutos y modales asistidos.
    - **RF-43 (Autenticación Multifactor MFA / TOTP):** Verificación de claims `amr` y perfil de usuario con indicador de seguridad.
    - **RF-44 (Alertas de Cotización y Centro de Notificaciones):** Modelo `ExchangeAlert`, señal `post_save` en `ExchangeRate` y `NotificationService`.
    - **RF-45 (Módulo de Permisos RBAC y Menú Dinámico):** Mixins, decoradores de rol, respuestas HTTP 403 y navegación condicional.
  - **Requerimientos No Funcionales (4.3):**
    - `RNF-SEC-05`: Firma criptográfica en webhooks de pasarelas.
    - `RNF-SEC-06`: Garantía de idempotencia (*exactly-once*) con `PaymentWebhookEvent`.
    - `RNF-SEC-07`: Principio de menor privilegio y bloqueo estricto (HTTP 403 Forbidden).
  - **Historial de Cambios (7):** Asentada la versión 3.4 fechada el 12 de Octubre de 2026.

### 2. Actualización del Diagrama de Clases UML (`DIS_CLA_01`)
- **Documento:** `docs/documentacion/Proyecto/EQUIPO_88_B_DIS_CLA_01.md`
- **Clases y Modelos Formalizados:**
  - `PaymentWebhookEvent` (`payments.models`): Atributos de idempotencia, firma y procesamiento.
  - `PaymentGatewayRecord` (`payments.models`): Registro de órdenes en pasarela y métodos de transición.
  - `SipapTransferRecord` (`payments.models`): Entidad de liquidación interbancaria local.
  - `StripeService` y `SipapService` (`payments.services`): Métodos de pasarela y conciliación.
  - `Transaction` (`transactions.models`): Nuevos atributos `fecha_pago`, `referencia_externa_pago` y `pasarela_pago`.
  - `ExchangeAlert` (`rates.models`): Entidad de alertas de volatilidad con umbrales y condiciones.
  - `NotificationService` (`rates.services`): Despacho de avisos a usuarios asignados.
  - `RoleRequiredMixin` y decoradores (`authentication`): Control RBAC.
  - Diagrama Mermaid consolidado actualizado con todas las nuevas clases y multiplicidades.

### 3. Actualización del Diagrama de Paquetes y Arquitectura (`DIS_PAQ_01`)
- **Documento:** `docs/documentacion/Proyecto/EQUIPO_88_B_DIS_PAQ_01.md`
- **Módulos Actualizados:**
  - `apps.payments`: Catálogo bancario, medios de pago/cobro y pasarelas Stripe/SIPAP con sus endpoints de webhook y conciliación.
  - `apps.transactions`: Vista de checkout (`/pago/`), comprobante de recibo y orquestación en `TransactionService`.
  - `apps.rates`: Modelo de alertas, señal `post_save` y `NotificationService`.
  - `apps.authentication`: Módulo centralizado de permisos RBAC y claims MFA.
  - Catálogo de interfaces y tabla de dependencias inter-paquete ampliada.

### 4. Actualización de Casos de Prueba (`DIS_CPR_01`)
- **Documento:** `docs/documentacion/Proyecto/EQUIPO_88_B_DIS_CPR_01.md`
- **Nuevos Módulos de Casos de Prueba Formalizados:**
  - **Módulo 16 (CPR-STR):** 6 casos de prueba para Stripe Checkout, firmas inválidas (HTTP 400), idempotencia y `PaymentWebhookEvent`.
  - **Módulo 17 (CPR-SIP):** 6 casos de prueba para SIPAP: simulación, confirmación, rechazo controlado y validación de cuentas.
  - **Módulo 18 (CPR-ALT):** 6 casos de prueba para alertas de tipo de cambio, señales reactivas y despacho multi-usuario.
  - **Módulo 19 (CPR-RBC):** 7 casos de prueba para permisos RBAC (HTTP 403/redirect), claims MFA y prevención IDOR.
  - **Módulo 20 (CPR-ORQ):** 6 casos de prueba para liquidación atómica en `TransactionService`, discrepancia de montos y bloqueo en órdenes terminales.

## Verificación de Calidad y Pruebas
- Se ejecutó la batería completa de pruebas unitarias (`python manage.py test`):
  - **455 tests ejecutados.**
  - **455 tests exitosos (100% OK), 0 fallos, 0 errores.**
  - Compatibilidad total con la suite previa y sin regresiones.
