import datetime
import unittest
from decimal import Decimal

from proteus import Model, Wizard
from trytond.modules.account.tests.tools import (create_chart,
                                                 create_fiscalyear, create_tax)
from trytond.modules.account_invoice.tests.tools import (
    create_payment_term, set_fiscalyear_invoice_sequences)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.party.exceptions import EraseError
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Install contract
        activate_modules('account_insurance_credit_limit')

        # Create company
        _ = create_company()
        company = get_company()

        # Create fiscal year
        today = datetime.date(2015, 1, 1)
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company, today))
        fiscalyear.click('create_period')
        period = fiscalyear.periods[0]

        # Create chart of accounts
        _ = create_chart(company)

        # Create tax
        tax = create_tax(Decimal('.10'))
        tax.save()

        # Create payment term
        payment_term = create_payment_term()
        payment_term.save()

        # Create parties
        Party = Model.get('party.party')
        party = Party(name='Customer')
        party.save()
        party2 = Party(name='Customer')
        party2.save()

        # Create Account Insurance Credit
        InsuranceCredit = Model.get('party.credit')
        ins_credit = InsuranceCredit()
        ins_credit.party = party
        ins_credit.start_date = period.start_date
        ins_credit.end_date = period.end_date
        ins_credit.requested_credit_limit = Decimal('20.00')
        ins_credit.first_approved_credit_limit = Decimal('20.00')
        ins_credit.save()

        # Try erase active party
        erase = Wizard('party.erase', models=[party])
        self.assertEqual(erase.form.party == party, True)
        with self.assertRaises(EraseError):

            erase.execute('erase')
