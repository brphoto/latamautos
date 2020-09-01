#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime as dt

from odoo.addons.report_xlsx.report.report_xlsx import ReportXlsxAbstract
from odoo.tools.translate import _

slip_state = {
    "draft": "BORRADOR",
    "verify": "ESPERANDO",
    "done": "REALIZADO",
    "cancel": "RECHAZADO",
}

payment_type = {"transfer": "TRANSFERENCIA", "check": "CHEQUE"}


class HrPayslipRunXlsx(ReportXlsxAbstract):
    def date_format(self, date):
        res = dt.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y")
        return res

    def get_worked_days(self, slip):
        return (
            sum(
                [
                    i.number_of_days
                    for i in slip.worked_days_line_ids
                    if i.code == "WORK100"
                ]
            )
            or 0.0
        )

    def get_line(self, slip, code):
        return float(sum([i.amount for i in slip.line_ids if i.code in code]) or 0.0)

    def get_overtime(self, slip):
        res = {
            "025_qty": 0.0,
            "050_qty": 0.0,
            "100_qty": 0.0,
            "025_amount": 0.0,
            "050_amount": 0.0,
            "100_amount": 0.0,
        }
        for i in slip.input_line_ids:
            if i.code == "HE025":
                res["025_qty"] = i.quantity
                res["025_amount"] = i.amount
            if i.code == "HE050":
                res["050_qty"] = i.quantity
                res["050_amount"] = i.amount
            if i.code == "HE100":
                res["100_qty"] = i.quantity
                res["100_amount"] = i.amount
        return res

    def get_biweekly_data(self, sheet, workbook, i, run):
        float_format = workbook.add_format({"align": "right", "num_format": "#,##0.00"})
        for slip in run.slip_ids:
            sheet.write(i, 0, slip.number or "")
            sheet.write(i, 1, slip_state[slip.state] or "")
            sheet.write(i, 2, slip.employee_id.code or "")
            sheet.write(
                i,
                3,
                slip.employee_id.identification_id
                or slip.employee_id.passport_id
                or "",
            )
            sheet.write(i, 4, slip.employee_id.name or "")
            sheet.write(i, 5, slip.contract_id.type_id.name or "")
            sheet.write(i, 6, self.date_format(slip.contract_id.date_start) or "")
            sheet.write(i, 7, self.date_format(slip.date_from) or "")
            sheet.write(i, 8, self.date_format(slip.date_to) or "")
            sheet.write(i, 9, slip.employee_id.department_id.complete_name or "")
            # TODO Crear Reglas Salariales para Pagar Proviciones 13ro y 14to
            sheet.write(i, 10, self.get_line(slip, ["DTACUM"]) or 0.0, float_format)
            sheet.write(i, 11, self.get_line(slip, ["DCACUM"]) or 0.0, float_format)
            sheet.write(i, 12, self.get_line(slip, ["PTU"]) or 0.0, float_format)
            sheet.write(i, 13, self.get_line(slip, ["FRPAG"]) or 0.0, float_format)
            sheet.write(i, 14, self.get_line(slip, ["ALWQ"]) or 0.0, float_format)
            sheet.write(i, 15, self.get_line(slip, ["NET"]) or 0.0, float_format)
            sheet.write(i, 16, payment_type[slip.payment_type])
            i += 1

    def get_monthly_data(self, sheet, workbook, i, run):
        days_format = workbook.add_format({"align": "right", "num_format": "00"})
        float_format = workbook.add_format({"align": "right", "num_format": "#,##0.00"})
        for slip in run.slip_ids:
            sheet.write(i, 0, slip.number or "")
            sheet.write(i, 1, slip_state[slip.state] or "")
            sheet.write(i, 2, slip.employee_id.code or "")
            sheet.write(
                i,
                3,
                slip.employee_id.identification_id
                or slip.employee_id.passport_id
                or "",
            )
            sheet.write(i, 4, slip.employee_id.name or "")
            sheet.write(i, 5, slip.contract_id.type_id.name or "")
            sheet.write(i, 6, self.date_format(slip.contract_id.date_start) or "")
            sheet.write(i, 7, self.date_format(slip.date_from) or "")
            sheet.write(i, 8, self.date_format(slip.date_to) or "")
            sheet.write(i, 9, slip.employee_id.department_id.complete_name or "")
            sheet.write(i, 10, slip.contract_id.wage or "", float_format)
            sheet.write(i, 11, self.get_worked_days(slip) or "", days_format)
            sheet.write(i, 12, self.get_line(slip, ["BASE"]) or "", float_format)
            overtime = self.get_overtime(slip)
            sheet.write(i, 13, overtime["025_qty"] or 0.0, float_format)
            sheet.write(i, 14, overtime["050_qty"] or 0.0, float_format)
            sheet.write(i, 15, overtime["100_qty"] or 0.0, float_format)
            sheet.write(i, 16, overtime["025_amount"] or 0.0, float_format)
            sheet.write(i, 17, overtime["050_amount"] or 0.0, float_format)
            sheet.write(i, 18, overtime["100_amount"] or 0.0, float_format)
            sheet.write(i, 19, self.get_line(slip, ["COMI"]) or 0.0, float_format)
            sheet.write(i, 20, self.get_line(slip, ["13PAG"]) or 0.0, float_format)
            sheet.write(i, 21, self.get_line(slip, ["14PAG"]) or 0.0, float_format)
            row = i + 1
            sheet.write_array_formula(
                "W{row}".format(row=row),
                "=SUM(M{row},Q{row}:V{row})".format(row=row),
                float_format,
                0,
            )
            sheet.write_array_formula(
                "X{row}".format(row=row),
                "=SUM(M{row},Q{row}:T{row})".format(row=row),
                float_format,
                0,
            )
            sheet.write(i, 24, self.get_line(slip, ["RJCNJ"]) or 0.0, float_format)
            sheet.write(i, 25, self.get_line(slip, ["IESSPER"]) or 0.0, float_format)
            sheet.write(
                i, 26, self.get_line(slip, ["DED75", "DED66"]) or 0.0, float_format
            )
            sheet.write(
                i,
                27,
                self.get_line(slip, ["PRIESS", "QUIRO", "HIPO"]) or 0.0,
                float_format,
            )
            sheet.write(i, 28, self.get_line(slip, ["DEDQ"]) or 0.0, float_format)
            sheet.write(i, 29, self.get_line(slip, ["LOAN"]) or 0.0, float_format)
            sheet.write(i, 30, self.get_line(slip, ["DEDF"]) or 0.0, float_format)
            sheet.write(
                i, 31, self.get_line(slip, ["DESC", "DED"]) or 0.0, float_format
            )
            sheet.write(i, 32, self.get_line(slip, ["DEDIR"]) or 0.0, float_format)
            sheet.write_array_formula(
                "AH{row}".format(row=row),
                "=SUM(Y{row}:AG{row})".format(row=row),
                float_format,
                0,
            )
            sheet.write(i, 34, self.get_line(slip, ["NET"]) or 0.0, float_format)
            sheet.write(i, 35, payment_type[slip.payment_type])
            sheet.write(i, 36, self.get_line(slip, ["13PROV"]) or 0.0, float_format)
            sheet.write(i, 37, self.get_line(slip, ["14PROV"]) or 0.0, float_format)
            sheet.write(i, 38, self.get_line(slip, ["VAC"]) or 0.0, float_format)
            sheet.write_array_formula(
                "AN{row}".format(row=row),
                '=DATEDIF(G{row},I{row},"y")&" años "&DATEDIF(G{row},I{row},"ym")&" meses "&DATEDIF(G{row},I{row},"md")&" dias"'.format(
                    row=row
                ),
                float_format,
                0,
            )
            sheet.write(i, 40, self.get_line(slip, ["FRPROV"]) or 0.0, float_format)
            sheet.write(i, 41, self.get_line(slip, ["IESSPATRO"]) or 0.0, float_format)
            i += 1

    def generate_xlsx_report(self, workbook, data, objects):
        workbook.set_properties(
            {"comments": "Created with Python and XlsxWriter from Odoo 9.0"}
        )
        sheet = workbook.add_worksheet(_("Payslip Run"))
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.set_zoom(70)
        sheet.freeze_panes(1, 9)
        header_style = workbook.add_format({"bold": True, "bottom": 1})
        payslip_header = [
            _("REF"),
            _("ESTADO"),
            _("CODIGO"),
            _("IDENTIFICACION"),
            _("EMPLEADO"),
            _("CONTRATO"),
            _("FECHA INGRESO"),
            _("ROL DESDE"),
            _("ROL HASTA"),
            _("DEPARTAMENTO"),
        ]
        monthly_header = [
            _("SUELDO"),
            _("DIAS TRABAJADOS"),
            _("SALARIO"),
            _("HORAS 25%"),
            _("HORAS 50%"),
            _("HORAS 100%"),
            _("TOTAL HORAS 25%"),
            _("TOTAL HORAS 50%"),
            _("TOTAL HORAS 100%"),
            _("COMISIONES"),
            _("DECIMO TERCERO"),
            _("DECIMO CUARTO"),
            _("TOTAL INGRESOS"),
            _("BASE IESS"),
            _("RETENCION JUDICIAL"),
            _("APORTE PERSONAL IESS"),
            _("SUBSIDIOS"),
            _("PRESTAMOS IESS"),
            _("ANTICIPO QUINCENA"),
            _("PRESTAMOS/AVANCES"),
            _("FACTURAS"),
            _("OTROS DESCUENTOS"),
            _("IMPUESTO A LA RENTA"),
            _("TOTAL DESCUENTOS"),
            _("NETO A RECIBIR"),
            _("TIPO DE PAGO"),
            _("PROVISION DECIMO TERCERO"),
            _("PROVISION DECIMO CUARTO"),
            _("PROVISION VACACIONES"),
            _("DERECHO FONDOS DE REVERVA"),
            _("PROVISION FONDOS DE REVERVA"),
            _("APORTE PATRONAL IESS"),
        ]
        biweekly_header = [
            _("DECIMO TERCERO"),
            _("DECIMO CUARTO"),
            _("PARTICIPACION UTILIDADES"),
            _("FONDOS DE RESERVA"),
            _("QUINCENA"),
            _("NETO A RECIBIR"),
            _("TIPO DE PAGO"),
        ]
        i = 1
        if objects.run_id.payroll_type.name == "Mensual":
            payslip_header += monthly_header
            sheet.autofilter("A1:AO1")
            self.get_monthly_data(sheet, workbook, i, objects.run_id)
        if objects.run_id.payroll_type.name == "Quincenal":
            payslip_header += biweekly_header
            sheet.autofilter("A1:P1")
            self.get_biweekly_data(sheet, workbook, i, objects.run_id)
        sheet.write_row(0, 0, payslip_header, header_style)


HrPayslipRunXlsx("report.hr_payslip_report_xls", "wizard.hr.payroll.print")
