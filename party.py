# -*- coding: utf-8 -*-

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelSQL, ModelView, fields, Workflow
from trytond.pyson import Eval
from trytond.transaction import Transaction
from sql import Null, Column, Null, Window, Literal
from sql.aggregate import Sum, Max, Min
from sql.conditionals import Coalesce, Case
from dateutil.relativedelta import relativedelta

__all__ = ['Party', 'PartyCredit', 'PartyRiskAnalysis',
    'PartyRiskAnalysisTable']


class Party:
    __name__ = 'party.party'
    __metaclass__ = PoolMeta

    company_credit_limit = fields.Numeric('Company Credit Limit')
    insurance_credit_limit = fields.Function(fields.Numeric(
        'Insurance credit limit', digits=(16, 2)),
        'get_insurance_credit_limit')

    @staticmethod
    def default_company_credit_limit():
        return 0

    def get_insurance_credit_limit(self, name):
        """ Get the value of the field approved_credit_limit of the model
            party.credit which belongs to this party instance whose
            state=approved.
        """
        pool = Pool()
        PartyCredit = pool.get('party.credit')
        party_credits = PartyCredit.search([
            ('party', '=', self),
            ('state', '=', 'approved')
        ], limit=1)
        # There won't be two records of the model party.credit corresponding
        # to the same party with state=approved
        if (party_credits and
        party_credits[0].approved_credit_limit is not None):
            return party_credits[0].approved_credit_limit
        return 0


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
            'readonly': Eval('state') == 'approved'
        })
    # approved_credit_limit: amount of money granted by the insurance company
    approved_credit_limit = fields.Numeric('Approved Credit Limit',
        digits=(16, 2), states={
            'readonly': Eval('state') == 'approved'
        })
    # invoice_line: Link to Credit and Suretyship supplier invoice line
    # invoice_line = fields.Many2One('account.invoice.line')
    state = fields.Selection([
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], 'State', required=True, states={
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

    # accounts_data = fields.Function(fields.One2Many('party.risk.analysis',
    #        'party_credit', 'Accounts'), 'on_change_with_accounts_data')
    accounts_data = fields.One2Many('party.risk.analysis',
            'party_credit', 'Accounts', readonly=True)

    @classmethod
    def __setup__(cls):
        super(PartyCredit, cls).__setup__()
        # Error messages
        cls._error_messages.update({
            'approved_party_credit': ('It is only allowed an approved credit '
                'per party and the party credit "%(rec_name)s" you want to '
                'add exceeds this limit.')
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
            }
        })

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_end_date():
        Date_ = Pool().get('ir.date')
        return Date_.today()

    @staticmethod
    def default_start_date():
        Date_ = Pool().get('ir.date')
        return Date_.today() - relativedelta(years=1)

    @staticmethod
    def default_state():
        return 'requested'

    def get_rec_name(self, name):
        return '%s - %s' % (self.party.rec_name, self.state)

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

    @classmethod
    @ModelView.button
    @Workflow.transition('approved')
    def approve(cls, party_credits):
        Party = Pool().get('party.party')
        to_write = []
        for party_credit in party_credits:
            duplicate = cls.search([
                ('party', '=', party_credit.party.id),
                ('start_date', '<=', party_credit.start_date),
                ('end_date', '>=', party_credit.start_date),
                ('state', '=', 'approved')], limit=1)
            if duplicate:
                cls.raise_user_error('approved_party_credit', {
                        'rec_name': party_credit.rec_name
                        })
            if (party_credit.party.company_credit_limit is not None and
            party_credit.approved_credit_limit is not None):

                credit_limit_amount = (
                    party_credit.party.company_credit_limit +
                    party_credit.approved_credit_limit)
            else:
                credit_limit_amount = 0
            to_write.extend(([party_credit.party],
                {
                    'credit_limit_amount': credit_limit_amount,
                }))
        Party.write(*to_write)

    @classmethod
    @ModelView.button
    @Workflow.transition('rejected')
    def reject(cls, party_credits):
        Party = Pool().get('party.party')
        to_write = []
        for party_credit in party_credits:

            credit_limit_amount = party_credit.party.credit_limit_amount

            if (party_credit.party.company_credit_limit is not None and
            party_credit.party.insurance_credit_limit is not None):

                credit_limit_amount -= (
                    party_credit.party.company_credit_limit +
                    party_credit.approved_credit_limit)

                if not credit_limit_amount:
                    credit_limit_amount = 0
            else:
                credit_limit_amount = 0
            to_write.extend(([party_credit.party],
                {
                    'credit_limit_amount': credit_limit_amount
                }))
        Party.write(*to_write)

    @classmethod
    @ModelView.button
    @Workflow.transition('requested')
    def request(cls, party_credites):
        pass

    @classmethod
    def validate(cls, vlist):

        PartyRisk = Pool().get('party.risk.analysis')
        PartyRisk.delete(PartyRisk.search([
            ('party_credit', 'in', [v.id for v in vlist])]))

        for value in vlist:
            party_vlist = []
            for account in value.accounts:
                if account.date >= value.start_date:
                    if party_vlist and party_vlist[-1]['date'] == account.date:
                        party_vlist[-1]['balance'] = account.balance
                        party_vlist[-1]['credit'] = account.credit
                        party_vlist[-1]['debit'] = account.debit
                    else:
                        party_vlist.append({
                            'date': account.date,
                            'debit': account.debit,
                            'credit': account.credit,
                            'balance': account.balance,
                            'description': account.description,
                            'party_credit': value.id,
                            })
            PartyRisk.create(party_vlist)
        return super(PartyCredit, cls).validate(vlist)

    @classmethod
    def copy(cls, records, default):

        if not default:
            default = {}
        default = default.copy()
        default['accounts_data'] = []
        default['accounts'] = []

        return super(PartyCredit, cls).copy(records, default)

    @classmethod
    def delete(cls, records):
        PartyRisk = Pool().get('party.risk.analysis')
        PartyRisk.delete(PartyRisk.search([
                ('party_credit', 'in', [x.id for x in records])]))
        super(PartyCredit, cls).delete(records)


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
        required=True, readonly=True)


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
        required=True, readonly=True)

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
