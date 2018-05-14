# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import doctest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker


class TestAccountInsuranceCreditLimitCase(ModuleTestCase):
    'Test Account Insurance Credit Limit module'
    module = 'account_insurance_credit_limit'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            TestAccountInsuranceCreditLimitCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_account_insurance_credit_limit.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
