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
    >>> cash = accounts['cash']

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create Moves::

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
    >>> move.date = period.start_date + relativedelta(days=1)
    >>> move.date == period.start_date + relativedelta(days=1)
    True
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(42)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(42)
    >>> line.party = customer
    >>> move.save()

    >>> move2 = Move()
    >>> move2.period = period
    >>> move2.journal = journal_revenue
    >>> move2.company = company
    >>> move2.date = period.start_date + relativedelta(days=2)
    >>> move2.date == period.start_date + relativedelta(days=2)
    True
    >>> line = move2.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(20)
    >>> line = move2.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(20)
    >>> line.party = customer
    >>> move2.save()

    >>> move3 = Move()
    >>> move3.period = period
    >>> move3.journal = journal_cash
    >>> move3.company = company
    >>> move3.date = period.start_date + relativedelta(days=2)
    >>> move3.date == period.start_date + relativedelta(days=2)
    True
    >>> line = move3.lines.new()
    >>> line.account = cash
    >>> line.debit = Decimal(42)
    >>> line = move3.lines.new()
    >>> line.account = receivable
    >>> line.credit = Decimal(42)
    >>> line.party = customer
    >>> move3.save()

    >>> move4 = Move()
    >>> move4.period = period
    >>> move4.journal = journal_revenue
    >>> move4.company = company
    >>> move4.date = period.start_date + relativedelta(days=2)
    >>> move4.date == period.start_date + relativedelta(days=2)
    True
    >>> line = move4.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(10)
    >>> line = move4.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(10)
    >>> line.party = customer
    >>> move4.save()

    >>> move5 = Move()
    >>> move5.period = period
    >>> move5.journal = journal_cash
    >>> move5.company = company
    >>> move5.date = period.start_date + relativedelta(days=2)
    >>> move5.date == period.start_date + relativedelta(days=2)
    True
    >>> line = move5.lines.new()
    >>> line.account = cash
    >>> line.debit = Decimal(20)
    >>> line = move5.lines.new()
    >>> line.account = receivable
    >>> line.credit = Decimal(20)
    >>> line.party = customer
    >>> move5.save()

Create Account Insurance Credit::

    >>> InsuranceCredit = Model.get('party.credit')
    >>> ins_credit = InsuranceCredit()
    >>> ins_credit.party = customer
    >>> ins_credit.date == today
    True
    >>> ins_credit.start_date == today
    True
    >>> ins_credit.start_date = period.start_date
    >>> ins_credit.end_date == today + relativedelta(years=1,days=-1)
    True
    >>> ins_credit.end_date = period.end_date
    >>> ins_credit.requested_credit_limit = Decimal('20.00')
    >>> ins_credit.first_approved_credit_limit = Decimal('20.00')
    >>> ins_credit.save()
    >>> ins_credit.click('approve')
    >>> ins_credit.state
    u'approved'
    >>> ins_credit.approved_credit_limit
    Decimal('20.00')
    >>> ins_credit.accounts[0].balance == 42
    True
    >>> ins_credit.accounts[1].credit == 62
    True
    >>> ins_credit.accounts[1].debit == 30
    True
    >>> ins_credit.accounts[1].balance == 10
    True
    >>> ins_credit.maximum_registered == 42
    True

Duplicate same insurance credit::

    >>> ins_credit = InsuranceCredit()
    >>> ins_credit.party = customer
    >>> ins_credit.start_date = period.start_date
    >>> ins_credit.end_date = period.end_date
    >>> ins_credit.requested_credit_limit = Decimal('20.00')
    >>> ins_credit.first_approved_credit_limit = Decimal('20.00')
    >>> ins_credit.save()
    >>> ins_credit.click('approve')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserError: ('UserError', (u'It is only allowed an approved credit per party and the party credit "Customer - requested" you want to add exceeds this limit.', ''))
