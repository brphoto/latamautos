#!/usr/bin/env python
# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    payroll_slip_id = fields.Many2one("hr.payslip")
    payroll_slip_run_id = fields.Many2one("hr.payslip.run")
    loan_id = fields.Many2one("hr.payslip.loans", string=_("Loan"))
    loan_ids = fields.Many2many("hr.payslip.loans", string=_("Related Emplayee Loans"))
    new_ids = fields.Many2many("hr.payslip.news", string=_("Related Payslip News"))

    @api.multi
    def post(self):
        res = super(AccountPayment, self).post()
        for row in self:
            if row.journal_id.payroll_discount:
                row.with_context(check_employee=True).create_news()
        return res

    @api.multi
    def create_news(self):
        new_obj = self.env["hr.payslip.news"]
        loan_obj = self.env["hr.payslip.loans"]
        emp_obj = self.env["hr.employee"]
        check_employee = self._context.get("disable_verification", False)
        for row in self:
            news = []
            loans = []
            emp_id = emp_obj.with_context(show_unemployed=True).search(
                [("address_home_id", "=", row.partner_id.id)]
            )
            if check_employee:
                if not emp_id:
                    raise ValidationError(
                        _(
                            "There is not a related employee for the client %s"
                            % row.partner_id.name
                        )
                    )
            if emp_id:
                if row.journal_id.payroll_discount_type == "fixed":
                    if not row.new_ids:
                        for inv in row.invoice_ids.filtered(
                            lambda x: x.state == "paid"
                        ):
                            new = new_obj.create(
                                {
                                    "name": _(
                                        "Discount: {}".format(inv.name_get()[0][1])
                                    ),
                                    "employee_id": emp_id.id,
                                    "date": inv.date_invoice,
                                    "rule_id": row.journal_id.rule_id.id,
                                    "payroll_type": row.journal_id.payroll_type.id,
                                    "amount": inv.total,
                                    "state": "approved",
                                }
                            )
                            news.append(new.id)
                if row.journal_id.payroll_discount_type == "deferred":
                    if not row.loan_ids:
                        year, month, day = row.payment_date.split("-")
                        loan = loan_obj.create(
                            {
                                "name": _(
                                    "Discount: {}".format(
                                        ", ".join(
                                            map(
                                                str,
                                                [
                                                    i.name_get()[0][1]
                                                    for i in row.invoice_ids
                                                ],
                                            )
                                        )
                                    )
                                ),
                                "employee_id": emp_id.id,
                                "application_date": row.payment_date,
                                "rule_id": row.journal_id.rule_id.id,
                                "payroll_type": row.journal_id.payroll_type.id,
                                "amount": row.amount,
                                "dues": 1,
                                "month": month,
                                "year": year,
                                "state": "draft",
                            }
                        )
                        loans.append(loan.id)
            if news:
                row.update({"new_ids": [(6, 0, news)]})
            if loans:
                row.update({"loan_ids": [(6, 0, loans)]})
        return True


class AccountJournal(models.Model):
    _inherit = "account.journal"

    payroll_discount = fields.Boolean(_("Payroll Discount"))
    payroll_discount_type = fields.Selection(
        [("fixed", _("Fixed")), ("deferred", _("Deferred"))],
        string=_("Payroll Discount Type"),
        default="fixed",
    )
    payroll_type = fields.Many2one("hr.payslip.type", _("Payslip Type"))
    rule_id = fields.Many2one("hr.salary.rule", _("Salary Rule"))

