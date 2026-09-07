# MÓDULO 4: PRUEBAS DE SOFTWARE
## INGENIERÍA DE SOFTWARE II
### UNIVERSIDAD NACIONAL DE ASUNCIÓN - FACULTAD POLITÉCNICA

---

## CONTENIDO

1. **INTRODUCCIÓN** [cite: 5]
2. **ESTRATEGIAS DE PRUEBAS** [cite: 5]
   - 2.1. Prueba de unidad [cite: 5]
     - Consideraciones de las pruebas de unidad [cite: 5].
     - Procedimientos de prueba de unidad [cite: 5].
   - 2.2. Prueba de integración [cite: 5]
     - Integración descendente [cite: 5].
     - Pasos para la integración descendente [cite: 5].
     - Integración ascendente [cite: 5].
3. **NIVELES DE PRUEBA** [cite: 5]
4. **TÉCNICAS DE PRUEBA** [cite: 5]
   - 4.1. Basado en la intuición y experiencia del ingeniero de software [cite: 5]
     - 4.1.1. Ad hoc [cite: 5]
     - 4.1.2. Prueba exploratoria [cite: 5]
   - 4.2. Técnicas de entrada basadas en el dominio [cite: 5]
     - 4.2.1. Partición de equivalencia [cite: 5]
     - 4.2.2. Prueba por pares [cite: 5]
     - 4.2.3. Análisis de valor límite [cite: 5]
     - 4.2.4. Pruebas aleatorias [cite: 5]
   - 4.3. Técnicas basadas en códigos [cite: 5]
     - 4.3.1. Control de criterios basados en el flujo [cite: 5]
     - 4.3.2. Criterios basados en el flujo de datos [cite: 5]
     - 4.3.3. Modelos de referencia para código basado en pruebas [cite: 5]
   - 4.4. Técnicas basadas en fallas [cite: 5]
     - 4.4.1. Error Adivinando (Error Guessing) [cite: 5]
     - 4.4.2. Prueba de mutación [cite: 5]
   - 4.5. Técnicas basadas en el uso [cite: 5]
     - 4.5.1. Perfil operacional [cite: 5]
     - 4.5.2. Heurística de observación del usuario [cite: 5]
   - 4.6. Técnicas de prueba basadas en modelos [cite: 5]
     - 4.6.1. Tablas de decisiones [cite: 5]
     - 4.6.2. Máquinas de estado finito [cite: 5]
     - 4.6.3. Especificaciones formales [cite: 5]
     - 4.6.4. Modelos de flujo de trabajo [cite: 5]
   - 4.7. Técnicas basadas en la naturaleza de la Solicitud [cite: 5]
   - 4.8. Selección y combinación de técnicas [cite: 5]
     - 4.8.1. Combinando funcional y estructural [cite: 5]
     - 4.8.2. Determinista versus aleatorio [cite: 5]
5. **PROCESO DE LAS PRUEBAS** [cite: 5]
   - 5.1. Consideraciones prácticas [cite: 5]
     - 5.1.1. Actitudes y programación egoless [cite: 5]
     - 5.1.2. Guías para las pruebas [cite: 5]
     - 5.1.3. Gestión del proceso de las pruebas [cite: 5]
     - 5.1.4. Documentación y productos de las pruebas [cite: 5]
     - 5.1.5. Equipo de pruebas interno vs equipo externo [cite: 5]
     - 5.1.6. Estimación coste/esfuerzo y otras medidas [cite: 5]
     - 5.1.7. Finalización [cite: 5]
     - 5.1.8. Reutilización de pruebas y patrones de pruebas [cite: 5]
   - 5.2. Actividades de las pruebas [cite: 5]
     - 5.2.1. Planificación [cite: 5]
     - 5.2.2. Generación de casos de pruebas [cite: 5]
     - 5.2.3. Desarrollo en el entorno de pruebas [cite: 5]
     - 5.2.4. Ejecución [cite: 5]
     - 5.2.5. Evaluación de los resultados de las pruebas [cite: 5]
     - 5.2.6. Notificación de problemas/Diario de pruebas [cite: 5]
     - 5.2.7. Seguimiento de defectos [cite: 5]
6. **BIBLIOGRAFÍA** [cite: 5]

---

## 1. INTRODUCCIÓN

El proceso de software puede verse como una espiral [cite: 5]. Inicialmente, la ingeniería de sistemas define el papel del software y conduce al análisis de los requerimientos del mismo, donde se establecen los criterios de dominio, función, comportamiento, desempeño, restricciones y validación de información para el software [cite: 5]. Al avanzar hacia adentro a lo largo de la espiral, se llega al diseño y finalmente a la codificación [cite: 5]. Para desarrollar software de computadoras, se avanza en espiral hacia adentro (contra las manecillas del reloj) a lo largo de una línea que reduce el nivel de abstracción en cada vuelta [cite: 5].

La prueba de unidad comienza en el vértice de la espiral y se concentra en cada unidad (por ejemplo, componente, clase o un objeto de contenido de una webapp) del software como se implementó en el código fuente [cite: 5]. La prueba avanza al moverse hacia afuera a lo largo de la espiral, hacia la prueba de integración, donde el enfoque se centra en el diseño y la construcción de la arquitectura del software [cite: 5]. Al dar otra vuelta hacia afuera de la espiral, se encuentra la prueba de validación, donde los requerimientos establecidos como parte de su modelado se validan confrontándose con el software que se construyó [cite: 5]. Finalmente, se llega a la prueba del sistema, donde el software y otros elementos del sistema se prueban como un todo [cite: 5]. Para probar el software de cómputo, se avanza en espiral hacia afuera en dirección de las manecillas del reloj a lo largo de líneas que ensanchan el alcance de las pruebas con cada vuelta [cite: 5].

Al considerar el proceso desde un punto de vista procedural, las pruebas dentro del contexto de la ingeniería del software en realidad son una serie de cuatro pasos que se implementan de manera secuencial [cite: 5]:

1. **Prueba de unidad:** Las pruebas se enfocan en cada componente de manera individual, lo que garantiza que funcionan adecuadamente como unidad [cite: 5]. Esta prueba utiliza mucho de las técnicas de prueba que ejercitan rutas específicas en una estructura de control de componentes para asegurar una cobertura completa y la máxima detección de errores [cite: 5].
2. **Prueba de integración:** A continuación, los componentes deben ensamblarse o integrarse para formar el paquete de software completo [cite: 5]. La prueba de integración aborda los conflictos asociados con los problemas duales de verificación y construcción de programas [cite: 5]. Durante la integración, se usan más las técnicas de diseño de casos de prueba que se enfocan en entradas y salidas, aunque también pueden usarse técnicas que ejercitan rutas de programa específicas para asegurar la cobertura de las principales rutas de control [cite: 5].
3. **Prueba de validación:** Después de integrar (construir) el software, se realiza una serie de pruebas de orden superior [cite: 5]. Deben evaluarse criterios de validación (establecidos durante el análisis de requerimientos) [cite: 5]. La prueba de validación proporciona la garantía final de que el software cumple con todos los requerimientos informativos, funcionales, de comportamiento y de rendimiento [cite: 5].
4. **Prueba del sistema:** El último paso de la prueba de orden superior cae fuera de las fronteras de la ingeniería de software y en el contexto más amplio de la ingeniería de sistemas de cómputo [cite: 5]. El software, una vez validado, debe combinarse con otros elementos del sistema (por ejemplo, hardware, personal, bases de datos) [cite: 5]. La prueba del sistema verifica que todos los elementos se mezclan de manera adecuada y que se logra el funcionamiento/rendimiento global del sistema [cite: 5].

> **Definición Clave:** Las pruebas de software son en realidad un elemento diferente dentro del proceso de desarrollo [cite: 5]. Al contrario que el resto de actividades, su éxito radica en la detección de errores tanto en el propio proceso como en el software obtenido como resultado del mismo [cite: 5]. Una prueba de software es todo proceso orientado a comprobar la calidad del software mediante la identificación de fallos en el mismo, implicando necesariamente la ejecución del software [cite: 5].

---

## 2. ESTRATEGIAS DE PRUEBAS

Existen muchas estrategias que pueden usarse para probar el software [cite: 5]. En un extremo, puede esperarse hasta que el sistema esté completamente construido y luego realizar las pruebas sobre el sistema total, con la esperanza de encontrar errores (enfoque *big bang*, que simplemente no funciona y da como resultado software defectuoso) [cite: 5]. En el otro extremo, podrían realizarse pruebas diariamente, siempre que se construya alguna parte del sistema [cite: 5].

La estrategia de prueba que eligen la mayoría de los equipos de software se coloca entre los dos extremos: toma una visión incremental de las pruebas, comenzando con la de unidades de programa individuales, avanza hacia pruebas diseñadas para facilitar la integración de las unidades y culmina con pruebas que ejercitan el sistema construido [cite: 5].

### 2.1. Prueba de unidad

La prueba de unidad enfoca los esfuerzos de verificación en la unidad más pequeña del diseño de software: el componente o módulo de software [cite: 5]. Al usar la descripción del diseño de componente como guía, las rutas de control importantes se prueban para descubrir errores dentro de la frontera del módulo [cite: 5]. Las pruebas se enfocan en la lógica de procesamiento interno y de las estructuras de datos dentro de las fronteras de un componente y pueden realizarse en paralelo para múltiples componentes [cite: 5].

**Consideraciones de las pruebas de unidad:**
- **Interfaz del módulo:** Se prueba para garantizar que la información fluya de manera adecuada hacia y desde la unidad de software [cite: 5].
- **Estructuras de datos locales:** Se examinan para asegurar que los datos almacenados temporalmente mantienen su integridad durante la ejecución de un algoritmo [cite: 5].
- **Rutas independientes:** Todas las rutas independientes a través de la estructura de control se ejercitan para asegurar que todos los estatutos en un módulo se ejecuten al menos una vez [cite: 5].
- **Condiciones de frontera:** Se prueban para asegurar que el módulo opera adecuadamente en las fronteras establecidas para limitar el procesamiento [cite: 5].
- **Rutas de manejo de error:** Se ponen a prueba todas las rutas para el manejo de errores [cite: 5].

Entre los potenciales errores de manejo de errores están [cite: 5]:
1. Descripción de error ininteligible [cite: 5].
2. El error indicado no corresponde con el error encontrado [cite: 5].
3. La condición del error causa la intervención del sistema antes de manejar el error [cite: 5].
4. El procesamiento de excepción-condición es incorrecto [cite: 5].
5. La descripción del error no proporciona suficiente información para auxiliar en la localización de la causa [cite: 5].

**Procedimientos de prueba de unidad:**
Por lo general se consideran adjuntas al paso de codificación [cite: 5]. Puesto que un componente no es un programa independiente, con frecuencia debe desarrollarse **software controlador** (driver, un "programa principal" que acepta datos de caso de prueba, pasa datos e imprime resultados) y/o **de resguardo** (**representantes** o *stubs*, subprogramas tontos que sustituyen módulos subordinados) [cite: 5].

### 2.2. Prueba de integración

Las pruebas de integración son una técnica sistemática para construir la arquitectura del software mientras se llevan a cabo pruebas para descubrir errores asociados con la interfaz [cite: 5]. El objetivo es tomar los componentes probados de manera individual y construir una estructura de programa dictada por el diseño [cite: 5].

La **integración incremental** (antítesis del enfoque *big bang*) construye y prueba el software en pequeños incrementos, donde los errores son más fáciles de aislar y corregir [cite: 5].

- **Integración descendente:** Los módulos se integran al moverse hacia abajo a través de la jerarquía de control, comenzando con el módulo de control principal [cite: 5]. Los subordinados se incorporan en profundidad o anchura mediante el uso de representantes (*stubs*) que se van sustituyendo uno a uno por componentes reales [cite: 5].
- **Integración ascendente:** Comienza la construcción y la prueba con módulos atómicos (niveles inferiores) [cite: 5]. Puesto que se integran de abajo hacia arriba, la funcionalidad de los componentes subordinados siempre está disponible, eliminando la necesidad de representantes (*stubs*) y utilizando controladores (*drivers*) [cite: 5].

---

## 3. NIVELES DE PRUEBA

Las pruebas de software generalmente se realizan en diferentes niveles a lo largo del desarrollo y mantenimiento [cite: 5]. Los niveles se distinguen basados en el **objeto de prueba** (el objetivo: un solo módulo, un grupo de módulos o un sistema completo) o en su **propósito** [cite: 5]. Las tres etapas principales son: **unidad**, **integración** y **sistema** [cite: 5]. Estas etapas no implican ningún modelo de proceso en particular ni se asume que una sea más importante que las otras [cite: 5].

---

## 4. TÉCNICAS DE PRUEBA

Las técnicas de prueba intentan "romper" un programa siendo tan sistemáticas como sea posible en la identificación de entradas que produzcan comportamientos representativos [cite: 5]. 

Se clasifican habitualmente en:
- **Caja blanca** (o caja de cristal): Basadas en información sobre cómo se diseñó o codificó el software [cite: 5].
- **Caja negra:** Basadas solo en el comportamiento de entrada/salida del software [cite: 5].

### 4.1. Basado en la intuición y experiencia del ingeniero de software
- **4.1.1. Ad hoc:** Las pruebas se derivan basándose en la habilidad, intuición y experiencia del ingeniero de software con programas similares [cite: 5]. Útiles para identificar casos no fáciles de generar mediante técnicas formalizadas [cite: 5].
- **4.1.2. Prueba exploratoria:** Aprendizaje simultáneo, diseño de prueba y ejecución de prueba [cite: 5]. No están definidas de antemano en un plan, sino diseñadas, ejecutadas y modificadas dinámicamente [cite: 5].

### 4.2. Técnicas de entrada basadas en el dominio
- **4.2.1. Partición de equivalencia:** Parte el dominio de entrada en subconjuntos (clases de equivalencia) válidos e inválidos, tomando un conjunto representante de cada clase [cite: 5].
- **4.2.2. Prueba por pares (Pairwise):** Se derivan combinando valores interesantes para cada par de variables de entrada en lugar de considerar todas las combinaciones posibles (pertenece a pruebas combinatorias o $t$-wise) [cite: 5].
- **4.2.3. Análisis de valor límite:** Los casos de prueba se eligen en o cerca de los límites del dominio de entrada [cite: 5]. Incluye la prueba de robustez (fuera del dominio) [cite: 5].
- **4.2.4. Pruebas aleatorias:** Generadas puramente al azar dentro del dominio de entrada conocido [cite: 5]. El *fuzzing* (pruebas de fuzz) es una forma especial destinada a romper el software, usada frecuentemente para seguridad [cite: 5].

### 4.3. Técnicas basadas en códigos
- **4.3.1. Control de criterios basados en el flujo:** Cubrir declaraciones, bloques o combinaciones (ej. cobertura de sentencia, cobertura de sucursal, cobertura de ruta) [cite: 5].
- **4.3.2. Criterios basados en el flujo de datos:** Se anota el gráfico de flujo de control con información sobre cómo se definen y usan las variables (ej. todas las definiciones, todos los usos) [cite: 5].
- **4.3.3. Modelos de referencia (Diagramas de flujo):** Representación gráfica de la estructura de control de un programa mediante un grafo dirigido [cite: 5].

### 4.4. Técnicas basadas en fallas
- **4.4.1. Error Adivinando (Error Guessing):** Casos de prueba diseñados intentando anticipar fallas más plausibles basándose en la historia y experiencia [cite: 5].
- **4.4.2. Prueba de mutación:** Se ejecutan versiones ligeramente modificadas del programa (mutantes) para comprobar si los casos de prueba logran identificarlos ("matarlos") [cite: 5]. Se basa en el *efecto de acoplamiento* [cite: 5].

### 4.5. Técnicas basadas en el uso
- **4.5.1. Perfil operacional:** Reproduce el entorno operativo real asignando probabilidades a las entradas según su frecuencia de ocurrencia para inferir la confiabilidad futura [cite: 5].
- **4.5.2. Heurística de observación del usuario:** Métodos de inspección de usabilidad (tutoriales cognitivos, análisis de reclamos, observación de campo, pensar en voz alta, encuestas) [cite: 5].

### 4.6. Técnicas de prueba basadas en modelos
Utilizan representaciones resumidas/formales del software o sus requisitos (tablas de decisiones, máquinas de estado finito, especificaciones formales como TTCN-3, modelos de flujo de trabajo) [cite: 5].

### 4.7. Técnicas basadas en la naturaleza de la Solicitud
Derivación basada en el tipo específico de software (orientado a objetos, componentes, web, concurrente, protocolos, tiempo real, crítico para la seguridad, servicios, código abierto, empotrado) [cite: 5].

### 4.8. Selección y combinación de técnicas
- **4.8.1. Combinando funcional y estructural:** Complementarias, usan diferentes fuentes de información y detectan distintos problemas [cite: 5].
- **4.8.2. Determinista versus aleatorio:** Selección según criterios formales o extracción aleatoria [cite: 5].

---

## 5. PROCESO DE LAS PRUEBAS

El proceso de pruebas integra conceptos, estrategias, técnicas y medidas bajo una gestión controlada [cite: 5].

### 5.1. Consideraciones prácticas
- **5.1.1. Actitudes y programación egoless:** Fomentar colaboración y evitar que los programadores se obsesionen con la propiedad del código impidiendo reportar fallos [cite: 5].
- **5.1.2. Guías para las pruebas:** Pruebas basadas en riesgos o basadas en situaciones (escenarios) [cite: 5].
- **5.1.3. Gestión del proceso:** Organizar actividades, personas y herramientas integradas en el ciclo de vida (estándar IEEE 1074) [cite: 5].
- **5.1.4. Documentación y productos:** Uso del estándar IEEE 829-98 (Plan de pruebas, especificación de diseño, casos de prueba, diario de pruebas, informe de problemas) [cite: 5].
- **5.1.5. Equipo de pruebas interno vs externo:** Decisiones basadas en costos, planificación, madurez y criticidad [cite: 5].
- **5.1.6. Estimación coste/esfuerzo y medidas:** Controlar recursos invertidos, número de casos ejecutados/superados, análisis de causa raíz [cite: 5].
- **5.1.7. Finalización:** Criterios para decidir cuándo las pruebas son suficientes (cobertura de código, densidad de errores, análisis costo/riesgo) [cite: 5].
- **5.1.8. Reutilización y patrones de pruebas:** Repositorios de material de pruebas bajo control de gestión de configuraciones [cite: 5].

### 5.2. Actividades de las pruebas
1. **Planificación:** Coordinación de personal, instalaciones, equipos y gestión de líneas base [cite: 5].
2. **Generación de casos de pruebas:** Según nivel y técnicas, controlados por gestión de configuraciones [cite: 5].
3. **Desarrollo en el entorno de pruebas:** Entorno compatible que facilite scripts y almacenamiento de resultados [cite: 5].
4. **Ejecución:** Seguir principios científicos con pasos claros y reproducibles sobre versiones definidas [cite: 5].
5. **Evaluación de resultados:** Determinar si el comportamiento fue el esperado, analizando ruido frente a errores reales [cite: 5].
6. **Notificación de problemas / Diario de pruebas:** Registro en diario de pruebas y sistema de notificación de problemas / incidentes [cite: 5].
7. **Seguimiento de defectos:** Análisis de cuándo y cómo se introdujeron los defectos para mejorar procesos de ingeniería [cite: 5].

---

## 6. BIBLIOGRAFÍA

- Kimmel, P. (2007). *Manual de UML*. México: McGraw-Hill [cite: 5].
- Rumbaugh, J., Jacobson, I., & Booch, G. (2005). *El Lenguaje Unificado de Modelado Manual de Referencia* (2ª ed.). Madrid: Pearson [cite: 5].
- Rumbaugh, J., Jacobson, I., & Booch, G. (1999). *El lenguaje Unificado de Modelado Manual de Referencia*. Madrid: Pearson Educación, S.A [cite: 5].
- Kimmel, P. (2010). *Manual de UML*. México: McGraw-Hill Interamericana [cite: 5].
- Campderrich, F. B. (2003). *Ingeniería del software*. España: Editorial UOC [cite: 5].
- Gutierrez, C. C. (2011). *Casos prácticos de UML*. España: Editorial Complutense [cite: 5].
- Weitzenfeld, A. (2005). *Ingeniería de Software Orientada a Objetos con UML, Java e Internet*. México City: Cengage Learning [cite: 5].
