=======================================
Account Insurance Credit Limit Scenario
=======================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()

Install product_cost_plan Module::

    >>> config = activate_modules('account_insurance_credit_limit')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

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
    >>> party = Party(name='Customer')
    >>> party.save()
    >>> party2 = Party(name='Customer')
    >>> party2.save()

Create Account Insurance Credit::

    >>> InsuranceCredit = Model.get('party.credit')
    >>> ins_credit = InsuranceCredit()
    >>> ins_credit.party = party
    >>> ins_credit.start_date = period.start_date
    >>> ins_credit.end_date = period.end_date
    >>> ins_credit.requested_credit_limit = Decimal('20.00')
    >>> ins_credit.first_approved_credit_limit = Decimal('20.00')
    >>> ins_credit.save()

Try replace active party::

    >>> replace = Wizard('party.replace', models=[party])
    >>> replace.form.source = party
    >>> replace.form.destination = party2
    >>> replace.execute('replace')

Check fields have been replaced::

    >>> ins_credit.reload()
    >>> ins_credit.party == party2
    True
