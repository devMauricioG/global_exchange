# Walkthrough Técnico: Módulo de Parametrización de Comisiones por Segmento y Motor de Cálculo de Tasas Netas (SCRUM-53)

## 📌 Resumen de la Tarea

* **Código Jira:** SCRUM-53
* **Título:** Módulo de parametrización de comisiones por segmento y motor de cálculo de tasas netas
* **Historia Principal:** SCRUM-47 (Configuración de Comisiones por Tipo de Cliente)
* **Sprint:** Sprint 2
* **Rama de Trabajo:** `feature/SCRUM-53`
* **Estado:** Finalizado

---

## 🎯 Objetivo y Alcance

El propósito de la tarea **SCRUM-53** es desarrollar la capa completa de lógica de negocio, motor matemático financiero, controladores web e interfaces interactivas para:
1. **Parametrización de Comisiones por Segmento (`SegmentCommission`):** Permitir a los administradores y operadores del sistema configurar tarifas porcentuales, cargos fijos y bonificaciones de margen cambiario (*spread discount*) para cada uno de los segmentos de cliente (`Minorista`, `Mayorista`, `Corporativo`, `VIP`).
2. **Motor Financiero de Cotizaciones y Tasas Netas (`RateCalculationService`):** Implementar las fórmulas matemáticas que calculan la tasa preferencial ajustada por spread, liquidan comisiones sobre el volumen operado y determinan el importe neto final a pagar o recibir según el tipo de operación (Compra / Venta) y el cliente activo.
3. **Simulador y Cotizador Interactivo:** Proveer una interfaz visual moderna y reactiva con gráficos y tarjetas analíticas, así como endpoints API REST JSON (`/rates/api/calculate/`) para cotizaciones dinámicas en tiempo real.

---

## 🏛️ Arquitectura y Componentes Implementados

### 1. Motor de Cálculo Financiero (`rates/services.py`)

Se desarrolló la clase de servicio `RateCalculationService` y la función de resolución de contexto `get_active_customer`:

* **`get_active_customer(request)`:**
  Resuelve de forma priorizada el cliente activo en la sesión mediante:
  1. Atributo inyectado en middleware (`request.active_customer`).
  2. Identificador persistido en sesión (`request.session['active_customer_id']`).
  3. Relación de asignación de usuario (:class:`~customers.models.CustomerUserAssignment`).
  4. Coincidencia por correo institucional/personal.
  5. Parámetro `cliente_id` (para roles administrativos/staff).

* **`RateCalculationService`:**
  * `get_commission_rule(segment_or_customer)`: Obtiene la regla activa para el segmento o retorna una regla virtual por defecto (0.00%).
  * `get_latest_exchange_rate(base_currency, target_currency)`: Recupera la cotización oficial más reciente entre dos divisas.
  * `calculate_quotation(exchange_rate, segment_or_customer, amount, operation_type, is_source_base)`:
    * **Operación BUY (Cliente compra divisa base):** La casa vende a `sell_rate`. El descuento sobre el spread acerca la tasa a favor del cliente:
      $$\text{effective\_rate} = \text{sell\_rate} - \left(\frac{\text{spread\_benefit}}{2}\right)$$
      $$\text{total\_commission} = (\text{gross\_target} \times \text{commission\_pct}) + \text{fixed\_fee}$$
      $$\text{net\_target\_amount} = \text{gross\_target} + \text{total\_commission}$$
    * **Operación SELL (Cliente vende divisa base):** La casa compra a `buy_rate`. La bonificación de spread incrementa la tasa que recibe el cliente:
      $$\text{effective\_rate} = \text{buy\_rate} + \left(\frac{\text{spread\_benefit}}{2}\right)$$
      $$\text{net\_target\_amount} = \max\left(0, \text{gross\_target} - \text{total\_commission}\right)$$
  * `calculate_quotation_by_codes(...)`: Helper de cotización directa por códigos ISO de divisas.

---

### 2. Formularios de Parametrización y Cotización (`rates/forms.py`)

* **`SegmentCommissionForm`:** Formulario basado en modelo con validaciones de rango (porcentajes de 0.00% a 100.00%, cargo fijo >= 0) y widgets integrados con el diseño corporativo.
* **`SegmentCommissionFilterForm`:** Formulario de filtrado interactivo para la grilla administrativa por segmento y estado.
* **`RateCalculatorForm`:** Formulario interactivo con soporte de par de cotizaciones, tipo de operación (Compra/Venta), monto a operar, selector de segmento/cliente de referencia y toggle de moneda base.

---

### 3. Vistas Basadas en Clases y Endpoints API (`rates/views.py`)

* **Gestión de Comisiones:**
  * `SegmentCommissionListView`: Grilla administrativa con métricas resumen (Total reglas, activas, comisión promedio y descuento de spread promedio).
  * `SegmentCommissionCreateView`: Alta de nueva regla con prevención de duplicados por segmento.
  * `SegmentCommissionUpdateView`: Edición de tarifas existentes.
  * `SegmentCommissionDeleteView`: Eliminación segura con aviso de impacto.
  * `SegmentCommissionDetailView`: Ficha analítica con tabla de simulación de impacto financiero para múltiples rangos de volumen ($100 a $50.000).
* **Simulador y Motor de Cotizaciones:**
  * `RateCalculatorView`: Vista interactiva con procesamiento dual (GET y POST) y desglose de liquidación en tiempo real.
  * `CalculateNetRateApiView`: Endpoint REST JSON (`/rates/api/calculate/`) para cálculos asíncronos en tiempo real.
  * `SegmentCommissionListApiView` & `SegmentCommissionDetailApiView`: Endpoints REST para consulta programática de parámetros tarifarios.

---

### 4. Plantillas HTML con Estética Premium (`templates/rates/`)

* `templates/rates/commission_list.html`: Grilla con badges por segmento (`MIN`, `MAY`, `COR`, `VIP`), métricas clave y acciones CRUD.
* `templates/rates/commission_form.html`: Formulario con inputs monetarios y porcentuales, explicaciones contextuales y alertas.
* `templates/rates/commission_detail.html`: Ficha analítica y matriz de impacto tarifario.
* `templates/rates/commission_confirm_delete.html`: Diálogo de confirmación con detalle de tarifas a eliminar.
* `templates/rates/rate_calculator.html`: Interfaz del cotizador con selector interactivo, card de total neto a pagar/recibir y desglose paso a paso de tasas y comisiones.
* `templates/base.html`: Barra de navegación actualizada con accesos directos a `🧮 Cotizador` y `💱 Comisiones`.

---

## 🧪 Pruebas Unitarias y Cobertura de Código

Se construyó una suite de pruebas exhaustiva en `rates/tests.py` con **71 casos de prueba** dedicados que evalúan:
1. **Modelos:** Creación, normalización de códigos ISO, unicidad de segmentos, validación de rangos, cálculo automático de spread y métodos auxiliares.
2. **Servicios (`RateCalculationService`):** Resolución de cliente activo, cotización de compra/venta, descuentos de spread por segmento, comisiones porcentuales y fijas, manejo de excepciones y validaciones de montos.
3. **Formularios:** Validación de campos y límites numéricos.
4. **Vistas CBVs:** Peticiones GET, POST, filtros, contexto y redirecciones.
5. **Endpoints API JSON:** Peticiones GET con query params, POST con payloads JSON, manejo de errores 400 y 404.

### Resultados de Ejecución:
* **Pruebas en `rates`:** 71 tests pasados (100% OK).
* **Cobertura en `rates`:** **97% de cobertura de código**.
* **Suite Total del Proyecto:** **167 tests ejecutados exitosamente (0 errores, 0 fallos)**.

---

## 🗂️ Registro de Archivos Creados y Modificados

| Componente | Archivo | Acción |
| :--- | :--- | :--- |
| **Servicios** | `rates/services.py` | Creado |
| **Formularios** | `rates/forms.py` | Creado |
| **Vistas y APIs** | `rates/views.py` | Creado |
| **Enrutamiento** | `rates/urls.py` | Creado |
| **Configuración** | `config/urls.py` | Modificado |
| **Modelos** | `rates/models.py` | Modificado |
| **Plantillas** | `templates/rates/commission_list.html` | Creado |
| **Plantillas** | `templates/rates/commission_form.html` | Creado |
| **Plantillas** | `templates/rates/commission_detail.html` | Creado |
| **Plantillas** | `templates/rates/commission_confirm_delete.html` | Creado |
| **Plantillas** | `templates/rates/rate_calculator.html` | Creado |
| **Navegación** | `templates/base.html` | Modificado |
| **Pruebas Unitarias** | `rates/tests.py` | Creado / Ampliado |
| **Documentación** | `docs/documentacion/Proyecto/SCRUM-53.md` | Creado |
| **Documentación** | `docs/documentacion/RESOLUCION_TAREAS_IA.md` | Modificado |
| **Documentación** | `docs/documentacion/Jira workflow/TAREAS.md` | Modificado |
| **Documentación** | `docs/chat_ia.md` | Modificado |
