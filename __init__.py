# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import party


def register():
    Pool.register(
        party.Party,
        party.PartyCompanyCreditLimit,
        party.PartyCredit,
        party.PartyRiskAnalysis,
        party.PartyCreditRenewStart,
        party.PartyCreditAmount,
        module='account_insurance_credit_limit', type_='model')
    Pool.register(
        party.PartyCreditRenew,
        party.PartyReplace,
        party.PartyErase,
        module='account_insurance_credit_limit', type_='wizard')
