import datetime
import unittest
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from proteus import Model, Wizard
from trytond.exceptions import UserError, UserWarning
from trytond.modules.account.tests.tools import (create_chart,
                                                 create_fiscalyear,
                                                 get_accounts)
from trytond.modules.account_invoice.tests.tools import \
    set_fiscalyear_invoice_sequences
from trytond.modules.company.tests.tools import create_company, get_company
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

        # Install product_cost_plan Module
        activate_modules('account_insurance_credit_limit')

        # Create company
        _ = create_company()
        company = get_company()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')
        period = fiscalyear.periods[0]

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        receivable = accounts['receivable']
        revenue = accounts['revenue']
        cash = accounts['cash']

        # Create parties
        Party = Model.get('party.party')
        customer = Party(name='Customer')
        customer.save()

        # Create Moves
        Journal = Model.get('account.journal')
        Move = Model.get('account.move')
        journal_revenue, = Journal.find([
            ('code', '=', 'REV'),
        ])
        journal_cash, = Journal.find([
            ('code', '=', 'CASH'),
        ])
        move = Move()
        move.period = period
        move.company = company
        move.journal = journal_revenue
        move.date = period.start_date + relativedelta(days=1)
        self.assertEqual(move.date, period.start_date + relativedelta(days=1))
        line = move.lines.new()
        line.account = revenue
        line.credit = Decimal(42)
        line = move.lines.new()
        line.account = receivable
        line.debit = Decimal(42)
        line.party = customer
        move.save()
        move2 = Move()
        move2.period = period
        move2.journal = journal_revenue
        move2.company = company
        move2.date = period.start_date + relativedelta(days=2)
        self.assertEqual(move2.date, period.start_date + relativedelta(days=2))
        line = move2.lines.new()
        line.account = revenue
        line.credit = Decimal(20)
        line = move2.lines.new()
        line.account = receivable
        line.debit = Decimal(20)
        line.party = customer
        move2.save()
        move3 = Move()
        move3.period = period
        move3.journal = journal_cash
        move3.company = company
        move3.date = period.start_date + relativedelta(days=2)
        self.assertEqual(move3.date, period.start_date + relativedelta(days=2))
        line = move3.lines.new()
        line.account = cash
        line.debit = Decimal(42)
        line = move3.lines.new()
        line.account = receivable
        line.credit = Decimal(42)
        line.party = customer
        move3.save()
        move4 = Move()
        move4.period = period
        move4.journal = journal_revenue
        move4.company = company
        move4.date = period.start_date + relativedelta(days=2)
        self.assertEqual(move4.date, period.start_date + relativedelta(days=2))
        line = move4.lines.new()
        line.account = revenue
        line.credit = Decimal(10)
        line = move4.lines.new()
        line.account = receivable
        line.debit = Decimal(10)
        line.party = customer
        move4.save()
        move5 = Move()
        move5.period = period
        move5.journal = journal_cash
        move5.company = company
        move5.date = period.start_date + relativedelta(days=2)
        self.assertEqual(move5.date, period.start_date + relativedelta(days=2))
        line = move5.lines.new()
        line.account = cash
        line.debit = Decimal(20)
        line = move5.lines.new()
        line.account = receivable
        line.credit = Decimal(20)
        line.party = customer
        move5.save()

        # Create Account Insurance Credit
        today = datetime.date.today()
        InsuranceCredit = Model.get('party.credit')
        ins_credit = InsuranceCredit()
        ins_credit.party = customer
        self.assertEqual(ins_credit.date == today, True)
        self.assertEqual(ins_credit.start_date == today, True)
        ins_credit.start_date = period.start_date
        self.assertEqual(ins_credit.end_date,
                         today + relativedelta(years=1, days=-1))
        ins_credit.end_date = period.end_date
        ins_credit.requested_credit_limit = Decimal('20.00')
        ins_credit.first_approved_credit_limit = Decimal('20.00')
        ins_credit.save()
        ins_credit.click('approve')
        self.assertEqual(ins_credit.state, 'approved')
        self.assertEqual(ins_credit.approved_credit_limit, Decimal('20.00'))
        self.assertEqual(ins_credit.accounts[0].balance == 42, True)
        self.assertEqual(ins_credit.accounts[1].credit == 62, True)
        self.assertEqual(ins_credit.accounts[1].debit == 30, True)
        self.assertEqual(ins_credit.accounts[1].balance, 10
                         or ins_credit.accounts[1].balance)
        self.assertEqual(ins_credit.maximum_registered == 42, True)

        # Renew Account Insurance Credit
        party_credit_renew = Wizard('party.credit.renew', models=[ins_credit])
        self.assertEqual(party_credit_renew.form.credit, Decimal('20.00'))
        party_credit_renew.form.credit = Decimal('64.00')
        with self.assertRaises(UserWarning):

            party_credit_renew.execute('renew')
        party_credit_renew.form.credit = Decimal('50.00')
        party_credit_renew.execute('renew')
        party_credit = InsuranceCredit().find([
            ('start_date', '=', period.end_date + relativedelta(days=1))
        ])
        self.assertEqual(party_credit[0].approved_credit_limit,
                         Decimal('50.00'))

        # Duplicate same insurance credit
        ins_credit = InsuranceCredit()
        ins_credit.party = customer
        ins_credit.start_date = period.start_date
        ins_credit.end_date = period.end_date
        ins_credit.requested_credit_limit = Decimal('20.00')
        ins_credit.first_approved_credit_limit = Decimal('20.00')
        ins_credit.save()
        with self.assertRaises(UserError):

            ins_credit.click('approve')
