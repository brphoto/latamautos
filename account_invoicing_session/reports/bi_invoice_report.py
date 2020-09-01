# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

import logging
_logger = logging.getLogger(__name__)


INVOICE_TYPES = {
    'in_invoice': _('Purchase invoice'),
    'out_invoice': _('Sale invoice'),
    'in_refund': _('Purchase refund'),
    'out_refund': _('Sale refund'),
}

INVOICE_STATES = {
    'draft': _('Draft'),
    'open': _('Open'),
    'paid': _('Paid'),
    'cancel': _('Cancelled'),
}


class BiInvoiceReport(models.TransientModel):
    _inherit = 'bi.invoice.report'

    session_ids = fields.Many2many(
        'account.invoicing.session',
        'session_invoice_rel',
        'invoice_ids',
        'session_ids',
        string='Sessions',
    )

    type = fields.Selection(selection_add=[("session", "Invoicing session")])
    group_by = fields.Selection(selection_add=[("session", "Invoicing session")])

    def get_session_vals(self, i):
        # try:
        #     if i.state == 'open':
        #         state = 'ABIERTA'
        #     elif i.state == 'paid':
        #         state = "PAGADA"
        # except:
        #     state = i.state

        sign = i.type in ['in_refund', 'out_refund'] and -1 or 1
        payments = ""
        payment_dates = ""
        payment_moves = ""
        if i.payment_move_line_ids:
            payments = ', '.join([p.name for p in i.payment_move_line_ids.mapped('payment_id')])
            payment_dates = ', '.join([p.payment_date for p in i.payment_move_line_ids.mapped('payment_id')])
            payment_moves = ', '.join([m.name for m in i.payment_move_line_ids.mapped('move_id')])

        session = i.invoicing_session_ids and i.invoicing_session_ids[0] or False

        total = i.total + i.no_declarado
        retencion = 0.0 if i.secretencion1 else i.total_retenciones
        vals = [
            session and session.name or "",
            session and session.date_from or "",
            session and session.date_to or "",
            session and session.state or "",
            i.comprobante_id.name,
            i.number,
            i.partner_id.name,
            i.get_sri_secuencial_completo_factura(),
            i.date_invoice,
            total * sign,
            i.total_retenciones * sign,
            (i.residual + retencion) * sign,
            payments,
            payment_dates,
            payment_moves,
            i.state,
        ]
        return vals

    def get_session_header(self):
        return [
            [
                (self.env.user.company_id.name, 'Title'),
            ],
            [
                ('REPORTE DE FACTURAS POR SESIÓN', 'Title'),
            ],
            [
                ('DESDE:', 'Headline 1'),
                '{}'.format(str(self.date_from and self.date_from or '')),
                '',
                ('HASTA:', 'Headline 1'),
                '{}'.format(str(self.date_to and self.date_to or ''))
            ],
            [
                (_(u'SESIÓN'), 'Headline 2'),
                (_(u'APERTURA'), 'Headline 2'),
                (_(u'CIERRE'), 'Headline 2'),
                (_(u'ESTADO SESIÓN'), 'Headline 2'),
                (_(u'COMPROBANTE'), 'Headline 2'),
                (_(u'FACTURA'), 'Headline 2'),
                (_(u'CLIENTE'), 'Headline 2'),
                (_(u'SECUENCIAL'), 'Headline 2'),
                (_(u'FECHA EMISIÓN'), 'Headline 2'),
                (_(u'TOTAL FACTURA'), 'Headline 2'),
                (_(u'VALOR RETENCIÓN'), 'Headline 2'),
                (_(u'VALOR PENDIENTE'), 'Headline 2'),
                (_(u'PAGOS'), 'Headline 2'),
                (_(u'FECHAS DE PAGO'), 'Headline 2'),
                (_(u'ASIENTOS DE CIERRE'), 'Headline 2'),
                (_(u'ESTADO FACTURA'), 'Headline 2'),
            ]
        ]

    def get_session_report_sheet(self, sheetname, rows, inv, header=[]):
        for i in inv:
            vals = self.get_session_vals(i)
            rows.append(vals)
        return {
            'name': sheetname,
            'rows': rows,
            'header': header,
        }

    @api.multi
    def get_report_data(self):
        if not self.type == 'session':
            return super(BiInvoiceReport, self).get_report_data()

        inv_obj = self.env['account.invoice']

        report_filter = []
        types = []

        if self.out_invoice:
            types.append('out_invoice')
        if self.in_invoice:
            types.append('in_invoice')
        if self.out_refund:
            types.append('out_refund')
        if self.in_refund:
            types.append('in_refund')

        report_filter.append(('type', 'in', types))

        if self.partner_ids:
            report_filter.append(('partner_id', 'in', self.partner_ids.ids))
        if self.date_from:
            report_filter.append(('date_invoice', '>=', self.date_from))
        if self.date_to:
            report_filter.append(('date_invoice', '<=', self.date_to))
        report_filter.append(('state', 'not in', ['draft', 'cancel']))
        inv = inv_obj.search(report_filter)

        if not self.local:
            inv = inv.filtered(lambda x: x.partner_id.country_id != self.env.user.companty_id.country_id)
        if not self.foreign:
            inv = inv.filtered(lambda x: x.partner_id.country_id == self.env.user.companty_id.country_id)

        if self.session_ids:
            inv = inv.filtered(lambda x: any(s in self.session_ids for s in x.invoicing_session_ids))

        sheets = []
        filename = 'reporte_de_sesiones.xlsx'
        sheetname = 'Facturas'
        header = self.get_session_header()

        if self.group_by == 'session':
            for s in self.session_ids:
                sheetname = s.name
                rows = []
                s_inv = inv.filtered(lambda x: s in x.session_ids)
                sheet = self.get_session_report_sheet(sheetname, rows, s_inv, header=header)
                sheets.append(sheet)
        else:
            rows = []
            sheet = self.get_session_report_sheet(sheetname, rows, inv, header=header)
            sheets.append(sheet)

        data = {
            'wizard': 'bi.invoice.report',
            'filename': filename,
            'sheets': sheets,
        }

        return data

