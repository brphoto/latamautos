#!/usr/bin/env python
# -*- coding: utf-8 -*-
import base64
import csv
from datetime import datetime as dt
from io import StringIO

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrPayslipEmployees(models.TransientModel):
    _inherit = "hr.payslip.employees"

    @api.onchange("run_id")
    def onchange_slip_id(self):
        domain = []
        no_ids = []
        ids = []
        payroll_obj = self.env["hr.payslip"]
        date_from = dt.strptime(str(self.run_id.date_start), "%Y-%m-%d")
        date_run = dt.strptime(str(self.run_id.date_end), "%Y-%m-%d")
        if self.run_id.department_id:
            domain.append(
                (
                    "department_id",
                    "in",
                    self.run_id.department_id._get_subdepartmets().ids,
                )
            )
        if self.run_id.slip_ids:
            no_ids += self.run_id.mapped("slip_ids").mapped("employee_id").ids
        res = {}
        employee_obj = self.env["hr.employee"]
        employees = employee_obj.with_context(show_unemployed=True).search([])
        for emp in employees:
            if not emp.contract_id:
                no_ids.append(emp.id)

            if self.run_id.payroll_type.name == "Quincenal":
                date_in = emp.mapped("contract_id").date_start and dt.strptime(str(emp.mapped("contract_id").date_start), "%Y-%m-%d") or False
                if date_in and date_in.month == date_run.month and date_in.year == date_run.year:
                    if int(date_in.day) >= int(11):
                        no_ids.append(emp.id)

            if not payroll_obj.get_contract(emp, date_from, date_run):
                no_ids.append(emp.id)
        if no_ids:
            domain.append(("id", "not in", no_ids))
        ids += employee_obj.with_context(show_unemployed=True).search(domain).ids
        res.update({"domain": {"employee_ids": [("id", "in", ids)]}})
        return res

    run_id = fields.Many2one(
        "hr.payslip.run",
        string="Batch Payslip",
        default=lambda x: x._context.get("active_id", False),
    )
    load_type = fields.Selection(
        [("manual", "Manual"), ("file", "File")],
        string="Load Type",
        required=True,
        default="manual",
    )
    employees_file = fields.Binary(_("Employees File"))
    delimeter = fields.Char("Delimeter", default=",", help='Default delimeter is ","')

    @api.multi
    def compute_sheet(self):
        employee_obj = self.env["hr.employee"]
        payslips = self.env["hr.payslip"]
        [data] = self.read()
        active_id = self.env.context.get("active_id")
        if active_id:
            [run_data] = (
                self.env["hr.payslip.run"]
                .browse(active_id)
                .read(
                    [
                        "date_start",
                        "date_end",
                        "credit_note",
                        "journal_id",
                        "payroll_type",
                    ]
                )
            )
        from_date = run_data.get("date_start")
        to_date = run_data.get("date_end")
        employees = []
        if self.load_type == "manual":
            if not data["employee_ids"]:
                raise UserError(
                    _("You must select employee(s) to generate payslip(s).")
                )
            employees = employee_obj.browse(data["employee_ids"])
        if self.load_type == "file":
            data = base64.b64decode(self.employees_file)
            file_input = StringIO.StringIO(data)
            file_input.seek(0)
            reader_info = []
            if self.delimeter:
                delimeter = str(self.delimeter)
            else:
                delimeter = ","
            reader = csv.reader(file_input, delimiter=delimeter, lineterminator="\r\n")
            try:
                reader_info.extend(reader)
            except Exception:
                raise UserError(_("Not a valid file!"))
            keys = reader_info[0]
            if not isinstance(keys, list) or (
                "identification" not in keys or "passport" not in keys
            ):
                raise UserError(_("Not 'identification' or 'passport' keys found"))
            del reader_info[0]
            for i in range(len(reader_info)):
                field = reader_info[i]
                values = dict(zip(keys, field))
                identification = "{:0>10}".format(int(values["identification"]))
                employee_id = employee_obj.search(
                    [
                        "|",
                        ("identification_id", "=", identification),
                        ("passport_id", "=", values["passport"]),
                    ]
                )
                if not employee_id:
                    employee_id = employee_obj.with_context(
                        show_unemployed=True
                    ).search(
                        [
                            "|",
                            ("identification_id", "=", identification),
                            ("passport_id", "=", values["passport"]),
                        ]
                    )
                employees.append(employee_id)
        for employee in employees:
            slip_data = (
                self.env["hr.payslip"]
                .with_context(payroll_type=run_data.get("payroll_type"))
                .onchange_employee_id(
                    from_date, to_date, employee.id, contract_id=False
                )
            )
            contract_data = {"job_id": False, "wage": 0.0}
            contract_id = slip_data["value"].get("contract_id", False)
            if contract_id:
                contract = self.env['hr.contract'].browse(contract_id)
                contract_data = self.env["hr.payslip"].get_contract_info(
                    contract, from_date, to_date
                )
#            contract = {"id": contract_id.id, "type_id": contract_id.type_id.id}
#             if slip_data["value"].get("contract_id"):
#                 contract_id = self.env["hr.contract"].browse(
#                     [slip_data["value"].get("contract_id")]
#                 )
#                 contract["id"] = contract_id.id
#                 contract["type_id"] = contract_id.type_id.id
            res = {
                "employee_id": employee.id,
                "job_id": contract_data["job_id"],
                "wage": contract_data["wage"],
                "name": slip_data["value"].get("name"),
                "struct_id": slip_data["value"].get("struct_id"),
                "contract_id": contract.id,
                "contract_type": contract.type_id.id,
                "payslip_run_id": active_id,
                "input_line_ids": [
                    (0, 0, x) for x in slip_data["value"].get("input_line_ids")
                ],
                "worked_days_line_ids": [
                    (0, 0, x) for x in slip_data["value"].get("worked_days_line_ids")
                ],
                "date_from": from_date,
                "date_to": to_date,
                "credit_note": run_data.get("credit_note"),
                "company_id": employee.company_id.id,
                "payroll_type": run_data.get("payroll_type")[0],
                "journal_id": run_data.get("journal_id")[0],
            }
            payslips += self.env["hr.payslip"].create(res)
        payslips.compute_sheet()
        return {"type": "ir.actions.act_window_close"}
