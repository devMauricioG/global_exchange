"""
Paquete contenedor conceptual de aplicaciones para Global Exchange.

Provee resolución dinámica para importaciones bajo el espacio de nombres `apps.*`.
"""

import sys
import payments

sys.modules['apps.payments'] = payments
