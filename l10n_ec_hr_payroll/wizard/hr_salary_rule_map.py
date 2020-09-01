#!/usr/bin/env python
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class WizardHrSalaryRuleMap(models.TransientModel):
    _name = 'wizard.hr.salary.rule.map'
    _description = 'Salary Rule Map'

    @api.one
    @api.depends('department_id')
    def _get_rules(self):
        self.salary_rule_ids = self.department_id.salaryrule_map_ids.mapped(
            'salary_rule_id').mapped('id')

    department_id = fields.Many2one('hr.department', string=_('Department'))
    line_ids = fields.One2many('wizard.hr.salary.rule.map.line',
                               'wiz_id', string=_('Salary Rules'))
    salary_rule_ids = fields.Many2many(
        'hr.salary.rule', compute='_get_rules', string=_('Rules'))

    @api.multi
    def map_rule_ids(self):
        map_obj = self.env['hr.department.salaryrule.map']
        for row in self:
            if row.department_id.mapped('salaryrule_map_ids'):
                row.department_id.salaryrule_map_ids.unlink()
            for rule in row.line_ids:
                map_obj.create({
                    'department_id': row.department_id.id,
                    'salary_rule_id': rule.salary_rule_id.id,
                    'account_credit': rule.account_credit.id or False,
                    'account_debit': rule.account_debit.id or False,
                    'analytic_account_id': rule.analytic_account_id.id or False,
                    'account_tax_id': rule.account_tax_id.id or False,
                    'partner_id': rule.partner_id.id or False,
                })


class WizardHrSalaryRuleMapLine(models.TransientModel):
    _name = 'wizard.hr.salary.rule.map.line'

    @api.onchange('salary_rule_id')
    def _onchnage_rule_id(self):
        rule_ids = self.wiz_id.salary_rule_ids.mapped('id')
        return {'domain': {'salary_rule_id': [('id', 'not in', rule_ids)]}}

    wiz_id = fields.Many2one('wizard.hr.salary.rule.map')
    salary_rule_id = fields.Many2one('hr.salary.rule',
                                     string=_('Salary Rule'),
                                     required=True)
    account_debit = fields.Many2one('account.account',
                                    string=_('Debit Account'),
                                    domain=[('deprecated', '=', False)])
    account_credit = fields.Many2one('account.account',
                                     string=_('Credit Account'),
                                     domain=[('deprecated', '=', False)])

    analytic_account_id = fields.Many2one('account.analytic.account',
                                          string=_('Analytic Account'))

    account_tax_id = fields.Many2one('account.tax', string=_('Tax'))
    partner_id = fields.Many2one(
        'res.partner', _('Contribution Register Partner'))
