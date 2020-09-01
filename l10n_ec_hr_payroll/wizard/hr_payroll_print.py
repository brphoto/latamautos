#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64
from datetime import datetime as dt
from io import StringIO
from io import BytesIO
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WizardHrPayrollPrint(models.TransientModel):
    """
    Wizard to print Payslip Run
    """
    _name = 'wizard.hr.payroll.print'
    _description = __doc__

    @api.multi
    @api.depends('print_option', 'department_ids', 'employee_ids')
    def _compute_slip_ids(self):
        employee_obj = self.env['hr.employee']
        department_obj = self.env['hr.department']
        slip_ids = None
        for row in self:
            if row.print_option == 'department' and row.department_ids:
                department_ids = department_obj.browse(
                    row.department_ids.mapped('id'))._get_subdepartmets().ids
                employee_ids = employee_obj.search(
                    [('department_id', 'in', department_ids)])
                if employee_ids:
                    slip_ids = row.run_id.mapped('slip_ids').filtered(
                        lambda x: x.employee_id in employee_ids)
                else:
                    raise ValidationError(_('There are no payment roles generated for the {} department!'.format(
                        row.department_ids.mapped('name'))))
            elif row.print_option == 'employees' and row.employee_ids:
                slip_ids = row.run_id.mapped('slip_ids').filtered(
                    lambda x: x.employee_id.id in row.mapped('employee_ids').ids)
            else:
                slip_ids = row.run_id.mapped('slip_ids')
            row.slip_ids = slip_ids.sorted(
                key=lambda s: s.employee_id.name).ids
        return True

    run_id = fields.Many2one('hr.payslip.run', string=_(
        'Batch Payslip'), default=lambda x: x._context.get('active_id', False))
    print_option = fields.Selection([('all', _('All')),
                                     ('employees', _('Employees')),
                                     ('department', _('Department'))], string=_('Print Option'), required=True, default='all')
    department_ids = fields.Many2many('hr.department', string=_('Departments'))
    employee_ids = fields.Many2many('hr.employee', string=_('Employees'))
    slip_ids = fields.One2many('hr.payslip', compute=_compute_slip_ids)

    @api.multi
    def print_payslip_pdf(self):
        if self.print_option == 'department' and not self.department_ids:
            raise ValidationError(
                _('Please select a department, to continue!'))
        if self.print_option == 'employees' and not self.employee_ids:
            raise ValidationError(
                _('Please select a employee, to continue!'))
        return self.env.ref("hr_payroll.action_report_payslip").report_action(self.slip_ids)
        #return {'type': 'ir.actions.report','report_name': 'l10n_ec_hr_payroll.hr_payroll.action_report_payslip','report_type':"qweb-pdf",'data': self,
        #}
       # return self.env.ref('l10n_ec_hr_payroll.custom_letter_portrait').report_action(self.slip_ids)
       # return self.env['report'].get_action(self.slip_ids, 'l10n_ec_hr_payroll.hr_payslip_report')
        #return self.env['report'].get_action(self, 'l10n_ec_hr_payroll.hr_payslip_report_batch')

    @api.multi
    def print_payslip_xlsx(self):
        if self.print_option == 'department' and not self.department_ids:
            raise ValidationError(
                _('Please select a department, to continue!'))
        if self.print_option == 'employees' and not self.employee_ids:
            raise ValidationError(
                _('Please select a employee, to continue!'))
        data = self.read()[0]
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'hr_payslip_run.xlsx',
            'datas': data
        }
   
        
    @api.multi
    def print_payslip_txt(self):
        attachment_obj = self.env['ir.attachment']
        template = '{}{:40}{:0<11}{:0>14}{}N\r\n'
        template = '{:0>13};{:0>4};{:0>4};{:0>2};INS;{:0>10};{:.2f};X\r\n'
        for row in self:
            file_data = StringIO()
            #date = dt.strptime("2020-05-25", '%Y-%m-%d')
            #file_name = '{}_{:0>4}{:0>2}.txt'.format(
                #'IESS', date.year, date.month)
            file_name="archivo.txt"
            for slip in row.run_id.slip_ids:
                amount = float(sum([i.amount for i in slip.line_ids if i.code in [
                               'HE025', 'HE050', 'HE100', 'COMI']]) or 0.0)
                if amount > 0:
                    file_data.write(
                        template.format(row.run_id.company_id.vat, 1, date.year, date.month, slip.employee_id.identification_id, amount))
            file_data.seek(0)
            #data = base64.encodestring(file_data.read())
            attachment_id = attachment_obj.search([('name', '=', file_name),
                                                   ('res_model', '=',
                                                    row.run_id._name),
                                                   ('res_id', '=', row.run_id.id)])
            if attachment_id:
                attachment_id.write({
                    'name': file_name,
                    'datas_fname': file_name,
                    'res_model': row.run_id._name,
                    'res_id': row.run_id.id,
                })
            else:
                attachment_obj.create({
                    'name': file_name,
                    'datas_fname': file_name,
                    'res_model': row.run_id._name,
                    'res_id': row.run_id.id,
                    'type': 'binary',
                    'company_id': row.run_id.company_id.id,
                    #'db_datas': data
                })
        return True

