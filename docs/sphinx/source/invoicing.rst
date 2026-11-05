invoicing package
=================

Módulo de Facturación Electrónica SIFEN / e-Kuatia (apps.invoicing).
Implementa la arquitectura desacoplada Strategy / Adapter para emisión,
cálculo matemático y consulta de Documentos Tributarios Electrónicos (SCRUM-117).
Agrega el modelo canónico ``FacturaElectronica`` y el servicio ``InvoiceService``
para persistencia del CDC, estados SIFEN, XML firmado y KuDE PDF (SCRUM-118).
Provee las vistas y endpoints para consulta, visualización y descarga de KuDE PDF y XML (SCRUM-119).
Implementa el cliente HTTP ``FacturaSeguraClient`` con protocolo de cuota estricto y
reserva blindada de 10 pruebas para la presentación en vivo (SCRUM-120).

Submodules
----------

apps.invoicing.apps module
--------------------------

.. automodule:: apps.invoicing.apps
   :members:
   :show-inheritance:
   :undoc-members:

apps.invoicing.calculators module
---------------------------------

.. automodule:: apps.invoicing.calculators
   :members:
   :show-inheritance:
   :undoc-members:

apps.invoicing.exceptions module
--------------------------------

.. automodule:: apps.invoicing.exceptions
   :members:
   :show-inheritance:
   :undoc-members:

apps.invoicing.types module
---------------------------

.. automodule:: apps.invoicing.types
   :members:
   :show-inheritance:
   :undoc-members:

apps.invoicing.client module
----------------------------

.. automodule:: apps.invoicing.client
   :members:
   :show-inheritance:
   :undoc-members:

apps.invoicing.providers.base module
------------------------------------

.. automodule:: apps.invoicing.providers.base
   :members:
   :show-inheritance:
   :undoc-members:

apps.invoicing.providers.mock module
------------------------------------

.. automodule:: apps.invoicing.providers.mock
   :members:
   :show-inheritance:
   :undoc-members:

apps.invoicing.providers.facturasegura module
---------------------------------------------

.. automodule:: apps.invoicing.providers.facturasegura
   :members:
   :show-inheritance:
   :undoc-members:

apps.invoicing.providers.factory module
---------------------------------------

.. automodule:: apps.invoicing.providers.factory
   :members:
   :show-inheritance:
   :undoc-members:

apps.invoicing.models module
----------------------------

.. automodule:: apps.invoicing.models
   :members:
   :show-inheritance:
   :undoc-members:

apps.invoicing.services module
------------------------------

.. automodule:: apps.invoicing.services
   :members:
   :show-inheritance:
   :undoc-members:

apps.invoicing.admin module
---------------------------

.. automodule:: apps.invoicing.admin
   :members:
   :show-inheritance:
   :undoc-members:

apps.invoicing.views module
---------------------------

.. automodule:: apps.invoicing.views
   :members:
   :show-inheritance:
   :undoc-members:

apps.invoicing.urls module
--------------------------

.. automodule:: apps.invoicing.urls
   :members:
   :show-inheritance:
   :undoc-members:


