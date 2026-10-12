"""
Paquete contenedor conceptual de aplicaciones para Global Exchange.

Provee resolución dinámica para importaciones bajo el espacio de nombres `apps.*`.
"""

import sys
import authentication
import customers
import payments
import rates
import transactions

sys.modules['apps.authentication'] = authentication
sys.modules['apps.customers'] = customers
sys.modules['apps.payments'] = payments
sys.modules['apps.rates'] = rates
sys.modules['apps.transactions'] = transactions

# Export test module references for apps.* paths
if hasattr(authentication, 'tests'):
    sys.modules['apps.authentication.tests'] = authentication.tests
if hasattr(customers, 'tests'):
    sys.modules['apps.customers.tests'] = customers.tests
if hasattr(payments, 'tests'):
    sys.modules['apps.payments.tests'] = payments.tests
if hasattr(rates, 'tests'):
    sys.modules['apps.rates.tests'] = rates.tests
if hasattr(transactions, 'tests'):
    sys.modules['apps.transactions.tests'] = transactions.tests
