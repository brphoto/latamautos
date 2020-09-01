# -*- coding: utf-8 -*-
from calendar import monthrange
from datetime import datetime, timedelta

from dateutil import relativedelta
from dateutil.relativedelta import relativedelta
from lxml import etree
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import drop_view_if_exists, float_compare, float_is_zero

month_days = [
    ("01", "01"),
    ("02", "02"),
    ("03", "03"),
    ("04", "04"),
    ("05", "05"),
    ("06", "06"),
    ("07", "07"),
    ("08", "08"),
    ("09", "09"),
    ("10", "10"),
    ("11", "11"),
    ("12", "12"),
    ("13", "13"),
    ("14", "14"),
    ("15", "15"),
    ("16", "16"),
    ("17", "17"),
    ("18", "18"),
    ("19", "19"),
    ("20", "20"),
    ("21", "21"),
    ("22", "22"),
    ("23", "23"),
    ("24", "24"),
    ("25", "25"),
    ("26", "26"),
    ("27", "27"),
    ("28", "28"),
    ("29", "29"),
    ("30", "30"),
]


class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"
    _order = "sequence"

    analytic = fields.Boolean(
        "Analytic",
        help=_(
            "Check this box if you want to keep an analytical record for this salary rule"
        ),
        default=False,
    )
    allowed_in_news = fields.Boolean(
        string='Allowed in news',
        default=True,
    )
    biweekly_deduction = fields.Boolean(
        _("Biweekly Deduction"),
        help=_(
            "Check this option if this item should be deducted in the monthly payment roll"
        ),
    )
    payroll_type_ids = fields.Many2many("hr.payslip.type", string=_("Payroll Type"))
    rule_deduction = fields.Boolean(_("Rule Deduction"), default=False)
    rule_deduction_type = fields.Selection(
        [("fixed", _("Fixed")), ("deferred", _("Deferred"))],
        string=_("Payroll Discount Type"),
        default="fixed",
    )
    rule_deduction_payroll_type = fields.Many2one("hr.payslip.type", _("Payslip Type"))
    rule_deduction_id = fields.Many2one("hr.salary.rule", _("Salary Rule"))


class HrPayslipType(models.Model):
    """
    Model to manage Type of Payslip
    """

    _name = "hr.payslip.type"

    active = fields.Boolean(string='Active', default=True, )
    name = fields.Char(_("Name"))
    description = fields.Text(_("Description"))
    day_from = fields.Selection(month_days, string=_("Day From"))
    day_to = fields.Selection(month_days, string=_("Day To"))
    overtime = fields.Boolean("Overtime")
    invoices = fields.Boolean("Invoices")
    exclude_entry = fields.Selection(
        month_days,
        string=_("Entry Exclude"),
        help=_("Eclude to payslip if contract date start"),
    )


class HrPayslipInput(models.Model):
    """
    Add news links to hr.payslip.input
    """

    _inherit = ["hr.payslip.input"]
    _description = __doc__

    new_id = fields.Many2one("hr.payslip.news", string=_("New"), ondelete="cascade")
    overtime_id = fields.Many2one(
        "hr.payslip.overtime.line", string=_("New"), ondelete="cascade"
    )
    invoice_id = fields.Many2one("account.invoice", string=_("Invoice"))
    quantity = fields.Char(_("Quantity"))


class HrPayslipLine(models.Model):
    _inherit = "hr.payslip.line"

    def _get_partner_id(self, map_id, payslip_line, credit_account):
        """
        Get partner_id of slip line to use in account_move_line
        """
        # use partner of salary rule or fallback on employee's address
        partner_id = (
            map_id.partner_id.id
            or payslip_line.salary_rule_id.register_id.partner_id.id
            or payslip_line.slip_id.employee_id.address_home_id.id
        )
        if map_id:
            if credit_account:
                if map_id.account_credit.internal_type in ("receivable", "payable"):
                    return partner_id
            else:
                if map_id.account_debit.internal_type in ("receivable", "payable"):
                    return partner_id
        if credit_account:
            if (
                payslip_line.salary_rule_id.register_id.partner_id
                or payslip_line.salary_rule_id.account_credit.internal_type
                in ("receivable", "payable")
            ):
                return partner_id
        else:
            if (
                payslip_line.salary_rule_id.register_id.partner_id
                or payslip_line.salary_rule_id.account_debit.internal_type
                in ("receivable", "payable")
            ):
                return partner_id
        return False

    payroll_type = fields.Many2one(
        "hr.payslip.type", related="slip_id.payroll_type", store=True
    )
    date_from = fields.Date(related="slip_id.date_from", store=True)
    date_to = fields.Date(related="slip_id.date_to", store=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("verify", "Waiting"),
            ("done", "Done"),
            ("cancel", "Rejected"),
        ],
        related="slip_id.state",
        store=True,
    )


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"
    _order = "date_end"

    @api.multi
    def undo_payslip_run(self):
        for row in self:
            row.slip_ids.undo_sheet()
            row.write({"state": "draft"})

    @api.multi
    def post_payslip_run(self):
        for row in self:
            slips = row.slip_ids.filtered(
                lambda x: x.state == 'done' and not x.exclude
            )
            slips.post_sheet()
            row.post = True

    @api.multi
    def print_hr_payslip_run(self):
        wizard_form = self.env.ref(
            "l10n_ec_hr_payroll.view_wizard_hr_payroll_print", False
        )
        return {
            "name": _("Print {}".format(self.name)),
            "type": "ir.actions.act_window",
            "res_model": "wizard.hr.payroll.print",
            "view_id": wizard_form.id,
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
        }
  


    @api.multi
    def compute_sheet(self):
        for row in self:
            row.slip_ids.compute_inputs()
            row.slip_ids.update_sheet()

    @api.multi
    def confirm_payslip_run(self):
        for row in self:
            slips = row.slip_ids.filtered(
                lambda x: x.state == 'draft' and not x.exclude
            )
            slips.process_sheet()
            row.write({"state": "confirm"})

    @api.multi
    def action_spi(self):
        wiz_obj = self.env["wizard.hr.payslip.spi"]
        wiz_id = wiz_obj.create(
            {
                "slip_id": self.id,
                "partner_id": self.company_id.partner_id.id,
                "payment_date": self.date_end,
            }
        )
        return {
            "name": _("Generate Cash Management"),
            "view_mode": "form",
            "view_type": "form",
            "res_model": "wizard.hr.payslip.spi",
            "res_id": wiz_id.id,
            "type": "ir.actions.act_window",
            "target": "new",
            "context": self._context,
        }

    @api.multi
    def action_payment(self):
        context = {
                "default_payslip_run_id": self.id,
                "default_date": self.date_end,
            }
        return {
            "name": _("Generate Payments"),
            "view_mode": "form",
            "view_type": "form",
            "res_model": "wizard.hr.payslip.payment",
            "type": "ir.actions.act_window",
            "target": "new",
            "context": context,
        }

    def _get_default_company(self):
        return self.env.user.company_id

    def _get_default_journal(self):
        res = self.env.user.company_id.default_payroll_journal_id
        if res:
            return res
        return False

    @api.multi
    @api.depends("slip_ids.amount", 'slip_ids.due_amount', "state")
    def _get_slip_pay_amount(self):
        for row in self:
            row.exclude_amount = sum(
                row.mapped("slip_ids").filtered(lambda x: x.exclude).mapped("amount")
            )
            row.transfer_amount = sum(
                row.mapped("slip_ids")
                .filtered(lambda x: not x.exclude and x.employee_id.bank_account_id)
                .mapped("amount")
            )
            row.check_amount = sum(
                row.mapped("slip_ids")
                .filtered(lambda x: not x.exclude and not x.employee_id.bank_account_id)
                .mapped("amount")
            )
            row.amount = row.transfer_amount + row.check_amount
            row.due_amount = sum(row.mapped('slip_ids.due_amount'))

    department_id = fields.Many2one(
        "hr.department",
        string=_("Department"),
        help=_("Fill this box to generate a department payment role"),
    )
    payment_ids = fields.One2many(
        "account.payment", "payroll_slip_run_id", string=_("Payments")
    )
    payroll_type = fields.Many2one(
        "hr.payslip.type", string="Payroll Type", required=True
    )
    journal_id = fields.Many2one(default=_get_default_journal)
    company_id = fields.Many2one(
        "res.company",
        _("Company"),
        required=True,
        readonly=True,
        default=_get_default_company,
    )
    state = fields.Selection(selection_add=[("confirm", _("Confirm"))])
    transfer_amount = fields.Float(
        "Amount to pay by transfer", compute=_get_slip_pay_amount, store=True
    )
    check_amount = fields.Float(
        "Amount to pay by check", compute=_get_slip_pay_amount, store=True
    )
    exclude_amount = fields.Float(
        "Exclude amount", compute=_get_slip_pay_amount, store=True
    )
    amount = fields.Float("Amount to pay", compute=_get_slip_pay_amount, store=True)
    due_amount = fields.Float("Due amount", compute=_get_slip_pay_amount, store=True)
    date = fields.Date(
        "Date Account",
        required=True,
        default=fields.Date.today(),
        help="Keep empty to use the period of the validation(Payslip) date.",
    )
    post = fields.Boolean(_("Post Payslip?"))
    paid = fields.Boolean(_("Paid Payslip?"))

    transfer_count = fields.Integer(
        compute="_compute_payment_ids", string="# Transfers"
    )
    transfer_ids = fields.Many2many(
        "account.payment",
        compute="_compute_payment_ids",
        string="Payment associated to this Payslip",
    )
    check_count = fields.Integer(compute="_compute_payment_ids", string="# Checks")
    check_ids = fields.Many2many(
        "account.payment",
        compute="_compute_payment_ids",
        string="Payment associated to this Payslip",
    )
    bank_transfer_count = fields.Integer(
        compute="_compute_payment_ids", string="# Bank Transfer"
    )
    bank_transfer_ids = fields.Many2many(
        "account.payment",
        compute="_compute_payment_ids",
        string="Payment associated to this Payslip",
    )

    @api.multi
    def unlink(self):
        if any(
            self.filtered(
                lambda run: run.state not in ("draft", "cancel")
                or run.mapped("slip_ids")
            )
        ):
            raise UserError(
                _(
                    "You can not delete a payment role that is not in draft or canceled status, or that has generated roles.!"
                )
            )
        return super(HrPayslipRun, self).unlink()

    @api.multi
    @api.depends("slip_ids.payment_ids")
    def _compute_payment_ids(self):
        payment_obj = self.env["account.payment"]
        for row in self:
            payment_ids = payment_obj.search([("payroll_slip_run_id", "=", row.id)])
            row.transfer_ids = (
                payment_ids.filtered(
                    lambda x: x.payment_method_id.code == "manual"
                    and x.payment_type == "outbound"
                ).ids
                if payment_ids
                else []
            )
            row.transfer_count = len(row.transfer_ids)
            row.check_ids = (
                payment_ids.filtered(
                    lambda x: x.payment_method_id.code == "check_printing"
                    and x.payment_type == "outbound"
                ).ids
                if payment_ids
                else []
            )
            row.check_count = len(row.check_ids)
            row.bank_transfer_ids = (
                payment_ids.filtered(lambda x: x.payment_type == "transfer").ids
                if payment_ids
                else []
            )
            row.bank_transfer_count = len(row.bank_transfer_ids)

    @api.multi
    def action_view_transfers(self):
        context = {"tree_view_ref": "account.view_account_supplier_payment_tree"}
        return {
            "name": _("Transfers for {}".format(self.name)),
            "view_type": "form",
            "view_mode": "tree",
            "res_model": "account.payment",
            "type": "ir.actions.act_window",
            "domain": [("id", "in", self.mapped("transfer_ids").ids)],
            "context": context,
        }

    @api.multi
    def action_view_checks(self):
        context = {"tree_view_ref": "account.view_account_supplier_payment_tree"}
        return {
            "name": _("Checks for {}".format(self.name)),
            "view_type": "form",
            "view_mode": "tree",
            "res_model": "account.payment",
            "type": "ir.actions.act_window",
            "domain": [("id", "in", self.mapped("check_ids").ids)],
            "context": context,
        }

    @api.multi
    def action_view_bank_transfers(self):
        context = {"tree_view_ref": "account.view_account_supplier_payment_tree"}
        return {
            "name": _("Bank Transfers for {}".format(self.name)),
            "view_type": "form",
            "view_mode": "tree",
            "res_model": "account.payment",
            "type": "ir.actions.act_window",
            "domain": [("id", "in", self.mapped("bank_transfer_ids").ids)],
            "context": context,
        }

    @api.onchange("date_start", "payroll_type")
    def _onchange_date_start(self):
        date_start = datetime.strptime(str(self.date_start), "%Y-%m-%d")
        self.name = "{prefix} {type} {month}-{year}".format(
            prefix=_("BP"),
            type=self.payroll_type.name if self.payroll_type else "",
            month=date_start.strftime("%m"),
            year=date_start.year,
        ).upper()
        date_end = date_start + relativedelta(months=+1, day=1, days=-1)
        if int(self.payroll_type.day_to) <= 15:
            date_end = date_start + relativedelta(day=15)
        self.date_end = str(date_end)[:10]

class HrPayslip(models.Model):
    _inherit = "hr.payslip"
    
    @api.multi
    def print_hr_payslip(self):
        self.ensure_one()
        self.sent = True
        #return self.env["report"].get_action(
         #   self, "l10n_ec_hr_payroll.hr_payslip_report"
        #)
        return self.env.ref("l10n_ec_hr_payroll.hr_payslip_report").report_action()
    def get_news(self, obj):
        
        res = {"loan": "0.00", "he050": "0.00", "he100": "0.00"}
        new_obj = self.pool.get("hr.payslip.news")
        for i in obj.input_line_ids:
            try:
                qty = float(i.quantity)
            except ValueError:
                qty = 0
            if i.code == "HE050":
                res["he050"] = "{:.2f}".format(qty)
            elif i.code == "HE100":
                res["he100"] = "{:.2f}".format(qty)
            elif i.code == "LOAN":
                new_ids = new_obj.search(
                    self.cr, self.uid, [("loan_id", "=", i.new_id.loan_id.id)]
                )
                current = i.quantity.split("/")[0]
                loan = 0.0
                if new_ids:
                    for n in new_obj.browse(self.cr, self.uid, new_ids):
                        if n.quantity.split("/")[0] > current:
                            loan += n.amount
                res["loan"] = "{:.2f}".format(loan)
        return res

    def get_details(self, obj, hr_payslip_id=None):
        payslip_line = self.pool.get("hr.payslip.line")
        hr_payslip_input_pool = self.pool.get("hr.payslip.input")
        res = []
        result = {}
        ids = []
        income_total = 0
        outcome_total = 0
        for id in range(len(obj)):
            ids.append(obj[id].id)
        if ids:
            self.env.cr.execute(
                """SELECT pl.id, pl.category_id FROM hr_payslip_line as pl \
				LEFT JOIN hr_salary_rule_category AS rc on (pl.category_id = rc.id) \
				LEFT JOIN hr_salary_rule AS sr on (pl.salary_rule_id = sr.id) \
				WHERE pl.id in %s and rc.code in ('BASIC','ALW','INGNOGRAV', 'INGGRAV', 'HE050', 'HE100') \
				GROUP BY rc.parent_id, sr.sequence, pl.id, pl.category_id \
				ORDER BY sr.sequence, rc.parent_id""",
                (tuple(ids),),
            )
            for x in self.env.cr.fetchall():
                result.setdefault(x[1], [])
                result[x[1]].append(x[0])
            for key, value in result.items():
                print("result.items")
                print(result.items())
                print("self.env.cr")
                print(self.env.cr)
                print("self.env.uid")
                print(self.env.uid)

                for line in payslip_line.browse(value,self.env.cr, self.env.uid):
                    tlt = "%.2f" % abs(line.total)
                    detalle = line.name
                    if float(tlt) > 0:
                        res.append(
                            {
                                "detalle": detalle,
                                "ingreso": tlt,
                                "egreso": "",
                                "recibir": "",
                            }
                        )
                    income_total += line.total
            self.cr.execute(
                """SELECT pl.id, pl.category_id FROM hr_payslip_line as pl \
				LEFT JOIN hr_salary_rule_category AS rc on (pl.category_id = rc.id) \
				LEFT JOIN hr_salary_rule AS sr on (pl.salary_rule_id = sr.id) \
				WHERE pl.id in %s and rc.code in ('DED', 'LOAN', 'SUBIESS') \
				GROUP BY rc.parent_id, sr.sequence, pl.id, pl.category_id \
				ORDER BY sr.sequence, rc.parent_id""",
                (tuple(ids),),
            )
            result = {}
            for x in self.cr.fetchall():
                result.setdefault(x[1], [])
                result[x[1]].append(x[0])
            for key, value in result.iteritems():
                for line in payslip_line.browse(self.cr, self.uid, value):
                    tlt = "%.2f" % abs(line.total)
                    detalle = line.name
                    if float(tlt) > 0:
                        res.append(
                            {
                                "detalle": detalle,
                                "ingreso": "",
                                "egreso": tlt,
                                "recibir": "",
                            }
                        )
                        outcome_total += line.total
            res.append(
                {
                    "detalle": "Total",
                    "ingreso": income_total,
                    "egreso": abs(outcome_total),
                    "recibir": (income_total - abs(outcome_total)),
                }
            )
        return res

    @api.multi
    def _compute_pay_amount(self):
        line_obj = self.env["hr.payslip.line"]
        # TODO LIQ se deja por compatibilidad, una vez pagados los sueldos con LIQ, dejar solo NET.
        for r in self:
            if r.state in ("draft", "verify", "done"):
                liquido = line_obj.search(
                    [("code", "in", ("NET", "LIQ")), ("slip_id", "=", r.id)]
                )
                amount = sum(liquido.mapped('amount'))
                payments = r.payment_ids.filtered(lambda x: x.state in ('posted', 'sent', 'reconciled'))
                due_amount = amount - sum(payments.mapped('amount'))
                r.amount = amount
                r.due_amount = due_amount

    
    def fields_view_get(
        self,
        view_id=None,
        view_type='form',
        toolbar=False,
        submenu=False
    ):        
        res = super(HrPayslip, self).fields_view_get(
            view_id=view_id,
            view_type=view_type,
            toolbar=toolbar,
            submenu=submenu,
        )
        update = view_type in ["form", "tree"]
        if update:
            doc = etree.XML(res["arch"])
            for t in doc.xpath("//" + view_type):
                t.attrib["create"] = "false"
            res["arch"] = etree.tostring(doc)
        return res

    def _get_default_journal(self):
        res = self.env.user.company_id.default_payroll_journal_id
        if res:
            return res
        return False

    def _get_default_company(self):
        return self.env.user.company_id

    @api.multi
    @api.depends("state")
    def _get_payment_type(self):
        res = ""
        for row in self:
            if row.employee_id.bank_account_id:
                res = "transfer"
            else:
                res = "check"
            row.payment_type = res

    wage = fields.Float(_("Wage"))
    job_id = fields.Many2one("hr.job", _("Job"))
    contract_type = fields.Many2one(
        "hr.contract.type",
        string="Contract Type",
        required=True,
        related="contract_id.type_id",
        store=True,
    )
    payroll_type = fields.Many2one(
        "hr.payslip.type", string="Payroll Type", required=True
    )
    payment_ids = fields.One2many(
        "account.payment", "payroll_slip_id", string=_("Payment")
    )
    journal_id = fields.Many2one(default=_get_default_journal)
    company_id = fields.Many2one(
        "res.company",
        _("Company"),
        required=True,
        readonly=True,
        default=_get_default_company,
    )
    payment_type = fields.Selection(
        [("check", "Check"), ("transfer", "Transfer")],
        string="Payment Type",
        compute=_get_payment_type,
        store=True,
    )
    amount = fields.Float("Amount to pay", compute=_compute_pay_amount)
    due_amount = fields.Float("Due Amount", compute=_compute_pay_amount)
    exclude = fields.Boolean("Exclude")

    def get_contract_info(self, contract, date_from, date_to):

        if type(contract) == list or type(contract) == int:
            contract = self.env['hr.contract'].browse(contract)
            
        res = {"job_id": contract.job_id.id, "wage": contract.wage}
        
        domain = [
            ("contract_id", "=", contract.id),
            ("date_from", "<=", date_to),
            ("date_to", ">=", date_to),
        ]
        hjob_obj = self.env["hr.contract.job"]
        hwage_obj = self.env["hr.contract.wage"]
        hjob_ids = hjob_obj.search(domain)
        hwage_ids = hwage_obj.search(domain)

        if type(hjob_ids) == int or type(hjob_ids) == list:
            hjob_ids = hjob_ids.browse(hjob_ids)
        
        if type(hwage_ids) == int or type(hwage_ids) == list:
            hwage_ids = hwage_obj.browse(hwage_ids)
             
        if hjob_ids:
            for hj in hjob_ids:
                if hj.date >= date_to:
                    res["job_id"] = hj.old_job_id.id
        if hwage_ids:
            for hw in hwage_obj:
                if hw.date >= date_to:
                    res["wage"] = hw.old_wage
        return res

    def get_worked_day_lines(self, contract, date_from, date_to):

        if type(contract) == list or type(contract) == int:
            contract = self.env['hr.contract'].browse(contract)

        employee_id = contract.employee_id

        holiday_ids = self.env["hr.leave"].search(
            [
                ("state", "=", "validate"),
                ("employee_id", "=", employee_id.id),
#                ("type", "=", "remove"),
                ("date_from", "<=", date_to),
                ("date_to", ">=", date_from),
            ],
        )
        holidays = holiday_ids
        status = holidays.mapped("holiday_status_id")
        res = []

        # Transformamos las fechas a datetime para usar relativedelta
        payroll_from = datetime.strptime(str(date_from), "%Y-%m-%d")
        payroll_to = datetime.strptime(str(date_to), "%Y-%m-%d")
        # Calculamos el número de días en el mes.
        days_in_month = monthrange(payroll_from.year, payroll_from.month)[1]

        # Todos los contratos inician con 30 días.
        if days_in_month > 30:
            work100 = 30
        else:
            work100 = days_in_month

        # Todos los contratos deben tener fecha de inicio.
        start_day = datetime.strptime(str(contract.date_start), "%Y-%m-%d")

        # Restamos los días no trabajados al inicio del mes.
        out_of_contract = 0
        # Dias entre el inicio del contrato y el inicio de la nómina.
        ddin = relativedelta(payroll_from, start_day).days
        # Si es negativo, lo debemos restar de los días trabajados.
        if ddin < 0:
            out_of_contract += ddin

        if contract.date_end:
            end_day = datetime.strptime(str(contract.date_end), "%Y-%m-%d")
            # Días que el contrato termina antes del fin de la nómina.
            dafn = relativedelta(end_day, payroll_to).days
            # Si el valor es negativo, debemos restar los días no trabajados.
            if dafn < 0:
                # Calculamos los días que se laboraron
                dl = relativedelta(end_day, payroll_from).days + 1
                # Los días no trabajados se calculan sobre una base de 30 días.
                # restamos dias laborados menos 30 para obtener un valor negativo.
                dnt = dl - 30
                if dnt < 0:
                    out_of_contract += dnt

        # El signo es positivo porque estamos trabajando con valor negativo.
        if out_of_contract < 0:
            # Restamos los días trabajados para evitar que se calculen décimos y
            # otros beneficios.
            work100 += out_of_contract

            res.append({
                "name": _("OUT OF CONTRACT"),
                "sequence": 5,
                "code": "OUT",
                "number_of_days": abs(out_of_contract),
                "contract_id": contract.id,
                }
            )

        for s in status:
            h = holidays.filtered(lambda x: x.holiday_status_id == s)
            days = abs(sum(h.mapped('number_of_days')))
            work100 -= days
            if work100 < 0:
                work100 = 0
            res.append({
                "name": s.name,
                "sequence": 5,
                "code": s.code or "WORK100",
                "number_of_days": days,
                "contract_id": contract.id,
                }
            )
        res.append({
            "name": _("Normal Working Days paid at 100%"),
            "sequence": 1,
            "code": "WORK100",
            "number_of_days": work100,
            "number_of_hours": 0.0,
            "contract_id": contract.id,
            }
        )
        return res


    """
    def get_worked_day_lines(
        self, cr, uid, contract_ids, date_from, date_to, context=None
    ):

        #@param contract_ids: list of contract id
        #@return: returns a list of dict containing the input that should be applied for the given contract between date_from and date_to

        def check_contract_attendance(contract, day):
            res = True
            if contract.date_start:
                start_day = datetime.strptime(contract.date_start, "%Y-%m-%d")
                if day >= start_day:
                    if contract.date_end:
                        end_day = datetime.strptime(contract.date_end, "%Y-%m-%d")
                        if day <= end_day:
                            res = False
                    else:
                        res = False
            return res

        def was_on_leave(employee_id, datetime_day, context=None):
            res = {}
            day = datetime_day.strftime("%Y-%m-%d")
            holiday_ids = self.pool.get("hr.holidays").search(
                cr,
                uid,
                [
                    ("state", "=", "validate"),
                    ("employee_id", "=", employee_id),
                    ("type", "=", "remove"),
                    ("date_from", "<=", day),
                    ("date_to", ">=", day),
                ],
            )
            if holiday_ids:
                res["data"] = self.pool.get("hr.holidays").browse(
                    cr, uid, holiday_ids, context=context
                )[0]
                res["type"] = "ausent"
            return res

        res = []
        for contract in self.pool.get("hr.contract").browse(
            cr, uid, contract_ids, context=context
        ):
            attendances = {
                "name": _("Normal Working Days paid at 100%"),
                "sequence": 1,
                "code": "WORK100",
                "number_of_days": 0.0,
                "number_of_hours": 0.0,
                "contract_id": contract.id,
            }
            leaves = {}
            day_from = datetime.strptime(date_from, "%Y-%m-%d")

            nb_of_days = range(0, 30)
            for day in nb_of_days:
                leave_type = was_on_leave(
                    contract.employee_id.id,
                    day_from + timedelta(days=day),
                    context=context,
                )
                leave_contract = check_contract_attendance(
                    contract, day_from + timedelta(days=day)
                )
                if leave_type:
                    # the employee had to work
                    if leave_type["data"] in leaves:
                        leaves[leave_type["data"]]["number_of_days"] += 1.0
                    elif leave_type["type"] == "ausent":
                        leaves[leave_type["data"]] = {
                            "name": leave_type["data"].holiday_status_id.name,
                            "sequence": 5,
                            "code": leave_type["data"].holiday_status_id.code or "",
                            "number_of_days": 1.0,
                            "contract_id": contract.id,
                        }
                else:
                    if leave_contract:
                        pass
                    else:
                        attendances["number_of_days"] += 1.0
            leaves = [value for key, value in leaves.items()]
            res += [attendances] + leaves
        return res
    """
    @api.model
    def _get_payslip_lines(self, contract_ids, payslip_id):
        def _sum_salary_rule_category(localdict, category, amount):
            if category.parent_id:
                localdict = _sum_salary_rule_category(
                    localdict, category.parent_id, amount
                )
            localdict["categories"].dict[category.code] = (
                category.code in localdict["categories"].dict
                and localdict["categories"].dict[category.code] + amount
                or amount
            )
            return localdict

        class BrowsableObject(object):
            def __init__(self, employee_id, dict, env):
                self.employee_id = employee_id
                self.dict = dict
                self.env = env

            def __getattr__(self, attr):
                return attr in self.dict and self.dict.__getitem__(attr) or 0.0

        class InputLine(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime("%Y-%m-%d")
                res = 0.0
                self.cr.execute(
                    "SELECT sum(amount) as sum\
                            FROM hr_payslip as hp, hr_payslip_input as pi \
                            WHERE hp.employee_id = %s AND hp.state = 'done' \
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s",
                    (self.employee_id, from_date, to_date, code),
                )
                res = self.cr.fetchone()[0]
                return res or 0.0

        class Sri(BrowsableObject):
            def tax_rent(
                self, contract, date_from, projectable, non_projectable, iess_percent
            ):
                rent_tax_obj = self.env["hr.sri.rent.tax"]
                annual_tax_obj = self.env["hr.sri.annual.rent.tax"]
                amount = 0.0
                month = str(date_from)[5:7]
                year = str(date_from)[0:4]
                annual_id = None
                if contract.rent_tax_ids:
                    for row in contract.rent_tax_ids:
                        if row.year == year:
                            annual_id = row.id
                            if row.line_ids:
                                for line in row.line_ids:
                                    if line.month == month:
                                        rent_tax_obj.unlink(self.cr, self.uid, line.id)
                else:
                    annual_id = annual_tax_obj.create(
                        {
                            "name": "Rent Tax %s" % year,
                            "year": year,
                            "contract_id": contract.id,
                        },
                    )
                base = projectable + non_projectable
                iess = base * iess_percent
                base -= iess

                deductible = 0
                if contract.projection_ids:
                    for row in contract.projection_ids:
                        if row.year == year:
                            deductible = row.monthly_amount

                table_obj = self.env["hr.sri.retention"]
                line_obj = self.env["hr.sri.retention.line"]

                table_ids = table_obj.search([("year", "=", year), ("active", "=", True)]
                )
                if table_ids:
                    for row in table_obj.browse(table_ids):
                        max_deductible = row.max_deductible / 12.0
                        if max_deductible < deductible and max_deductible > 0:
                            deductible = max_deductible
                        base -= deductible

                        line_ids = line_obj.search(
                            [
                                ("ret_id", "=", row.id),
                                ("monthly_basic_fraction", "<=", base),
                                ("monthly_excess_up", ">=", base),
                            ],
                        )
                        for line in line_obj.browse(line_ids):
                            amount += line.monthly_basic_fraction_tax
                            amount += (
                                (base - line.monthly_basic_fraction) * line.percent
                            ) / 100.0
                            rent_tax_obj.create(
                                {
                                    "year": year,
                                    "month": month,
                                    "projectable": projectable,
                                    "non_projectable": non_projectable,
                                    "amount": round(amount, 2),
                                    "rent_id": annual_id,
                                },
                            )
                if amount > 0:
                    return amount
                return 0

        class Utils(BrowsableObject):
            def check_reserve_funds(self, contract, payslip):
                if contract.force_reserve_founds:
                    return True
                date_format = "%Y-%m-%d"
                cdate = datetime.strptime(str(contract.date_start), date_format)
                pdate = datetime.strptime(str(payslip.date_to), date_format)
                tdays = (pdate - cdate).days
                if tdays > 365:
                    return True
                return False

            def reserve_funds(
                self, contract, payslip, inggrav, work100, fr_percent, method
            ):
                date_format = "%Y-%m-%d"
                total = 0.0
                cdate = datetime.strptime(str(contract.date_start), date_format)
                pdate = datetime.strptime(str(payslip.date_from), date_format)
                tdays = (pdate - cdate).days + work100
                sub_total = inggrav * (fr_percent / 100.0)
                if (tdays - 395) >= 0 or contract.force_reserve_founds:
                    total = sub_total
                else:
                    total = (sub_total / 30.0) * (tdays - 365.0)
                amount = total
                if method == "payslip":
                    type_obj = self.env["hr.payslip.type"]
                    type_id = type_obj.search(
                        [("name", "=", "Mensual")]
                    )
                    payslip_obj = self.env["hr.payslip"]
                    line_obj = self.env["hr.payslip.line"]
                    payslip_date = datetime.strptime(
                        str(payslip.date_from), date_format
                    ) - relativedelta(months=1)
                    date_from = "{}-{:0>2}-{:0>2}".format(
                        payslip_date.year, payslip_date.month, payslip_date.day
                    )
                    date_to = "{}-{:0>2}-{:0>2}".format(
                        payslip_date.year,
                        payslip_date.month,
                        monthrange(payslip_date.year, payslip_date.month)[1],
                    )
                    payslip_id = payslip_obj.search(
                        self.cr,
                        self.uid,
                        [
                            ("contract_id", "=", contract.id),
                            ("date_from", ">=", date_from),
                            ("date_to", "<=", date_to),
                            ("payroll_type", "in", type_id),
                        ],
                    )
                    line_id = line_obj.search(
                        [("slip_id", "in", payslip_id), ("code", "=", "FRPROV")],
                    )
                    if line_id:
                        amount = sum(
                            [
                                prov.amount
                                for prov in line_obj.browse(line_id)
                            ]
                        )
                return round(amount, 2)

            def biweekly(self, employee, contract, date_from, date_to):
                amount = 0.0
                rule_obj = self.env["hr.salary.rule"]
                line_obj = self.env["hr.payslip.line"]
                rule_id = rule_obj.search([("biweekly_deduction", "=", True)]
                )
                if rule_id:
                    line_id = line_obj.search(                        
                        [
                            ("contract_id", "=", contract.id),
                            ("date_from", ">=", date_from),
                            ("date_to", "<=", date_to),
                            ("salary_rule_id", "=", rule_id.id),
                            ("state", "=", "done"),
                        ],
                    )
                    if line_id:
                        amount = sum(
                            [
                                ded.amount
                                for ded in line_id
                            ]
                        )
                if amount > 0:
                    return amount
                return 0

            def invoices(self, employee, date_from, date_to):
                amount = 0.0
                payment_obj = self.env["account.payment"]
                journal_obj = self.env["account.journal"]
                journal_id = journal_obj.search([("payroll_discount", "=", True)])
                partner_id = employee.address_home_id.id
                payment_id = payment_obj.search(                    
                    [
                        ("partner_id", "=", partner_id),
                        ("journal_id", "in", journal_id),
                        ("payment_date", ">=", date_from),
                        ("payment_date", "<=", date_to),
                        ("state", "=", "posted"),
                    ],
                )
                if payment_id:
                    amount = sum(
                        [
                            pay.amount
                            for pay in payment_obj.browse(payment_id)
                        ]
                    )
                if amount > 0:
                    return amount
                return 0

        class WorkedDays(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def _sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime("%Y-%m-%d")
                self.cr.execute(
                    "SELECT sum(number_of_days) as number_of_days, sum(number_of_hours) as number_of_hours\
                            FROM hr_payslip as hp, hr_payslip_worked_days as pi \
                            WHERE hp.employee_id = %s AND hp.state = 'done'\
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s",
                    (self.employee_id, from_date, to_date, code),
                )
                return self.cr.fetchone()

            def sum(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[0] or 0.0

            def sum_hours(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[1] or 0.0

        class Payslips(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime("%Y-%m-%d")
                self.cr.execute(
                    "SELECT sum(case when hp.credit_note = False then (pl.total) else (-pl.total) end)\
                            FROM hr_payslip as hp, hr_payslip_line as pl \
                            WHERE hp.employee_id = %s AND hp.state = 'done' \
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pl.slip_id AND pl.code = %s",
                    (self.employee_id, from_date, to_date, code),
                )
                res = self.cr.fetchone()
                return res and res[0] or 0.0

        # we keep a dict with the result because a value can be overwritten by
        # another rule with the same code
        result_dict = {}
        rules = {}
        categories_dict = {}
        blacklist = []
        payslip_obj = self.env["hr.payslip"]
        obj_rule = self.env["hr.salary.rule"]
        payslip = payslip_obj.browse(payslip_id)
        worked_days = {}
        for worked_days_line in payslip.worked_days_line_ids:
            worked_days[worked_days_line.code] = worked_days_line
        inputs = {}
        inputs_vals = {}
        for input_line in payslip.input_line_ids:
            inputs[input_line.code] = input_line

        categories_obj = BrowsableObject(
            payslip.employee_id.id, categories_dict, self.env
        )
        input_obj = InputLine(payslip.employee_id.id, inputs, self.env)
        worked_days_obj = WorkedDays(
            payslip.employee_id.id, worked_days, self.env
        )
        payslip_obj = Payslips(payslip.employee_id.id, payslip, self.env)
        rules_obj = BrowsableObject(payslip.employee_id.id, rules, self.env)

        sri_obj = Sri(payslip.employee_id.id, payslip_obj, self.env)
        utils_obj = Utils(payslip.employee_id.id, payslip_obj, self.env)
        baselocaldict = {
            "categories": categories_obj,
            "rules": rules_obj,
            "payslip": payslip_obj,
            "worked_days": worked_days_obj,
            "inputs": input_obj,
            "sri": sri_obj,
            "utils": utils_obj,
        }
        if type(contract_ids) == list or type(contract_ids) == int:
            contract_ids = self.env["hr.contract"].browse(contract_ids)
        # get the ids of the structures on the contracts and their parent id as well
        structure_ids = contract_ids.get_all_structures()

        # get the rules of the structure and thier children
        rule_ids = self.env["hr.payroll.structure"].browse(structure_ids).get_all_rules()

        # run the rules by sequence
        sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x: x[1])]

        for contract in contract_ids:
            employee = contract.employee_id
            localdict = dict(baselocaldict, employee=employee, contract=contract)

            payroll_rule_ids = []

            for rule_id in sorted_rule_ids:
                rule = obj_rule.browse(rule_id)
                if rule.payroll_type_ids:
                    if payslip.payroll_type in rule.payroll_type_ids:
                        payroll_rule_ids.append(rule_id)
                else:
                    payroll_rule_ids.append(rule_id)

            for rule in obj_rule.browse(payroll_rule_ids):
                key = rule.code + "-" + str(contract.id)
                localdict["result"] = None
                localdict["result_qty"] = 1.0
                localdict["result_rate"] = 100
                # check if the rule can be applied
                if (
                    rule._satisfy_condition(localdict)
                    and rule.id not in blacklist
                ):
                    # compute the amount of the rule
                    amount, qty, rate = rule._compute_rule(localdict)
                    # sum inputs amount
                    if rule.code in inputs_vals:
                        amount = inputs_vals[rule.code]["amount"]
                    # check if there is already a rule computed with that code
                    previous_amount = (
                        rule.code in localdict and localdict[rule.code] or 0.0
                    )
                    # set/overwrite the amount computed for this rule in the localdict
                    tot_rule = amount * qty * rate / 100.0
                    localdict[rule.code] = tot_rule
                    rules[rule.code] = rule
                    # sum the amount for its salary category
                    localdict = _sum_salary_rule_category(
                        localdict, rule.category_id, tot_rule - previous_amount
                    )
                    # create/overwrite the rule in the temporary results
                    result_dict[key] = {
                        "salary_rule_id": rule.id,
                        "contract_id": contract.id,
                        "name": rule.name,
                        "code": rule.code,
                        "category_id": rule.category_id.id,
                        "sequence": rule.sequence,
                        "appears_on_payslip": rule.appears_on_payslip,
                        "condition_select": rule.condition_select,
                        "condition_python": rule.condition_python,
                        "condition_range": rule.condition_range,
                        "condition_range_min": rule.condition_range_min,
                        "condition_range_max": rule.condition_range_max,
                        "amount_select": rule.amount_select,
                        "amount_fix": rule.amount_fix,
                        "amount_python_compute": rule.amount_python_compute,
                        "amount_percentage": rule.amount_percentage,
                        "amount_percentage_base": rule.amount_percentage_base,
                        "register_id": rule.register_id.id,
                        "amount": amount,
                        "employee_id": contract.employee_id.id,
                        "quantity": qty,
                        "rate": rate,
                    }
                else:
                    # blacklist this rule and its children
                    blacklist += [id for id, seq in rule._recursive_search_of_rules()]

        result = [value for code, value in result_dict.items()]
        return result

    @api.multi
    def contract_info(self):
        for payslip in self:
            contract_ids = payslip.contract_id.ids or self.get_contract(
                payslip.employee_id, payslip.date_from, payslip.date_to
            )
            hist_data = self.get_contract_info(
                contract_ids, payslip.date_from, payslip.date_to
            )
            payslip.write({"job_id": hist_data["job_id"], "wage": hist_data["wage"]})
        return True

    @api.multi
    def compute_worked_days(self):
        for payslip in self:
            worked_days_ids = payslip.mapped("worked_days_line_ids")
            if worked_days_ids:
                # delete old worked days lines
                worked_days_ids.unlink()
            contract_id = payslip.contract_id
            wdays = payslip.get_worked_day_lines(
                contract_id, payslip.date_from, payslip.date_to
            )
            worked_days = [
                (0, 0, wd) for wd in wdays
            ]
            payslip.write({"worked_days_line_ids": worked_days})
        return True

    @api.multi
    def create_news(self, lines):
        new_obj = self.env["hr.payslip.news"]
        loan_obj = self.env["hr.payslip.loans"]
        for l in lines:
            if l.salary_rule_id.rule_deduction_type == "fixed":
                date_to = (
                    datetime.strftime(str(l.date_to, "%Y-%m-%d")) + relativedelta(months=+1)
                ).strftime("%Y-%m-%d")
                new_obj.create(
                    {
                        "name": _(
                            "Discount Paylsip Negative: {}".format(l.slip_id.number)
                        ),
                        "employee_id": l.employee_id.id,
                        "date": date_to,
                        "rule_id": l.salary_rule_id.rule_deduction_id.id,
                        "payroll_type": l.salary_rule_id.rule_deduction_payroll_type.id,
                        "amount": l.amount,
                        "state": "approved",
                    }
                )
            if l.salary_rule_id.rule_deduction_type == "deferred":
                year, month, day = l.date_to.split("-")
                loan_obj.create(
                    {
                        "name": _(
                            "Discount Paylsip Negative: {}".format(l.slip_id.number)
                        ),
                        "employee_id": l.employee_id.id,
                        "application_date": l.date_to,
                        "rule_id": l.salary_rule_id.rule_deduction_id.id,
                        "payroll_type": l.salary_rule_id.rule_deduction_payroll_type.id,
                        "amount": l.amount,
                        "dues": 1,
                        "month": month,
                        "year": year,
                        "state": "draft",
                    }
                )
        return True

    @api.multi
    def process_sheet(self):
        for row in self:
            for line in row.input_line_ids:
                if line.new_id:
                    line.new_id.write({"state": "done"})
                if line.overtime_id:
                    line.overtime_id.write({"state": "done"})
                    line.overtime_id.overtime_id.write({"state": "done"})
            rule_deduction = row.mapped("line_ids").filtered(
                lambda x: x.salary_rule_id.rule_deduction
            )
            if rule_deduction:
                self.create_news(rule_deduction)
            row.write({"paid": True, "state": "done"})

    @api.multi
    def post_sheet(self):
        move_pool = self.env["account.move"]
        precision = self.env["decimal.precision"].precision_get("Payroll")

        for slip in self:
            if slip.exclude:
                continue
            line_ids = []
            debit_sum = 0.0
            credit_sum = 0.0
            date = slip.payslip_run_id.date or slip.date or slip.date_to

            name = _("Payslip of %s") % (slip.employee_id.name)
            move = {
                "narration": name,
                "ref": slip.number,
                "journal_id": slip.journal_id.id,
                "date": date,
            }
            for line in slip.details_by_salary_rule_category:
                amt = slip.credit_note and -line.total or line.total
                if float_is_zero(amt, precision_digits=precision):
                    continue
                debit_account_id = False
                credit_account_id = False
                analytic_account_id = False
                tax_line_id = False
                map_id = False
                if slip.contract_id.department_id:
                    department_id = slip.contract_id.department_id
                    while department_id:
                        map_id = department_id.mapped("salaryrule_map_ids").filtered(
                            lambda x: x.department_id.id == department_id.id
                            and x.salary_rule_id.id == line.salary_rule_id.id
                        )
                        if map_id:
                            break
                        else:
                            department_id = department_id.parent_id
                    if map_id:
                        debit_account_id = (
                            map_id.account_debit and map_id.account_debit.id
                        )
                        credit_account_id = (
                            map_id.account_credit and map_id.account_credit.id
                        )
                        analytic_account_id = (
                            map_id.analytic_account_id and map_id.analityc_account_id.id
                        )
                        tax_line_id = map_id.account_tax_id and map_id.account_tax_id.id
                else:
                    debit_account_id = line.salary_rule_id.account_debit.id
                    credit_account_id = line.salary_rule_id.account_credit.id
                    analytic_account_id = (
                        line.salary_rule_id.analytic_account_id
                        and line.salary_rule_id.analytic_account_id.id
                        or False
                    )
                    tax_line_id = (
                        line.salary_rule_id.account_tax_id
                        and line.salary_rule_id.account_tax_id.id
                        or False
                    )
                if line.salary_rule_id.analytic:
                    analytic_account_id = (
                        line.mapped("employee_id")
                        .mapped("job_id")
                        .mapped("analytic_account_id")
                        .id
                    )
                if debit_account_id:
                    debit_line = (
                        0,
                        0,
                        {
                            "name": line.name,
                            "partner_id": line._get_partner_id(
                                map_id, line, credit_account=False
                            ),
                            "account_id": debit_account_id,
                            "journal_id": slip.journal_id.id,
                            "date": date,
                            "debit": amt > 0.0 and amt or 0.0,
                            "credit": amt < 0.0 and -amt or 0.0,
                            "analytic_account_id": analytic_account_id,
                            "tax_line_id": tax_line_id,
                        },
                    )
                    line_ids.append(debit_line)
                    debit_sum += debit_line[2]["debit"] - debit_line[2]["credit"]

                if credit_account_id:
                    credit_line = (
                        0,
                        0,
                        {
                            "name": line.name,
                            "partner_id": line._get_partner_id(
                                map_id, line, credit_account=True
                            ),
                            "account_id": credit_account_id,
                            "journal_id": slip.journal_id.id,
                            "date": date,
                            "debit": amt < 0.0 and -amt or 0.0,
                            "credit": amt > 0.0 and amt or 0.0,
                            "analytic_account_id": analytic_account_id,
                            "tax_line_id": tax_line_id,
                        },
                    )
                    line_ids.append(credit_line)

                    credit_sum += credit_line[2]["credit"] - credit_line[2]["debit"]
            if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                acc_id = slip.journal_id.default_credit_account_id.id
                if not acc_id:
                    raise UserError(
                        _(
                            'The Expense Journal "%s" has not properly configured the Credit Account!'
                        )
                        % (slip.journal_id.name)
                    )
                adjust_credit = (
                    0,
                    0,
                    {
                        "name": _("Adjustment Entry"),
                        "partner_id": False,
                        "account_id": acc_id,
                        "journal_id": slip.journal_id.id,
                        "date": date,
                        "debit": 0.0,
                        "credit": debit_sum - credit_sum,
                    },
                )
                line_ids.append(adjust_credit)

            elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                acc_id = slip.journal_id.default_debit_account_id.id
                if not acc_id:
                    raise UserError(
                        _(
                            'The Expense Journal "%s" has not properly configured the Debit Account!'
                        )
                        % (slip.journal_id.name)
                    )
                adjust_debit = (
                    0,
                    0,
                    {
                        "name": _("Adjustment Entry"),
                        "partner_id": False,
                        "account_id": acc_id,
                        "journal_id": slip.journal_id.id,
                        "date": date,
                        "debit": credit_sum - debit_sum,
                        "credit": 0.0,
                    },
                )
                line_ids.append(adjust_debit)
            if not slip.move_id:
                move["line_ids"] = line_ids
                move_id = move_pool.create(move)
                move_id.post()
                slip.write({"move_id": move_id.id, "date": date})
        return True

    @api.model
    def get_inputs(self, contract_ids, date_from, date_to):
        try:
            payroll_type = self._context.get("payroll_type", False)[0]
        except TypeError:
            payroll_type = self._context.get("payroll_type", False)
        payroll_type = self.env["hr.payslip.type"].browse([payroll_type])
        contract_obj = self.env["hr.contract"]
        if type(contract_ids) == list or type(contract_ids) == int: 
            contract_ids = contract_obj.browse(contract_ids)
        res = super(HrPayslip, self).get_inputs(contract_ids, date_from, date_to)
        news_obj = self.env["hr.payslip.news"]
        overtime_obj = self.env["hr.payslip.overtime.line"]        
        for contract in contract_ids:
            news_ids = news_obj.search(
                [
                    ("date", ">=", date_from),
                    ("date", "<=", date_to),
                    ("payroll_type", "in", payroll_type.ids),
                    ("employee_id", "=", contract.employee_id.id),
                    ("state", "=", "approved"),
                ]
            )

            for new in news_ids:
                inputs = {
                    "name": str(new.name or new.rule_id.name).upper(),
                    "code": new.rule_id.code,
                    "contract_id": contract.id,
                    "quantity": new.quantity,
                    "new_id": new.id,
                    "amount": new.amount,
                }
                res += [inputs]
            if payroll_type.overtime:
                overtime_ids = overtime_obj.search(
                    [
                        ("date", ">=", date_from),
                        ("date", "<=", date_to),
                        ("employee_id", "=", contract.employee_id.id),
                        ("state", "=", "approved"),
                    ]
                )

                for over in overtime_ids:
                    if over.overtime_025:
                        inputs = {
                            "name": _("HOURS NIGHT SHIFT (25%)"),
                            "code": "HE025",
                            "contract_id": contract.id,
                            "overtime_id": over.id,
                            "quantity": over.overtime_025,
                            "amount": over.hour_cost * over.overtime_025 * 1.75,
                        }
                        res += [inputs]
                    if over.overtime_050:
                        inputs = {
                            "name": _("OVERTIME (50%)"),
                            "code": "HE050",
                            "contract_id": contract.id,
                            "overtime_id": over.id,
                            "quantity": over.overtime_050,
                            "amount": over.hour_cost * over.overtime_050 * 1.50,
                        }
                        res += [inputs]
                    if over.overtime_100:
                        inputs = {
                            "name": _("EXTRA HOURS (100%)"),
                            "code": "HE100",
                            "contract_id": contract.id,
                            "overtime_id": over.id,
                            "quantity": over.overtime_100,
                            "amount": over.hour_cost * over.overtime_100 * 2.00,
                        }
                        res += [inputs]
        return res

    @api.multi
    def compute_inputs(self):
        for payslip in self:
            old_input_ids = payslip.mapped("input_line_ids")
            if old_input_ids:
                # delete old input lines
                old_input_ids.unlink()

            contract_ids = payslip.contract_id.ids or self.get_contract(
                payslip.employee_id, payslip.date_from, payslip.date_to
            )
            inputs = [
                (0, 0, inputs)
                for inputs in self.with_context(
                    payroll_type=payslip.payroll_type.id
                ).get_inputs(contract_ids, payslip.date_from, payslip.date_to)
            ]
            payslip.write({"input_line_ids": inputs})
        return True

    @api.multi
    def update_sheet(self):
        self.contract_info()
        self.compute_worked_days()
        self.compute_inputs()
        self.compute_sheet()
        return True

    @api.multi
    def undo_sheet(self):
        for row in self:
            if row.move_id.state == "posted":
                raise ValidationError(
                    _(
                        "You can not re-draft a payment role that has already been posted!"
                    )
                )
            for line in row.input_line_ids:
                if line.new_id:
                    line.new_id.write({"state": "approved"})
                if line.overtime_id:
                    line.overtime_id.write({"state": "draft"})
                    line.overtime_id.overtime_id.write({"state": "draft"})
            row.write({"paid": False, "state": "draft"})


class PayrollReportView(models.Model):
    _name = "hr.payroll.report.view"
    _auto = False

    name = fields.Many2one("hr.employee", string="Employee")
    payroll_type = fields.Many2one(
        "hr.payslip.type", string="Payroll Type", required=True
    )
    date_from = fields.Date(string="From")
    date_to = fields.Date(string="To")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("verify", "Waiting"),
            ("done", "Done"),
            ("cancel", "Rejected"),
        ],
        string="Status",
    )
    job_id = fields.Many2one("hr.job", string=_("Job"))
    job = fields.Char(_("Job Title"))
    company_id = fields.Many2one("res.company", string=_("Company"))
    category_id = fields.Many2one("hr.salary.rule.category", string=_("Category"))
    category = fields.Char(_("Category Name"))
    slip_id = fields.Many2one("hr.payslip", string=_("Slip"))
    rule_id = fields.Many2one("hr.salary.rule", string=_("Rule"))
    rule = fields.Char(_("Rule Name"))
    department_id = fields.Many2one("hr.department", string=_("Department"))
    department = fields.Char(_("Department Name"))
    amount = fields.Float(string="amount")
    @api.multi
    def generate_template(self):
        for row in self:
            rules = []
            if not row.line_ids:
                raise UserError(
                    _(
                        "Please select at least one salary rule to generate the template!!"
                    )
                )
            for rule in row.line_ids:
                rules.append("%s|%s" % (rule.name, rule.rule_id.code))
            employee_data = []
            file_data = BytesIO()
            xbook = xlsxwriter.Workbook(file_data, {"in_memory": True})
            xsheet = xbook.add_worksheet("News")
            header = [_("Identification"), _("Passport"), _("Name")] + rules
            for hr in row.employee_ids:
                data = []
                data.insert(0, hr.identification_id or "")
                data.insert(1, hr.passport_id or "")
                data.insert(2, hr.name)
                employee_data.append(data + [0.0 for x in rules])
                xsheet.write_row(0, 0, header)
            for line in range(0, len(employee_data)):
                xsheet.write_row(line + 1, 0, employee_data[line])
            xbook.close()
            out = base64.encodestring(file_data.getvalue())
            row.write(
                {
                    "name": _("News_Template.xlsx"),
                    "file_template": out,
                    "state": "exported",
                }
            )
        return {
            "context": self.env.context,
            "view_type": "form",
            "view_mode": "form",
            "res_model": "wizard.hr.payslip.news",
            "view_id": False,
            "res_id": self.id,
            "type": "ir.actions.act_window",
            "target": "new",
        }
    def init(self):
        drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """CREATE or REPLACE VIEW %s as (
               SELECT hpl.id AS id,
                      hpl.company_id AS company_id,
                      he.id AS name,
                      hj.id AS job_id,
                      hj.name AS job,
                      hd.id AS department_id,
                      hd.name AS department,
                      hpl.slip_id AS slip_id,
                      hpl.payroll_type AS payroll_type,
                      hsrc.id AS category_id,
                      hsrc.name AS category,
                      hpl.salary_rule_id AS rule_id,
                      hpl.name AS rule,
                      hpl.date_from AS date_from,
                      hpl.date_to AS date_to,
                      hpl.amount AS amount,
                     hpl.state AS state
              FROM hr_payslip_line hpl
                   JOIN hr_employee he ON hpl.employee_id = he.id
                   JOIN hr_department hd ON he.department_id = hd.id
                   JOIN hr_job hj ON he.job_id = hj.id
                   JOIN hr_salary_rule_category hsrc ON hpl.category_id = hsrc.id)"""
            % (self._table)
        )
