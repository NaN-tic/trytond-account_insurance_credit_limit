
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.modules.company.tests import CompanyTestMixin
from trytond.modules.company.tests import create_company, set_company
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import with_transaction


class AccountInsuranceCreditLimitTestCase(CompanyTestMixin, ModuleTestCase):
    'Test AccountInsuranceCreditLimit module'
    module = 'account_insurance_credit_limit'

    @with_transaction()
    def test_credit_limit_amount_matches_multivalue(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Party = pool.get('party.party')
        PartyCredit = pool.get('party.credit')

        company = create_company()
        with set_company(company):
            party, = Party.create([{
                        'name': 'Party',
                        }])
            party.company_credit_limit = Decimal('100')
            party.save()

            today = Date.today()
            credit, = PartyCredit.create([{
                        'party': party.id,
                        'company': company.id,
                        'start_date': today,
                        'end_date': today,
                        'requested_credit_limit': Decimal('50'),
                        'first_approved_credit_limit': Decimal('50'),
                        }])
            PartyCredit.approve([credit])

            party, = Party.browse([party.id])
            self.assertEqual(
                party.get_multivalue('credit_limit_amount',
                    company=company.id),
                Decimal('150'))
            self.assertEqual(party.credit_limit_amount, Decimal('150'))


del ModuleTestCase
