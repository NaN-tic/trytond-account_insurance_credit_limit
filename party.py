# -*- coding: utf-8 -*-

from trytond.pool import PoolMeta, Pool
from trytond.model import fields


__all__ = ['Party']


class Party:
    __name__ = 'party.party'
    __metaclass__ = PoolMeta

    company_credit_limit = fields.Numeric('Company Credit Limit')
    insurance_credit_limit = fields.Function(fields.Numeric(
        'Insurance credit limit', digits=(16, 2)),
        'get_insurance_credit_limit')

    def get_insurance_credit_limit(self, name):
        """ Get the value of the field approved_credit_limit of the model
            party.credit which belongs to this party instance whose
            state=approved.
        """
        pool = Pool()
        PartyCredit = pool.get('party.credit')
        party_credits = PartyCredit.search([
            ('party', '=', self.id),  # TODO: check self.id or self
            ('state', '=', 'approved')
        ], limit=1)
        # There won't be two records of the model party.credit corresponding
        # to the same party with state=approved
        if party_credits:
            return party_credits[0].approved_credit_limit
        return 0
