#!/usr/bin/env python
# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class WizardHrContractUpdate(models.TransientModel):
    """
    This wizard allows you to update the work order or the salary of an employee,
    either individually or by department
    """

    _name = "wizard.hr.contract.update"
    _description = __doc__

    option = fields.Selection(
        [("wage", _("Wage Update")), ("job", _("Job Update"))],
        string=_("Option"),
        default="wage",
    )
    wage_ids = fields.One2many(
        "wizard.hr.contract.update.wage", "wiz_id", string=_("Update Wage")
    )
    job_ids = fields.One2many(
        "wizard.hr.contract.update.job", "wiz_id", string=_("Update Job")
    )

    @api.multi
    def update_contract(self):
        wage_obj = self.env["hr.contract.wage"]
        job_obj = self.env["hr.contract.job"]
        for row in self:
            if row.option == "wage":
                if row.wage_ids:
                    for w in row.wage_ids:
                        if w.wage <= w.old_wage:
                            raise UserError(
                                _(
                                    "The value of the new salary must be greater than the value of the previous salary"
                                )
                            )
                        old = wage_obj.search(
                            [
                                ("date_to", "<", w.date),
                                ("contract_id", "=", w.contract_id.id),
                            ],
                            limit=1,
                        )
                        if old:
                            date_from = old.date_to
                        else:
                            date_from = w.contract_id.date_start
                        wage_vals = {
                            "contract_id": w.contract_id.id,
                            "date_from": date_from,
                            "date_to": w.date,
                            "date": fields.Datetime.now(),
                            "old_wage": w.old_wage,
                            "wage": w.wage,
                            "name": w.name.upper(),
                        }
                        w.contract_id.write({"wage": w.wage, "basic_wage": False})
                        wage_obj.create(wage_vals)
                else:
                    raise UserError(
                        _(
                            "¡You must select at least one employee to perform the wage update!"
                        )
                    )
            if row.option == "job":
                if row.job_ids:
                    for j in row.job_ids:
                        old = job_obj.search(
                            [
                                ("date_to", "<", j.date),
                                ("contract_id", "=", j.contract_id.id),
                            ],
                            limit=1,
                        )
                        if old:
                            date_from = old.date_to
                        else:
                            date_from = j.contract_id.date_start
                        job_vals = {
                            "contract_id": j.contract_id.id,
                            "date_from": date_from,
                            "date_to": j.date,
                            "date": fields.Datetime.now(),
                            "old_job_id": j.old_job_id.id,
                            "job_id": j.job_id.id,
                            "name": j.name.upper(),
                        }
                        j.employee_id.write({"job_id": j.job_id.id})
                        job_obj.create(job_vals)
                else:
                    raise UserError(
                        _(
                            "You must select at least one employee to perform the job update"
                        )
                    )


class WizardHrContractUpdateWage(models.TransientModel):
    """
    Register salary update to one or more employees
    """

    _name = "wizard.hr.contract.update.wage"
    _description = __doc__

    wiz_id = fields.Many2one("wizard.hr.contract.update", string=_("Wizard"))
    name = fields.Char(_("Reason"))
    employee_id = fields.Many2one("hr.employee", string=_("Employee"))
    contract_id = fields.Many2one("hr.contract", string=_("Contract"))
    old_wage = fields.Float(_("Old Wage"))
    wage = fields.Float(_("Wage"))
    date = fields.Date(_("Update Date"), default=datetime.now().strftime('%Y-%m-%d'))

    @api.onchange("employee_id")
    def onchange_employee_id(self):
        contract_obj = self.env["hr.contract"]
        contract_ids = contract_obj.search(
            [("employee_id", "=", self.employee_id.id), ("state", "!=", "close")]
        )
        if self.employee_id:
            if contract_ids:
                self.contract_id = contract_ids.id
                self.old_wage = contract_ids.wage
            else:
                raise ValidationError(
                    _("The employee %s has no active contract" % self.employee_id.name)
                )


class WizardHrContractUpdateJob(models.TransientModel):
    """
    Register salary update to one or more employees
    """

    _name = "wizard.hr.contract.update.job"
    _description = __doc__

    wiz_id = fields.Many2one("wizard.hr.contract.update", string=_("Wizard"))
    name = fields.Char(_("Reason"))
    employee_id = fields.Many2one("hr.employee", string=_("Employee"))
    contract_id = fields.Many2one("hr.contract", string=_("Contract"))
    old_job_id = fields.Many2one("hr.job", string=_("Old Job"))
    job_id = fields.Many2one("hr.job", string=_("Job"))
    date = fields.Date(_("Update Date"), default=datetime.now().strftime('%Y-%m-%d'))

    @api.onchange("employee_id")
    def onchange_employee_id(self):
        contract_obj = self.env["hr.contract"]
        contract_ids = contract_obj.search(
            [("employee_id", "=", self.employee_id.id), ("state", "!=", "close")]
        )
        if self.employee_id:
            if contract_ids:
                self.contract_id = contract_ids.id
                self.old_job_id = contract_ids.job_id.id
            else:
                raise ValidationError(
                    _("The employee %s has no active contract" % self.employee_id.name)
                )
