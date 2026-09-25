"""
Módulo de pruebas automatizadas (PyUnit / Django TestCase) para la aplicación payments (SCRUM-83 / SCRUM-68).

Cubre exhaustivamente:
- Integridad, ordenamiento y catálogo del modelo :class:`~payments.models.EntidadFinanciera`.
- Integridad y validaciones del modelo :class:`~payments.models.PaymentMethod` (Transferencias, Billeteras, Tarjetas, Efectivo).
- Reglas de negocio de exclusividad de medio predeterminado por cliente.
- Formularios dedicados :class:`~payments.forms.CreditDebitCardForm`, :class:`~payments.forms.BankTransferForm`,
  :class:`~payments.forms.DigitalWalletForm`, :class:`~payments.forms.CashBranchForm` y :class:`~payments.forms.ReceivingMethodForm`.
- Integridad y reglas del modelo :class:`~payments.models.ReceivingMethod` (cuentas de acreditación de fondos).
- Vistas CBV web (aislamiento de datos, prevención de IDOR y control de acceso).
- Endpoints de API REST (GET, POST, PUT, PATCH, DELETE).
"""

from datetime import date
import json
import re

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from customers.models import Cliente, CustomerUserAssignment
from payments.forms import (
    BankTransferForm,
    CashBranchForm,
    CreditDebitCardForm,
    DigitalWalletForm,
    PaymentMethodFilterForm,
    PaymentMethodForm,
    ReceivingMethodForm,
)
from payments.models import EntidadFinanciera, PaymentMethod, ReceivingMethod

User = get_user_model()


class EntidadFinancieraModelTestCase(TestCase):
    """
    Pruebas unitarias para el catálogo de Entidades Financieras (Bancos y Billeteras).
    """

    def setUp(self):
        self.banco_itau, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Banco Itaú',
            defaults={
                'tipo': EntidadFinanciera.TipoEntidad.BANCO,
                'activo': True,
                'orden': 1,
            },
        )
        self.billetera_tigo, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Tigo Money',
            defaults={
                'tipo': EntidadFinanciera.TipoEntidad.BILLETERA,
                'activo': True,
                'orden': 2,
            },
        )
        self.banco_inactivo, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Banco Extinto Test',
            defaults={
                'tipo': EntidadFinanciera.TipoEntidad.BANCO,
                'activo': False,
                'orden': 99,
            },
        )

    def test_entidad_creation_and_str(self):
        """Verifica la correcta persistencia y representación en cadena."""
        self.assertEqual(str(self.banco_itau), 'Banco Itaú (Banco)')
        self.assertEqual(str(self.billetera_tigo), 'Tigo Money (Billetera Digital)')

    def test_ordering_and_active_filtering(self):
        """Verifica que el filtrado por activo y orden funcione adecuadamente."""
        activas = EntidadFinanciera.objects.filter(activo=True)
        self.assertGreaterEqual(activas.count(), 2)
        self.assertNotIn(self.banco_inactivo, activas)


class PaymentMethodModelTestCase(TestCase):
    """
    Pruebas unitarias para el modelo PaymentMethod y validaciones por tipo de instrumento.
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

        self.banco_itau, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Banco Itaú',
            defaults={
                'tipo': EntidadFinanciera.TipoEntidad.BANCO,
                'activo': True,
            },
        )
        self.billetera_tigo, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Tigo Money',
            defaults={
                'tipo': EntidadFinanciera.TipoEntidad.BILLETERA,
                'activo': True,
            },
        )

    def test_transferencia_creation_and_str(self):
        """Verifica la creación de un medio de transferencia bancaria válido."""
        pm = PaymentMethod.objects.create(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria=self.banco_itau,
            tipo_cuenta_bancaria=PaymentMethod.TipoCuentaBancaria.CORRIENTE,
            numero_cuenta='12-345678-9',
            titular='Empresa Uno S.A.',
            documento_titular='80011111-1',
            es_predeterminado=True,
            activo=True,
        )
        self.assertIn('Banco Itaú', str(pm))
        self.assertIn('12-345678-9', str(pm))
        self.assertIn('(Predeterminado)', str(pm))
        self.assertEqual(pm.cliente, self.cliente1)

    def test_billetera_creation_and_validation(self):
        """Verifica la creación y validación de billetera digital."""
        pm = PaymentMethod.objects.create(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.BILLETERA,
            entidad_bancaria=self.billetera_tigo,
            numero_cuenta='0981111111',
            telefono_billetera='0981111111',
            titular='Empresa Uno S.A.',
            es_predeterminado=False,
            activo=True,
        )
        self.assertEqual(pm.telefono_billetera, '0981111111')

        # Teléfono inválido debe disparar ValidationError
        pm_invalido = PaymentMethod(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.BILLETERA,
            entidad_bancaria=self.billetera_tigo,
            numero_cuenta='1234',
            telefono_billetera='1234',
            titular='Empresa Uno S.A.',
        )
        with self.assertRaises(ValidationError):
            pm_invalido.save()

    def test_tarjeta_creation_and_validation(self):
        """Verifica la creación y validaciones de tarjeta de débito/crédito."""
        pm = PaymentMethod.objects.create(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.TARJETA,
            entidad_bancaria=self.banco_itau,
            numero_cuenta='XXXX-XXXX-XXXX-4321',
            titular='Empresa Uno S.A.',
            tarjeta_ultimos_digitos='4321',
            tarjeta_mes_vencimiento=12,
            tarjeta_anio_vencimiento=2028,
            es_predeterminado=False,
            activo=True,
        )
        self.assertEqual(pm.tarjeta_ultimos_digitos, '4321')

        # Tarjeta con dígitos inválidos (< 4 o no numéricos)
        pm_invalido = PaymentMethod(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.TARJETA,
            entidad_bancaria=self.banco_itau,
            numero_cuenta='XXXX',
            titular='Titular',
            tarjeta_ultimos_digitos='12A',
            tarjeta_mes_vencimiento=10,
            tarjeta_anio_vencimiento=2028,
        )
        with self.assertRaises(ValidationError):
            pm_invalido.save()

        # Tarjeta vencida (año en el pasado)
        pm_vencida = PaymentMethod(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.TARJETA,
            entidad_bancaria=self.banco_itau,
            numero_cuenta='XXXX',
            titular='Titular',
            tarjeta_ultimos_digitos='1234',
            tarjeta_mes_vencimiento=10,
            tarjeta_anio_vencimiento=2020,
        )
        with self.assertRaises(ValidationError):
            pm_vencida.save()

    def test_default_uniqueness_per_client(self):
        """
        Verifica que al marcar un nuevo medio como predeterminado,
        el anterior del mismo cliente deja de ser predeterminado de forma atómica.
        """
        pm1 = PaymentMethod.objects.create(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria=self.banco_itau,
            tipo_cuenta_bancaria=PaymentMethod.TipoCuentaBancaria.AHORRO,
            numero_cuenta='111111',
            titular='Empresa Uno S.A.',
            es_predeterminado=True,
            activo=True,
        )
        pm2 = PaymentMethod.objects.create(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.BILLETERA,
            entidad_bancaria=self.billetera_tigo,
            numero_cuenta='0981111111',
            telefono_billetera='0981111111',
            titular='Empresa Uno S.A.',
            es_predeterminado=True,
            activo=True,
        )

        pm1.refresh_from_db()
        pm2.refresh_from_db()

        self.assertFalse(pm1.es_predeterminado)
        self.assertTrue(pm2.es_predeterminado)

    def test_cannot_set_inactive_as_default(self):
        """Verifica que no se puede marcar un medio inactivo como predeterminado."""
        pm = PaymentMethod(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria=self.banco_itau,
            tipo_cuenta_bancaria=PaymentMethod.TipoCuentaBancaria.AHORRO,
            numero_cuenta='111111',
            titular='Empresa Uno S.A.',
            es_predeterminado=True,
            activo=False,
        )
        with self.assertRaises(ValidationError):
            pm.save()


class DedicatedFormsTestCase(TestCase):
    """
    Pruebas unitarias para los formularios dedicados por instrumento de pago (SCRUM-72).
    """

    def setUp(self):
        self.banco, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Banco Continental',
            defaults={
                'tipo': EntidadFinanciera.TipoEntidad.BANCO,
                'activo': True,
            },
        )
        self.billetera, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Personal Pay Test',
            defaults={
                'tipo': EntidadFinanciera.TipoEntidad.BILLETERA,
                'activo': True,
            },
        )

    def test_credit_debit_card_form_valid_luhn(self):
        """Tarjeta con algoritmo de Luhn válido es aceptada y extrae últimos 4 dígitos."""
        # 4532015112830366 es un número de tarjeta de prueba con checksum Luhn válido
        data = {
            'entidad_bancaria': self.banco.id,
            'numero_tarjeta': '4532 0151 1283 0366',
            'cvv': '123',
            'titular': 'Juan Pérez',
            'documento_titular': '1234567',
            'tarjeta_mes_vencimiento': 12,
            'tarjeta_anio_vencimiento': 2029,
            'es_predeterminado': False,
            'activo': True,
        }
        form = CreditDebitCardForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        pm = form.save(commit=False)
        self.assertEqual(pm.tarjeta_ultimos_digitos, '0366')

    def test_credit_debit_card_form_invalid_luhn(self):
        """Tarjeta con checksum Luhn erróneo es rechazada."""
        data = {
            'entidad_bancaria': self.banco.id,
            'numero_tarjeta': '4111 1111 1111 1112',  # Falla Luhn
            'cvv': '123',
            'titular': 'Juan Pérez',
            'tarjeta_mes_vencimiento': 12,
            'tarjeta_anio_vencimiento': 2029,
            'es_predeterminado': False,
            'activo': True,
        }
        form = CreditDebitCardForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('numero_tarjeta', form.errors)

    def test_bank_transfer_form_validation(self):
        """Formulario de transferencia bancaria valida formato de cuenta y tipo de cuenta."""
        data_valida = {
            'entidad_bancaria': self.banco.id,
            'tipo_cuenta_bancaria': PaymentMethod.TipoCuentaBancaria.CORRIENTE,
            'numero_cuenta': '12-345678-9',
            'titular': 'Agro S.A.',
            'documento_titular': '80012345-6',
            'es_predeterminado': True,
            'activo': True,
        }
        form = BankTransferForm(data=data_valida)
        self.assertTrue(form.is_valid(), form.errors)

        data_invalida = {
            'entidad_bancaria': self.banco.id,
            'numero_cuenta': 'ABC',  # Formato no numérico
            'titular': 'Agro S.A.',
        }
        form_bad = BankTransferForm(data=data_invalida)
        self.assertFalse(form_bad.is_valid())

    def test_digital_wallet_form_validation(self):
        """Formulario de billetera móvil valida prefijos celulares paraguayos."""
        data_valida = {
            'entidad_bancaria': self.billetera.id,
            'telefono_billetera': '0981123456',
            'titular': 'Carlos Gómez',
            'es_predeterminado': False,
            'activo': True,
        }
        form = DigitalWalletForm(data=data_valida)
        self.assertTrue(form.is_valid(), form.errors)
        pm = form.save(commit=False)
        self.assertEqual(pm.numero_cuenta, '0981123456')

        data_invalida = {
            'entidad_bancaria': self.billetera.id,
            'telefono_billetera': '021123456',  # Teléfono de línea fija, no celular
            'titular': 'Carlos Gómez',
        }
        form_bad = DigitalWalletForm(data=data_invalida)
        self.assertFalse(form_bad.is_valid())
        self.assertIn('telefono_billetera', form_bad.errors)

    def test_cash_branch_form(self):
        """Formulario de efectivo/ventanilla configura automáticamente los campos requeridos."""
        data = {
            'titular': 'María López',
            'documento_titular': '4567890',
            'es_predeterminado': False,
            'activo': True,
        }
        form = CashBranchForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        pm = form.save(commit=False)
        self.assertEqual(pm.tipo_medio, PaymentMethod.TipoMedio.EFECTIVO)
        self.assertEqual(pm.numero_cuenta, 'N/A')


class ReceivingMethodTestCase(TestCase):
    """
    Pruebas unitarias para el modelo y formulario de Cuentas de Acreditación (ReceivingMethod).
    """

    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Cliente Acreditación',
            documento_ruc='90011122-3',
            correo='acreditacion@test.com',
        )
        self.banco, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Banco Atlas',
            defaults={
                'tipo': EntidadFinanciera.TipoEntidad.BANCO,
                'activo': True,
            },
        )
        self.billetera, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Wally',
            defaults={
                'tipo': EntidadFinanciera.TipoEntidad.BILLETERA,
                'activo': True,
            },
        )

    def test_receiving_method_creation_and_str(self):
        """Verifica la persistencia y exclusividad de cuenta receptora predeterminada."""
        rm1 = ReceivingMethod.objects.create(
            cliente=self.cliente,
            entidad_bancaria=self.banco,
            tipo_cuenta=ReceivingMethod.TipoCuenta.AHORRO,
            numero_cuenta='111-222-333',
            titular='Cliente Acreditación',
            es_predeterminado=True,
            activo=True,
        )
        self.assertIn('Banco Atlas', str(rm1))
        self.assertIn('(Predeterminado)', str(rm1))

        rm2 = ReceivingMethod.objects.create(
            cliente=self.cliente,
            entidad_bancaria=self.billetera,
            tipo_cuenta=ReceivingMethod.TipoCuenta.BILLETERA,
            numero_cuenta='0971555666',
            titular='Cliente Acreditación',
            es_predeterminado=True,
            activo=True,
        )
        rm1.refresh_from_db()
        self.assertFalse(rm1.es_predeterminado)
        self.assertTrue(rm2.es_predeterminado)

    def test_receiving_method_form_validation(self):
        """Formulario de cuenta receptora valida coherencia entre entidad y tipo de cuenta."""
        data_valida = {
            'entidad_bancaria': self.banco.id,
            'tipo_cuenta': ReceivingMethod.TipoCuenta.CORRIENTE,
            'numero_cuenta': '555-666',
            'titular': 'Cliente Acreditación',
            'es_predeterminado': True,
            'activo': True,
        }
        form = ReceivingMethodForm(data=data_valida)
        self.assertTrue(form.is_valid(), form.errors)

        # Incoherencia: Entidad BANCO con TipoCuenta BILLETERA
        data_invalida = {
            'entidad_bancaria': self.banco.id,
            'tipo_cuenta': ReceivingMethod.TipoCuenta.BILLETERA,
            'numero_cuenta': '555-666',
            'titular': 'Cliente Acreditación',
        }
        form_bad = ReceivingMethodForm(data=data_invalida)
        self.assertFalse(form_bad.is_valid())


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

        self.banco_itau, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Banco Itaú',
            defaults={
                'tipo': EntidadFinanciera.TipoEntidad.BANCO,
                'activo': True,
            },
        )
        self.billetera_tigo, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Tigo Money',
            defaults={
                'tipo': EntidadFinanciera.TipoEntidad.BILLETERA,
                'activo': True,
            },
        )

        self.pm1 = PaymentMethod.objects.create(
            cliente=self.cliente1,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria=self.banco_itau,
            tipo_cuenta_bancaria=PaymentMethod.TipoCuentaBancaria.AHORRO,
            numero_cuenta='111-111',
            titular='Cliente Uno',
            es_predeterminado=True,
            activo=True,
        )

        self.pm2 = PaymentMethod.objects.create(
            cliente=self.cliente2,
            tipo_medio=PaymentMethod.TipoMedio.BILLETERA,
            entidad_bancaria=self.billetera_tigo,
            numero_cuenta='0982222222',
            telefono_billetera='0982222222',
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
        self.assertNotContains(response, '0982222222')

    def test_create_payment_method_web(self):
        """Creación mediante formulario web asigna automáticamente al cliente del usuario."""
        self.client.force_login(self.user1)
        data = {
            'tipo_medio': PaymentMethod.TipoMedio.BILLETERA,
            'entidad_bancaria': self.billetera_tigo.id,
            'numero_cuenta': '0971999888',
            'telefono_billetera': '0971999888',
            'titular': 'Cliente Uno Personal',
            'es_predeterminado': False,
            'activo': True,
        }
        response = self.client.post(reverse('payments:paymentmethod-create'), data=data)
        self.assertEqual(response.status_code, 302)
        nuevo_pm = PaymentMethod.objects.filter(numero_cuenta='0971999888').first()
        self.assertIsNotNone(nuevo_pm)
        self.assertEqual(nuevo_pm.cliente, self.cliente1)

    def test_prevent_idor_on_update(self):
        """Prevención de IDOR: user1 no puede editar el medio de pago pm2 de user2."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('payments:paymentmethod-update', kwargs={'pk': self.pm2.pk}))
        self.assertEqual(response.status_code, 404)

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
            entidad_bancaria=self.billetera_tigo,
            numero_cuenta='0981999999',
            telefono_billetera='0981999999',
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
        self.banco, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Banco Familiar',
            defaults={
                'tipo': EntidadFinanciera.TipoEntidad.BANCO,
                'activo': True,
            },
        )
        self.pm = PaymentMethod.objects.create(
            cliente=self.cliente,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria=self.banco,
            tipo_cuenta_bancaria=PaymentMethod.TipoCuentaBancaria.AHORRO,
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
            'tipo_medio': 'TRANSFERENCIA',
            'entidad_bancaria': 'Banco Familiar',
            'tipo_cuenta_bancaria': 'CORRIENTE',
            'numero_cuenta': '777-888',
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
        self.assertEqual(data['entidad_bancaria'], 'Banco Familiar')
        self.assertEqual(data['cliente_id'], self.cliente.id)

    def test_api_detail(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('payments:paymentmethod-api-detail', kwargs={'pk': self.pm.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], self.pm.id)

    def test_api_update(self):
        self.client.force_login(self.user)
        payload = {
            'numero_cuenta': '999-999',
        }
        response = self.client.patch(
            reverse('payments:paymentmethod-api-detail', kwargs={'pk': self.pm.pk}),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.pm.refresh_from_db()
        self.assertEqual(self.pm.numero_cuenta, '999-999')

    def test_api_delete(self):
        self.client.force_login(self.user)
        response = self.client.delete(reverse('payments:paymentmethod-api-detail', kwargs={'pk': self.pm.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PaymentMethod.objects.filter(pk=self.pm.pk).exists())
