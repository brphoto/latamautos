#!/usr/bin/env python
# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'
    
    name = fields.Char(default=lambda self: self._context.get('employee_name', False))
    vat = fields.Char(default=lambda self: self._context.get('employee_identification')
                       or self._context.get("employee_passport")
                       )    

class ResBank(models.Model):
    _name = "res.bank"
    _inherit = "res.bank"

    journal_id = fields.Many2one(
        "account.journal",
        string=_("Journal to generate transfers"),
        domain=[("type", "=", "bank")],
        help=_("Accounting journal used to generate payroll payments"),
    )
    check_journal_id = fields.Many2one(
        "account.journal",
        string=_("Journal to generate checks"),
        domain=[("type", "=", "bank")],
        help=_("Accounting journal used to generate payroll payments"),
    )


class ResPartnerBank(models.Model):
    _name = "res.partner.bank"
    _inherit = "res.partner.bank"

    # @api.multi
    # def name_get(self):
    #     res = []
    #     for row in self:
    #         res.append((row.id, self.bank_id.name or '' + ' - ' + self.acc_number or ''))
    #     return res
    partner_id = fields.Char(default=lambda self: self._context.get('partner_id', False))
