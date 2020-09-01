#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64
import logging
import time
from io import StringIO, BytesIO

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import pandas as pd
except ImportError:
    _logger.error("The module pandas can't be loaded, try: pip3 install pandas")

try:
    import xlrd
except ImportError:
    _logger.error("The module xlrd can't be loaded, try: pip3 install xlrd")

try:
    import xlsxwriter
except ImportError:
    _logger.error("The module xlsxwriter can't be loaded, try: pip install xlsxwriter")


class WizardHrPayslipNews(models.TransientModel):
    """
    Generate and Imports news from Template
    """

    _name = "wizard.hr.payslip.news"
    _description = __doc__

    employee_ids = fields.Many2many(
        "hr.employee", "hr_employee_wiz_news", "wiz_id", "employee_id", _("Employees")
    )
    generate_name = fields.Char(_("Description"))
    generate_option = fields.Selection(
        [
            ("all", _("All")),
            ("employee", _("Employee")),
            ("department", _("Department")),
        ],
        string="Generate Option",
        default="all",
    )
    generate_employee_ids = fields.Many2many("hr.employee", string=_("Employees"))
    generate_department_ids = fields.Many2many("hr.department", string=_("Departments"))
    generate_payroll_type = fields.Many2one("hr.payslip.type", string="Payroll Type")

    @api.multi
    @api.onchange('generate_payroll_type')
    def _onchange_generate_payroll_type(self):
        for r in self:
            if not r.generate_payroll_type:
                domain = {'domain':{'generate_rule_id':[('id', 'in', [])]}}
            else:
                rules = self.env['hr.salary.rule'].search(
                    [
                        ('allowed_in_news', '=', True)
                    ]
                ).filtered(lambda x: r.generate_payroll_type in x.payroll_type_ids)
                domain = {'domain':{'generate_rule_id':[('id', 'in', rules.ids)]}}
            return domain

    generate_rule_id = fields.Many2one(
        "hr.salary.rule",
        string=_("Salary Rule"),
    )
    generate_type = fields.Selection(
        [
            ("fixed", _("Fixed Amount")),
            ("salary_percent", _("Salary Percent")),
            ("net_percent", _("Net Percent")),
        ],
        string="Generate Type",
        default="fixed",
    )
    generate_date = fields.Date(_("Date"))
    generate_amount = fields.Float(_("Amount"))
    generate_percent = fields.Float(_("Percent"))
    generate_approve_news = fields.Boolean(_("Approve news"))
    name = fields.Char(_("Name"))
    date = fields.Date("Register Date")
    file_template = fields.Binary(_("Template"))
    file_upload = fields.Binary(_("Template"))
    approve_news = fields.Boolean(_("Approve news"))

    line_ids = fields.One2many(
        "wizard.hr.payslip.news.line", "wiz_id", string=_("Salary Rules")
    )
    option = fields.Selection(
        [
            ("export", _("Export Template")),
            ("import", _("Import Template")),
            ("generate", _("Generate")),
        ],
        string=_("Option"),
        default="export",
    )
    state = fields.Selection(
        [("draft", _("Draft")), ("exported", _("Exported"))],
        string="State",
        default="draft",
    )
    payroll_type = fields.Many2one("hr.payslip.type", string="Payroll Type")


    @api.multi
    def generate_news(self):
        department_obj = self.env["hr.department"]
        employee_obj = self.env["hr.employee"]
        contract_obj = self.env["hr.contract"]
        payroll_obj = self.env["hr.payslip"]
        news_obj = self.env["hr.payslip.news"]
        basic_wage = 0
        iess_personal = 0
        domain = []
        news_data = []
        for row in self:
            if row.generate_news == 0:
                raise UserError(_("The amount can not be 0!"))
            state = "approved" if row.generate_approve_news else "draft"
            date_from = "{}-{}-{}".format(
                row.generate_date.strftime('%Y-%m-%d')[0:4], row.generate_date.strftime('%Y-%m-%d')[5:7], "01"
            )
            date_to = row.generate_date
            if row.generate_option == "department" and row.generate_department_ids:
                department_ids = (
                    department_obj.browse(row.generate_department_ids.mapped("id"))
                    ._get_subdepartmets()
                    .ids
                )
                domain.append(("department_id", "in", department_ids))
            elif row.generate_option == "employee" and row.generate_employee_ids:
                ids = row.mapped("generate_employee_ids").ids
                domain.append(("id", "in", ids))
            employee_ids = employee_obj.search(domain)
            contracts = []

            for emp in employee_ids:
                contract_id = payroll_obj.get_contract(emp, date_from, date_to)
                if contract_id:
                    contracts.append(contract_id)
            contract_ids = sum(contracts, [])
            for contr in contract_obj.browse(contract_ids):
                amount = 0
                wage = payroll_obj.get_contract_info(contr, date_from, date_to)[
                    "wage"
                ]
                if row.generate_type == "fixed":
                    amount = row.generate_amount
                if row.generate_type in ["salary_percent", "net_percent"] and not (
                    1 <= row.generate_percent <= 100
                ):
                    raise UserError(
                        _("The percentage to calculate must be between 1 to 100!")
                    )
                percent = row.generate_percent / 100.0
                if row.generate_type == "salary_percent":
                    amount = wage * percent
                if row.generate_type == "net_percent":
                    incomming = 0
                    outcomming = 0

                    #query = """
                    #SELECT
                    #  SUM(sn.amount) as amount
                    #FROM
                    #  hr_payslip_news sn
                    #  JOIN hr_salary_rule hrs ON sn.rule_id = hrs.id
                    #  JOIN hr_salary_rule_category rc ON hrs.category_id = rc.id
                    #WHERE
                    #  sn.employee_id = {} AND
                    #  sn.date >='{}' AND
                    #  sn.date <='{}' AND
                    #  sn.state IN ('approved', 'done') AND
                    #  rc.code IN {}"""
                    #self.env.cr.execute(
                    #    query.format(
                    #        contr.employee_id.id,
                    #        date_from,
                    #        date_to,
                    #        tuple(["ALW", "INGGRAV"]),
                    #    )
                    #)
                    #in_grav_data = self.env.cr.dictfetchall()[0]
                    #incomming = sum([wage, in_grav_data.get("amount", False) or 0])

                    payroll_type = self.env.ref('l10n_ec_hr_payroll.payslip_type_m')
                    news = self.env['hr.payslip.news'].search([
                        ("employee_id","=", contr.employee_id.id),
                        ("date", ">=", date_from),
                        ("date", "<=", date_to),
                        ("state", "!=", "draft"),
                        ("payroll_type", "=", payroll_type.id)
                    ])

                    ing_grav = sum(news.filtered(
                        lambda x: x.rule_id.category_id.code in ("ALW", "INGGRAV")
                    ).mapped('amount'))
                    incomming = wage + ing_grav
                    # # Calculamos el IESS solo con los ingresos grabados.
                    retencion_iess_personal = 0
                    iess_personal =  contr.employee_id.company_id \
                        .get_porcentaje_iess_personal()
                    retencion_iess_personal = incomming * iess_personal/100
                    # Agregamos los ingresos no gravados.
                    #self.env.cr.execute(
                    #    query.format(
                    #        contr.employee_id.id,
                    #        date_from,
                    #        date_to,
                    #        tuple(["INGNOGRAV","INGRESONOGRAVADO"]),
                    #    )
                    #)
                    #in_no_grav_data = self.env.cr.dictfetchall()[0]
                    #incomming = sum([incomming, in_no_grav_data.get("amount", False) or 0])
                    ing_no_grav = sum(news.filtered(
                        lambda x: x.rule_id.category_id.code == "INGNORAV"
                    ).mapped('amount'))
                    incomming += ing_no_grav
                    # Icluir décimo cuarto si se paga en rol
                    if contr.decimo_tercero_rol:
                        # para quincena, usamos solo el sueldo base.
                        incomming += wage/12

                    # Icluir décimo tercero si se paga en rol
                    if contr.decimo_cuarto_rol:
                        basic_wage = contr.employee_id \
                            .company_id.get_basic_wage()
                        incomming += basic_wage / 12

                    # Incluímos los egresos.
                    #self.env.cr.execute(
                    #    query.format(
                    #        contr.employee_id.id,
                    #        date_from,
                    #        date_to,
                    #        tuple(["DED", "LOAN", "SUBIESS"])
                    #    )
                    #)
                    #out_data = self.env.cr.dictfetchall()[0]
                    #outcomming = out_data.get("amount", False) or 0
                    outcomming = sum(news.filtered(
                        lambda x: x.rule_id.category_id.code in ("LOAN", "DED", "SUBIESS")
                    ).mapped('amount'))
                    # Restamos la deducción del IESS personal.
                    outcomming += retencion_iess_personal
                    amount = (incomming - outcomming) * percent
                vals = {
                    "name": row.generate_name,
                    "date": row.generate_date,
                    "rule_id": row.generate_rule_id.id,
                    "payroll_type": row.generate_payroll_type.id,
                    "state": state,
                    "employee_id": contr.employee_id.id,
                    "amount": round(amount, 2),
                }
                news_data.append(vals)
        if news_data:
            for new in news_data:
                news_obj.create(new)
        return {
            "context": self.env.context,
            "view_type": "form",
            "view_mode": "tree,form",
            "res_model": "hr.payslip.news",
            "view_id": False,
            "res_id": False,
            "type": "ir.actions.act_window",
        }

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
            if not row.employee_ids:
                raise UserError(
                    _("Please select at least one employee to generate the template!!")
                )
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

    @api.multi
    def import_template(self):
        employee_obj = self.env["hr.employee"]
        news_obj = self.env["hr.payslip.news"]
        rule_obj = self.env["hr.salary.rule"]
        news_data = []
        news_ids = []
        for row in self:
            if not row.file_upload:
                raise UserError(_("Please Select file to import"))
            xdata = base64.b64decode(row.file_upload)
            xbook = xlrd.open_workbook(file_contents=xdata)
            df = pd.read_excel(xbook, "News", engine="xlrd")
            state = "approved" if row.approve_news else "draft"
            for index, y in df.iterrows():
                identification = "{:0>10}".format(int(y[0]))
                employee_id = employee_obj.search(
                    [
                        "|",
                        ("identification_id", "=", identification),
                        ("passport_id", "=", y[1]),
                    ]
                )
                if not employee_id:
                    employee_id = employee_obj.with_context(
                        show_unemployed=True
                    ).search(
                        [
                            "|",
                            ("identification_id", "=", identification),
                            ("passport_id", "=", y[1]),
                        ]
                    )
                data = y.to_dict()
                if not employee_id:
                    raise UserError(_("Employee not found: {}".format(y[2])))
                for key in data:
                    if "|" in key and data[key] > 0:
                        news_name, news_code = key.split("|")
                        rule_id = rule_obj.search([("code", "=", news_code)])
                        if row.payroll_type not in rule_id.payroll_type_ids:
                            raise UserError(
                                _(
                                    "No puede utilizar la regla {} en un rol {}"
                                ).format(rule_id.name, row.payroll_type.name)
                            )
                        news_data.append(
                            {
                                "name": news_name,
                                "date": row.date,
                                "rule_id": rule_id.id,
                                "payroll_type": row.payroll_type.id,
                                "employee_id": employee_id.id,
                                "amount": data[key],
                                "state": state,
                            }
                        )
        for new in news_data:
            news = news_obj.create(new)
            news_ids.append(news.id)
        return {
            "context": self.env.context,
            "view_type": "form",
            "view_mode": "tree,form",
            "res_model": "hr.payslip.news",
            "view_id": False,
            "res_id": False,
            "domain": [("id", "in", news_ids)],
            "type": "ir.actions.act_window",
        }


class WizardHrPayslipNewsLine(models.TransientModel):
    """
    Salary Rule detail
    """

    _name = "wizard.hr.payslip.news.line"
    _description = __doc__

    wiz_id = fields.Many2one("wizard.hr.payslip.news", string=_("Wizard"))
    name = fields.Char(_("Reason"), required=True)
    rule_id = fields.Many2one(
        "hr.salary.rule",
        string=_("Salary Rule"),
        required=True,
        domain=[("allowed_in_news", "=", True)],
    )

