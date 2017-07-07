=======================================
Account Insurance Credit Limit Scenario
=======================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account::

    >>> Module = Model.get('ir.module')
    >>> module, = Module.find([
    ...         ('name', '=', 'account_insurance_credit_limit'),
    ...         ])
    >>> module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create Move to cancel::

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])
    >>> journal_cash, = Journal.find([
    ...         ('code', '=', 'CASH'),
    ...         ])
    >>> move = Move()
    >>> move.period = period
    >>> move.company = company
    >>> move.journal = journal_revenue
    >>> move.date = today - relativedelta(months=2)
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(0)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(42)
    >>> line.party = customer
    >>> move.save()

    >>> move2 = Move()
    >>> move2.period = period
    >>> move2.journal = journal_revenue
    >>> move2.company = company
    >>> move2.date = today - relativedelta(months=1)
    >>> line = move2.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(20)
    >>> line = move2.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(0)
    >>> line.party = customer
    >>> move2.save()

Create Account Insurance Credit::

    >>> InsuranceCredit = Model.get('party.credit')
    >>> ins_credit = InsuranceCredit()
    >>> ins_credit.party = customer
    >>> ins_credit.date = today
    >>> ins_credit.requested_credit_limit = Decimal('20.00')
    >>> ins_credit.first_approved_credit_limit = Decimal('20.00')
    >>> ins_credit.save()
    >>> bool(ins_credit.accounts_data)
    True
    >>> len(ins_credit.accounts_data)
    1
    >>> ins_credit.click('approve')
    >>> ins_credit.state
    u'approved'

Duplicate same insurance credit::

    >>> ins_credit = InsuranceCredit()
    >>> ins_credit.party = customer
    >>> ins_credit.date = today
    >>> ins_credit.requested_credit_limit = Decimal('20.00')
    >>> ins_credit.first_approved_credit_limit = Decimal('20.00')
    >>> ins_credit.save()
    >>> ins_credit.click('approve')
    Traceback (most recent call last):
        ...
    UserError: ('UserError', (u'It is only allowed an approved credit per party and the party credit "Customer - requested" you want to add exceeds this limit.', ''))
