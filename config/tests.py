"""Pruebas de integración para el visualizador de documentación Sphinx."""

from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


class ServeSphinxDocsTests(TestCase):
    """Verifica el índice y los controles de ruta de la documentación compilada."""

    def setUp(self):
        user = get_user_model().objects.create_user(
            username='sphinx_docs_user',
            password='Password123!',
        )
        self.client.force_login(user)

    def test_serves_sphinx_index_from_html_build_directory(self):
        with TemporaryDirectory() as temporary_directory:
            build_directory = Path(temporary_directory) / 'docs' / 'sphinx' / 'build' / 'html'
            build_directory.mkdir(parents=True)
            (build_directory / 'index.html').write_text(
                '<html><body>Documentación Global Exchange</body></html>',
                encoding='utf-8',
            )

            with override_settings(BASE_DIR=Path(temporary_directory)):
                response = self.client.get(reverse('sphinx_docs', kwargs={'path': ''}))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Documentación Global Exchange')
                response.close()

    def test_rejects_path_traversal(self):
        response = self.client.get('/docs/../../config/settings.py')

        self.assertEqual(response.status_code, 404)
