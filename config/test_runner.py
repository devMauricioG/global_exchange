"""Test runner que impide tráfico de red durante la suite unitaria."""

from unittest.mock import patch

from django.test.runner import DiscoverRunner


class OfflineDiscoverRunner(DiscoverRunner):
    """Hace que toda conexión de red sea un fallo inmediato y determinista."""

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._network_blockers = [
            patch('socket.socket.connect', side_effect=AssertionError(
                'SCRUM-125: no se permiten conexiones de red durante las pruebas unitarias.'
            )),
            patch('socket.socket.connect_ex', side_effect=AssertionError(
                'SCRUM-125: no se permiten conexiones de red durante las pruebas unitarias.'
            )),
        ]
        for blocker in self._network_blockers:
            blocker.start()

    def teardown_test_environment(self, **kwargs):
        for blocker in reversed(getattr(self, '_network_blockers', [])):
            blocker.stop()
        super().teardown_test_environment(**kwargs)
