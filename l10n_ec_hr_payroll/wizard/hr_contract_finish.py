#!/usr/bin/env python
# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class HrContractFinish(models.TransientModel):
    _name = "hr.contract.finish"

    contract_id = fields.Many2one(
        "hr.contract",
        string="Contract",
        default=lambda self: self._context.get("active_id"),
    )
    reason_id = fields.Many2one("hr.contract.finish.reason", string="Finish Reason")
    employee = fields.Boolean(string="Archive Employee")
    date = fields.Date("Finish Date")

    @api.multi
    def close(self):
        if self.contract_id.employee_id.active:
            self.contract_id.employee_id.update({"status": "inactive"})
        self.contract_id.update(
            {"reason_id": self.reason_id.id, "date_end": self.date, "state": "close"}
        )
