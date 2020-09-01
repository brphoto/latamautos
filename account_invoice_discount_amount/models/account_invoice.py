# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    price_discount = fields.Monetary(
        compute='_compute_price_discount',
        string='Price discount',
        readonly=True, store=True, )

    def get_price_without_discounts(self):
        currency = self.invoice_id and self.invoice_id.currency_id or None
        price = self.price_unit
        price_without_discounts=0
        taxes = False
        if self.invoice_line_tax_ids:
            taxes = self.invoice_line_tax_ids.compute_all(
                price, currency, self.quantity, product=self.product_id,
                partner=self.invoice_id.partner_id
            )
            price_without_discounts = taxes['total_excluded'] if taxes else self.quantity * price
        if (
            self.invoice_id.currency_id and
            self.invoice_id.company_id and
            self.invoice_id.currency_id != self.invoice_id.company_id.currency_id
        ):
            price_without_discounts = self.invoice_id.currency_id.with_context(
                date=self.invoice_id.date_invoice).compute(
                    price_without_discounts, self.invoice_id.company_id.currency_id
            )
        return price_without_discounts

    @api.depends('quantity', 'price_subtotal', 'price_unit')
    def _compute_price_discount(self):
        """
        Compute the amounts of the price discount.
        """
        for line in self:
            # diff_cents = (round(line.price_unit, 2) * line.quantity) - \
            #     (line.price_unit * line.quantity)
            price = line.quantity * line.price_unit

            if any(tax.price_include for tax in line.invoice_line_tax_ids):
                price = line.get_price_without_discounts()

            # discount = price - (line.price_subtotal + diff_cents)
            discount = price - line.price_subtotal
            line.update({
                'price_discount': discount,
            })


class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    price_discount = fields.Monetary(
        compute='_compute_price_discount',
        string='Price discount',
        readonly=True, store=True, )

    @api.depends('invoice_line_ids.price_discount')
    def _compute_price_discount(self):
        for record in self:
            record.price_discount = sum(record.invoice_line_ids.mapped('price_discount'))
