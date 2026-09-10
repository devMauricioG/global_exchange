"""
Módulo de pruebas automatizadas (PyUnit / Django TestCase) para la aplicación payments.

Cubre exhaustivamente:
- Integridad y validaciones del modelo :class:`~payments.models.PaymentMethod`.
- Reglas de negocio de exclusividad de medio predeterminado por cliente.
- Validación de formularios :class:`~payments.forms.PaymentMethodForm`.
- Vistas CBV web (aislamiento de datos, prevención de IDOR y control de acceso).
- Endpoints de API REST (GET, POST, PUT, PATCH, DELETE).
"""

import json
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from customers.models import Cliente, CustomerUserAssignment
from payments.forms import PaymentMethodFilterForm, PaymentMethodForm
from payments.models import PaymentMethod

User = get_user_model()


class PaymentMethodModelTestCase(TestCase):
    """
    Pruebas unitarias para el modelo PaymentMethod.
    """

    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='password123',
        )
        self.cliente1 = Cliente.objects.create(
            nombre='Empresa Uno S.A.',
            documento_ruc='80011111-1',
            correo='empresa1@test.com',
            telefono='0981111111',
            segmentacion=Cliente.Segmentacion.CORPORATIVO,
        )
        CustomerUserAssignment.objects.create(
            customer=self.cliente1,
            user=self.user1,
            is_primary_representative=True,
            is_active=True,
        )

        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='password123',
        )
        self.cliente2 = Cliente.objects.create(
            nombre='Empresa Dos S.A.',
            documento_ruc='80022222-2',
            correo='empresa2@test.com',
            telefono='0982222222',
            segmentacion=Cliente.Segmentacion.MINORISTA,
        )
        CustomerUserAssignment.objects.create(
            customer=self.cliente2,
            user=self.user2,
            is_primary_representative=True,
            is_active=True,
        )

    def test_payment_method_creation_and_str(self):
        """Verifica la correcta creación del modelo y su representación __str__."""
        pm = PaymentMethod.objects.create(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria='Banco Itaú',
            numero_cuenta='12-345678-9',
            titular='Empresa Uno S.A.',
            es_predeterminado=True,
            activo=True,
        )
        self.assertIn('Banco Itaú', str(pm))
        self.assertIn('12-345678-9', str(pm))
        self.assertIn('(Predeterminado)', str(pm))
        self.assertEqual(pm.cliente, self.cliente1)

    def test_default_uniqueness_per_client(self):
        """
        Verifica que al marcar un nuevo medio como predeterminado,
        el anterior del mismo cliente deja de ser predeterminado de forma atómica.
        """
        pm1 = PaymentMethod.objects.create(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria='Banco Itaú',
            numero_cuenta='111111',
            titular='Empresa Uno S.A.',
            es_predeterminado=True,
            activo=True,
        )
        pm2 = PaymentMethod.objects.create(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.BILLETERA,
            entidad_bancaria='Tigo Money',
            numero_cuenta='0981111111',
            titular='Empresa Uno S.A.',
            es_predeterminado=True,
            activo=True,
        )

        pm1.refresh_from_db()
        pm2.refresh_from_db()

        self.assertFalse(pm1.es_predeterminado)
        self.assertTrue(pm2.es_predeterminado)

    def test_default_uniqueness_does_not_affect_other_clients(self):
        """
        Verifica que definir un predeterminado para el Cliente 1
        no altera el predeterminado del Cliente 2.
        """
        pm1 = PaymentMethod.objects.create(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria='Banco Itaú',
            numero_cuenta='111111',
            titular='Empresa Uno S.A.',
            es_predeterminado=True,
            activo=True,
        )
        pm_cliente2 = PaymentMethod.objects.create(
            cliente=self.cliente2,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria='Banco Continental',
            numero_cuenta='222222',
            titular='Empresa Dos S.A.',
            es_predeterminado=True,
            activo=True,
        )

        pm1.refresh_from_db()
        pm_cliente2.refresh_from_db()

        self.assertTrue(pm1.es_predeterminado)
        self.assertTrue(pm_cliente2.es_predeterminado)

    def test_cannot_set_inactive_as_default(self):
        """Verifica que no se puede marcar un medio inactivo como predeterminado."""
        pm = PaymentMethod(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria='Banco Itaú',
            numero_cuenta='111111',
            titular='Empresa Uno S.A.',
            es_predeterminado=True,
            activo=False,
        )
        with self.assertRaises(ValidationError):
            pm.save()

    def test_validation_empty_fields(self):
        """Verifica que campos vacíos o sólo espacios disparen ValidationError."""
        pm = PaymentMethod(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria='   ',
            numero_cuenta='12345',
            titular='Titular',
        )
        with self.assertRaises(ValidationError):
            pm.save()


class PaymentMethodFormTestCase(TestCase):
    """
    Pruebas unitarias para los formularios PaymentMethodForm y FilterForm.
    """

    def test_valid_form(self):
        data = {
            'tipo_medio': PaymentMethod.TipoMedio.TRANSFERENCIA,
            'entidad_bancaria': 'Banco Sudameris',
            'numero_cuenta': '987654321',
            'titular': 'Carlos González',
            'documento_titular': '3.456.789',
            'es_predeterminado': True,
            'activo': True,
        }
        form = PaymentMethodForm(data=data)
        self.assertTrue(form.is_valid())

    def test_form_rejects_inactive_default(self):
        data = {
            'tipo_medio': PaymentMethod.TipoMedio.TRANSFERENCIA,
            'entidad_bancaria': 'Banco Sudameris',
            'numero_cuenta': '987654321',
            'titular': 'Carlos González',
            'es_predeterminado': True,
            'activo': False,
        }
        form = PaymentMethodForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('es_predeterminado', form.errors)

    def test_filter_form_valid(self):
        form = PaymentMethodFilterForm(data={'q': 'Itaú', 'tipo_medio': 'TRANSFERENCIA', 'activo': 'true'})
        self.assertTrue(form.is_valid())


class PaymentMethodViewsTestCase(TestCase):
    """
    Pruebas de integración para las vistas CBV web y prevención de IDOR.
    """

    def setUp(self):
        self.client = Client()

        self.user1 = User.objects.create_user(
            username='cliente_user1',
            email='user1@ge.com',
            password='Password123!',
        )
        self.cliente1 = Cliente.objects.create(
            nombre='Cliente Uno',
            documento_ruc='10001-1',
            correo='user1@ge.com',
        )
        CustomerUserAssignment.objects.create(
            customer=self.cliente1,
            user=self.user1,
            is_primary_representative=True,
            is_active=True,
        )

        self.user2 = User.objects.create_user(
            username='cliente_user2',
            email='user2@ge.com',
            password='Password123!',
        )
        self.cliente2 = Cliente.objects.create(
            nombre='Cliente Dos',
            documento_ruc='20002-2',
            correo='user2@ge.com',
        )
        CustomerUserAssignment.objects.create(
            customer=self.cliente2,
            user=self.user2,
            is_primary_representative=True,
            is_active=True,
        )

        self.pm1 = PaymentMethod.objects.create(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria='Banco Itaú',
            numero_cuenta='111-111',
            titular='Cliente Uno',
            es_predeterminado=True,
            activo=True,
        )

        self.pm2 = PaymentMethod.objects.create(
            cliente=self.cliente2,
            tipo_medio=PaymentMethod.TipoMedio.BILLETERA,
            entidad_bancaria='Tigo Money',
            numero_cuenta='0982222222',
            titular='Cliente Dos',
            es_predeterminado=True,
            activo=True,
        )

    def test_list_requires_authentication(self):
        """Acceso anónimo a la lista redirige al login."""
        response = self.client.get(reverse('payments:paymentmethod-list'))
        self.assertEqual(response.status_code, 302)

    def test_list_shows_only_own_payment_methods(self):
        """Aislamiento de datos: user1 sólo ve pm1 y jamás ve pm2."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('payments:paymentmethod-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Banco Itaú')
        self.assertContains(response, '111-111')
        self.assertNotContains(response, 'Tigo Money')
        self.assertNotContains(response, '0982222222')

    def test_create_payment_method_web(self):
        """Creación mediante formulario web asigna automáticamente al cliente del usuario."""
        self.client.force_login(self.user1)
        data = {
            'tipo_medio': PaymentMethod.TipoMedio.BILLETERA,
            'entidad_bancaria': 'Billetera Personal',
            'numero_cuenta': '0971999888',
            'titular': 'Cliente Uno Personal',
            'es_predeterminado': False,
            'activo': True,
        }
        response = self.client.post(reverse('payments:paymentmethod-create'), data=data)
        self.assertEqual(response.status_code, 302)
        nuevo_pm = PaymentMethod.objects.filter(numero_cuenta='0971999888').first()
        self.assertIsNotNone(nuevo_pm)
        self.assertEqual(nuevo_pm.cliente, self.cliente1)

    def test_first_payment_method_becomes_default(self):
        """Si un cliente no tenía medios de pago, el primero que crea se marca como predeterminado."""
        user3 = User.objects.create_user(username='user3', email='user3@test.com', password='pwd')
        cliente3 = Cliente.objects.create(nombre='Cliente 3', documento_ruc='333-3', correo='user3@test.com')
        CustomerUserAssignment.objects.create(customer=cliente3, user=user3, is_primary_representative=True, is_active=True)
        self.client.force_login(user3)
        data = {
            'tipo_medio': PaymentMethod.TipoMedio.TRANSFERENCIA,
            'entidad_bancaria': 'Ueno Bank',
            'numero_cuenta': '555555',
            'titular': 'Cliente 3',
            'es_predeterminado': False,
            'activo': True,
        }
        response = self.client.post(reverse('payments:paymentmethod-create'), data=data)
        self.assertEqual(response.status_code, 302)
        pm3 = PaymentMethod.objects.filter(cliente=cliente3).first()
        self.assertIsNotNone(pm3)
        self.assertTrue(pm3.es_predeterminado)

    def test_prevent_idor_on_update(self):
        """Prevención de IDOR: user1 no puede editar el medio de pago pm2 de user2."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('payments:paymentmethod-update', kwargs={'pk': self.pm2.pk}))
        self.assertEqual(response.status_code, 404)

        data = {
            'tipo_medio': PaymentMethod.TipoMedio.BILLETERA,
            'entidad_bancaria': 'Hack Banco',
            'numero_cuenta': '999999',
            'titular': 'Hacker',
            'activo': True,
        }
        response = self.client.post(reverse('payments:paymentmethod-update', kwargs={'pk': self.pm2.pk}), data=data)
        self.assertEqual(response.status_code, 404)
        self.pm2.refresh_from_db()
        self.assertEqual(self.pm2.entidad_bancaria, 'Tigo Money')

    def test_prevent_idor_on_delete(self):
        """Prevención de IDOR: user1 no puede eliminar el medio de pago de user2."""
        self.client.force_login(self.user1)
        response = self.client.post(reverse('payments:paymentmethod-delete', kwargs={'pk': self.pm2.pk}))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(PaymentMethod.objects.filter(pk=self.pm2.pk).exists())

    def test_set_default_action(self):
        """Acción rápida para marcar como predeterminado."""
        pm_otro = PaymentMethod.objects.create(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.BILLETERA,
            entidad_bancaria='Wally',
            numero_cuenta='0981999999',
            titular='Cliente Uno',
            es_predeterminado=False,
            activo=True,
        )
        self.client.force_login(self.user1)
        response = self.client.post(reverse('payments:paymentmethod-set-default', kwargs={'pk': pm_otro.pk}))
        self.assertEqual(response.status_code, 302)

        pm_otro.refresh_from_db()
        self.pm1.refresh_from_db()
        self.assertTrue(pm_otro.es_predeterminado)
        self.assertFalse(self.pm1.es_predeterminado)

    def test_toggle_active_action(self):
        """Alternar el estado activo del medio de pago."""
        self.client.force_login(self.user1)
        response = self.client.post(reverse('payments:paymentmethod-toggle-active', kwargs={'pk': self.pm1.pk}))
        self.assertEqual(response.status_code, 302)
        self.pm1.refresh_from_db()
        self.assertFalse(self.pm1.activo)
        self.assertFalse(self.pm1.es_predeterminado)


class PaymentMethodAPITestCase(TestCase):
    """
    Pruebas para los endpoints API REST (JSON).
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='api_user',
            email='api@test.com',
            password='password123',
        )
        self.cliente = Cliente.objects.create(
            nombre='API Cliente',
            documento_ruc='777777-7',
            correo='api@test.com',
        )
        CustomerUserAssignment.objects.create(
            customer=self.cliente,
            user=self.user,
            is_primary_representative=True,
            is_active=True,
        )
        self.pm = PaymentMethod.objects.create(
            cliente=self.cliente,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria='Banco Familiar',
            numero_cuenta='444-444',
            titular='API Cliente',
            es_predeterminado=True,
            activo=True,
        )

    def test_api_list(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('payments:paymentmethod-api-list'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['entidad_bancaria'], 'Banco Familiar')

    def test_api_create(self):
        self.client.force_login(self.user)
        payload = {
            'tipo_medio': 'BILLETERA',
            'entidad_bancaria': 'Zimple',
            'numero_cuenta': '0981777777',
            'titular': 'API Cliente',
            'es_predeterminado': False,
            'activo': True,
        }
        response = self.client.post(
            reverse('payments:paymentmethod-api-list'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['entidad_bancaria'], 'Zimple')
        self.assertEqual(data['cliente_id'], self.cliente.id)

    def test_api_detail(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('payments:paymentmethod-api-detail', kwargs={'pk': self.pm.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], self.pm.id)

    def test_api_update(self):
        self.client.force_login(self.user)
        payload = {
            'entidad_bancaria': 'Banco Familiar Renovado',
        }
        response = self.client.patch(
            reverse('payments:paymentmethod-api-detail', kwargs={'pk': self.pm.pk}),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.pm.refresh_from_db()
        self.assertEqual(self.pm.entidad_bancaria, 'Banco Familiar Renovado')

    def test_api_delete(self):
        self.client.force_login(self.user)
        response = self.client.delete(reverse('payments:paymentmethod-api-detail', kwargs={'pk': self.pm.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PaymentMethod.objects.filter(pk=self.pm.pk).exists())
