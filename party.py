# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import ModelSQL, ModelView, fields, Workflow
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import Eval, PYSONEncoder
from trytond.transaction import Transaction

from sql import Column, Window, Literal
from sql.aggregate import Sum, Min

from dateutil.relativedelta import relativedelta

__all__ = ['Party', 'PartyCredit', 'PartyRiskAnalysis',
    'PartyRiskAnalysisTable', 'PartyCreditRenewStart',
    'PartyCreditRenew', 'PartyCreditAmount']


class Party:
    __name__ = 'party.party'
    __metaclass__ = PoolMeta

    company_credit_limit = fields.Property(fields.Numeric(
        'Company Credit Limit',
        digits=(16, Eval('credit_limit_digits', 2)),
        depends=['credit_limit_digits']))
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

    @staticmethod
    def default_company_credit_limit():
        return 0

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
                ('party', '=', self.id),
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


class PartyCredit(Workflow, ModelSQL, ModelView):
    'Party Credit'
    __name__ = 'party.credit'
    _rec_name = 'party'

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

    accounts = fields.One2Many('party.risk.analysis.table', 'party_credit',
            'Accounts', readonly=True)

    accounts_data = fields.One2Many('party.risk.analysis',
            'party_credit', 'Accounts', readonly=True)

    party_credit_amounts = fields.One2Many('party.credit.amount',
        'party_credit', 'Party Credit Amounts')

    number_of_days = fields.Char('Number of days')

    @classmethod
    def __setup__(cls):
        super(PartyCredit, cls).__setup__()
        # Error messages
        cls._error_messages.update({
                'duplicate_party_credit': (
                    'Existing credit limit "%(duplicate)s" '
                    'overlaps with record "%(current)s" that you are trying '
                    'to approve.'),
                })
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

    def get_max(self, name):
        currency = self.company.currency
        if not self.accounts_data:
            return 0
        if not self.start_date:
            balances = [a.balance for a in self.accounts_data]
        if self.start_date:
            balances = [a.balance for a in self.accounts_data
                if a.date >= self.start_date]
        if not balances:
            return 0
        return currency.round(max(balances))

    @fields.depends('party_credit_amounts')
    def on_change_party_credit_limit(self, name=None):
        if self.party_credit_amounts:
            self.approved_credit_limit = self.party_credit_amounts[-1].amount

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
                 cls.raise_user_error('duplicate_party_credit', {
                         'duplicate': duplicate[0].rec_name,
                         'current': party_credit.rec_name,
                         })
            if party_credit.party_credit_amounts:
                continue

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
        default['accounts_data'] = []
        default['accounts'] = []
        default['number_of_days'] = ''
        default['party_credit_amounts'] = []
        return super(PartyCredit, cls).copy(records, default)

    @classmethod
    def delete(cls, records):
        PartyRisk = Pool().get('party.risk.analysis')
        PartyRisk.delete(PartyRisk.search([
                ('party_credit', 'in', [x.id for x in records])]))
        super(PartyCredit, cls).delete(records)


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
        cls._error_messages.update({
                'invalid_date': 'The entered date is outside the period'
                })

    @classmethod
    def create(cls, vlist):
        PartyCredit = Pool().get('party.credit')
        for value in vlist:
            party_credit = PartyCredit(value['party_credit'])
            if (party_credit.start_date > value['date'] or
                    value['date'] > party_credit.end_date):
                cls.raise_user_error('invalid_date')

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


class PartyRiskAnalysis(ModelView, ModelSQL):
    'Party Risk Analysis'
    __name__ = 'party.risk.analysis'

    date = fields.Date('Date')

    debit = fields.Numeric('Debit',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    credit = fields.Numeric('Credit',
        digits=(16, Eval('currency_digits', 2)))
    balance = fields.Numeric('Balance',
        digits=(16, Eval('currency_digits', 2)))
    description = fields.Char('Description')
    party_credit = fields.Many2One('party.credit', 'Party Credit',
        required=True, readonly=True, ondelete='CASCADE')


class PartyRiskAnalysisTable(ModelSQL, ModelView):
    'Party Risk Analysis'
    __name__ = 'party.risk.analysis.table'
    # TODO reuse rec_name of Account
    date = fields.Date('Date')
    party = fields.Many2One('party.party', 'Party',
        states={
            'invisible': ~Eval('party_required', False),
            },
        depends=['party_required'])
    # party_required = fields.Boolean('Party Required')
    # company = fields.Many2One('company.company', 'Company')
    debit = fields.Numeric('Debit',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    credit = fields.Numeric('Credit',
        digits=(16, Eval('currency_digits', 2)))
    balance = fields.Numeric('Balance',
        digits=(16, Eval('currency_digits', 2)))
    description = fields.Char('Description')
    move = fields.Many2One('account.move', 'Move')
    party_credit = fields.Many2One('party.credit', 'Party Credit',
        required=True, readonly=True,)

    @classmethod
    def __setup__(cls):
        super(PartyRiskAnalysisTable, cls).__setup__()
        cls._order.insert(0, ('date', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Line = pool.get('account.move.line')
        Move = pool.get('account.move')
        Account = pool.get('account.account')
        PartyCredit = pool.get('party.credit')

        line = Line.__table__()
        move = Move.__table__()
        account = Account.__table__()
        party_credit = PartyCredit.__table__()
        columns = []
        for fname, field in cls._fields.iteritems():
            column = None
            if hasattr(field, 'set'):
                continue
            if fname == 'balance':
                w_columns = [party_credit.id]
                column = Sum(line.debit - line.credit,
                    window=Window(w_columns,
                        order_by=[move.date.asc, line.id])).as_('balance')
            elif fname == 'party_credit':
                column = Min(Column(party_credit, 'id')).as_(fname)
            elif fname == 'date':
                column = Column(move, fname).as_(fname)
            elif fname in ['create_uid', 'write_uid',
                    'create_date', 'write_date']:
                columns.append(Literal(None).as_(fname))
                continue
            elif fname == 'id':
                column = (Column(line, 'id')).as_('id')
            else:
                column = Column(line, fname).as_(fname)
            if column:
                columns.append(column)

        return line.join(account, condition=account.id == line.account
            ).join(move, condition=move.id == line.move
            ).join(party_credit,
                condition=((party_credit.company == move.company) &
                    (line.party == party_credit.party))
            ).select(*columns,
                where=(move.date <= party_credit.end_date),
                group_by=(party_credit.party, move.date, line.debit,
                    line.credit, line.id, party_credit.id),
                order_by=move.date)


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

    @classmethod
    def __setup__(cls):
        super(PartyCreditRenew, cls).__setup__()
        cls._error_messages.update({
            'big_amount': ('The entered amount is a 50% bigger '
                'than the maximum registered amount from the previous period')
            })

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

        to_create = []
        active_ids = Transaction().context['active_ids']
        for credit in PartyCredit.browse(active_ids):

            if len(active_ids) == 1:
                raise_flag_amount = ((credit.maximum_registered / 2)
                    + credit.maximum_registered)
                if self.start.credit > raise_flag_amount:
                    self.raise_user_warning(str(credit), 'big_amount')
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
                    'approved_credit_limit': limit,
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
