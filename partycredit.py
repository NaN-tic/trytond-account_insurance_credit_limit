# -*- coding: utf-8 -*-

from trytond.model import ModelSQL, ModelView, fields, Workflow
from trytond.pool import Pool
from trytond.pyson import Eval

__all__ = ['PartyCredit']


class PartyCredit(ModelSQL, ModelView, Workflow):
    'Party Credit'
    __name__ = 'party.credit'

    party = fields.Many2One('party.party', 'Party', required=True)
    # date when the party requested the credit
    date = fields.Date('Date', required=True)
    # date when the requested credit was approved by the
    # insurance company. start_date is introduced manually.
    start_date = fields.Date('Start Date')
    # end_date: date when the approved credit expires.
    # end_date is introduced manually.
    end_date = fields.Date('End Date')
    # requested_credit_limit: amount of money requested by the party to the
    # insurance company
    requested_credit_limit = fields.Numeric('Credit Limit', digits=(16, 2),
        required=True)
    # approved_credit_limit: amount of money granted by the insurance company
    approved_credit_limit = fields.Numeric('Approved Credit Limit',
        digits=(16, 2))
    # invoice_line: Link to Credit and Suretyship supplier invoice line
    # invoice_line = fields.Many2One('account.invoice.line')
    state = fields.Selection([
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], 'State', required=True)
    # Returns the maximum risk amount registered for the given timeframe
    # maximum_registered_credit_amount = fields.Function(
    #    fields.Numeric('Maximum Registered Credit Amount', digits=(16, 2)))
# TODO: How to calculate maximum_registered_credit_amount?.
# Necesita el wizard de partyriskanalysis.py

    @staticmethod
    def default_state():
        return 'requested'

    def get_rec_name(self, name):
        return '%s - %s' % (self.party.name, self.date)

    # TODO: search_rec_name
    @classmethod
    def search_rec_name(cls, name, clause):
        pass

    @classmethod
    def __setup__(cls):
        super(PartyCredit, cls).__setup__()
        # Error messages
        cls._error_messages.update({
            'approved_credit_party': ('It is only allowed an approved credit '
                'per party and the party credit "%(rec_name)s" you want to '
                'add exceeds this limit. An approved party credit assigned to '
                'this party already exists "%(approved_party_credits)s"')
        })
        # Workflow transitions
        cls._transitions |= set((
            ('requested', 'approved'),
            ('approved', 'rejected')
        ))
        # Buttons
        cls._buttons.update({
            'approve': {
                'invisible': Eval('state').in_(['rejected', 'approved'])
            },
            'reject': {
                'invisible': Eval('state').in_(['requested', 'rejected'])
            }
        })

    @classmethod
    def validate(cls, party_credits):
        super(PartyCredit, cls).validate(party_credits)
        for party_credit in party_credits:
            party_credit.check_one_approved_credit_per_party()

    def check_one_approved_credit_per_party(self):
        """ It checks that there won't be two records of the model
            party.credit corresponding to the same party with state=approved
        """
        pool = Pool()
        PartyCredit = pool.get('party.credit')
        party_credits = PartyCredit.search([
            ('party', '=', self.party),
            ('state', '=', 'approved')
        ], limit=2)

        if len(party_credits) > 1:
            self.raise_user_error('approved_credit_party', {
                'rec_name': self.rec_name,
                'approved_party_credits':
                    ','.join(x.rec_name for x in party_credits)
            })

    @classmethod
    @ModelView.button
    @Workflow.transition('approved')
    def approve(cls, party_credits):
        for party_credit in party_credits:
            party_credit.party.credit_limit_amount = (
                party_credit.party.company_credit_limit +
                party_credit.party.insurance_credit_limit)

    @classmethod
    @ModelView.button
    @Workflow.transition('rejected')
    def reject(cls, party_credits):
        for party_credit in party_credits:
            party_credit.party.credit_limit_amount -= (
                party_credit.party.company_credit_limit +
                party_credit.party.insurance_credit_limit)
