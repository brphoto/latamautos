#!/usr/bin/env python
# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrPayslipNews(models.Model):
    """
    Manage income, expenses to payslip
    """

    _name = "hr.payslip.news"
    _inherit = ['mail.thread']
    _description = __doc__

    active = fields.Boolean(
        string='Active',
        default=True,
    )
    name = fields.Char(
        _("Description"),
        readonly=True,
        required=True,
        track_visibility='onchange',
        states={"draft": [("readonly", False)]},
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string=_("Employee"),
        required=True,
        readonly=True,
        track_visibility='onchange',
        states={"draft": [("readonly", False)]},
    )
    department_id = fields.Many2one(
        "hr.department",
        string=_("Department"),
        related="employee_id.department_id",
        track_visibility='onchange',
        store=True,
    )
    rule_id = fields.Many2one(
        "hr.salary.rule",
        string=_("Salary Rule"),
        readonly=True,
        required=True,
        track_visibility='onchange',
        states={"draft": [("readonly", False)]},
    )
    loan_id = fields.Many2one(
        "hr.payslip.loans",
        string=_("Loan"),
        ondelete="cascade",
        track_visibility='onchange',
    )
    date = fields.Date(
        _("Date"),
        readonly=True,
        track_visibility='onchange',
        states={"draft": [("readonly", False)]}
    )
    amount = fields.Float(
        _("Amount"),
        readonly=True,
        required=True,
        track_visibility='onchange',
        states={"draft": [("readonly", False)]},
    )
    quantity = fields.Char(
        _("Quantity"),
        default="1",
        track_visibility='onchange',
    )
    state = fields.Selection(
        [
            ("draft", _("Draft")),
            ("approved", _("Approved")),
            ("done", _("Done")),
            ("cancel", _("Cancel")),
        ],
        string=_("State"),
        track_visibility='onchange',
        default="draft",
    )
    payroll_type = fields.Many2one(
        "hr.payslip.type",
        string="Payroll Type",
        required=True,
        track_visibility='onchange',
    )

    @api.multi
    @api.onchange('payroll_type')
    def _onchange_payroll_type(self):
        for r in self:
            if not r.payroll_type:
                domain = {'domain':{'rule_id':[('id', 'in', [])]}}
            else:
                rules = self.env['hr.salary.rule'].search(
                    [
                        ('allowed_in_news', '=', True)
                    ]
                ).filtered(lambda x: r.payroll_type in x.payroll_type_ids)
                domain = {'domain':{'rule_id':[('id', 'in', rules.ids)]}}
            return domain

    @api.multi
    def approved_new(self):
        for r in self:
            if not self.date:
                raise UserError(_("Debe ingresar una fecha."))
            if self.amount <= 0:
                raise UserError(_("El monto debe ser superior a cero."))
            r.state = "approved"

    @api.multi
    def cancel_new(self):
        for r in self:
            r.state = "cancel"

    @api.multi
    def button_draft(self):
        for r in self:
            r.state = "draft"

    @api.multi
    def unlink(self):
        delete = True
        for row in self:
            if row.state in ["approved", "done"]:
                delete = False
        if not delete:
            raise UserError(_("Can not delete a record in an approved state!"))
        return super(HrPayslipNews, self).unlink()

