"""
Módulo de pruebas automatizadas para la aplicación de clientes.

Contiene las suites de pruebas unitarias y de integración para validar el modelo
:class:`~customers.models.Cliente`, las vistas web basadas en clases (CBVs)
y los endpoints de la API REST (JSON).
"""

import json
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from .models import Cliente, CustomerUserAssignment

User = get_user_model()


class ClienteModelTests(TestCase):
    """
    Suite de pruebas unitarias para el modelo :class:`~customers.models.Cliente`.

    Verifica la instanciación de entidades, asignación de valores por defecto,
    métodos de representación y restricciones de unicidad en la base de datos.
    """

    def test_cliente_creation(self):
        """Valida la creación exitosa de un cliente con todos sus campos y segmentación."""
        cliente = Cliente.objects.create(
            nombre='Acme Corporation',
            documento_ruc='80012345-6',
            correo='contacto@acme.com',
            telefono='+595 21 123456',
            segmentacion=Cliente.Segmentacion.CORPORATIVO,
        )
        self.assertEqual(cliente.nombre, 'Acme Corporation')
        self.assertEqual(cliente.segmentacion, 'COR')
        self.assertTrue(cliente.is_active)
        self.assertEqual(str(cliente), 'Acme Corporation (Corporativo)')

    def test_cliente_default_values(self):
        """Verifica que los valores por defecto (segmentación MINORISTA y activo True) se asignen correctamente."""
        cliente = Cliente.objects.create(
            nombre='Juan Pérez',
            documento_ruc='1234567',
            correo='juan@correo.com',
        )
        self.assertEqual(cliente.segmentacion, Cliente.Segmentacion.MINORISTA)
        self.assertTrue(cliente.is_active)
        self.assertEqual(str(cliente), 'Juan Pérez (Minorista)')

    def test_cliente_unique_documento_ruc(self):
        """Asegura que no sea posible registrar dos clientes con el mismo documento/RUC."""
        Cliente.objects.create(
            nombre='Cliente 1',
            documento_ruc='111111-1',
            correo='cliente1@test.com',
        )
        with self.assertRaises(IntegrityError):
            Cliente.objects.create(
                nombre='Cliente 2',
                documento_ruc='111111-1',
                correo='cliente2@test.com',
            )

    def test_cliente_unique_correo(self):
        """Asegura que no sea posible registrar dos clientes con la misma dirección de correo electrónico."""
        Cliente.objects.create(
            nombre='Cliente A',
            documento_ruc='222222-1',
            correo='duplicado@test.com',
        )
        with self.assertRaises(IntegrityError):
            Cliente.objects.create(
                nombre='Cliente B',
                documento_ruc='333333-1',
                correo='duplicado@test.com',
            )


class ClienteWebViewsTests(TestCase):
    """
    Suite de pruebas para las vistas basadas en clases (CBVs) de la interfaz web de clientes.

    Cubre el acceso autenticado, renderizado de listados, filtros por segmento y RUC,
    búsqueda general y operaciones CRUD mediante formularios web.
    """

    def setUp(self):
        """Inicializa el entorno de prueba creando un usuario autenticado y un catálogo diverso de clientes."""
        self.user = User.objects.create_user(
            username='operador',
            email='operador@globalexchange.com',
            password='Password123!',
        )
        self.client_auth = Client()
        self.client_auth.force_login(self.user)

        self.c_min = Cliente.objects.create(
            nombre='Carlos Minorista',
            documento_ruc='1001-MIN',
            correo='carlos@min.com',
            telefono='0981111111',
            segmentacion=Cliente.Segmentacion.MINORISTA,
            is_active=True,
        )
        self.c_may = Cliente.objects.create(
            nombre='Distribuidora Mayorista S.A.',
            documento_ruc='2002-MAY',
            correo='ventas@mayorista.com',
            telefono='0982222222',
            segmentacion=Cliente.Segmentacion.MAYORISTA,
            is_active=True,
        )
        self.c_cor = Cliente.objects.create(
            nombre='Banco Corporativo S.A.',
            documento_ruc='3003-COR',
            correo='contacto@corporativo.com',
            telefono='0983333333',
            segmentacion=Cliente.Segmentacion.CORPORATIVO,
            is_active=False,
        )
        self.c_vip = Cliente.objects.create(
            nombre='Inversiones VIP',
            documento_ruc='4004-VIP',
            correo='ceo@vip.com',
            telefono='0984444444',
            segmentacion=Cliente.Segmentacion.VIP,
            is_active=True,
        )

    def test_list_view_login_required(self):
        """Verifica que un usuario no autenticado sea redirigido al intentar acceder al listado de clientes."""
        unauthenticated_client = Client()
        response = unauthenticated_client.get(reverse('customers:cliente-list'))
        self.assertEqual(response.status_code, 302)

    def test_list_view_authenticated(self):
        """Verifica que un usuario autenticado pueda visualizar el listado completo de clientes."""
        response = self.client_auth.get(reverse('customers:cliente-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Carlos Minorista')
        self.assertContains(response, 'Distribuidora Mayorista S.A.')
        self.assertContains(response, 'Banco Corporativo S.A.')
        self.assertContains(response, 'Inversiones VIP')

    def test_list_view_filter_by_segmentation(self):
        """Verifica que el filtrado por código de segmentación (MIN, VIP) devuelva únicamente los registros coincidentes."""
        response_min = self.client_auth.get(
            reverse('customers:cliente-list'),
            {'segmentacion': 'MIN'}
        )
        self.assertEqual(response_min.status_code, 200)
        self.assertContains(response_min, 'Carlos Minorista')
        self.assertNotContains(response_min, 'Distribuidora Mayorista S.A.')
        self.assertNotContains(response_min, 'Inversiones VIP')

        response_vip = self.client_auth.get(
            reverse('customers:cliente-list'),
            {'segmentacion': 'VIP'}
        )
        self.assertEqual(response_vip.status_code, 200)
        self.assertContains(response_vip, 'Inversiones VIP')
        self.assertNotContains(response_vip, 'Carlos Minorista')

    def test_list_view_filter_by_documento_ruc(self):
        """Verifica el filtrado exacto o parcial por el campo documento_ruc."""
        response = self.client_auth.get(
            reverse('customers:cliente-list'),
            {'documento_ruc': '2002-MAY'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Distribuidora Mayorista S.A.')
        self.assertNotContains(response, 'Carlos Minorista')

    def test_list_view_search_q(self):
        """Verifica la búsqueda abierta por texto 'q' sobre el nombre o teléfono del cliente."""
        response = self.client_auth.get(
            reverse('customers:cliente-list'),
            {'q': 'Banco'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Banco Corporativo S.A.')
        self.assertNotContains(response, 'Carlos Minorista')

        response_tel = self.client_auth.get(
            reverse('customers:cliente-list'),
            {'q': '0984444444'}
        )
        self.assertEqual(response_tel.status_code, 200)
        self.assertContains(response_tel, 'Inversiones VIP')

    def test_list_view_filter_by_is_active(self):
        """Verifica el filtrado según el estado de actividad (is_active=false)."""
        response_inactive = self.client_auth.get(
            reverse('customers:cliente-list'),
            {'is_active': 'false'}
        )
        self.assertEqual(response_inactive.status_code, 200)
        self.assertContains(response_inactive, 'Banco Corporativo S.A.')
        self.assertNotContains(response_inactive, 'Carlos Minorista')

    def test_detail_view(self):
        """Verifica el renderizado de la vista de detalle de un cliente."""
        response = self.client_auth.get(
            reverse('customers:cliente-detail', kwargs={'pk': self.c_vip.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inversiones VIP')
        self.assertContains(response, '4004-VIP')
        self.assertContains(response, 'ceo@vip.com')

    def test_create_view_get(self):
        """Verifica que la petición GET al formulario de creación devuelva código 200."""
        response = self.client_auth.get(reverse('customers:cliente-create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nuevo Cliente')

    def test_create_view_post_success(self):
        """Verifica la creación exitosa de un cliente a través del formulario web."""
        payload = {
            'nombre': 'Nuevo Cliente Prueba',
            'documento_ruc': '999999-9',
            'correo': 'nuevo@cliente.com',
            'telefono': '0985555555',
            'segmentacion': 'COR',
            'is_active': True,
        }
        response = self.client_auth.post(reverse('customers:cliente-create'), data=payload)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Cliente.objects.filter(documento_ruc='999999-9').exists())

    def test_create_view_post_duplicate_error(self):
        """Verifica el manejo de errores de validación al intentar registrar un documento duplicado."""
        payload = {
            'nombre': 'Cliente Duplicado',
            'documento_ruc': self.c_min.documento_ruc,
            'correo': 'otro@correo.com',
            'telefono': '098111',
            'segmentacion': 'MIN',
        }
        response = self.client_auth.post(reverse('customers:cliente-create'), data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

    def test_update_view(self):
        """Verifica la actualización de los datos de un cliente mediante el formulario de edición."""
        payload = {
            'nombre': 'Carlos Minorista Actualizado',
            'documento_ruc': self.c_min.documento_ruc,
            'correo': 'carlos_nuevo@min.com',
            'telefono': '0989999999',
            'segmentacion': 'MAY',
            'is_active': True,
        }
        response = self.client_auth.post(
            reverse('customers:cliente-update', kwargs={'pk': self.c_min.pk}),
            data=payload
        )
        self.assertEqual(response.status_code, 302)
        self.c_min.refresh_from_db()
        self.assertEqual(self.c_min.nombre, 'Carlos Minorista Actualizado')
        self.assertEqual(self.c_min.segmentacion, 'MAY')

    def test_delete_view(self):
        """Verifica la eliminación definitiva de un cliente tras confirmar la acción en la vista de borrado."""
        pk = self.c_min.pk
        response = self.client_auth.post(
            reverse('customers:cliente-delete', kwargs={'pk': pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Cliente.objects.filter(pk=pk).exists())


class ClienteAPIEndpointsTests(TestCase):
    """
    Suite de pruebas para los endpoints de la API REST (JSON) de Clientes.

    Cubre operaciones de listado, filtros, creación (POST), consulta por PK y por RUC,
    actualizaciones totales (PUT) y parciales (PATCH), y borrado (DELETE).
    """

    def setUp(self):
        """Prepara datos iniciales de prueba para las llamadas API."""
        self.c1 = Cliente.objects.create(
            nombre='Tech Solutions',
            documento_ruc='12345-1',
            correo='info@tech.com',
            telefono='021123456',
            segmentacion=Cliente.Segmentacion.CORPORATIVO,
            is_active=True,
        )
        self.c2 = Cliente.objects.create(
            nombre='Kiosko Central',
            documento_ruc='67890-2',
            correo='kiosko@central.com',
            telefono='021654321',
            segmentacion=Cliente.Segmentacion.MINORISTA,
            is_active=False,
        )

    def test_api_list_clients(self):
        """Verifica que el endpoint GET /customers/api/ devuelva todos los clientes en formato JSON."""
        response = self.client.get(reverse('customers:api-cliente-list-create'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 2)
        self.assertEqual(len(data['results']), 2)

    def test_api_filter_by_segmentation(self):
        """Verifica el filtrado de clientes en la API por el parámetro ?segmentacion=COR."""
        response = self.client.get(
            reverse('customers:api-cliente-list-create'),
            {'segmentacion': 'COR'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['nombre'], 'Tech Solutions')
        self.assertEqual(data['results'][0]['segmentacion_display'], 'Corporativo')

    def test_api_filter_by_documento_ruc(self):
        """Verifica el filtrado en la API por el parámetro ?documento_ruc=67890-2."""
        response = self.client.get(
            reverse('customers:api-cliente-list-create'),
            {'documento_ruc': '67890-2'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['nombre'], 'Kiosko Central')

    def test_api_filter_by_search_q(self):
        """Verifica la búsqueda general en la API usando el parámetro ?q=kiosko."""
        response = self.client.get(
            reverse('customers:api-cliente-list-create'),
            {'q': 'kiosko'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['documento_ruc'], '67890-2')

    def test_api_filter_by_is_active(self):
        """Verifica el filtrado en la API por estado de actividad ?is_active=true."""
        response = self.client.get(
            reverse('customers:api-cliente-list-create'),
            {'is_active': 'true'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['nombre'], 'Tech Solutions')

    def test_api_create_client_success(self):
        """Verifica la creación de un nuevo cliente vía POST enviando un cuerpo JSON estructurado."""
        payload = {
            'nombre': 'Supermercado El Sol',
            'documento_ruc': '55555-5',
            'correo': 'contacto@elsol.com',
            'telefono': '0981999888',
            'segmentacion': 'MAY',
            'is_active': True,
        }
        response = self.client.post(
            reverse('customers:api-cliente-list-create'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['cliente']['nombre'], 'Supermercado El Sol')
        self.assertEqual(data['cliente']['segmentacion'], 'MAY')
        self.assertTrue(Cliente.objects.filter(documento_ruc='55555-5').exists())

    def test_api_create_client_validation_error(self):
        """Verifica que el envío de datos inválidos (RUC duplicado, segmento erróneo) retorne HTTP 400."""
        payload = {
            'nombre': 'Cliente Invalido',
            'documento_ruc': self.c1.documento_ruc,
            'correo': 'correo_invalido',
            'segmentacion': 'XYZ',
        }
        response = self.client.post(
            reverse('customers:api-cliente-list-create'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('details', data)

    def test_api_create_client_invalid_json(self):
        """Verifica que un JSON malformado devuelva HTTP 400 Bad Request."""
        response = self.client.post(
            reverse('customers:api-cliente-list-create'),
            data='{invalid_json',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_api_get_detail_by_id(self):
        """Verifica la recuperación de un cliente individual por su ID (PK)."""
        response = self.client.get(
            reverse('customers:api-cliente-detail', kwargs={'pk': self.c1.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], self.c1.pk)
        self.assertEqual(data['nombre'], 'Tech Solutions')

    def test_api_get_detail_by_documento_ruc(self):
        """Verifica la recuperación de un cliente individual utilizando su documento_ruc."""
        response = self.client.get(
            reverse('customers:api-cliente-by-doc', kwargs={'documento_ruc': self.c1.documento_ruc})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['documento_ruc'], self.c1.documento_ruc)

    def test_api_get_detail_not_found(self):
        """Verifica que la consulta de un cliente inexistente devuelva HTTP 404 Not Found."""
        response = self.client.get(
            reverse('customers:api-cliente-detail', kwargs={'pk': 999999})
        )
        self.assertEqual(response.status_code, 404)

    def test_api_update_put(self):
        """Verifica la actualización completa de un cliente mediante el método HTTP PUT."""
        payload = {
            'nombre': 'Tech Solutions S.A.',
            'documento_ruc': self.c1.documento_ruc,
            'correo': 'nuevo_tech@tech.com',
            'telefono': '021999999',
            'segmentacion': 'VIP',
            'is_active': True,
        }
        response = self.client.put(
            reverse('customers:api-cliente-detail', kwargs={'pk': self.c1.pk}),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.nombre, 'Tech Solutions S.A.')
        self.assertEqual(self.c1.segmentacion, 'VIP')

    def test_api_update_patch(self):
        """Verifica la actualización parcial de atributos de un cliente mediante el método HTTP PATCH."""
        payload = {
            'telefono': '0987111222',
            'segmentacion': 'VIP',
        }
        response = self.client.patch(
            reverse('customers:api-cliente-detail', kwargs={'pk': self.c1.pk}),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.telefono, '0987111222')
        self.assertEqual(self.c1.segmentacion, 'VIP')
        self.assertEqual(self.c1.nombre, 'Tech Solutions')

    def test_api_delete(self):
        """Verifica la eliminación de un cliente a través del endpoint HTTP DELETE."""
        pk = self.c1.pk
        response = self.client.delete(
            reverse('customers:api-cliente-detail', kwargs={'pk': pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Cliente.objects.filter(pk=pk).exists())


class ClienteKeycloakVinculationTests(TestCase):
    """
    Suite de pruebas para la lógica de vinculación automática de identidades Keycloak (claim sub).
    """

    def setUp(self):
        """Inicializa usuarios y fichas de prueba."""
        self.user = User.objects.create_user(
            username='carlos_kc',
            email='carlos.keycloak@globalexchange.com',
            first_name='Carlos',
            last_name='Keycloak',
            password='Password123!',
        )
        self.sub_uuid = 'f47ac10b-58cc-4372-a567-0e02b2c3d479'

    def test_vincular_cliente_por_sub_existente(self):
        """Verifica que si ya existe un cliente con el sub registrado, se asocie con el usuario."""
        cliente_previo = Cliente.objects.create(
            nombre='Carlos Previo',
            documento_ruc='99999-1',
            correo='carlos.previo@test.com',
            keycloak_id=self.sub_uuid,
        )
        from customers.services import vincular_cliente_keycloak

        cliente = vincular_cliente_keycloak(
            user=self.user,
            keycloak_id=self.sub_uuid,
            email='carlos.keycloak@globalexchange.com',
        )

        self.assertIsNotNone(cliente)
        self.assertEqual(cliente.pk, cliente_previo.pk)
        self.assertEqual(cliente.keycloak_id, self.sub_uuid)
        self.assertTrue(cliente.assignments.filter(user=self.user, is_primary_representative=True, is_active=True).exists())
        self.assertEqual(cliente.representante_principal.user, self.user)

    def test_vincular_cliente_por_correo_existente(self):
        """Verifica que una ficha existente creada por un admin se vincule automáticamente por email."""
        cliente_admin = Cliente.objects.create(
            nombre='Carlos Registrado Previamente',
            documento_ruc='88888-2',
            correo='carlos.keycloak@globalexchange.com',
            keycloak_id=None,
        )
        from customers.services import vincular_cliente_keycloak

        cliente = vincular_cliente_keycloak(
            user=self.user,
            keycloak_id=self.sub_uuid,
            email='carlos.keycloak@globalexchange.com',
        )

        self.assertIsNotNone(cliente)
        self.assertEqual(cliente.pk, cliente_admin.pk)
        self.assertEqual(cliente.keycloak_id, self.sub_uuid)
        self.assertTrue(cliente.assignments.filter(user=self.user, is_primary_representative=True, is_active=True).exists())
        self.assertEqual(cliente.representante_principal.user, self.user)

    def test_crear_y_vincular_cliente_automatico(self):
        """Verifica que se cree una nueva ficha de cliente automáticamente si no existía previamente."""
        from customers.services import vincular_cliente_keycloak

        nuevo_user = User.objects.create_user(
            username='nuevo_cliente',
            email='nuevo.cliente@globalexchange.com',
            first_name='Ana',
            last_name='Gómez',
        )
        nuevo_sub = 'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d'
        claims = {
            'sub': nuevo_sub,
            'email': 'nuevo.cliente@globalexchange.com',
            'given_name': 'Ana',
            'family_name': 'Gómez',
            'preferred_username': 'nuevo_cliente',
        }

        cliente = vincular_cliente_keycloak(
            user=nuevo_user,
            keycloak_id=nuevo_sub,
            claims=claims,
        )

        self.assertIsNotNone(cliente)
        self.assertEqual(cliente.nombre, 'Ana Gómez')
        self.assertEqual(cliente.correo, 'nuevo.cliente@globalexchange.com')
        self.assertEqual(cliente.keycloak_id, nuevo_sub)
        self.assertTrue(cliente.assignments.filter(user=nuevo_user, is_primary_representative=True, is_active=True).exists())
        self.assertEqual(cliente.representante_principal.user, nuevo_user)
        self.assertTrue(cliente.is_active)

    def test_signal_keycloak_user_authenticated_dispatched(self):
        """Verifica que al emitir la señal keycloak_user_authenticated se ejecute la vinculación."""
        from customers.signals import keycloak_user_authenticated

        signal_sub = 'signal-sub-uuid-1234'
        keycloak_user_authenticated.send(
            sender=self.__class__,
            user=self.user,
            keycloak_id=signal_sub,
            claims={'sub': signal_sub, 'email': self.user.email},
        )

        cliente = Cliente.objects.filter(keycloak_id=signal_sub).first()
        self.assertIsNotNone(cliente)
        self.assertTrue(cliente.assignments.filter(user=self.user, is_primary_representative=True, is_active=True).exists())
        self.assertEqual(cliente.representante_principal.user, self.user)

    def test_signal_user_logged_in_triggers_vinculation(self):
        """Verifica que la señal nativa user_logged_in sincronice la ficha existente."""
        from django.contrib.auth.signals import user_logged_in
        from django.test import RequestFactory

        cliente_existente = Cliente.objects.create(
            nombre='Usuario Logeado',
            documento_ruc='77777-3',
            correo='login.test@globalexchange.com',
        )
        login_user = User.objects.create_user(
            username='login_user',
            email='login.test@globalexchange.com',
        )
        factory = RequestFactory()
        request = factory.get('/')

        user_logged_in.send(
            sender=login_user.__class__,
            request=request,
            user=login_user,
        )

        cliente_existente.refresh_from_db()
        self.assertTrue(cliente_existente.assignments.filter(user=login_user, is_primary_representative=True, is_active=True).exists())
        self.assertEqual(cliente_existente.representante_principal.user, login_user)



class ClienteModelValidationTests(TestCase):
    """
    Suite de pruebas unitarias para las validaciones de campo del modelo
    :class:`~customers.models.Cliente`.

    Verifica restricciones de longitud máxima, formato de correo electrónico,
    validez del catálogo de segmentación y auto-poblado de timestamps.
    """

    def test_segmentacion_choices_valid(self):
        """Verifica que todos los valores del catálogo de segmentación (MIN, MAY, COR, VIP) sean aceptados."""
        for code, _ in Cliente.Segmentacion.choices:
            cliente = Cliente(
                nombre=f'Cliente {code}',
                documento_ruc=f'DOC-{code}',
                correo=f'{code.lower()}@test.com',
                segmentacion=code,
            )
            try:
                cliente.full_clean()
            except Exception as exc:
                self.fail(
                    f'full_clean() rechazó segmentacion={code!r} inesperadamente: {exc}'
                )

    def test_segmentacion_invalid_value(self):
        """Verifica que un valor fuera del catálogo de segmentación genere un ValidationError."""
        from django.core.exceptions import ValidationError

        cliente = Cliente(
            nombre='Cliente Malo',
            documento_ruc='BAD-SEG',
            correo='bad@test.com',
            segmentacion='XXX',
        )
        with self.assertRaises(ValidationError):
            cliente.full_clean()

    def test_correo_field_validates_format(self):
        """Verifica que un correo electrónico mal formado sea rechazado por full_clean()."""
        from django.core.exceptions import ValidationError

        cliente = Cliente(
            nombre='Email Invalido',
            documento_ruc='BADRUC-1',
            correo='esto_no_es_un_correo',
        )
        with self.assertRaises(ValidationError) as ctx:
            cliente.full_clean()
        self.assertIn('correo', ctx.exception.message_dict)

    def test_documento_ruc_max_length(self):
        """Verifica que un documento/RUC de más de 20 caracteres sea rechazado por full_clean()."""
        from django.core.exceptions import ValidationError

        cliente = Cliente(
            nombre='RUC Largo',
            documento_ruc='A' * 21,
            correo='ruc_largo@test.com',
        )
        with self.assertRaises(ValidationError) as ctx:
            cliente.full_clean()
        self.assertIn('documento_ruc', ctx.exception.message_dict)

    def test_nombre_max_length(self):
        """Verifica que un nombre de más de 150 caracteres sea rechazado por full_clean()."""
        from django.core.exceptions import ValidationError

        cliente = Cliente(
            nombre='N' * 151,
            documento_ruc='LONG-NAME-RUC',
            correo='longname@test.com',
        )
        with self.assertRaises(ValidationError) as ctx:
            cliente.full_clean()
        self.assertIn('nombre', ctx.exception.message_dict)

    def test_timestamps_auto_populated(self):
        """Verifica que created_at y updated_at se rellenen automáticamente al crear el registro."""
        cliente = Cliente.objects.create(
            nombre='Timestamps Test',
            documento_ruc='TS-001',
            correo='timestamps@test.com',
        )
        self.assertIsNotNone(cliente.created_at)
        self.assertIsNotNone(cliente.updated_at)
        self.assertEqual(cliente.created_at.date(), cliente.updated_at.date())


class ClienteSegmentacionContextTests(TestCase):
    """
    Suite de pruebas de integración para el contexto enriquecido de
    :class:`~customers.views.ClienteListView`.

    Valida la presencia de conteos KPI por segmento, el estado de filtros activos
    y el comportamiento de la paginación cuando el número de registros supera el límite.
    """

    def setUp(self):
        """Crea un usuario autenticado y un conjunto diverso de clientes de prueba."""
        self.user = User.objects.create_user(
            username='ctx_tester',
            email='ctx@globalexchange.com',
            password='Password123!',
        )
        self.client_auth = Client()
        self.client_auth.force_login(self.user)

        for i in range(2):
            Cliente.objects.create(
                nombre=f'Minorista {i}',
                documento_ruc=f'MIN-{i}',
                correo=f'min{i}@test.com',
                segmentacion=Cliente.Segmentacion.MINORISTA,
            )
            Cliente.objects.create(
                nombre=f'Mayorista {i}',
                documento_ruc=f'MAY-{i}',
                correo=f'may{i}@test.com',
                segmentacion=Cliente.Segmentacion.MAYORISTA,
            )
            Cliente.objects.create(
                nombre=f'Corporativo {i}',
                documento_ruc=f'COR-{i}',
                correo=f'cor{i}@test.com',
                segmentacion=Cliente.Segmentacion.CORPORATIVO,
            )
            Cliente.objects.create(
                nombre=f'VIP {i}',
                documento_ruc=f'VIP-{i}',
                correo=f'vip{i}@test.com',
                segmentacion=Cliente.Segmentacion.VIP,
            )

    def test_list_context_contains_kpi_counts(self):
        """Verifica que el contexto de ClienteListView incluya los conteos KPI por segmento."""
        response = self.client_auth.get(reverse('customers:cliente-list'))
        self.assertEqual(response.status_code, 200)

        # Accedemos directamente con la clave (response.context soporta lookup en todas las capas)
        self.assertGreaterEqual(response.context['count_min'], 2)
        self.assertGreaterEqual(response.context['count_may'], 2)
        self.assertGreaterEqual(response.context['count_cor'], 2)
        self.assertGreaterEqual(response.context['count_vip'], 2)
        self.assertGreaterEqual(response.context['total_count'], 8)
        self.assertIn('active_count', response.context)
        self.assertIn('inactive_count', response.context)

    def test_list_context_filter_state_preserved(self):
        """Verifica que los valores de filtro activos se reflejen en el contexto."""
        response = self.client_auth.get(
            reverse('customers:cliente-list'),
            {'segmentacion': 'VIP', 'q': 'vip'},
        )
        self.assertEqual(response.status_code, 200)
        # Los valores de filtro activos deben estar en el contexto de la vista
        self.assertEqual(response.context['current_segment'], 'VIP')
        self.assertEqual(response.context['current_q'], 'vip')

    def test_pagination_context(self):
        """Verifica que con más de 10 clientes la paginación se active y is_paginated sea True."""
        for i in range(3):
            Cliente.objects.create(
                nombre=f'Extra {i}',
                documento_ruc=f'EXTRA-{i}',
                correo=f'extra{i}@test.com',
            )
        response = self.client_auth.get(reverse('customers:cliente-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_paginated'])
        self.assertLessEqual(len(response.context['clientes']), 10)


class ClienteFormValidationTests(TestCase):
    """
    Suite de pruebas unitarias para :class:`~customers.forms.ClienteForm`
    y :class:`~customers.forms.ClienteFilterForm`.

    Verifica la aceptación de datos válidos, el rechazo de datos mal formados
    y la validez del formulario de filtros cuando está vacío.
    """

    def test_form_valid_data(self):
        """Verifica que ClienteForm acepte un conjunto de datos completos y válidos."""
        from customers.forms import ClienteForm

        form = ClienteForm(data={
            'nombre': 'Empresa Válida S.A.',
            'documento_ruc': '80080080-0',
            'correo': 'valida@empresa.com',
            'telefono': '+595 21 123456',
            'segmentacion': 'COR',
            'is_active': True,
        })
        self.assertTrue(form.is_valid(), msg=f'Errores inesperados: {form.errors}')

    def test_form_invalid_correo(self):
        """Verifica que ClienteForm rechace un correo electrónico mal formado."""
        from customers.forms import ClienteForm

        form = ClienteForm(data={
            'nombre': 'Empresa Sin Correo',
            'documento_ruc': '99099099-9',
            'correo': 'esto_no_es_email',
            'segmentacion': 'MIN',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('correo', form.errors)

    def test_form_missing_required_fields(self):
        """Verifica que ClienteForm requiera nombre, documento_ruc y correo."""
        from customers.forms import ClienteForm

        form = ClienteForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('nombre', form.errors)
        self.assertIn('documento_ruc', form.errors)
        self.assertIn('correo', form.errors)

    def test_filter_form_empty_is_valid(self):
        """Verifica que ClienteFilterForm vacío sea siempre válido (todos sus campos son opcionales)."""
        from customers.forms import ClienteFilterForm

        form = ClienteFilterForm(data={})
        self.assertTrue(form.is_valid(), msg=f'Errores inesperados: {form.errors}')


class CustomerUserAssignmentTests(TestCase):
    """
    Suite de pruebas para el modelo CustomerUserAssignment y la relación de multi-representación
    Usuario ↔ Clientes.
    """

    def setUp(self):
        """Inicializa usuarios y clientes de prueba."""
        self.user_titular = User.objects.create_user(
            username='titular_corp',
            email='titular@empresa.com',
            first_name='Titular',
            last_name='Corporativo',
        )
        self.user_gestor = User.objects.create_user(
            username='gestor_corp',
            email='gestor@empresa.com',
            first_name='Gestor',
            last_name='Financiero',
        )
        self.cliente_corp = Cliente.objects.create(
            nombre='Holding Global S.A.',
            documento_ruc='80012345-6',
            correo='contacto@holdingglobal.com',
            segmentacion=Cliente.Segmentacion.CORPORATIVO,
        )
        self.cliente_personal = Cliente.objects.create(
            nombre='Titular Personal',
            documento_ruc='1234567-8',
            correo='titular.personal@test.com',
            segmentacion=Cliente.Segmentacion.MINORISTA,
        )

    def test_user_represents_multiple_customers(self):
        """Verifica que un único usuario pueda representar a múltiples clientes (1 Usuario -> N Clientes)."""
        from customers.models import CustomerUserAssignment

        asig1 = CustomerUserAssignment.objects.create(
            customer=self.cliente_personal,
            user=self.user_titular,
            is_primary_representative=True,
            is_active=True,
        )
        asig2 = CustomerUserAssignment.objects.create(
            customer=self.cliente_corp,
            user=self.user_titular,
            is_primary_representative=True,
            is_active=True,
        )

        self.assertEqual(self.user_titular.customer_assignments.count(), 2)
        self.assertIn(asig1, self.user_titular.customer_assignments.all())
        self.assertIn(asig2, self.user_titular.customer_assignments.all())
        self.assertEqual(self.user_titular.clientes_representados.count(), 2)

    def test_customer_has_multiple_representatives(self):
        """Verifica que un cliente corporativo pueda tener múltiples usuarios representantes (1 Cliente -> N Usuarios)."""
        from customers.models import CustomerUserAssignment

        CustomerUserAssignment.objects.create(
            customer=self.cliente_corp,
            user=self.user_titular,
            is_primary_representative=True,
            is_active=True,
        )
        CustomerUserAssignment.objects.create(
            customer=self.cliente_corp,
            user=self.user_gestor,
            is_primary_representative=False,
            is_active=True,
        )

        self.assertEqual(self.cliente_corp.assignments.count(), 2)
        self.assertEqual(self.cliente_corp.usuarios.count(), 2)
        self.assertEqual(self.cliente_corp.representante_principal.user, self.user_titular)

    def test_unique_constraint_customer_user(self):
        """Verifica que no se puedan duplicar asignaciones para el mismo par (customer, user)."""
        from django.db import IntegrityError
        from customers.models import CustomerUserAssignment

        CustomerUserAssignment.objects.create(
            customer=self.cliente_corp,
            user=self.user_titular,
            is_primary_representative=True,
        )

        with self.assertRaises(IntegrityError):
            CustomerUserAssignment.objects.create(
                customer=self.cliente_corp,
                user=self.user_titular,
                is_primary_representative=False,
            )

    def test_assignment_is_active_toggle(self):
        """Verifica el comportamiento al desactivar una asignación de representación."""
        from customers.models import CustomerUserAssignment

        asig = CustomerUserAssignment.objects.create(
            customer=self.cliente_corp,
            user=self.user_titular,
            is_primary_representative=True,
            is_active=False,
        )

        self.assertIsNone(self.cliente_corp.representante_principal)
        self.assertEqual(self.cliente_corp.assignments.filter(is_active=True).count(), 0)

        asig.is_active = True
        asig.save()
        self.assertEqual(self.cliente_corp.representante_principal.user, self.user_titular)

    def test_assignment_str_representation(self):
        """Verifica la representación en string del modelo CustomerUserAssignment."""
        from customers.models import CustomerUserAssignment

        asig_principal = CustomerUserAssignment.objects.create(
            customer=self.cliente_corp,
            user=self.user_titular,
            is_primary_representative=True,
            is_active=True,
        )
        asig_secundaria = CustomerUserAssignment.objects.create(
            customer=self.cliente_corp,
            user=self.user_gestor,
            is_primary_representative=False,
            is_active=False,
        )

        self.assertIn('Principal', str(asig_principal))
        self.assertIn('Activo', str(asig_principal))
        self.assertIn('Secundario', str(asig_secundaria))
        self.assertIn('Inactivo', str(asig_secundaria))

    def test_serialize_cliente_includes_assignments(self):
        """Verifica que _serialize_cliente serialice correctamente las asignaciones y el representante principal."""
        from customers.models import CustomerUserAssignment
        from customers.views import _serialize_cliente

        CustomerUserAssignment.objects.create(
            customer=self.cliente_corp,
            user=self.user_titular,
            is_primary_representative=True,
            is_active=True,
        )
        CustomerUserAssignment.objects.create(
            customer=self.cliente_corp,
            user=self.user_gestor,
            is_primary_representative=False,
            is_active=True,
        )

        data = _serialize_cliente(self.cliente_corp)
        self.assertEqual(data['id'], self.cliente_corp.id)
        self.assertEqual(data['usuario_id'], self.user_titular.id)
        self.assertEqual(data['representante_principal_id'], self.user_titular.id)
        self.assertEqual(len(data['assignments']), 2)
        self.assertEqual(data['assignments'][0]['user_id'], self.user_titular.id)
        self.assertTrue(data['assignments'][0]['is_primary_representative'])


class ActiveCustomerSelectorTests(TestCase):
    """
    Suite de pruebas para el selector y cambio dinámico de Cliente Activo (SCRUM-40).
    """

    def setUp(self):
        """Inicializa clientes, usuarios y cliente de pruebas."""
        self.user = User.objects.create_user(
            username='selector_user',
            email='selector@test.com',
            first_name='Selector',
            last_name='Tester',
            password='Password123!',
        )
        self.cliente_a = Cliente.objects.create(
            nombre='Empresa Alfa S.A.',
            documento_ruc='80011111-1',
            correo='alfa@test.com',
            segmentacion=Cliente.Segmentacion.CORPORATIVO,
        )
        self.cliente_b = Cliente.objects.create(
            nombre='Empresa Beta S.R.L.',
            documento_ruc='80022222-2',
            correo='beta@test.com',
            segmentacion=Cliente.Segmentacion.MAYORISTA,
        )
        self.cliente_no_asignado = Cliente.objects.create(
            nombre='Empresa Ajena S.A.',
            documento_ruc='80099999-9',
            correo='ajena@test.com',
        )

        from customers.models import CustomerUserAssignment
        CustomerUserAssignment.objects.create(
            customer=self.cliente_a,
            user=self.user,
            is_primary_representative=True,
            is_active=True,
        )
        CustomerUserAssignment.objects.create(
            customer=self.cliente_b,
            user=self.user,
            is_primary_representative=False,
            is_active=True,
        )

        self.client_auth = Client()
        self.client_auth.force_login(self.user)

    def test_context_processor_injects_active_and_available_customers(self):
        """Verifica que el procesador de contexto inyecte el cliente activo y los disponibles."""
        from django.test import RequestFactory
        from customers.context_processors import active_customer

        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.user
        request.session = {'active_customer_id': self.cliente_b.id}

        context = active_customer(request)
        self.assertEqual(context['active_customer'], self.cliente_b)
        self.assertIn(self.cliente_a, context['available_customers'])
        self.assertIn(self.cliente_b, context['available_customers'])

    def test_switch_active_customer_success(self):
        """Verifica que al hacer POST a cambiar-activo se actualice el cliente activo en sesión."""
        url = reverse('customers:switch-active-customer', kwargs={'customer_id': self.cliente_b.id})
        response = self.client_auth.post(url, HTTP_REFERER='/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client_auth.session['active_customer_id'], self.cliente_b.id)

    def test_switch_active_customer_unauthorized_returns_404(self):
        """Verifica que un usuario no pueda activar un cliente al que no está asignado."""
        url = reverse('customers:switch-active-customer', kwargs={'customer_id': self.cliente_no_asignado.id})
        response = self.client_auth.post(url)
        self.assertEqual(response.status_code, 404)

    def test_navbar_renders_active_customer_and_dropdown(self):
        """Verifica que la barra superior renderice el nombre, RUC y opciones de cambio de cliente."""
        response = self.client_auth.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Debe mostrar el selector y los datos del cliente activo
        self.assertIn('activeCustomerDropdown', content)
        self.assertIn('Empresa Alfa S.A.', content)
        self.assertIn('80011111-1', content)

        # Debe contener la opción para alternar hacia el segundo cliente
        self.assertIn('Empresa Beta S.R.L.', content)
        self.assertIn('80022222-2', content)
        self.assertIn(f'/customers/cambiar-activo/{self.cliente_b.id}/', content)


class SeedDataCommandTests(TestCase):
    """
    Suite de pruebas unitarias para el comando de gestión seed_data (SCRUM-75 / SCRUM-62).
    """

    def test_seed_data_command_execution(self):
        """Valida que seed_data pueble correctamente todas las entidades del sistema."""
        import io
        from django.core.management import call_command
        from payments.models import EntidadFinanciera, PaymentMethod, ReceivingMethod
        from rates.models import Currency, ExchangeRate, OperationLimit, SegmentCommission
        from transactions.models import Transaction

        out = io.StringIO()
        call_command('seed_data', stdout=out)
        output = out.getvalue()

        self.assertIn('Seeding de datos completado exitosamente', output)

        # 1. Usuarios y roles
        self.assertTrue(User.objects.filter(username='admin', is_superuser=True).exists())
        self.assertTrue(User.objects.filter(username='operador', is_staff=True).exists())
        self.assertTrue(User.objects.filter(username='cliente_minorista').exists())
        self.assertTrue(User.objects.filter(username='cliente_vip').exists())

        # 2. Clientes y asignaciones
        self.assertEqual(Cliente.objects.count(), 4)
        self.assertEqual(CustomerUserAssignment.objects.count(), 4)

        # 3. Monedas
        self.assertEqual(Currency.objects.filter(code__in=['USD', 'PYG', 'EUR', 'BRL', 'ARS', 'GBP']).count(), 6)

        # 4. Tasas de cambio (activas e históricas)
        self.assertEqual(ExchangeRate.objects.filter(is_active=True).count(), 6)
        self.assertGreaterEqual(ExchangeRate.objects.filter(is_active=False).count(), 90)

        # 5. Comisiones por segmento
        self.assertEqual(SegmentCommission.objects.count(), 4)

        # 6. Entidades financieras
        self.assertGreaterEqual(EntidadFinanciera.objects.count(), 13)

        # 7. Medios de pago y acreditación
        self.assertGreaterEqual(PaymentMethod.objects.count(), 12)
        self.assertGreaterEqual(ReceivingMethod.objects.count(), 8)

        # 8. Límites operativos
        self.assertGreaterEqual(OperationLimit.objects.count(), 10)

        # 9. Transacciones de ejemplo
        self.assertEqual(Transaction.objects.filter(estado=Transaction.Estado.COMPLETADA).count(), 3)
        self.assertEqual(Transaction.objects.filter(estado=Transaction.Estado.PENDIENTE).count(), 1)
        self.assertEqual(Transaction.objects.filter(estado=Transaction.Estado.CANCELADA).count(), 1)

    def test_seed_data_idempotency(self):
        """Valida que ejecutar seed_data múltiples veces sea idempotente y no duplique registros."""
        import io
        from django.core.management import call_command
        from payments.models import EntidadFinanciera
        from rates.models import Currency, SegmentCommission
        from transactions.models import Transaction

        out1 = io.StringIO()
        call_command('seed_data', stdout=out1)

        out2 = io.StringIO()
        call_command('seed_data', stdout=out2)

        self.assertEqual(Cliente.objects.count(), 4)
        self.assertEqual(Currency.objects.count(), 6)
        self.assertEqual(SegmentCommission.objects.count(), 4)
        self.assertEqual(EntidadFinanciera.objects.count(), 13)
        self.assertEqual(Transaction.objects.count(), 5)

    def test_seed_data_reset_option(self):
        """Valida que la opción --reset limpie las entidades transaccionales antes de sembrar."""
        import io
        from django.core.management import call_command
        from transactions.models import Transaction

        out = io.StringIO()
        call_command('seed_data', reset=True, stdout=out)
        output = out.getvalue()

        self.assertIn('Datos previos eliminados para reinicio', output)
        self.assertEqual(Transaction.objects.count(), 5)



