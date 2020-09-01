# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import locale
from datetime import datetime

from odoo.osv import osv
from odoo.report import report_sxw


class payslip_report(report_sxw.rml_parse):
    # locale.setlocale(locale.LC_ALL, 'es_EC')

    def __init__(self, cr, uid, name, context):
        super(payslip_report, self).__init__(cr, uid, name, context)
        self.localcontext.update(
            {
                "get_period_name": self.get_period_name,
                "get_news": self.get_news,
                "get_details_by_rule_category": self.get_details_by_rule_category,
                "get_details": self.get_details,
            }
        )
    
    def get_period_name(self, obj):
        res = None
        ds = datetime.strptime(str(obj.date_to), "%Y-%m-%d")
        month = str(ds.strftime("%B"))
        year = str(ds.strftime("%Y"))
        res = "{} {}".format(month, year)
        return res

    def get_details_by_rule_category(self, obj):
        payslip_line = self.pool.get("hr.payslip.line")
        rule_cate_obj = self.pool.get("hr.salary.rule.category")

        def get_recursive_parent(rule_categories):
            if not rule_categories:
                return []
            if rule_categories[0].parent_id:
                rule_categories = rule_categories[0].parent_id | rule_categories
                get_recursive_parent(rule_categories)
            return rule_categories

        res = []
        result = {}
        ids = []

        for id in range(len(obj)):
            ids.append(obj[id].id)
        if ids:
            self.cr.execute(
                """SELECT pl.id, pl.category_id FROM hr_payslip_line as pl \
                LEFT JOIN hr_salary_rule_category AS rc on (pl.category_id = rc.id) \
                WHERE pl.id in %s \
                GROUP BY rc.parent_id, pl.sequence, pl.id, pl.category_id \
                ORDER BY pl.sequence, rc.parent_id""",
                (tuple(ids),),
            )
            for x in self.cr.fetchall():
                result.setdefault(x[1], [])
                result[x[1]].append(x[0])
            for key, value in result.items():
                rule_categories = rule_cate_obj.browse(self.cr, self.uid, [key])
                parents = get_recursive_parent(rule_categories)
                category_total = 0
                for line in payslip_line.browse(self.cr, self.uid, value):
                    category_total += line.total
                level = 0
                for parent in parents:
                    res.append(
                        {
                            "rule_category": parent.name,
                            "name": parent.name,
                            "code": parent.code,
                            "level": level,
                            "total": category_total,
                        }
                    )
                    level += 1
                for line in payslip_line.browse(self.cr, self.uid, value):
                    res.append(
                        {
                            "rule_category": line.name,
                            "name": line.name,
                            "code": line.code,
                            "total": line.total,
                            "level": level,
                        }
                    )
        return res

    def get_news(self, obj):
        
        res = {"loan": "0.00", "he050": "0.00", "he100": "0.00"}
        new_obj = self.pool.get("hr.payslip.news")
        for i in obj.input_line_ids:
            try:
                qty = float(i.quantity)
            except ValueError:
                qty = 0
            if i.code == "HE050":
                res["he050"] = "{:.2f}".format(qty)
            elif i.code == "HE100":
                res["he100"] = "{:.2f}".format(qty)
            elif i.code == "LOAN":
                new_ids = new_obj.search(
                    self.cr, self.uid, [("loan_id", "=", i.new_id.loan_id.id)]
                )
                current = i.quantity.split("/")[0]
                loan = 0.0
                if new_ids:
                    for n in new_obj.browse(self.cr, self.uid, new_ids):
                        if n.quantity.split("/")[0] > current:
                            loan += n.amount
                res["loan"] = "{:.2f}".format(loan)
        return res

    def get_details(self, obj, hr_payslip_id=None):
        payslip_line = self.pool.get("hr.payslip.line")
        hr_payslip_input_pool = self.pool.get("hr.payslip.input")
        res = []
        result = {}
        ids = []
        income_total = 0
        outcome_total = 0
        for id in range(len(obj)):
            ids.append(obj[id].id)
        if ids:
            self.cr.execute(
                """SELECT pl.id, pl.category_id FROM hr_payslip_line as pl \
				LEFT JOIN hr_salary_rule_category AS rc on (pl.category_id = rc.id) \
				LEFT JOIN hr_salary_rule AS sr on (pl.salary_rule_id = sr.id) \
				WHERE pl.id in %s and rc.code in ('BASIC','ALW','INGNOGRAV', 'INGGRAV', 'HE050', 'HE100') \
				GROUP BY rc.parent_id, sr.sequence, pl.id, pl.category_id \
				ORDER BY sr.sequence, rc.parent_id""",
                (tuple(ids),),
            )
            for x in self.cr.fetchall():
                result.setdefault(x[1], [])
                result[x[1]].append(x[0])
            for key, value in result.iteritems():
                for line in payslip_line.browse(self.cr, self.uid, value):
                    tlt = "%.2f" % abs(line.total)
                    detalle = line.name
                    if float(tlt) > 0:
                        res.append(
                            {
                                "detalle": detalle,
                                "ingreso": tlt,
                                "egreso": "",
                                "recibir": "",
                            }
                        )
                    income_total += line.total
            self.cr.execute(
                """SELECT pl.id, pl.category_id FROM hr_payslip_line as pl \
				LEFT JOIN hr_salary_rule_category AS rc on (pl.category_id = rc.id) \
				LEFT JOIN hr_salary_rule AS sr on (pl.salary_rule_id = sr.id) \
				WHERE pl.id in %s and rc.code in ('DED', 'LOAN', 'SUBIESS') \
				GROUP BY rc.parent_id, sr.sequence, pl.id, pl.category_id \
				ORDER BY sr.sequence, rc.parent_id""",
                (tuple(ids),),
            )
            result = {}
            for x in self.cr.fetchall():
                result.setdefault(x[1], [])
                result[x[1]].append(x[0])
            for key, value in result.iteritems():
                for line in payslip_line.browse(self.cr, self.uid, value):
                    tlt = "%.2f" % abs(line.total)
                    detalle = line.name
                    if float(tlt) > 0:
                        res.append(
                            {
                                "detalle": detalle,
                                "ingreso": "",
                                "egreso": tlt,
                                "recibir": "",
                            }
                        )
                        outcome_total += line.total
            res.append(
                {
                    "detalle": "Total",
                    "ingreso": income_total,
                    "egreso": abs(outcome_total),
                    "recibir": (income_total - abs(outcome_total)),
                }
            )
        return res


class wrapped_report_payslip(osv.AbstractModel):
    _name = "report.l10n_ec_hr_payroll.hr_payslip_report"
    _inherit = "report.abstract_report"
    _template = "l10n_ec_hr_payroll.hr_payslip_report"
    _wrapped_report_class = payslip_report


class payslip_batch_report(report_sxw.rml_parse):
    # locale.setlocale(locale.LC_ALL, 'es_EC')

    def __init__(self, cr, uid, name, context):
        super(payslip_batch_report, self).__init__(cr, uid, name, context)
        self.localcontext.update(
            {
                "get_period_name": self.get_period_name,
                "get_news": self.get_news,
                "get_details_by_rule_category": self.get_details_by_rule_category,
                "get_details": self.get_details,
            }
        )

    def get_period_name(self, obj):
        res = None
        ds = datetime.strptime(str(obj.date_to), "%Y-%m-%d")
        month = str(ds.strftime("%B"))
        year = str(ds.strftime("%Y"))
        res = "{} {}".format(month, year)
        return res

    def get_details_by_rule_category(self, obj):
        payslip_line = self.pool.get("hr.payslip.line")
        rule_cate_obj = self.pool.get("hr.salary.rule.category")

        def get_recursive_parent(rule_categories):
            if not rule_categories:
                return []
            if rule_categories[0].parent_id:
                rule_categories = rule_categories[0].parent_id | rule_categories
                get_recursive_parent(rule_categories)
            return rule_categories

        res = []
        result = {}
        ids = []

        for id in range(len(obj)):
            ids.append(obj[id].id)
        if ids:
            self.cr.execute(
                """SELECT pl.id, pl.category_id FROM hr_payslip_line as pl \
                LEFT JOIN hr_salary_rule_category AS rc on (pl.category_id = rc.id) \
                WHERE pl.id in %s \
                GROUP BY rc.parent_id, pl.sequence, pl.id, pl.category_id \
                ORDER BY pl.sequence, rc.parent_id""",
                (tuple(ids),),
            )
            for x in self.cr.fetchall():
                result.setdefault(x[1], [])
                result[x[1]].append(x[0])
            for key, value in result.iteritems():
                rule_categories = rule_cate_obj.browse(self.cr, self.uid, [key])
                parents = get_recursive_parent(rule_categories)
                category_total = 0
                for line in payslip_line.browse(self.cr, self.uid, value):
                    category_total += line.total
                level = 0
                for parent in parents:
                    res.append(
                        {
                            "rule_category": parent.name,
                            "name": parent.name,
                            "code": parent.code,
                            "level": level,
                            "total": category_total,
                        }
                    )
                    level += 1
                for line in payslip_line.browse(self.cr, self.uid, value):
                    res.append(
                        {
                            "rule_category": line.name,
                            "name": line.name,
                            "code": line.code,
                            "total": line.total,
                            "level": level,
                        }
                    )
        return res

    def get_news(self, obj):
        
        res = {"loan": "0.00", "he050": "0.00", "he100": "0.00"}
        new_obj = self.pool.get("hr.payslip.news")
        for i in obj.input_line_ids:
            try:
                qty = float(i.quantity)
            except ValueError:
                qty = 0
            if i.code == "HE050":
                res["he050"] = "{:.2f}".format(qty)
            elif i.code == "HE100":
                res["he100"] = "{:.2f}".format(qty)
            elif i.code == "LOAN":
                new_ids = new_obj.search(
                    self.cr, self.uid, [("loan_id", "=", i.new_id.loan_id.id)]
                )
                current = i.quantity.split("/")[0]
                loan = 0.0
                if new_ids:
                    for n in new_obj.browse(self.cr, self.uid, new_ids):
                        if n.quantity.split("/")[0] > current:
                            loan += n.amount
                res["loan"] = "{:.2f}".format(loan)
        return res
   
    
    def get_details(self, obj, hr_payslip_id=None):
        payslip_line = self.pool.get("hr.payslip.line")
        hr_payslip_input_pool = self.pool.get("hr.payslip.input")
        res = []
        result = {}
        ids = []
        income_total = 0
        outcome_total = 0
        for id in range(len(obj)):
            ids.append(obj[id].id)
        if ids:
            self.cr.execute(
                """SELECT pl.id, pl.category_id FROM hr_payslip_line as pl \
				LEFT JOIN hr_salary_rule_category AS rc on (pl.category_id = rc.id) \
				LEFT JOIN hr_salary_rule AS sr on (pl.salary_rule_id = sr.id) \
				WHERE pl.id in %s and rc.code in ('BASIC','ALW','INGNOGRAV', 'INGGRAV', 'HE050', 'HE100') \
				GROUP BY rc.parent_id, sr.sequence, pl.id, pl.category_id \
				ORDER BY sr.sequence, rc.parent_id""",
                (tuple(ids),),
            )
            for x in self.cr.fetchall():
                result.setdefault(x[1], [])
                result[x[1]].append(x[0])
            for key, value in result.iteritems():
                for line in payslip_line.browse(self.cr, self.uid, value):
                    tlt = "%.2f" % abs(line.total)
                    detalle = line.name
                    if float(tlt) > 0:
                        res.append(
                            {
                                "detalle": detalle,
                                "ingreso": tlt,
                                "egreso": "",
                                "recibir": "",
                            }
                        )
                    income_total += line.total
            self.cr.execute(
                """SELECT pl.id, pl.category_id FROM hr_payslip_line as pl \
				LEFT JOIN hr_salary_rule_category AS rc on (pl.category_id = rc.id) \
				LEFT JOIN hr_salary_rule AS sr on (pl.salary_rule_id = sr.id) \
				WHERE pl.id in %s and rc.code in ('DED', 'LOAN') \
				GROUP BY rc.parent_id, sr.sequence, pl.id, pl.category_id \
				ORDER BY sr.sequence, rc.parent_id""",
                (tuple(ids),),
            )
            result = {}
            for x in self.cr.fetchall():
                result.setdefault(x[1], [])
                result[x[1]].append(x[0])
            for key, value in result.iteritems():
                for line in payslip_line.browse(self.cr, self.uid, value):
                    tlt = "%.2f" % abs(line.total)
                    detalle = line.name
                    if float(tlt) > 0:
                        res.append(
                            {
                                "detalle": detalle,
                                "ingreso": "",
                                "egreso": tlt,
                                "recibir": "",
                            }
                        )
                        outcome_total += line.total
            res.append(
                {
                    "detalle": "Total",
                    "ingreso": income_total,
                    "egreso": abs(outcome_total),
                    "recibir": (income_total - abs(outcome_total)),
                }
            )
        return res
        


class wrapped_report_payslip_batch(osv.AbstractModel):
    _name = "report.l10n_ec_hr_payroll.hr_payslip_report_batch"
    _inherit = "report.abstract_report"
    _template = "l10n_ec_hr_payroll.hr_payslip_report_batch"
    _wrapped_report_class = payslip_batch_report
