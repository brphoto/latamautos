# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class res_company(models.Model):
    _inherit = "res.company"

    basic_wage = fields.Float(
        string="Basic Wage ($)",
        oldname="sueldo_basico",
        compute="_compute_basic_wage",
        store=False,
    )
    iess_representante_legal = fields.Float("Contribución Representante legal IESS (%)")
    iess_personal = fields.Float("Contribución personal IESS (%)")
    iess_empleador = fields.Float("Contribución patronal IESS (%)")
    porcentaje_fondos_reserva = fields.Float("Fondos de reserva (%)")  # TODO calcular
    default_payroll_journal_id = fields.Many2one(
        "account.journal",
        string="Default Payroll Journal",
        domain="[('type','=','general')]",
        help="This journal will be used on payroll creation",
    )
    loan_account_id = fields.Many2one(
        "account.account", string=_("Loan Account"), required=False
    )

    @api.multi
    def _compute_basic_wage(self):
        for r in self:
            bw = r.get_basic_wage(payslip=False)
            r.basic_wage = bw

    def get_basic_wage(self, payslip=False):
        return 394.00

    def get_porcentaje_iess_personal(self, payslip=False):
        return 9.45

