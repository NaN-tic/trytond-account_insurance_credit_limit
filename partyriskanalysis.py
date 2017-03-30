# -*- coding: utf-8 -*-

from trytond.model import ModelSQL, ModelView, fields
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pool import Pool

__all__ = ['PartyRiskAnalysis']


class PartyRiskAnalysis(ModelSQL, ModelView):
    'Party Risk Analysis'
    __name__ = 'party.risk.analysis'

    """
        This model represents the money the party's clients owe it taking
        the party's sale invoices from a specific date
    """

    party = fields.Many2One('party.party', 'Party', required=True,
        readonly=True)
    # Invoice maturity date
    date = fields.Date('Date', required=True, readonly=True)
    # Invoice total amount
    amount = fields.Numeric('Amount', digits=(16, 2), readonly=True)

    invoices = fields.Function(fields.One2Many('account.invoice', None,
        'Invoices', required=True, readonly=True), 'get_invoices')

    def get_invoices(self, name=None):
        Invoice = Pool().get('account.invoice')
        invoices = Invoice.search([
            ('party', '=', self.party.id),
            ('type', '=', 'out_invoice'),
            ('invoice_date', '>=', self.date),
            ('state', '=', 'posted')
        ])

        return tuple([i.id for i in invoices])


class PartyRiskAnalysisCalculateStart(ModelView):
    'Party Risk Analysis Calculate Start'

    __name__ = 'party.risk.analysis.calculate.start'

    date = fields.Date('Start Date')

    @staticmethod
    def default_date():
        return Pool().get('ir.date').today()


class PartyRiskAnalysisCalculate(Wizard):
    'Party Risk Analysis Calculate'

    __name__ = 'party.risk.analysis.calculate'

    start = StateView(
        'party.risk.analysis.calculate.start',
        'account_insurance_credit_limit.party_risk_calculate_view_form',
        [
            Button('Calculate', 'calculate_risk', 'tryton-ok', default=True),
            Button('Cancel', 'end', 'tryton-cancel')
        ]
    )
    calculate_risk = StateTransition()

    def transition_calculate_risk(self):
        pool = Pool()
        PartyRiskAnalysis = pool.get('party.risk.analysis')
        Invoice = pool.get('account.invoice')
        invoices = Invoice.search([
            ('type', '=', 'out_invoice'),
            ('invoice_date', '>=', self.start.date),
            ('state', '=', 'posted')
        ], order=[('party', 'ASC')])
        parties_risks = []
        current_party = None

        self.remove_all_records()

        for invoice in invoices:
            if invoice.party is not current_party:
                if current_party:
                    parties_risks.append(party_risk)

                party_risk = PartyRiskAnalysis()
                current_party = invoice.party
                party_risk.party = invoice.party
                party_risk.date = self.start.date
                party_risk.amount = 0

            party_risk.amount += invoice.total_amount

        parties_risks.append(party_risk)

        PartyRiskAnalysis.create([
            partyrisk._save_values for partyrisk in parties_risks])
        return 'end'

    def remove_all_records(self):
        PartyRiskAnalysis = Pool().get('party.risk.analysis')
        records = PartyRiskAnalysis.search([])
        PartyRiskAnalysis.delete(records)
