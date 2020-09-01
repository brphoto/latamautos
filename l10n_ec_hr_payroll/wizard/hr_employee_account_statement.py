#!/usr/bin/env python
# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from datetime import datetime


class HrEmployeeAccountStatement(models.TransientModel):
    _name = "hr.employee.statement"

    date_from = fields.Date(_("Date From"))
    date_to = fields.Date(_("Date To"), default=datetime.now().strftime('%Y-%m-01'),
                       )
    type = fields.Selection(
        [("all", _("All")), ("news", _("News")), ("loans", _("Loans")), ("cargas", _("Cargas Familiares"))],
        string=_("Type"),
        default="all",
    )
    option = fields.Selection(
        [
            ("all", _("All")),
            ("employees", _("Employees")),
            ("departments", _("Departments")),
        ],
        string=_("Option"),
        default="all",
    )
    employee_ids = fields.Many2many("hr.employee", string=_("Employee"))
    department_ids = fields.Many2many("hr.department", string=_("Department"))

    @api.multi
    def print_statement_pdf(self):
        if self.option == "departments" and not self.department_ids:
            raise ValidationError(_("Please select a department, to continue!"))
        if self.option == "employees" and not self.employee_ids.with_context(
            show_unemployed=True
        ):
            raise ValidationError(_("Please select a employee, to continue!"))
        #return self.env["report"].get_action(
            #self, "l10n_ec_hr_payroll.hr_employee_statement")7
        return self.env.ref("l10n_ec_hr_payroll.action_report_hr_employee_staement").report_action(self)

    #@api.multi
    #def print_statement_xlsx(self):
     #   if self.option == "departments" and not self.department_ids:
      #      raise ValidationError(_("Please select a department, to continue!"))
       # if self.option == "employees" and not self.employee_ids.with_context(
        #    show_unemployed=True
        #):
         #   raise ValidationError(_("Please select a employee, to continue!"))
        #data = self.read()[0]
        #return {
         #   "type": "ir.actions.report.xml",
          #  "report_name": "hr_employee_statement_xlsx.xlsx",
           # "datas": data,
        #}

    @api.multi
    def get_statement(self):
        news_domain = ""
        loan_domain = ""
        if self.date_from:
            news_domain += " AND date::DATE >= '{}'".format(self.date_from)
            loan_domain += " AND approved_date::DATE >= '{}'".format(self.date_from)
        news_domain += " AND date::DATE <= '{}'".format(self.date_to)
        loan_domain += " AND application_date::DATE <= '{}'".format(self.date_to)
        employee_ids = None
        if self.option == "departments" and self.department_ids:
            department_ids = (
                self.department_ids.browse(self.department_ids.mapped("id"))
                ._get_subdepartmets()
                .ids
            )
            employee_ids = self.employee_ids.with_context(show_unemployed=True).search(
                [("department_id", "in", department_ids)]
            )
            if not employee_ids:
                raise ValidationError(
                    _(
                        "There are no payment roles generated for the {} department!".format(
                            self.department_ids.mapped("name")
                        )
                    )
                )
        elif self.option == "employees" and self.employee_ids:
            employee_ids = self.employee_ids.with_context(show_unemployed=True)
        else:
            employee_ids = self.employee_ids.with_context(show_unemployed=True).search(
                []
            )
        self.env.cr.execute(
            """
            SELECT
              he.id,
              he.identification_id AS vat,
              he.name,
              hc.date_start,
              hc.date_end,
              hd.name AS department,
              hj.name AS job
            FROM
              hr_employee he
              JOIN hr_contract hc ON hc.employee_id = he.id
              JOIN hr_department hd ON hc.department_id = hd.id
              JOIN hr_job hj ON hc.job_id = hj.id
            WHERE
              he.id IN ({}) ORDER BY he.name""".format(
                ",".join(map(str, employee_ids.ids))
            )
        )
        emp_data = self.env.cr.dictfetchall()
        res = []
        result = []
        vals = {}
        if emp_data:
            for emp in emp_data:
                vals = {
                    "id": emp.get("id", False),
                    "vat": emp.get("vat", False),
                    "name": emp.get("name", False),
                    "date_start": emp.get("date_start", False),
                    "date_end": emp.get("date_end", False),
                    "department": emp.get("department", False),
                    "job": emp.get("job", False),
                }
                if self.type in ["loans", "all"]:
                    self.env.cr.execute(
                        """
                        SELECT
                          pl.id,
                          CONCAT(pl.name, ' [', sr.name, ']') AS name,
                          pl.number,
                          pl.application_date,
                          pl.approved_date,
                          pl.pay_from,
                          pl.amount,
                          pl.pending_amount,
                          pl.dues,
                          CASE
                            WHEN pl.state::text = 'paid'::text THEN 'PAGADO'::text
                            WHEN pl.state::text = 'draft'::text THEN 'BORRADOR'::text
                            WHEN pl.state::text = 'approved'::text THEN 'APROBADO'::text
                            WHEN pl.state::text = 'cancel'::text THEN 'RECHAZADO'::text
                          ELSE NULL::text
                          END AS state
                        FROM hr_payslip_loans pl JOIN hr_salary_rule sr ON pl.rule_id = sr.id
                        WHERE employee_id = {} {} ORDER BY pay_from""".format(
                            emp.get("id", False), loan_domain
                        )
                    )
                    loan_data = self.env.cr.dictfetchall()
                    if loan_data:
                        loans = []
                        for loan in loan_data:
                            self.env.cr.execute(
                                """
                                SELECT
                                  pn.quantity,
                                  pn.date AS date,
                                  pn.amount,
                                  CASE
                                    WHEN pn.state::text = 'done'::text THEN 'REALIZADO'::text
                                    WHEN pn.state::text = 'draft'::text THEN 'BORRADOR'::text
                                    WHEN pn.state::text = 'approved'::text THEN 'APROBADO'::text
                                    WHEN pn.state::text = 'cancel'::text THEN 'RECHAZADO'::text
                                  ELSE NULL::text
                                  END AS state
                                FROM
                                  hr_payslip_news pn JOIN hr_salary_rule sr ON pn.rule_id = sr.id
                                WHERE loan_id = {} ORDER BY date""".format(
                                    loan.get("id", False)
                                )
                            )
                            line = self.env.cr.dictfetchall()
                            loans.append(
                                {
                                    "name": loan.get("name", False),
                                    "number": loan.get("number", False),
                                    "application_date": loan.get(
                                        "application_date", False
                                    ),
                                    "approved_date": loan.get("approved_date", False),
                                    "pay_from": loan.get("pay_from", False),
                                    "state": loan.get("state", False),
                                    "amount": loan.get("amount", False),
                                    "pending_amount": loan.get("pending_amount", False),
                                    "dues": loan.get("dues", False),
                                    "lines": line,
                                }
                            )
                        vals["loans"] = loans
                if self.type in ["news", "all"]:
                    self.env.cr.execute(
                        """
                        SELECT
                          pn.name AS name,
                          sr.name AS rule,
                          pn.date AS date,
                          pn.amount,
                          CASE
                            WHEN pn.state::text = 'done'::text THEN 'REALIZADO'::text
                            WHEN pn.state::text = 'draft'::text THEN 'BORRADOR'::text
                            WHEN pn.state::text = 'approved'::text THEN 'APROBADO'::text
                            WHEN pn.state::text = 'cancel'::text THEN 'RECHAZADO'::text
                          ELSE NULL::text
                          END AS state
                        FROM
                          hr_payslip_news pn JOIN hr_salary_rule sr ON pn.rule_id = sr.id
                        WHERE employee_id = {} {} AND loan_id IS NULL ORDER BY date""".format(
                            emp.get("id", False), news_domain
                        )
                    )
                    news_data = self.env.cr.dictfetchall()
                    if news_data:
                        vals["news"] = []
                        for n in news_data:
                            new = {
                                "name": n.get("name", False),
                                "date": n.get("date", False),
                                "rule": n.get("rule", False),
                                "amount": "{:.2f}".format(n.get("amount", False)),
                                "state": n.get("state", False),
                            }
                            vals["news"].append(new)
                
                if self.type in ["cargas", "all"]:
                    self.env.cr.execute(
                        """
                        SELECT COUNT(hf.id)               
                        FROM
                          hr_family hf              
                        WHERE hf.employee_id = {}""".format(
                            emp.get("id", False), news_domain
                        )
                    )
                    family_data = self.env.cr.dictfetchall()
                    if family_data:
                        vals["cargas"] = []
                        for n in family_data:
                            new = {
                                "cargas": n.get("count", False),                               
                            }
                            vals["cargas"].append(new)
                            
                keys = vals.keys()

                if "loans" in keys or "news" in keys or "cargas" in keys:
                    res.append(vals)
                
        return res
