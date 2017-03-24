# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from . import party, partycredit, partyriskanalysis
from trytond.pool import Pool


def register():
    Pool.register(
        party.Party,
        partycredit.PartyCredit,
        partyriskanalysis.PartyRiskAnalysis,
        partyriskanalysis.PartyRiskAnalysisCalculateStart,
        module='account_insurance_credit_limit', type_='model')
    Pool.register(
        partyriskanalysis.PartyRiskAnalysisCalculate,
        module='account_insurance_credit_limit', type_='wizard')
