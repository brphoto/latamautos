# -*- coding: utf-8 -*-
####################################################
# Parte del Proyecto LibreGOB: http://libregob.org #
# Licencia AGPL-v3                                 #
####################################################

from odoo import models, fields, api, _


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.multi
    def remove_move_reconcile(self):
        """ Undo a reconciliation """
        if not self:
            return True

        super(AccountMoveLine, self).remove_move_reconcile()
        move_ids = self.mapped('move_id')
        if any(
            line.reconciled and line.account_id.advance
            for line in move_ids.mapped('line_ids')
        ):
            lines = move_ids.mapped('line_ids').filtered(lambda x: x.reconciled)
            for l in lines:
                l.remove_move_reconcile()

            aml = move_ids.mapped('line_ids')
            return_moves = move_ids.reverse_moves(fields.Date.today(), move_ids.journal_id[0] or False)
            return_move_ids = self.env['account.move'].browse(return_moves)
            return_aml = return_move_ids.mapped('line_ids')

            for account in (aml | return_aml).mapped('account_id'):
                account_aml = aml.filtered(
                    lambda x: x.account_id == account
                )
                account_return_aml = return_aml.filtered(
                    lambda x: x.account_id == account
                )
                (account_aml | account_return_aml).reconcile()

