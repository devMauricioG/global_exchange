"""
Módulo de pruebas automatizadas para la autenticación y el sistema de navegación dinámica por roles.

Valida el procesador de contexto :func:`~authentication.context_processors.auth_roles`,
los filtros y etiquetas personalizadas de plantilla en :mod:`~authentication.templatetags.auth_tags`,
y la renderización condicional de la barra de navegación y el dashboard principal.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.template import Context, Template
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from authentication.context_processors import auth_roles
from authentication.templatetags.auth_tags import has_any_role, has_role, user_role_badge

User = get_user_model()


class ContextProcessorAuthRolesTests(TestCase):
    """
    Suite de pruebas para el procesador de contexto :func:`~authentication.context_processors.auth_roles`.
    """

    def setUp(self):
        """Prepara la fábrica de solicitudes HTTP y los grupos de roles."""
        self.factory = RequestFactory()
        self.group_admin, _ = Group.objects.get_or_create(name='admin')
        self.group_operator, _ = Group.objects.get_or_create(name='operator')
        self.group_user, _ = Group.objects.get_or_create(name='user')

    def test_anonymous_user(self):
        """Verifica que un usuario anónimo reciba variables por defecto sin privilegios."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        context = auth_roles(request)

        self.assertEqual(context['user_roles'], [])
        self.assertFalse(context['is_admin'])
        self.assertFalse(context['is_operator'])
        self.assertFalse(context['is_user_role'])
        self.assertEqual(context['primary_role'], 'Invitado')
        self.assertEqual(context['primary_role_code'], 'guest')

    def test_admin_user(self):
        """Verifica que un superusuario o usuario con grupo 'admin' obtenga las banderas de administrador."""
        admin_user = User.objects.create_superuser(
            username='superadmin',
            email='admin@globalexchange.com',
            password='AdminPassword123!',
        )
        request = self.factory.get('/')
        request.user = admin_user
        context = auth_roles(request)

        self.assertIn('admin', context['user_roles'])
        self.assertTrue(context['is_admin'])
        self.assertTrue(context['is_operator'])
        self.assertEqual(context['primary_role'], 'Administrador')
        self.assertEqual(context['primary_role_code'], 'admin')

    def test_operator_user(self):
        """Verifica que un usuario con grupo 'operator' obtenga privilegios operativos pero no de administración."""
        op_user = User.objects.create_user(
            username='operador1',
            email='operador1@globalexchange.com',
            password='OpPassword123!',
            is_staff=True,
        )
        op_user.groups.add(self.group_operator)

        request = self.factory.get('/')
        request.user = op_user
        context = auth_roles(request)

        self.assertIn('operator', context['user_roles'])
        self.assertFalse(context['is_admin'])
        self.assertTrue(context['is_operator'])
        self.assertEqual(context['primary_role'], 'Operador')
        self.assertEqual(context['primary_role_code'], 'operator')

    def test_standard_user(self):
        """Verifica que un usuario estándar sin privilegios especiales reciba el rol de Usuario."""
        std_user = User.objects.create_user(
            username='cliente_user',
            email='user@gmail.com',
            password='UserPassword123!',
        )
        std_user.groups.add(self.group_user)

        request = self.factory.get('/')
        request.user = std_user
        context = auth_roles(request)

        self.assertIn('user', context['user_roles'])
        self.assertFalse(context['is_admin'])
        self.assertFalse(context['is_operator'])
        self.assertTrue(context['is_user_role'])
        self.assertEqual(context['primary_role'], 'Usuario')
        self.assertEqual(context['primary_role_code'], 'user')


class AuthTemplateTagsTests(TestCase):
    """
    Suite de pruebas para las etiquetas y filtros de plantilla en :mod:`~authentication.templatetags.auth_tags`.
    """

    def setUp(self):
        """Inicializa usuarios con distintos roles para pruebas de template tags."""
        self.group_admin, _ = Group.objects.get_or_create(name='admin')
        self.group_operator, _ = Group.objects.get_or_create(name='operator')
        self.group_user, _ = Group.objects.get_or_create(name='user')

        self.admin_user = User.objects.create_superuser(
            username='admin_tag',
            email='admin_tag@test.com',
            password='Password123!',
        )
        self.op_user = User.objects.create_user(
            username='op_tag',
            email='op_tag@test.com',
            password='Password123!',
            is_staff=True,
        )
        self.op_user.groups.add(self.group_operator)

        self.std_user = User.objects.create_user(
            username='std_tag',
            email='std_tag@test.com',
            password='Password123!',
        )
        self.std_user.groups.add(self.group_user)

    def test_has_role_filter(self):
        """Valida el filtro has_role para distintos roles."""
        self.assertTrue(has_role(self.admin_user, 'admin'))
        self.assertTrue(has_role(self.admin_user, 'operator'))

        self.assertFalse(has_role(self.op_user, 'admin'))
        self.assertTrue(has_role(self.op_user, 'operator'))

        self.assertFalse(has_role(self.std_user, 'admin'))
        self.assertFalse(has_role(self.std_user, 'operator'))
        self.assertTrue(has_role(self.std_user, 'user'))

        self.assertFalse(has_role(AnonymousUser(), 'admin'))

    def test_has_any_role_filter(self):
        """Valida el filtro has_any_role con listas de roles separadas por coma."""
        self.assertTrue(has_any_role(self.admin_user, 'admin,operator'))
        self.assertTrue(has_any_role(self.op_user, 'admin,operator'))
        self.assertFalse(has_any_role(self.std_user, 'admin,operator'))
        self.assertTrue(has_any_role(self.std_user, 'user,guest'))

    def test_user_role_badge_tag(self):
        """Verifica la generación correcta del HTML del badge de rol."""
        badge_admin = user_role_badge(self.admin_user)
        self.assertIn('role-admin', badge_admin)
        self.assertIn('Administrador', badge_admin)

        badge_op = user_role_badge(self.op_user)
        self.assertIn('role-operator', badge_op)
        self.assertIn('Operador', badge_op)

        badge_user = user_role_badge(self.std_user)
        self.assertIn('role-user', badge_user)
        self.assertIn('Usuario', badge_user)

        badge_anon = user_role_badge(AnonymousUser())
        self.assertIn('role-guest', badge_anon)


class DynamicNavbarRenderingTests(TestCase):
    """
    Pruebas de renderizado de la barra de navegación dinámica en base.html y home.html.
    """

    def setUp(self):
        """Configura clientes autenticados para Admin, Operador y Usuario."""
        self.group_operator, _ = Group.objects.get_or_create(name='operator')
        self.group_user, _ = Group.objects.get_or_create(name='user')

        self.admin_user = User.objects.create_superuser(
            username='admin_nav',
            email='admin_nav@test.com',
            password='Password123!',
        )
        self.client_admin = Client()
        self.client_admin.force_login(self.admin_user)

        self.op_user = User.objects.create_user(
            username='op_nav',
            email='op_nav@test.com',
            password='Password123!',
            is_staff=True,
        )
        self.op_user.groups.add(self.group_operator)
        self.client_operator = Client()
        self.client_operator.force_login(self.op_user)

        self.std_user = User.objects.create_user(
            username='std_nav',
            email='std_nav@test.com',
            password='Password123!',
        )
        self.std_user.groups.add(self.group_user)
        self.client_user = Client()
        self.client_user.force_login(self.std_user)

    def test_admin_sees_all_navigation_links(self):
        """Verifica que el Administrador vea Inicio, Clientes y Panel Admin en la barra de navegación."""
        response = self.client_admin.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inicio')
        self.assertContains(response, 'Clientes')
        self.assertContains(response, 'Panel Admin')
        self.assertContains(response, 'Administrador')

    def test_operator_sees_clients_but_not_admin_panel(self):
        """Verifica que el Operador vea Clientes, pero NO tenga acceso al Panel Admin en el menú."""
        response = self.client_operator.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inicio')
        self.assertContains(response, 'Clientes')
        self.assertNotContains(response, 'Panel Admin')
        self.assertContains(response, 'Operador')

    def test_standard_user_sees_only_basic_menu(self):
        """Verifica que el Usuario estándar vea Inicio, pero no Clientes ni Panel Admin en el menú principal."""
        response = self.client_user.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inicio')
        self.assertNotContains(response, 'Panel Admin')
        self.assertContains(response, 'Usuario')

    def test_unauthenticated_user_redirects(self):
        """Verifica que un usuario no autenticado sea redirigido a login al intentar acceder a la raíz."""
        client = Client()
        response = client.get(reverse('home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/oidc/authenticate/', response.url)


class KeycloakBackendVinculationTests(TestCase):
    """
    Suite de pruebas para validar la vinculación de Cliente desde el backend OIDC.
    """

    def setUp(self):
        """Inicializa el backend de autenticación."""
        from authentication.backends import KeycloakOIDCAuthenticationBackend
        self.backend = KeycloakOIDCAuthenticationBackend()

    def test_create_user_links_cliente(self):
        """Verifica que al invocar create_user con claims OIDC se cree y vincule el Cliente."""
        from customers.models import Cliente

        claims = {
            'sub': 'oidc-backend-sub-001',
            'email': 'oidc.user@globalexchange.com',
            'preferred_username': 'oidc_user',
            'given_name': 'Juan',
            'family_name': 'OIDC',
            'realm_roles': ['user'],
        }

        user = self.backend.create_user(claims)
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'oidc_user')

        cliente = Cliente.objects.filter(keycloak_id='oidc-backend-sub-001').first()
        self.assertIsNotNone(cliente)
        self.assertTrue(cliente.assignments.filter(user=user, is_primary_representative=True, is_active=True).exists())
        self.assertEqual(cliente.representante_principal.user, user)
        self.assertEqual(cliente.correo, 'oidc.user@globalexchange.com')
        self.assertEqual(cliente.nombre, 'Juan OIDC')

    def test_update_user_syncs_cliente(self):
        """Verifica que al actualizar usuario con update_user se sincronice la vinculación de Cliente."""
        from customers.models import Cliente

        claims_initial = {
            'sub': 'oidc-backend-sub-002',
            'email': 'update.user@globalexchange.com',
            'preferred_username': 'update_user',
            'given_name': 'Pedro',
            'family_name': 'Inicial',
            'realm_roles': ['user'],
        }
        user = self.backend.create_user(claims_initial)

        claims_updated = {
            'sub': 'oidc-backend-sub-002',
            'email': 'update.user@globalexchange.com',
            'preferred_username': 'update_user',
            'given_name': 'Pedro',
            'family_name': 'Actualizado',
            'realm_roles': ['operator'],
        }
        self.backend.update_user(user, claims_updated)

        cliente = Cliente.objects.filter(keycloak_id='oidc-backend-sub-002').first()
        self.assertIsNotNone(cliente)
        self.assertTrue(cliente.assignments.filter(user=user, is_active=True).exists())
        self.assertEqual(cliente.representante_principal.user, user)



class AuthLoginRedirectTests(TestCase):
    """
    Suite de pruebas para verificar que las rutas protegidas redirijan correctamente
    a OIDC cuando el usuario no está autenticado, y sean accesibles con sesión activa.
    """

    def setUp(self):
        """Crea un usuario autenticado para pruebas de acceso."""
        self.group_operator, _ = Group.objects.get_or_create(name='operator')

        self.auth_user = User.objects.create_user(
            username='redirect_tester',
            email='redirect@globalexchange.com',
            password='Password123!',
            is_staff=True,
        )
        self.auth_user.groups.add(self.group_operator)

        self.client_auth = Client()
        self.client_auth.force_login(self.auth_user)

    def test_unauthenticated_customer_list_redirects(self):
        """Verifica que /customers/ redirija a OIDC cuando el usuario no está autenticado."""
        anon = Client()
        response = anon.get(reverse('customers:cliente-list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/oidc/', response.url)

    def test_unauthenticated_customer_detail_redirects(self):
        """Verifica que /customers/<pk>/ redirija a OIDC cuando el usuario no está autenticado."""
        from customers.models import Cliente
        cliente = Cliente.objects.create(
            nombre='Cliente Redirect Test',
            documento_ruc='REDIRECT-001',
            correo='redirect.test@test.com',
        )
        anon = Client()
        response = anon.get(reverse('customers:cliente-detail', kwargs={'pk': cliente.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/oidc/', response.url)

    def test_authenticated_accesses_home(self):
        """Verifica que un usuario autenticado acceda a home con HTTP 200."""
        response = self.client_auth.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_authenticated_accesses_customer_list(self):
        """Verifica que un operador autenticado acceda al listado de clientes con HTTP 200."""
        response = self.client_auth.get(reverse('customers:cliente-list'))
        self.assertEqual(response.status_code, 200)


class AuthRoleInheritanceTests(TestCase):
    """
    Suite de pruebas para validar la herencia de privilegios por rol y las
    restricciones de acceso basadas en grupos de usuarios (RBAC).
    """

    def setUp(self):
        """Configura usuarios con distintos perfiles de rol."""
        self.group_admin, _ = Group.objects.get_or_create(name='admin')
        self.group_operator, _ = Group.objects.get_or_create(name='operator')
        self.group_user, _ = Group.objects.get_or_create(name='user')

        self.admin_user = User.objects.create_superuser(
            username='admin_rbac',
            email='admin_rbac@globalexchange.com',
            password='AdminPass123!',
        )
        self.client_admin = Client()
        self.client_admin.force_login(self.admin_user)

        self.op_user = User.objects.create_user(
            username='op_rbac',
            email='op_rbac@globalexchange.com',
            password='OpPass123!',
            is_staff=True,
        )
        self.op_user.groups.add(self.group_operator)
        self.client_operator = Client()
        self.client_operator.force_login(self.op_user)

        self.std_user = User.objects.create_user(
            username='std_rbac',
            email='std_rbac@globalexchange.com',
            password='UserPass123!',
        )
        self.std_user.groups.add(self.group_user)
        self.client_user = Client()
        self.client_user.force_login(self.std_user)

    def test_admin_inherits_operator_privileges(self):
        """Verifica que el admin pueda acceder a las rutas del operador (clientes)."""
        response = self.client_admin.get(reverse('customers:cliente-list'))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access_django_admin_panel(self):
        """Verifica que el superusuario (admin) pueda acceder al panel de administración de Django."""
        response = self.client_admin.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)

    def test_standard_user_cannot_access_admin_panel(self):
        """Verifica que un usuario estándar (sin is_staff) sea redirigido al intentar acceder al panel de administración."""
        response = self.client_user.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_admin_role_flags_are_correct(self):
        """Verifica que las banderas de rol del contexto sean correctas para cada tipo de usuario."""
        from authentication.context_processors import auth_roles
        from django.test import RequestFactory

        factory = RequestFactory()
        req_admin = factory.get('/')
        req_admin.user = self.admin_user
        ctx_admin = auth_roles(req_admin)
        self.assertTrue(ctx_admin['is_admin'])
        self.assertTrue(ctx_admin['is_operator'])

        req_op = factory.get('/')
        req_op.user = self.op_user
        ctx_op = auth_roles(req_op)
        self.assertFalse(ctx_op['is_admin'])
        self.assertTrue(ctx_op['is_operator'])

        req_std = factory.get('/')
        req_std.user = self.std_user
        ctx_std = auth_roles(req_std)
        self.assertFalse(ctx_std['is_admin'])
        self.assertFalse(ctx_std['is_operator'])
        self.assertTrue(ctx_std['is_user_role'])


class KeycloakLogoutIntegrationTests(TestCase):
    """Pruebas de integración para la invalidación de sesión OIDC."""

    @override_settings(
        OIDC_OP_LOGOUT_ENDPOINT='https://keycloak.example.test/logout',
        OIDC_RP_CLIENT_ID='global-exchange-test',
        LOGOUT_REDIRECT_URL='/',
    )
    def test_logout_invalidates_local_session_and_redirects_to_keycloak(self):
        user = User.objects.create_user(
            username='logout_user',
            email='logout@test.com',
            password='Password123!',
        )
        client = Client()
        client.force_login(user)

        response = client.get(reverse('authentication:logout'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('https://keycloak.example.test/logout?', response.url)
        self.assertIn('client_id=global-exchange-test', response.url)
        self.assertNotIn('_auth_user_id', client.session)
