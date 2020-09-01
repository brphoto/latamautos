# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2015  ADHOC SA  (http://www.adhoc.com.ar)
#    All Rights Reserved.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name': 'Invoicing Session',
    'version': '12.0.1.0.0',
    'category': 'Accounting',
    'author': 'FÁBRICA DE SOFTWARE LIBRE',
    'website': 'fslibre.com',

    'images': [
    ],
    'depends': [
        'account',
        'account_check_printing',
        'bi_account',
        'base_report',
        'l10n_ec_sri',
        # 'account_check_deposit',
    ],
    'data': [
        'views/res_users.xml',
        'views/account_journal.xml',
        'views/account_payment.xml', # before account_invoice.xml
        'views/account_invoice.xml',
        # 'views/res_users.xml',
        'views/report_account_invoice.xml',
        'reports/bi_invoice_report_views.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
    ],
    'test': [
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
