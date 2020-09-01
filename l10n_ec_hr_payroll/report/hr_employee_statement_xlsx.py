#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime as dt

from odoo.addons.report_xlsx.report.report_xlsx import ReportXlsxAbstract
from odoo.tools.translate import _


class HrEmployeeStatementXlsx(ReportXlsxAbstract):
    def get_loans(self, sheet, data, st, j, loan_domain):
        self.env.cr.execute(
            """
            SELECT
              pl.id,
              CONCAT(pl.name, ' [', sr.name, ']') AS name,
              pl.number,
              pl.application_date,
              pl.approved_date,
              pl.pay_from,
              pl.amount,
              pl.pending_amount,
              pl.dues,
              CASE
                WHEN pl.state::text = 'paid'::text THEN 'PAGADO'::text
                WHEN pl.state::text = 'draft'::text THEN 'BORRADOR'::text
                WHEN pl.state::text = 'approved'::text THEN 'APROBADO'::text
                WHEN pl.state::text = 'cancel'::text THEN 'RECHAZADO'::text
              ELSE NULL::text
              END AS state
            FROM hr_payslip_loans pl JOIN hr_salary_rule sr ON pl.rule_id = sr.id
            WHERE employee_id = {} {} ORDER BY pay_from
            """.format(
                st.get("id", False), loan_domain
            )
        )
        loans = self.env.cr.dictfetchall()
        for ln in loans:
            sheet.write(j, 0, st.get("vat", False))
            sheet.write(j, 1, st.get("name", False))
            sheet.write(j, 2, st.get("date_start", False))
            sheet.write(j, 3, st.get("date_end", False))
            sheet.write(j, 4, st.get("department", False))
            sheet.write(j, 5, st.get("job", False))
            sheet.write(j, 6, ln.get("name", False))
            sheet.write(j, 7, ln.get("number", False))
            sheet.write(j, 8, ln.get("application_date", False))
            sheet.write(j, 9, ln.get("approved_date", False))
            sheet.write(j, 10, ln.get("pay_from", False))
            sheet.write(j, 11, ln.get("amount", False))
            sheet.write(j, 12, ln.get("pending_amount", False))
            sheet.write(j, 13, ln.get("dues", False))
            sheet.write(j, 14, ln.get("state", False))
            
            sheet.set_column(6, 6, 20)
            sheet.set_column(7, 7, 20)
            sheet.set_column(8, 8, 12)
            sheet.set_column(9, 9, 12)
            sheet.set_column(10, 10, 12)
            sheet.set_column(11, 11, 10)
            sheet.set_column(12, 12, 10)
            sheet.set_column(13, 13, 10)
            sheet.set_column(14, 14, 12)
            j += 1
        return j

    def get_news(self, sheet, data, st, i, news_domain):
        self.env.cr.execute(
            """
            SELECT
              pn.name AS name,
              sr.name AS rule,
              pn.date AS date,
              pn.amount,
              CASE
                WHEN pn.state::text = 'done'::text THEN 'REALIZADO'::text
                WHEN pn.state::text = 'draft'::text THEN 'BORRADOR'::text
                WHEN pn.state::text = 'approved'::text THEN 'APROBADO'::text
                WHEN pn.state::text = 'cancel'::text THEN 'RECHAZADO'::text
              ELSE NULL::text
              END AS state
            FROM
              hr_payslip_news pn JOIN hr_salary_rule sr ON pn.rule_id = sr.id
            WHERE employee_id = {} {} AND loan_id IS NULL ORDER BY date""".format(
                st.get("id", False), news_domain
            )
        )
        news = self.env.cr.dictfetchall()
        for ns in news:
            sheet.write(i, 0, st.get("vat", False))
            sheet.write(i, 1, st.get("name", False))
            sheet.write(i, 2, st.get("date_start", False))
            sheet.write(i, 3, st.get("date_end", False))
            sheet.write(i, 4, st.get("department", False))
            sheet.write(i, 5, st.get("job", False))
            sheet.write(i, 6, ns.get("name", False))
            sheet.write(i, 7, ns.get("rule", False))
            sheet.write(i, 8, ns.get("date", False))
            sheet.write(i, 9, ns.get("amount", False))
            sheet.write(i, 10, ns.get("state", False))

            sheet.set_column(6, 6, 20)
            sheet.set_column(7, 7, 20)
            sheet.set_column(8, 8, 12)
            sheet.set_column(9, 9, 10)
            sheet.set_column(10, 10, 12)
            i += 1
        return i
    
    def get_cargas_familiares(self, sheet, data, st, m, news_domain):
        self.env.cr.execute(
            """
            SELECT COUNT(hf.id)               
            FROM
              hr_family hf              
            WHERE hf.employee_id = {}""".format(
                st.get("id", False), news_domain
            )
        )
        news = self.env.cr.dictfetchall()
        for ns in news:
            sheet.write(m, 0, st.get("vat", False))
            sheet.write(m, 1, st.get("name", False))
            sheet.write(m, 2, st.get("date_start", False))
            sheet.write(m, 3, st.get("date_end", False))
            sheet.write(m, 4, st.get("department", False))
            sheet.write(m, 5, st.get("job", False))
            sheet.write(m, 6, ns.get("count", False))
            
            sheet.set_column(0, 0, 20)
            sheet.set_column(1, 1, 20)
            sheet.set_column(2, 2, 12)
            sheet.set_column(3, 3, 12)
            sheet.set_column(4, 4, 20)
            sheet.set_column(5, 5, 20)
            sheet.set_column(6, 6, 10)
            m += 1
        return m

    def generate_xlsx_report(self, workbook, data, objs):
        workbook.set_properties(
            {"comments": "Created with Python and XlsxWriter from Odoo 9.0"}
        )
        emp = objs.get_statement()
        header_style = workbook.add_format({"bold": True, "bottom": 1})
        base_header = [
            _("IDENTIFICACION"),
            _("EMPLEADO"),
            _("FECHA INGRESO"),
            _("FECHA SALIDA"),
            _("DEPARTAMENTO"),
            _("CARGO"),
        ]
        news_domain = ""
        loan_domain = ""
        if objs.date_from:
            news_domain += " AND date::DATE >= '{}'".format(objs.date_from)
            loan_domain += " AND approved_date::DATE >= '{}'".format(objs.date_from)
        news_domain += " AND date::DATE <= '{}'".format(objs.date_to)
        loan_domain += " AND application_date::DATE <= '{}'".format(objs.date_to)

        if objs.type in ["news", "all"]:
            sheet1 = workbook.add_worksheet(_("News"))
            sheet1.set_landscape()
            sheet1.fit_to_pages(1, 0)
            sheet1.set_zoom(70)
            sheet1.freeze_panes(1, 0)
            news_header = [
                _("DESCRIPCION"),
                _("REGLA SALARIAL"),
                _("FECHA"),
                _("MONTO"),
                _("ESTADO"),
            ]

            sheet1.write_row(0, 0, base_header + news_header, header_style)
            i = 1
            for st in emp:
                sheet1.write(i, 0, st.get("vat", False))
                sheet1.write(i, 1, st.get("name", False))
                sheet1.write(i, 2, st.get("date_start", False))
                sheet1.write(i, 3, st.get("date_end", False))
                sheet1.write(i, 4, st.get("department", False))
                sheet1.write(i, 5, st.get("job", False))
                i = self.get_news(sheet1, data, st, i, news_domain)
                
                sheet1.set_column(0, 0, 20)
                sheet1.set_column(1, 1, 20)
                sheet1.set_column(2, 2, 12)
                sheet1.set_column(3, 3, 12)
                sheet1.set_column(4, 4, 20)
                sheet1.set_column(5, 5, 20)
        
        if objs.type in ["loans", "all"]:
            sheet2 = workbook.add_worksheet(_("Loans"))
            sheet2.set_landscape()
            sheet2.fit_to_pages(1, 0)
            sheet2.set_zoom(70)
            sheet2.freeze_panes(1, 0)
            loans_header = [
                _("DESCRIPCION"),
                _("NUMERO"),
                _("FECHA SOLICITUD"),
                _("FECHA APROVACION"),
                _("PAGAR DESDE"),
                _("MONTO"),
                _("MONTO PENDIENTE"),
                _("CUOTAS"),
                _("ESTADO"),
            ]
            j = 1
            sheet2.write_row(0, 0, base_header + loans_header, header_style)
            for st in emp:
                sheet2.write(j, 0, st.get("vat", False))
                sheet2.write(j, 1, st.get("name", False))
                sheet2.write(j, 2, st.get("date_start", False))
                sheet2.write(j, 3, st.get("date_end", False))
                sheet2.write(j, 4, st.get("department", False))
                sheet2.write(j, 5, st.get("job", False))
                j = self.get_loans(sheet2, data, st, j, loan_domain)
                
                sheet2.set_column(0, 0, 20)
                sheet2.set_column(1, 1, 20)
                sheet2.set_column(2, 2, 12)
                sheet2.set_column(3, 3, 12)
                sheet2.set_column(4, 4, 20)
                sheet2.set_column(5, 5, 20)
        
        
        if objs.type in ["cargas", "all"]:
            sheet3 = workbook.add_worksheet(_("Cargas Familiares"))
            sheet3.set_landscape()
            sheet3.fit_to_pages(1, 0)
            sheet3.set_zoom(70)
            sheet3.freeze_panes(1, 0)
            
            family_header = [
                _("CARGAS FAMILIARES"),
            ]
            
            sheet3.write_row(0, 0, base_header + family_header, header_style)
            k = 1
            
            for st in emp:
                sheet3.write(k, 0, st.get("vat", False))
                sheet3.write(k, 1, st.get("name", False))
                sheet3.write(k, 2, st.get("date_start", False))
                sheet3.write(k, 3, st.get("date_end", False))
                sheet3.write(k, 4, st.get("department", False))
                sheet3.write(k, 5, st.get("job", False))
                k = self.get_cargas_familiares(sheet3, data, st, k, loan_domain)
                
                sheet3.set_column(0, 0, 20)
                sheet3.set_column(1, 1, 20)
                sheet3.set_column(2, 2, 12)
                sheet3.set_column(3, 3, 12)
                sheet3.set_column(4, 4, 20)
                sheet3.set_column(5, 5, 20)


HrEmployeeStatementXlsx(
    "report.hr_employee_statement_xlsx.xlsx", "hr.employee.statement"
)
