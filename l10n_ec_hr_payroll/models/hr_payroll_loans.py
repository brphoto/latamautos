#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import RedirectWarning, ValidationError

_logger = logging.getLogger(__name__)


class HrPayslipLoans(models.Model):
    """
    Manage employee loans to payslip
    """

    _name = "hr.payslip.loans"
    _description = __doc__

    @api.multi
    def pay_loan(self):
        if self.state == "draft":
            raise ValidationError(
                _("Can not generate the payment of a loan in draft state!")
            )

        account_id = self.employee_id.company_id.loan_account_id
        if not account_id:
            action = self.env.ref("base.action_res_company_form")
            raise RedirectWarning(
                _("Please config your Loan's Account!."),
                action.id,
                _("Go to the company configuration"),
            )
        amount = self.amount
        payment_form = self.env.ref("account.view_account_payment_form", False)
        ctx = {
            "default_model": "hr.payslip.loans",
            "default_secuencial": self.number,
            "default_partner_id": self.employee_id.address_home_id.id,
            "default_payment_type": "outbound",
            "default_res_id": self.id,
            "default_amount": amount,
            "default_name": self.name,
            "default_prepayment": True,
            "default_contrapartida_id": int(account_id),
            "default_communication": self.number,
            "default_payment_reference": self.number,
            "default_loan_id": self.id,
        }
        return {
            "name": _("Payment Loan"),
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "account.payment",
            "views": [(payment_form.id, "form")],
            "view_id": payment_form.id,
            "target": "new",
            "context": ctx,
        }

    @api.model
    def _compute_payment(self):
        payment_obj = self.env["account.payment"]
        self.payment_id = payment_obj.search([("loan_id", "=", self.id)])

    @api.model
    def _compute_paid_state(self):
        self.paid = False
        if self.payment_id:
            self.paid = True

    @api.one
    def _conciliate_loan(self):
        if not self.reconciled and self.payment_id:
            account_id = self.employee_id.company_id.loan_account_id
            partner_id = self.employee_id.address_home_id.id
            move_line_obj = self.env["account.move.line"]
            lines = move_line_obj.search(
                [
                    ("account_id", "=", int(account_id)),
                    ("partner_id", "=", partner_id),
                    ("reconciled", "=", False),
                ]
            )
            if len(lines) > 1:
                lines.reconcile()
                self.reconciled = True
            if self.line_ids:
                dues = [row.id for row in self.line_ids if row.state == "approved"]
                if len(dues) == 0:
                    self.write({"state": "paid"})

    @api.multi
    @api.depends("month", "year")
    def _get_pay_from(self):
        for row in self:
            row.pay_from = "%s/%s" % (row.month, row.year)

    def monthdelta(self, date, delta):
        month, year = (
            (date.month + delta) % 12,
            date.year + ((date.month) + delta - 1) // 12,
        )
        month = 12 if not month else month
        day = min(
            date.day,
            [
                31,
                29 if year % 4 == 0 and not year % 400 == 0 else 28,
                31,
                30,
                31,
                30,
                31,
                31,
                30,
                31,
                30,
                31,
            ][month - 1],
        )
        return date.replace(day=day, month=month, year=year)

    @api.multi
    def approve_loan(self):
        line_obj = self.env["hr.payslip.news"]
        for row in self:
            #row.approved_date = fields.Datetime.now()
            row.approved_date = datetime.now().strftime('%Y-%m-%d')
            row.state = "approved"
            amount_pay = round(row.amount / row.dues, 2)
            date_loan = datetime.strptime(
                "%s-%s-%s" % (row.year, row.month, "05"), "%Y-%m-%d"
            )
            for due in range(row.dues):
                if due == row.dues - 1:
                    amount_pay = row.amount - round(amount_pay, 2) * due
                due_date = self.monthdelta(date_loan, due)
                vals = {
                    "name": _("Due number %s for: %s" % (due + 1, row.name)),
                    "employee_id": row.employee_id.id,
                    "loan_id": row.id,
                    "payroll_type": row.payroll_type.id,
                    "rule_id": row.rule_id.id,
                    "amount": amount_pay,
                    "quantity": str(due + 1) + "/" + str(row.dues),
                    "date": due_date,
                    "state": "approved",
                }
                line_obj.create(vals)

    @api.multi
    @api.depends("state", "line_ids.state")
    def _get_pending_amount(self):
        for row in self:
            amount = 0.0
            for line in row.line_ids:
                amount += line.amount if line.state == "approved" else 0.0
            row.pending_amount = amount

    def _get_salary_rule(self):
        rule_obj = self.env["hr.salary.rule"]
        rule_id = rule_obj.search([("code", "=", "LOAN")])
        return rule_id.id if rule_id else None

    name = fields.Char(
        _("Concept"), rquired=True, states={"draft": [("readonly", False)]}
    )
    number = fields.Char(
        _("Preprinted number"), rquired=True, states={"draft": [("readonly", False)]}
    )
    payroll_type = fields.Many2one(
        "hr.payslip.type", string="Payroll Type", required=True
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string=_("Employee"),
        required=True,
        states={"draft": [("readonly", False)]},
    )
    rule_id = fields.Many2one(
        "hr.salary.rule",
        string=_("Salary Rule"),
        readonly=True,
        states={"draft": [("readonly", False)]},
        default=_get_salary_rule,
    )
    amount = fields.Float(
        _("Amount"), states={"draft": [("readonly", False)]}, default=0
    )
    dues = fields.Integer(
        _("Dues Number"), states={"draft": [("readonly", False)]}, default=1
    )
    pending_amount = fields.Float(
        compute=_get_pending_amount,
        string=_("Pending Amount"),
        states={"draft": [("readonly", False)]},
        store=True,
    )
    application_date = fields.Date(
        _("Applicaction Date"),
        default=datetime.now().strftime('%Y-%m-%d'),
        states={"draft": [("readonly", False)]},
    )
    approved_date = fields.Date(_("Approved Date"), readonly=True)
    month = fields.Selection(
        [
            ("01", _("January")),
            ("02", _("February")),
            ("03", _("March")),
            ("04", _("April")),
            ("05", _("May")),
            ("06", _("Jun")),
            ("07", _("July")),
            ("08", _("August")),
            ("09", _("September")),
            ("10", _("October")),
            ("11", _("November")),
            ("12", _("December")),
        ],
        string=_("Month"),
        required=True,
        default=datetime.now().strftime('%m'),
    )
    year = fields.Char(_("Year"), size=4, default=datetime.now().strftime('%Y'),
                       )
    pay_from = fields.Char(compute=_get_pay_from, string=_("Pay From"), store=True)
    line_ids = fields.One2many(
        "hr.payslip.news",
        "loan_id",
        string="Dues",
        states={"draft": [("readonly", False)]},
    )
    state = fields.Selection(
        [("draft", _("Draft")), ("approved", _("Approved")), ("paid", _("Paid"))],
        string=_("State"),
        default="draft",
        store=True,
    )
    note = fields.Text(_("Notes"), states={"draft": [("readonly", False)]})
    paid = fields.Boolean(
        _("Made Payment Order ?"),
        required=False,
        readonly=True,
        states={"draft": [("readonly", False)]},
        copy=False,
        compute="_compute_paid_state",
    )
    reconciled = fields.Boolean(
        _("Reconciled"),
        copy=False,
        compute=_conciliate_loan,
        help=_("Indicates whether the loan has been reconciled"),
    )
    payment_id = fields.Many2one(
        "account.payment", _("Payment"), compute=_compute_payment
    )

    @api.model
    def _cron_close_loan(self, ids=None):
        loan_ids = self.search([("state", "=", "approved"), ("pending_amount", "=", 0)])
        if loan_ids:
            for loan in loan_ids:
                _logger.info("Close contract {}".format(loan.name))
                loan.update({"state": "paid"})
