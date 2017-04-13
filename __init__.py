# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from . import party
from trytond.pool import Pool


def register():
    Pool.register(
        party.Party,
        party.PartyCredit,
        party.PartyRiskAnalysis,
        party.PartyRiskAnalysisTable,
        module='account_insurance_credit_limit', type_='model')
