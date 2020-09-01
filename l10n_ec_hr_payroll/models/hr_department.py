# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class HrDepartment(models.Model):
    """
    This module adds the accounting information for each salary item,
    depending on the department assigned to the employee
    """

    _inherit = "hr.department"

    @api.multi
    def _get_subdepartmets(self):
        return self.search([("id", "child_of", self.ids)])

    @api.multi
    def call_wizard(self):
        wizard_form = self.env.ref(
            "l10n_ec_hr_payroll.wizard_hr_salary_rule_map_form", False
        )
        res_obj = self.env["wizard.hr.salary.rule.map"]
        line_obj = self.env["wizard.hr.salary.rule.map.line"]
        vals = {"department_id": self.id}
        res_id = res_obj.create(vals)
        if self.salaryrule_map_ids:
            rule_ids = [
                x.mapped("salary_rule_id").mapped("id") for x in self.salaryrule_map_ids
            ]
            if rule_ids:
                res_id.write({"rule_ids": rule_ids})
            for rule in self.salaryrule_map_ids:
                line_obj.create(
                    {
                        "salary_rule_id": rule.salary_rule_id.id,
                        "wiz_id": res_id.id,
                        "account_credit": rule.account_credit.id or False,
                        "account_debit": rule.account_debit.id or False,
                        "analytic_account_id": rule.analytic_account_id.id or False,
                        "account_tax_id": rule.account_tax_id.id or False,
                        "partner_id": rule.partner_id.id or False,
                    }
                )
        return {
            "name": _("HR Salary Rule Map"),
            "type": "ir.actions.act_window",
            "res_model": "wizard.hr.salary.rule.map",
            "res_id": res_id.id,
            "view_id": wizard_form.id,
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
        }

    @api.multi
    @api.depends("parent_id", "name")
    def _get_display_name(self):
        for row in self:
            row.display_name = row.complete_name

    salaryrule_map_ids = fields.One2many(
        "hr.department.salaryrule.map", "department_id", string=_("Salary Rules")
    )
    display_name = fields.Char(_("Display Name"), compute=_get_display_name, store=True)

    @api.multi
    def unlink(self):
        for row in self:
            if row.mapped("salaryrule_map_ids"):
                row.salaryrule_map_ids.unlink()
        return super(HrDepartment, self).unlink()

    @api.one
    def name_get(self):
        name = self.name
        if self.parent_id:
            name = "%s/%s" % (self.parent_id.name_get()[0][1], name)
        return (self.id, name)


class HrDepartmentSalaryruleMap(models.Model):
    """
    This module contains the accounting detail of the salary rules
    by department
    """

    _name = "hr.department.salaryrule.map"
    _description = __doc__
    _order = "sequence"

    department_id = fields.Many2one("hr.department", string=_("Department"))
    salary_rule_id = fields.Many2one("hr.salary.rule", string=_("Salary Rule"))
    sequence = fields.Integer(related="salary_rule_id.sequence", store=True)
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string=_("Analytic Account"),
    )
    account_tax_id = fields.Many2one("account.tax", string=_("Tax"))
    account_debit = fields.Many2one(
        "account.account",
        string=_("Debit Account"),
        domain=[("deprecated", "=", False)],
    )
    account_credit = fields.Many2one(
        "account.account",
        string=_("Credit Account"),
        domain=[("deprecated", "=", False)],
    )
    partner_id = fields.Many2one("res.partner", _("Contribution Register Partner"))

    _sql_constraints = [
        (
            "rule_uniq",
            "unique(department_id, salary_rule_id)",
            "You can only map a salary rule by department!",
        )
    ]
