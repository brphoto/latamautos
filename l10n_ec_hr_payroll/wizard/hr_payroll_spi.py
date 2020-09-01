#!/usr/bin/env python
# -*- coding: utf-8 -*-
import base64
import sys
import unicodedata
from datetime import datetime
from io import StringIO

from odoo import _, api, fields, models
from odoo.addons.l10n_ec_payment.models.es_num2word import to_word
from odoo.exceptions import UserError

#reload(sys)
#sys.setdefaultencoding("utf-8")


class WizradHrPayslipSPI(models.TransientModel):
    """
    Generate SPI report from payslip
    """

    _name = "wizard.hr.payslip.spi"
    _description = __doc__

    slip_id = fields.Many2one("hr.payslip.run", _("Slip"))
    payment_date = fields.Date(_("Date"), required=True)
    partner_id = fields.Many2one("res.partner", _("Company"))
    bank_account_id = fields.Many2one("res.partner.bank", _("Company Bank Account"))
    payment_method_id = fields.Many2one(
        "account.payment.method", string="Payment Tranfer Type"
    )
    payment_method_check_id = fields.Many2one(
        "account.payment.method", string="Payment Check Type"
    )
    file_export = fields.Binary(_("File to Export"), readonly=True)
    name = fields.Char(_("File Name"), size=32)
    state = fields.Selection(
        [("draft", "Draft"), ("execute", "Execute")],
        string=_("Status"),
        default="draft",
    )

    def clean_not_unicode(self, s):
        return "".join(
            (
                c
                for c in unicodedata.normalize("NFD", s)
                if unicodedata.category(c) != "Mn"
            )
        )

    @api.onchange("bank_account_id")
    def _onchange_bank_account(self):
        if self.bank_account_id:
            # Set default payment method (we consider the first to be the default one)
            payment_transfer_methods = (
                self.bank_account_id.bank_id.journal_id.outbound_payment_method_ids
            )
            payment_check_methods = self.bank_account_id.bank_id.check_journal_id.outbound_payment_method_ids.filtered(
                lambda x: x.code == "check_printing"
            )
            self.payment_method_id = (
                payment_transfer_methods and payment_transfer_methods[0] or False
            )
            self.payment_method_check_id = (
                payment_check_methods and payment_check_methods[0] or False
            )
            # Set payment method domain (restrict to methods enabled for the journal and to selected payment type)
            return {
                "domain": {
                    "payment_method_id": [
                        ("payment_type", "=", "outbound"),
                        ("id", "in", payment_transfer_methods.ids),
                    ],
                    "payment_method_check_id": [
                        ("payment_type", "=", "outbound"),
                        ("id", "in", payment_check_methods.ids),
                    ],
                }
            }
        return {}

    @api.model
    def _compute_payment_data(self, slip_id):
        res = {"account_id": False, "amount": 0.0}
        for line in slip_id.move_id.line_ids:
            if (
                line.account_id.internal_type == "payable"
                and line.partner_id.id == slip_id.employee_id.address_home_id.id
            ):
                res["account_id"] = line.account_id.id
                res["amount"] = abs(line.balance)
        return res

    @api.model
    def _compute_pay_amount(self, row):
        return row.due_amount

    @api.multi
    def get_spi(self):
        attachment_obj = self.env["ir.attachment"]
        payment_obj = self.env["account.payment"]
        template = "{}{:40}{:0<11}{:0>14}{}N\r\n"
        for row in self:
            if not row.bank_account_id.bank_id.journal_id:
                raise UserError(
                    _("Error"),
                    _(
                        "The bank {} has not set up a diary for payroll payments!".format(
                            row.bank_account_id.bank_id.name
                        )
                    ),
                )
            if not row.slip_id:
                raise UserError(_("Error"), _("Please Select a Slip"))
            if row.payment_method_id.id == row.payment_method_check_id.id:
                raise UserError(
                    _("Error"),
                    _(
                        "The payment method to generate transfer and checks can not be the same!"
                    ),
                )
            file_data = StringIO.StringIO()
            date = datetime.strptime(str(self.payment_date), "%Y-%m-%d").strftime("%d%m%y")
            file_name = "{}_{}.txt".format("SPI", date)
            slip_ids = row.slip_id.mapped("slip_ids").filtered(
                lambda x: x.exclude is False and x.amount > 0
            )
            amount = "{:.2f}".format(row.slip_id.transfer_amount).replace(".", "")
            file_data.write(
                template.format(
                    "D",
                    row.slip_id.company_id.name.upper(),
                    row.bank_account_id.acc_number,
                    amount,
                    date,
                )
            )
            if not slip_ids:
                raise UserError(_("No slip generates for this month"))
            for slip in slip_ids:
                payment_data = self._compute_payment_data(slip)
                if slip.employee_id.bank_account_id:
                    amount = "{:.2f}".format(self._compute_pay_amount(slip)).replace(
                        ".", ""
                    )
                    name = slip.employee_id.name
                    file_data.write(
                        template.format(
                            "C",
                            self.clean_not_unicode(name.upper()),
                            slip.employee_id.bank_account_id.acc_number,
                            amount,
                            date,
                        )
                    )
                    payment = {
                        "partner_type": "supplier",
                        "payment_type": "outbound",
                        "partner_id": slip.employee_id.address_home_id.id,
                        "journal_id": row.bank_account_id.bank_id.journal_id.id,
                        "contrapartida_id": payment_data["account_id"],
                        "company_id": slip.company_id.id,
                        "payroll_slip_id": slip.id,
                        "payroll_slip_run_id": row.slip_id.id,
                        "payment_method_id": row.payment_method_id.id,
                        "amount": payment_data["amount"],
                        "payment_date": row.payment_date,
                        "communication": slip.number,
                    }
                else:
                    payment = {
                        "partner_type": "supplier",
                        "payment_type": "outbound",
                        "partner_id": slip.employee_id.address_home_id.id,
                        "journal_id": row.bank_account_id.bank_id.check_journal_id.id,
                        "contrapartida_id": payment_data["account_id"],
                        "company_id": slip.company_id.id,
                        "payroll_slip_id": slip.id,
                        "payroll_slip_run_id": row.slip_id.id,
                        "payment_method_id": row.payment_method_check_id.id,
                        "amount": payment_data["amount"],
                        "payment_date": row.payment_date,
                        "communication": slip.number,
                        "check_amount_in_words": to_word(payment_data["amount"]),
                    }
                if not slip.payment_ids:
                    payment = payment_obj.create(payment)
                    payment.post()
                    account_move_lines_to_reconcile = self.env["account.move.line"]
                    for line in payment.move_line_ids:
                        if line.account_id.internal_type == "payable":
                            account_move_lines_to_reconcile |= line
                    for line in slip.move_id.line_ids:
                        if (
                            line.account_id.internal_type == "payable"
                            and line.partner_id.id
                            == slip.employee_id.address_home_id.id
                        ):
                            account_move_lines_to_reconcile |= line
                    account_move_lines_to_reconcile.reconcile()
            if not row.slip_id.bank_transfer_ids and row.slip_id.transfer_amount > 0:
                batch_payment = {
                    "payment_type": "transfer",
                    "journal_id": row.bank_account_id.bank_id.check_journal_id.id,
                    "destination_journal_id": row.bank_account_id.bank_id.journal_id.id,
                    "company_id": slip.company_id.id,
                    "payroll_slip_run_id": row.slip_id.id,
                    "payment_method_id": row.payment_method_id.id,
                    "amount": row.slip_id.transfer_amount,
                    "payment_date": row.payment_date,
                    "communication": row.slip_id.name,
                }
                batch_payment = payment_obj.create(batch_payment)
                batch_payment.post()
                row.slip_id.paid = True
            file_data.seek(0)
            data = base64.encodestring(file_data.read())

            # row.slip_id.write({'state': 'paid'})
            attachment_id = attachment_obj.search(
                [
                    ("name", "=", file_name),
                    ("res_model", "=", row.slip_id._name),
                    ("res_id", "=", row.slip_id.id),
                ]
            )
            if attachment_id:
                attachment_id.write(
                    {
                        "name": file_name,
                        "datas_fname": file_name,
                        "res_model": row.slip_id._name,
                        "res_id": row.slip_id.id,
                    }
                )
            else:
                attachment_obj.create(
                    {
                        "name": file_name,
                        "datas_fname": file_name,
                        "res_model": row.slip_id._name,
                        "res_id": row.slip_id.id,
                        "type": "binary",
                        "company_id": row.slip_id.company_id.id,
                        "db_datas": data,
                    }
                )
        return True
