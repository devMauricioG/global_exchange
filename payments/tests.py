"""
Módulo de pruebas automatizadas (PyUnit / Django TestCase) para la aplicación payments (SCRUM-83 / SCRUM-68).

Cubre exhaustivamente:

- Integridad, ordenamiento y catálogo del modelo :class:`~payments.models.EntidadFinanciera`.
- Integridad y validaciones del modelo :class:`~payments.models.PaymentMethod` (Transferencias, Billeteras, Tarjetas, Efectivo).
- Reglas de negocio de exclusividad de medio predeterminado por cliente.
- Formularios dedicados :class:`~payments.forms.CreditDebitCardForm`, :class:`~payments.forms.BankTransferForm`, :class:`~payments.forms.DigitalWalletForm`, :class:`~payments.forms.CashBranchForm` y :class:`~payments.forms.ReceivingMethodForm`.
- Integridad y reglas del modelo :class:`~payments.models.ReceivingMethod` (cuentas de acreditación de fondos).
- Vistas CBV web (aislamiento de datos, prevención de IDOR y control de acceso).
- Endpoints de API REST (GET, POST, PUT, PATCH, DELETE).
"""

from datetime import date
from decimal import Decimal
import json
import re
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
import stripe

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
from payments.models import (
    EntidadFinanciera,
    PaymentGatewayRecord,
    PaymentMethod,
    PaymentWebhookEvent,
    ReceivingMethod,
)
from payments.services import StripeService
from rates.models import Currency, ExchangeRate
from transactions.models import Transaction

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


# ==============================================================================
# PRUEBAS AUTOMATIZADAS: PASARELA STRIPE Y WEBHOOKS (SCRUM-92 / SCRUM-87)
# ==============================================================================

class StripeTestBaseMixin:
    """
    Mixin auxiliar para inicializar datos base de transacciones y clientes en pruebas de Stripe.
    """

    def setUp(self):
        super().setUp()
        self.cliente = Cliente.objects.create(
            nombre='Carlos Stripe',
            documento_ruc='4455667-8',
            correo='carlos.stripe@test.com',
            segmentacion=Cliente.Segmentacion.MINORISTA,
        )
        self.user = User.objects.create_user(
            username='carlos_stripe',
            email='carlos.stripe@test.com',
            password='TestPassword123!',
        )
        CustomerUserAssignment.objects.create(
            customer=self.cliente,
            user=self.user,
            is_primary_representative=True,
            is_active=True,
        )

        self.otro_cliente = Cliente.objects.create(
            nombre='Ana Externa',
            documento_ruc='9988776-5',
            correo='ana.externa@test.com',
            segmentacion=Cliente.Segmentacion.CORPORATIVO,
        )
        self.otro_user = User.objects.create_user(
            username='ana_externa',
            email='ana.externa@test.com',
            password='TestPassword123!',
        )
        CustomerUserAssignment.objects.create(
            customer=self.otro_cliente,
            user=self.otro_user,
            is_primary_representative=True,
            is_active=True,
        )

        self.usd, _ = Currency.objects.get_or_create(
            code='USD',
            defaults={'name': 'Dólar Estadounidense', 'symbol': '$', 'decimals': 2, 'is_active': True},
        )
        self.pyg, _ = Currency.objects.get_or_create(
            code='PYG',
            defaults={'name': 'Guaraní Paraguayo', 'symbol': '₲', 'decimals': 0, 'is_active': True},
        )

        self.banco, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Banco de Prueba Stripe',
            defaults={'tipo': EntidadFinanciera.TipoEntidad.BANCO, 'activo': True},
        )
        self.medio_pago = PaymentMethod.objects.create(
            cliente=self.cliente,
            tipo_medio=PaymentMethod.TipoMedio.TARJETA,
            entidad_bancaria=self.banco,
            numero_cuenta='1111222233334444',
            titular='Carlos Stripe',
            tarjeta_ultimos_digitos='4444',
            tarjeta_mes_vencimiento=12,
            tarjeta_anio_vencimiento=2030,
            es_predeterminado=True,
            activo=True,
        )
        self.medio_acreditacion = ReceivingMethod.objects.create(
            cliente=self.cliente,
            entidad_bancaria=self.banco,
            tipo_cuenta=ReceivingMethod.TipoCuenta.AHORRO,
            numero_cuenta='987654321',
            titular='Carlos Stripe',
            es_predeterminado=True,
            activo=True,
        )

        self.transaccion = Transaction.objects.create(
            codigo_referencia='TX-STRIPE-001',
            cliente=self.cliente,
            tipo_operacion=Transaction.TipoOperacion.COMPRA,
            base_currency=self.usd,
            target_currency=self.pyg,
            tasa_base=Decimal('7500.00'),
            comision_segmento=Decimal('0.00'),
            tasa_neta=Decimal('7500.00'),
            monto_origen=Decimal('100.00'),
            monto_destino=Decimal('750000.00'),
            medio_pago_origen=self.medio_pago,
            medio_acreditacion_destino=self.medio_acreditacion,
            estado=Transaction.Estado.PENDIENTE,
        )


class PaymentGatewayModelTestCase(StripeTestBaseMixin, TestCase):
    """
    Pruebas unitarias para los modelos de datos de pasarela PaymentGatewayRecord y PaymentWebhookEvent.
    """

    def test_create_payment_gateway_record(self):
        record = PaymentGatewayRecord.objects.create(
            cliente=self.cliente,
            transaction=self.transaccion,
            gateway=PaymentGatewayRecord.Gateway.STRIPE,
            session_id='cs_test_session_123',
            payment_intent_id='pi_test_intent_123',
            monto=Decimal('100.00'),
            moneda='USD',
            estado=PaymentGatewayRecord.Estado.PENDIENTE,
            checkout_url='https://checkout.stripe.com/pay/cs_test_session_123',
            referencia_externa='TX-STRIPE-001',
        )
        self.assertIsNotNone(record.id)
        self.assertEqual(record.gateway, 'STRIPE')
        self.assertEqual(record.estado, 'PENDIENTE')
        self.assertFalse(record.is_paid)
        self.assertIn('Stripe', str(record))
        self.assertIn('cs_test_session_123', str(record))

    def test_gateway_record_is_paid_when_completed(self):
        record = PaymentGatewayRecord.objects.create(
            cliente=self.cliente,
            transaction=self.transaccion,
            gateway=PaymentGatewayRecord.Gateway.STRIPE,
            monto=Decimal('50.00'),
            moneda='USD',
            estado=PaymentGatewayRecord.Estado.COMPLETADO,
        )
        self.assertTrue(record.is_paid)

    def test_webhook_event_create_and_unique_constraint(self):
        event = PaymentWebhookEvent.objects.create(
            event_id='evt_test_unique_001',
            gateway='STRIPE',
            tipo_evento='checkout.session.completed',
            payload={'id': 'evt_test_unique_001'},
            procesado=False,
        )
        self.assertIsNotNone(event.id)
        self.assertIn('evt_test_unique_001', str(event))
        self.assertIn('Pendiente', str(event))

        # El identificador debe ser único
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            PaymentWebhookEvent.objects.create(
                event_id='evt_test_unique_001',
                tipo_evento='otro.evento',
            )


class StripeServiceTestCase(StripeTestBaseMixin, TestCase):
    """
    Pruebas unitarias para los métodos y lógica de negocio de StripeService.
    """

    def test_amount_conversions(self):
        # Moneda estándar con decimales: USD
        self.assertEqual(StripeService.to_stripe_amount(Decimal('10.50'), 'USD'), 1050)
        self.assertEqual(StripeService.to_stripe_amount(100, 'EUR'), 10000)
        self.assertEqual(StripeService.from_stripe_amount(1050, 'USD'), Decimal('10.50'))

        # Moneda de cero decimales: PYG
        self.assertEqual(StripeService.to_stripe_amount(Decimal('750000'), 'PYG'), 750000)
        self.assertEqual(StripeService.from_stripe_amount(750000, 'PYG'), Decimal('750000'))

    def test_get_api_key_and_secret(self):
        with self.settings(STRIPE_SECRET_KEY='sk_test_custom_key'):
            self.assertEqual(StripeService.get_api_key(), 'sk_test_custom_key')

        with self.settings(STRIPE_SECRET_KEY=''):
            with self.assertRaises(ValidationError):
                StripeService.get_api_key()

        with self.settings(STRIPE_WEBHOOK_SECRET='whsec_custom_secret'):
            self.assertEqual(StripeService.get_webhook_secret(), 'whsec_custom_secret')

        with self.settings(STRIPE_WEBHOOK_SECRET=''):
            with self.assertRaises(ValidationError):
                StripeService.get_webhook_secret()

    @patch('stripe.checkout.Session.create')
    def test_create_checkout_session_success(self, mock_session_create):
        mock_session = MagicMock()
        mock_session.id = 'cs_test_mock_12345'
        mock_session.url = 'https://checkout.stripe.com/pay/cs_test_mock_12345'
        mock_session.status = 'open'
        mock_session.payment_intent = None
        mock_session_create.return_value = mock_session

        with self.settings(STRIPE_SECRET_KEY='sk_test_valid_key'):
            result = StripeService.create_checkout_session(
                transaction_obj=self.transaccion,
                success_url='http://testserver/success',
                cancel_url='http://testserver/cancel',
            )

        self.assertEqual(result['session_id'], 'cs_test_mock_12345')
        self.assertEqual(result['checkout_url'], mock_session.url)
        self.assertEqual(result['status'], 'open')

        record = PaymentGatewayRecord.objects.get(session_id='cs_test_mock_12345')
        self.assertEqual(record.transaction, self.transaccion)
        self.assertEqual(record.cliente, self.cliente)
        self.assertEqual(record.estado, PaymentGatewayRecord.Estado.PENDIENTE)
        self.assertEqual(record.monto, self.transaccion.monto_origen)

    def test_create_checkout_session_zero_amount_raises_error(self):
        self.transaccion.monto_origen = Decimal('0.00')
        with self.settings(STRIPE_SECRET_KEY='sk_test_valid_key'):
            with self.assertRaises(ValidationError):
                StripeService.create_checkout_session(self.transaccion)

    @patch('stripe.PaymentIntent.create')
    def test_create_payment_intent_success(self, mock_intent_create):
        mock_intent = MagicMock()
        mock_intent.id = 'pi_test_mock_999'
        mock_intent.client_secret = 'pi_test_mock_999_secret'
        mock_intent.status = 'requires_payment_method'
        mock_intent_create.return_value = mock_intent

        with self.settings(STRIPE_SECRET_KEY='sk_test_valid_key'):
            result = StripeService.create_payment_intent(self.transaccion)

        self.assertEqual(result['payment_intent_id'], 'pi_test_mock_999')
        self.assertEqual(result['client_secret'], 'pi_test_mock_999_secret')

        record = PaymentGatewayRecord.objects.get(payment_intent_id='pi_test_mock_999')
        self.assertEqual(record.transaction, self.transaccion)
        self.assertEqual(record.estado, PaymentGatewayRecord.Estado.PENDIENTE)

    def test_verify_webhook_signature_missing_header(self):
        with self.assertRaises(ValidationError):
            StripeService.verify_webhook_signature(b'payload', '')

    @patch('stripe.Webhook.construct_event')
    def test_verify_webhook_signature_invalid(self, mock_construct):
        mock_construct.side_effect = stripe.SignatureVerificationError('Firma incorrecta', 'sig_header')
        with self.settings(STRIPE_WEBHOOK_SECRET='whsec_test'):
            with self.assertRaises(ValidationError):
                StripeService.verify_webhook_signature(b'bad_payload', 't=123,v1=abc')

    @patch('stripe.Webhook.construct_event')
    def test_verify_webhook_signature_valid(self, mock_construct):
        mock_construct.return_value = {'id': 'evt_valid_123', 'type': 'checkout.session.completed'}
        with self.settings(STRIPE_WEBHOOK_SECRET='whsec_test'):
            event = StripeService.verify_webhook_signature(b'valid_payload', 't=123,v1=abc')
        self.assertEqual(event['id'], 'evt_valid_123')

    def test_process_webhook_checkout_session_completed(self):
        # Crear registro de pasarela previo en estado PENDIENTE
        record = PaymentGatewayRecord.objects.create(
            cliente=self.cliente,
            transaction=self.transaccion,
            gateway=PaymentGatewayRecord.Gateway.STRIPE,
            session_id='cs_completed_123',
            monto=Decimal('100.00'),
            moneda='USD',
            estado=PaymentGatewayRecord.Estado.PENDIENTE,
        )

        event_data = {
            'id': 'evt_checkout_completed_001',
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'id': 'cs_completed_123',
                    'payment_intent': 'pi_completed_123',
                    'amount_total': 10000,
                    'currency': 'usd',
                    'metadata': {
                        'transaction_id': str(self.transaccion.id),
                        'codigo_referencia': self.transaccion.codigo_referencia,
                    },
                }
            }
        }

        result = StripeService.process_webhook_event(event_data)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['event_id'], 'evt_checkout_completed_001')

        # Verificar que el registro de pasarela pasó a COMPLETADO
        record.refresh_from_db()
        self.assertEqual(record.estado, PaymentGatewayRecord.Estado.COMPLETADO)
        self.assertEqual(record.payment_intent_id, 'pi_completed_123')

        # Verificar que la transacción cambió a COMPLETADA
        self.transaccion.refresh_from_db()
        self.assertEqual(self.transaccion.estado, Transaction.Estado.COMPLETADA)
        self.assertIn('Stripe', self.transaccion.observaciones)

        # Verificar idempotencia en reenvío del mismo webhook
        repeat_result = StripeService.process_webhook_event(event_data)
        self.assertEqual(repeat_result['status'], 'already_processed')

    def test_process_webhook_payment_intent_succeeded(self):
        record = PaymentGatewayRecord.objects.create(
            cliente=self.cliente,
            transaction=self.transaccion,
            gateway=PaymentGatewayRecord.Gateway.STRIPE,
            payment_intent_id='pi_success_999',
            monto=Decimal('100.00'),
            moneda='USD',
            estado=PaymentGatewayRecord.Estado.PENDIENTE,
        )

        event_data = {
            'id': 'evt_pi_succeeded_001',
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': 'pi_success_999',
                    'amount_received': 10000,
                    'currency': 'usd',
                    'metadata': {
                        'transaction_id': str(self.transaccion.id),
                    },
                }
            }
        }

        result = StripeService.process_webhook_event(event_data)
        self.assertEqual(result['status'], 'success')

        record.refresh_from_db()
        self.assertEqual(record.estado, PaymentGatewayRecord.Estado.COMPLETADO)
        self.transaccion.refresh_from_db()
        self.assertEqual(self.transaccion.estado, Transaction.Estado.COMPLETADA)

    def test_process_webhook_payment_intent_failed(self):
        record = PaymentGatewayRecord.objects.create(
            cliente=self.cliente,
            transaction=self.transaccion,
            gateway=PaymentGatewayRecord.Gateway.STRIPE,
            payment_intent_id='pi_failed_888',
            monto=Decimal('100.00'),
            moneda='USD',
            estado=PaymentGatewayRecord.Estado.PENDIENTE,
        )

        event_data = {
            'id': 'evt_pi_failed_001',
            'type': 'payment_intent.payment_failed',
            'data': {
                'object': {
                    'id': 'pi_failed_888',
                    'last_payment_error': {
                        'message': 'Fondos insuficientes.',
                    },
                }
            }
        }

        result = StripeService.process_webhook_event(event_data)
        self.assertEqual(result['status'], 'success')

        record.refresh_from_db()
        self.assertEqual(record.estado, PaymentGatewayRecord.Estado.FALLIDO)
        self.assertIn('Fondos insuficientes', record.error_mensaje)

    def test_process_webhook_checkout_session_expired(self):
        record = PaymentGatewayRecord.objects.create(
            cliente=self.cliente,
            transaction=self.transaccion,
            gateway=PaymentGatewayRecord.Gateway.STRIPE,
            session_id='cs_expired_777',
            monto=Decimal('100.00'),
            moneda='USD',
            estado=PaymentGatewayRecord.Estado.PENDIENTE,
        )

        event_data = {
            'id': 'evt_cs_expired_001',
            'type': 'checkout.session.expired',
            'data': {
                'object': {
                    'id': 'cs_expired_777',
                }
            }
        }

        result = StripeService.process_webhook_event(event_data)
        self.assertEqual(result['status'], 'success')

        record.refresh_from_db()
        self.assertEqual(record.estado, PaymentGatewayRecord.Estado.CANCELADO)


class StripeWebhookEndpointTestCase(StripeTestBaseMixin, TestCase):
    """
    Pruebas HTTP de integración para el endpoint stripe_webhook (/payments/webhook/stripe/).
    """

    def setUp(self):
        super().setUp()
        self.webhook_url = reverse('payments:stripe-webhook')

    def test_webhook_get_method_not_allowed(self):
        response = self.client.get(self.webhook_url)
        self.assertEqual(response.status_code, 405)

    def test_webhook_missing_signature_header_returns_400(self):
        response = self.client.post(
            self.webhook_url,
            data=json.dumps({'test': 'data'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Stripe-Signature', response.json()['error'])

    @patch.object(StripeService, 'verify_webhook_signature')
    def test_webhook_invalid_signature_returns_400(self, mock_verify):
        mock_verify.side_effect = ValidationError('Firma de webhook de Stripe inválida.')
        response = self.client.post(
            self.webhook_url,
            data=b'raw_payload_bytes',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='invalid_signature',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('inválida', response.json()['error'])

    @patch.object(StripeService, 'verify_webhook_signature')
    @patch.object(StripeService, 'process_webhook_event')
    def test_webhook_successful_processing_returns_200(self, mock_process, mock_verify):
        mock_verify.return_value = {
            'id': 'evt_http_test_100',
            'type': 'checkout.session.completed',
        }
        mock_process.return_value = {
            'status': 'success',
            'event_id': 'evt_http_test_100',
            'action': 'checkout_completed',
        }

        response = self.client.post(
            self.webhook_url,
            data=b'valid_raw_bytes',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=123,v1=signature_valid',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')


class StripeCreateCheckoutSessionViewTestCase(StripeTestBaseMixin, TestCase):
    """
    Pruebas HTTP para la vista StripeCreateCheckoutSessionView.
    """

    def setUp(self):
        super().setUp()
        self.checkout_url = reverse('payments:stripe-create-checkout', kwargs={'transaction_id': self.transaccion.id})

    def test_checkout_view_requires_login(self):
        response = self.client.post(self.checkout_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/oidc/authenticate/', response.url)

    def test_checkout_view_forbidden_for_other_customer(self):
        self.client.force_login(self.otro_user)
        response = self.client.post(self.checkout_url)
        self.assertEqual(response.status_code, 403)

    def test_checkout_view_rejected_if_not_pending(self):
        self.transaccion.estado = Transaction.Estado.COMPLETADA
        self.transaccion.save(update_fields=['estado'])

        self.client.force_login(self.user)
        response = self.client.post(self.checkout_url)
        self.assertEqual(response.status_code, 400)
        self.assertIn('pendiente', response.json()['error'])

    @patch.object(StripeService, 'create_checkout_session')
    def test_checkout_view_success_ajax(self, mock_create):
        mock_create.return_value = {
            'session_id': 'cs_ajax_123',
            'checkout_url': 'https://checkout.stripe.com/pay/cs_ajax_123',
            'status': 'open',
        }
        self.client.force_login(self.user)
        response = self.client.post(
            self.checkout_url,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['session_id'], 'cs_ajax_123')

    @patch.object(StripeService, 'create_checkout_session')
    def test_checkout_view_success_redirect(self, mock_create):
        mock_create.return_value = {
            'session_id': 'cs_redir_123',
            'checkout_url': 'https://checkout.stripe.com/pay/cs_redir_123',
            'status': 'open',
        }
        self.client.force_login(self.user)
        response = self.client.post(self.checkout_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'https://checkout.stripe.com/pay/cs_redir_123')

