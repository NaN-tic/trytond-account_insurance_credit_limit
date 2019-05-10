# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from dateutil.relativedelta import relativedelta
from sql import Column, Window, Literal
from sql.aggregate import Sum, Min
from trytond.pool import PoolMeta, Pool
from trytond.model import ModelSQL, ModelView, fields, Workflow
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import Eval, PYSONEncoder
from trytond.transaction import Transaction
from trytond.tools.multivalue import migrate_property
from trytond import backend
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)
from trytond.i18n import gettext
from trytond.exceptions import UserError, UserWarning

__all__ = ['Party', 'PartyCompanyCreditLimit', 'PartyCredit',
    'PartyRiskAnalysis', 'PartyCreditRenewStart', 'PartyCreditRenew',
    'PartyCreditAmount', 'PartyReplace', 'PartyErase']


class Party(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'party.party'
    company_credit_limits = fields.One2Many('party.party.company_credit_limit',
        'party', 'Company Credit Limits')
    insurance_credit_limit = fields.Function(fields.Numeric(
        'Insurance credit limit', digits=(16, 2)),
        'get_insurance_credit_limit')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls.credit_limit_amount = fields.Function(
            fields.Numeric('Credit Limit Amount',
                digits=(16, Eval('credit_limit_digits', 2)),
                depends=['credit_limit_digits']),
            'on_change_with_credit_limit_amount')
        cls.credit_limit_amount.on_change_with = ['insurance_credit_limit',
            'company_credit_limit']
        cls.company_credit_limit = fields.MultiValue(
            fields.Numeric('Company Credit Limit',
                digits=(16, Eval('credit_limit_digits', 2)),
                depends=['credit_limit_digits']))

    @classmethod
    def default_company_credit_limit(cls, **pattern):
        return 0

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'company_credit_limit':
            return pool.get('party.party.company_credit_limit')
        return super(Party, cls).multivalue_model(field)

    @fields.depends('insurance_credit_limit', 'company_credit_limit')
    def on_change_with_credit_limit_amount(self, name=None):
        if not self.insurance_credit_limit:
            self.insurance_credit_limit = 0
        if not self.company_credit_limit:
            self.company_credit_limit = 0
        return self.company_credit_limit + self.insurance_credit_limit

    def get_insurance_credit_limit(self, name):
        """
        Get the value of the field approved_credit_limit of the model
        party.credit which belongs to this party instance whose
        state==approved.
        """
        pool = Pool()
        PartyCredit = pool.get('party.credit')
        Date = pool.get('ir.date')
        credits = PartyCredit.search([
                ('party', '=', self),
                ('start_date', '<=', Date.today()),
                ('end_date', '>=', Date.today()),
                ('company', '=', Transaction().context.get('company')),
                ])
        if not credits:
            # If no credit has been requested, return None
            return None
        for credit in credits:
            if credit.state == 'approved':
                return credit.approved_credit_limit
        return 0


class PartyCompanyCreditLimit(ModelSQL, CompanyValueMixin):
    "Party Company Credit Limit"
    __name__ = 'party.party.company_credit_limit'
    party = fields.Many2One('party.party', "Party", ondelete='CASCADE',
        select=True)
    company_credit_limit = fields.Numeric('Company Credit Limit',
        digits=(16, Eval('credit_limit_digits', 2)),
        depends=['credit_limit_digits'])
    credit_limit_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_credit_limit_digits')

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Party = pool.get('party.party')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        exist = TableHandler.table_exist(cls._table)
        table = cls.__table__()
        party = Party.__table__()
        super(PartyCompanyCreditLimit, cls).__register__(module_name)

        if not exist:
            party_h = TableHandler(Party, module_name)
            if party_h.column_exist('company_credit_limit'):
                query = table.insert(
                    [table.party, table.company_credit_limit],
                    party.select(party.id, party.company_credit_limit))
                cursor.execute(*query)
                party_h.drop_column('company_credit_limit')
            else:
                cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('company_credit_limit')
        value_names.append('company_credit_limit')
        fields.append('company')
        migrate_property('party.party', field_names, cls, value_names,
            parent='party', fields=fields)

    def get_credit_limit_digits(self, name):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            company = Company(company_id)
            return company.currency.digits


class PartyCredit(Workflow, ModelSQL, ModelView):
    'Party Credit'
    __name__ = 'party.credit'
    party = fields.Many2One('party.party', 'Party', required=True,
        states={
            'readonly': Eval('state') == 'approved'
        })
    # date when the party requested the credit
    date = fields.Date('Requested Date', required=True,
        states={
            'readonly': Eval('state') == 'approved'
        })
    # date when the requested credit was approved by the
    # insurance company. start_date is introduced manually.
    start_date = fields.Date('Start Date', states={
            'readonly': Eval('state') == 'approved'
            })
    # end_date: date when the approved credit expires.
    # end_date is introduced manually.
    end_date = fields.Date('End Date', states={
            'readonly': Eval('state') == 'approved'
            })
    # requested_credit_limit: amount of money requested by the party to the
    # insurance company
    requested_credit_limit = fields.Numeric('Requested Credit Limit',
        digits=(16, 2), required=True, states={
            'readonly': Eval('state') == 'approved',
            })
    first_approved_credit_limit = fields.Numeric('First Approved Credit Limit',
        digits=(16, 2), required=True, states={
            'invisible': Eval('state') != 'requested',
            'readonly': Eval('state') == 'approved',
            })
    # approved_credit_limit: amount of money granted by the insurance company
    approved_credit_limit = fields.Function(
        fields.Numeric('Approved Credit Limit',
            digits=(16, 2), states={
                'invisible': Eval('state') == 'requested',
                }), 'get_credit_limit')
    # invoice_line: Link to Credit and Suretyship supplier invoice line
    # invoice_line = fields.Many2One('account.invoice.line')
    state = fields.Selection([
            ('requested', 'Requested'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ], 'State', required=True, readonly=True)
    reference = fields.Char('Reference',
        states={
            'readonly': Eval('state') == 'approved'
            })

    # Returns the maximum risk amount registered for the given timeframe
    maximum_registered = fields.Function(fields.Numeric(
        'Maximum Registered Credit Amount', digits=(16, 2), readonly=True),
        'get_max')

    company = fields.Many2One('company.company', 'Company', required=True,
        readonly=True)
    accounts = fields.Function(fields.One2Many('party.risk.analysis', None,
            'Accounts'), 'get_accounts')
    party_credit_amounts = fields.One2Many('party.credit.amount',
        'party_credit', 'Party Credit Amounts')
    number_of_days = fields.Char('Number of days')

    @classmethod
    def __setup__(cls):
        super(PartyCredit, cls).__setup__()
        # Workflow transitions
        cls._transitions = set((
            ('requested', 'approved'),
            ('approved', 'rejected'),
            ('requested', 'rejected'),
            ('rejected', 'requested')
        ))
        # Buttons
        cls._buttons.update({
            'approve': {
                'invisible': Eval('state').in_(['rejected', 'approved'])
            },
            'reject': {
                'invisible': Eval('state').in_(['rejected'])
            },
            'request': {
                'invisible': Eval('state').in_(['requested', 'approved'])
            },
            'renew': {
                'invisible': Eval('state') != 'approved'
            }
        })

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_end_date():
        Date = Pool().get('ir.date')
        return Date.today() + relativedelta(years=1, days=-1)

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @staticmethod
    def default_start_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @staticmethod
    def default_state():
        return 'requested'

    def get_rec_name(self, name):
        return '%s - %s' % (self.party.rec_name, self.date)

    def get_accounts(self, name):
        PartyRiskAnalysis = Pool().get('party.risk.analysis')
        party_risk_analysis = PartyRiskAnalysis.search([
                ('company', '=', self.company),
                ('party', '=', self.party.id),
                ('date', '>=', self.start_date),
                ('date', '<=', self.end_date),
                ])
        return [x.id for x in party_risk_analysis]

    def get_max(self, name):
        currency = self.company.currency
        if not self.accounts:
            return 0
        balances = [account.balance for account in self.accounts]
        if not balances:
            return 0
        return currency.round(max(balances))

    def get_credit_limit(self, name=None):
        if not self.party_credit_amounts:
            return self.first_approved_credit_limit
        return self.party_credit_amounts[-1].amount

    @classmethod
    @ModelView.button
    @Workflow.transition('approved')
    def approve(cls, party_credits):
        CreditAmount = Pool().get('party.credit.amount')

        to_create = []
        for party_credit in party_credits:
            duplicate = cls.search([
                    ('party', '=', party_credit.party.id),
                    ('state', '=', 'approved'),
                    ('company', '=', party_credit.company),
                    ('start_date', '<=', party_credit.end_date),
                    ('end_date', '>=', party_credit.start_date),
                    ], limit=1)
            if duplicate:
                 raise UserError(gettext(
                    'account_insurance_credit_limit.duplicate_party_credit',
                         duplicate=duplicate[0].rec_name,
                         current=party_credit.rec_name))

            if party_credit.party_credit_amounts:
                continue

            if not party_credit.start_date:
                party_credit.start_date = cls.default_start_date()
                party_credit.save()
            credit_amount = CreditAmount()
            credit_amount.date = party_credit.start_date
            credit_amount.amount = party_credit.first_approved_credit_limit
            credit_amount.party_credit = party_credit.id
            to_create.append(credit_amount)

        if to_create:
            CreditAmount.create([x._save_values for x in to_create])

    @classmethod
    @ModelView.button
    @Workflow.transition('rejected')
    def reject(cls, party_credits):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('requested')
    def request(cls, party_credits):
        pass

    @classmethod
    @ModelView.button_action(
        'account_insurance_credit_limit.wizard_renew_party_credit')
    def renew(cls, party_credits):
        pass

    @classmethod
    def copy(cls, records, default):

        if not default:
            default = {}
        default = default.copy()
        default['accounts'] = []
        default['number_of_days'] = ''
        default['party_credit_amounts'] = []
        return super(PartyCredit, cls).copy(records, default)


class PartyCreditAmount(ModelView, ModelSQL):
    'Party Credit Conceded Amount'
    __name__ = 'party.credit.amount'
    date = fields.Date('Date', required=True, states={
            'readonly': Eval('initial_value', False)
            })
    amount = fields.Numeric('Conceded amount', required=True, states={
            'readonly': Eval('initial_value', False)
            })
    party_credit = fields.Many2One('party.credit', 'Party Credit',
        required=True, ondelete='CASCADE', select=True)
    initial_value = fields.Function(fields.Boolean('Is initial value'),
        'get_initial_value')

    @classmethod
    def __setup__(cls):
        super(PartyCreditAmount, cls).__setup__()
        cls._order.insert(0, ('date', 'ASC'))

    @classmethod
    def create(cls, vlist):
        PartyCredit = Pool().get('party.credit')
        for value in vlist:
            party_credit = PartyCredit(value['party_credit'])
            if (party_credit.start_date > value['date'] or
                    value['date'] > party_credit.end_date):
                raise UserError(gettext(
                    'account_insurance_credit_limit.invalid_date'))

        return super(PartyCreditAmount, cls).create(vlist)

    def get_initial_value(self, name=None):
        return self.party_credit.party_credit_amounts[0] == self

    @classmethod
    def delete(cls, records):
        to_delete = []
        for record in records:
            if len(record.party_credit.party_credit_amounts) == 1:
                continue
            to_delete.append(record)
        super(PartyCreditAmount, cls).delete(to_delete)


class PartyRiskAnalysis(ModelSQL, ModelView):
    'Party Risk Analysis'
    __name__ = 'party.risk.analysis'
    date = fields.Date('Date')
    company = fields.Many2One('company.company','Company')
    party = fields.Many2One('party.party', 'Party', states={
            'invisible': ~Eval('party_required', False),
            }, depends=['party_required'])
    party_required = fields.Boolean('Party Required')
    debit = fields.Numeric('Debit',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    credit = fields.Numeric('Credit',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    balance = fields.Numeric('Balance',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')

    @classmethod
    def __setup__(cls):
        super(PartyRiskAnalysis, cls).__setup__()
        cls._order.insert(0, ('date', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Line = pool.get('account.move.line')
        Move = pool.get('account.move')
        Account = pool.get('account.account')

        transaction = Transaction()
        database = transaction.database

        line = Line.__table__()
        move = Move.__table__()
        account = Account.__table__()
        columns = []
        for fname, field in cls._fields.items():
            column = None
            if hasattr(field, 'set'):
                continue
            if fname == 'balance':
                if database.has_window_functions():
                    w_columns = [account.company, line.party]
                    order_by = [move.date.asc, Min(line.id)]
                    window = Window(w_columns, order_by=order_by)
                    balance = Sum(line.debit) - Sum(line.credit)
                    column = Sum(balance, window=window).as_('balance')
                else:
                    column = (line.debit - line.credit).as_('balance')
            elif fname in ('party_required', 'company'):
                column = Column(account, fname).as_(fname)
            elif fname == 'date':
                column = Column(move, fname).as_(fname)
            elif fname in ['create_uid', 'write_uid',
                    'create_date', 'write_date']:
                column = Literal(None).as_(fname)
            elif fname == 'id':
                column = Min(Column(line, fname)).as_(fname)
            elif fname in ('debit', 'credit'):
                column = Sum(Column(line, fname)).as_(fname)
            else:
                column = Column(line, fname).as_(fname)
            if column:
                columns.append(column)

        group_by = (account.company, line.party, move.date,
            account.party_required)
        return line.join(account, condition=account.id == line.account).join(
            move, condition=move.id == line.move).select(*columns,
                group_by=group_by, order_by=move.date).select()

    def get_currency_digits(self, name):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            company = Company(company_id)
            return company.currency.digits


class PartyCreditRenewStart(ModelView):
    'Party Credit Limit Renew Start'
    __name__ = 'party.credit.renew.start'
    credit = fields.Numeric('Credit Approved', digits=(16, 2), required=True,
        states={
            'invisible': Eval('multiple_ids', False)
        })
    multiple_ids = fields.Boolean('Multiple Active IDS', states={
            'invisible': True
            })


class PartyCreditRenew(Wizard):
    'Party Credit Renew Wizard'
    __name__ = 'party.credit.renew'
    start = StateView('party.credit.renew.start',
        'account_insurance_credit_limit.party_credit_renew_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Renew', 'renew', 'tryton-ok', default=True),
            ])
    renew = StateAction('account_insurance_credit_limit.act_party_credit')

    def default_start(self, fields):
        pool = Pool()
        PartyCredit = pool.get('party.credit')
        party_credit = PartyCredit(Transaction().context['active_id'])
        return {
            'credit': party_credit.approved_credit_limit,
            'multiple_ids': len(Transaction().context.get('active_ids')) > 1
            }

    def do_renew(self, action):
        pool = Pool()
        PartyCredit = pool.get('party.credit')
        Date = pool.get('ir.date')
        Warning = pool.get('res.user.warning')

        to_create = []
        active_ids = Transaction().context['active_ids']
        for credit in PartyCredit.browse(active_ids):

            if len(active_ids) == 1:
                raise_flag_amount = ((credit.maximum_registered / 2)
                    + credit.maximum_registered)
                if self.start.credit > raise_flag_amount:
                    if Warning.check(credit):
                        raise UserWarning(str(credit), gettext(
                            'account_insurance_credit_limit.big_amount'))
                limit = self.start.credit
            else:
                limit = credit.approved_credit_limit

            start_date = credit.end_date + relativedelta(days=1)
            end_date = credit.end_date + relativedelta(years=1)
            to_create.append({
                    'date': Date.today(),
                    'start_date': start_date,
                    'end_date': end_date,
                    'requested_credit_limit': limit,
                    'first_approved_credit_limit': limit,
                    'party': credit.party.id,
                    'company': credit.company.id,
                    'state': 'requested',
                    })

        credits = PartyCredit.create(to_create)
        PartyCredit.approve(credits)

        action['pyson_domain'] = PYSONEncoder().encode([
                ('id', 'in', [x.id for x in credits]),
                ])
        return action, {}


class PartyReplace(metaclass=PoolMeta):
    __metaclass__ = PoolMeta
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('party.party.company_credit_limit', 'party'),
            ('party.credit', 'party'),
            ]


class PartyErase(metaclass=PoolMeta):
    __metaclass__ = PoolMeta
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        Credits = pool.get('party.credit')
        super(PartyErase, self).check_erase_company(party, company)

        credits = Credits.search([
                ('party', '=', party.id),
                ('state', 'in', ['requested']),
                ])
        if credits:
            raise UserError(gettext(
                'account_insurance_credit_limit.requested_credits',
                party=party.rec_name,
                company=company.rec_name))
