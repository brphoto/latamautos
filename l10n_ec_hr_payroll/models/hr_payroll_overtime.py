#!/usr/bin/env python
# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class HrPayslipOvertime(models.Model):
    """
    Manage overtime of company employees
    """

    _name = "hr.payslip.overtime"
    _description = __doc__
    _order = "date"

    name = fields.Char(
        _("Name"), required=True, readonly=True, states={"draft": [("readonly", False)]}
    )
    date = fields.Date(
        _("Date"),
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
        default=datetime.now().strftime('%Y-%m-%d'),
    )
    line_ids = fields.One2many(
        "hr.payslip.overtime.line",
        "overtime_id",
        string=_("Overtime by Employees"),
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    department_id = fields.Many2one("hr.department", string=_("Department"))
    state = fields.Selection(
        [("draft", _("Draft")), ("approved", _("Approved")), ("done", _("Done"))],
        string="State",
        default="draft",
    )

    @api.one
    def approved(self):
        if self.line_ids:
            self.state = "approved"
            for line in self.line_ids:
                line.state = "approved"
        else:
            raise UserError(_("Can not approve a record without detail lines"))

    @api.multi
    def button_draft(self):
        for r in self:
            if r.state == 'done':
                raise UserError(_("No puede modificar un registro de horas extra en estado realizado."))
            r.state = 'draft'


    @api.multi
    def unlink(self):
        delete = True
        for row in self:
            if row.state in ["approved", "done"]:
                delete = False
        if not delete:
            raise UserError(_("Can not delete a record in an approved state!"))
        return super(HrPayslipOvertime, self).unlink()


class HrPayslipOvertimeLine(models.Model):
    """
    Overtime detail by employee
    """

    _name = "hr.payslip.overtime.line"
    _description = __doc__

    @api.onchange("employee_id", "wage", "hour_cost")
    def onchange_employee_id(self):
        if self.employee_id:
            date_from = "{}-{}-{}".format(
                self.overtime_id.date.strftime('%Y-%m-%d')[0:4], self.overtime_id.date.strftime('%Y-%m-%d')[5:7], "01"
            )
            date_to = self.overtime_id.date
            contract_obj = self.env["hr.contract"]
            payslip_obj = self.env["hr.payslip"]
            contract_id = contract_obj.search(
                [("employee_id", "=", self.employee_id.id)],
                limit=1,
                order="date_start desc",
            )
            if contract_id:
                wage = payslip_obj.get_contract_info(
                    contract_id.id, date_from, date_to
                )["wage"]
                self.wage = wage
                self.hour_cost = wage / 240.0
            else:
                raise ValidationError(
                    _("No exist active contract for employee %s")
                    % (self.employee_id.name)
                )

    overtime_id = fields.Many2one(
        "hr.payslip.overtime", string=_("Overtime"), ondelete="cascade"
    )
    employee_id = fields.Many2one(
        "hr.employee", string=_("Employee"), ondelete="cascade"
    )
    date = fields.Date(_("Date"), related="overtime_id.date", store=True, )
    wage = fields.Float(_("Wage"))
    hour_cost = fields.Float(_("Hour Cost"))
    overtime_025 = fields.Float(_("Hours Night Shift (25%)"), default="0")
    overtime_050 = fields.Float(_("Overtime (50%)"), default="0")
    overtime_100 = fields.Float(_("Extra Hours (100%)"), default="0")
    amount = fields.Float(_("Amount"), compute="_amount", default="0", store=True)
    state = fields.Selection(
        [("draft", _("Draft")), ("approved", _("Approved")), ("done", _("Done"))],
        string=_("State"),
        default="draft",
    )

    @api.multi
    @api.depends("hour_cost", "overtime_025", "overtime_050", "overtime_100")
    def _amount(self):
        for row in self:
            overtime_025 = row.hour_cost * row.overtime_025 * 1.75
            overtime_050 = row.hour_cost * row.overtime_050 * 1.50
            overtime_100 = row.hour_cost * row.overtime_100 * 2.00
            row.amount = overtime_025 + overtime_050 + overtime_100

    @api.constrains("employee_id")
    def check_contract(self):
        contract_obj = self.env["hr.contract"]
        for row in self:
            contract_id = contract_obj.search(
                [("employee_id", "=", row.employee_id.id)],
                limit=1,
                order="date_start desc",
            )
            if not contract_id:
                raise ValidationError(
                    _("No exist active contract for employee %s")
                    % (row.employee_id.name)
                )

