====================
Party Erase Scenario
====================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date(2015, 1, 1)

Install contract::

    >>> config = activate_modules('account_insurance_credit_limit')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company, today))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> cash = accounts['cash']

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

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

Try erase active party::

    >>> erase = Wizard('party.erase', models=[party])
    >>> erase.form.party == party
    True
    >>> erase.execute('erase')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserError: ...
