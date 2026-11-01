"""CU-008 Exportar Reporte PDF/Excel (RF-008). Ambos formatos se generan en memoria, con los mismos
datos que se ven en pantalla, y se descargan sin dejar archivos en el servidor."""
import io
import re
import unicodedata

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Font, PatternFill
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from gpizza.servicios.reportes import Reporte

OSCURO = colors.HexColor('#1f1b18')
ACENTO = colors.HexColor('#c2410c')


def indicadores(r: Reporte) -> list[tuple[str, str]]:
    """Las mismas tarjetas que la pantalla (boceto 10), como texto."""
    return [
        ('Pedidos totales', str(r.total)),
        ('Pedidos entregados', str(r.entregados)),
        ('Cancelaciones', str(r.cancelados)),
        ('Rechazados', str(r.rechazados)),
        ('Devoluciones', str(r.devoluciones)),
        ('Ingresos (entregados)', f'$ {r.ingresos:,.2f}'),
        ('Ticket promedio', f'$ {r.ticket_promedio:,.2f}'),
        ('Tiempo promedio de entrega', f'{r.minutos_entrega} min' if r.minutos_entrega is not None else '—'),
        ('Pizza más vendida', f'{r.pizza_mas_vendida[0]} ({r.pizza_mas_vendida[1]})' if r.pizza_mas_vendida else '—'),
    ]


def _titulo(sucursal: str, r: Reporte, repartidor: str | None) -> tuple[str, str]:
    filtro = f' · Repartidor: {repartidor}' if repartidor else ''
    return (f'Reporte de desempeño · {sucursal}',
            f'Del {r.filtros.desde:%d/%m/%Y} al {r.filtros.hasta:%d/%m/%Y}{filtro}')


def nombre_archivo(sucursal: str, r: Reporte, extension: str) -> str:
    """'Coyol (matriz)' → 'reporte_coyol_matriz_2026-10-18_2026-11-01.pdf' (sin espacios ni acentos raros)."""
    base = re.sub(r'[^a-z0-9]+', '_', unicodedata.normalize('NFKD', sucursal.lower()).encode('ascii', 'ignore').decode())
    return f'reporte_{base.strip("_")}_{r.filtros.desde}_{r.filtros.hasta}.{extension}'


def pdf(r: Reporte, sucursal: str, repartidor: str | None = None) -> bytes:
    salida = io.BytesIO()
    documento = SimpleDocTemplate(salida, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                                  topMargin=1.5 * cm, bottomMargin=1.5 * cm, title='Reporte de desempeño GPizza')
    estilos = getSampleStyleSheet()
    titulo, subtitulo = _titulo(sucursal, r, repartidor)
    estilo_tabla = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), OSCURO), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cfcac4')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f2ef')]),
        ('FONTSIZE', (0, 0), (-1, -1), 9), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')])

    contenido = [Paragraph(titulo, estilos['Title']), Paragraph(subtitulo, estilos['Normal']), Spacer(1, 0.4 * cm)]
    if r.vacio:
        contenido.append(Paragraph('No hay pedidos en el período seleccionado.', estilos['Normal']))
    else:
        tabla = Table([['Indicador', 'Valor']] + indicadores(r), colWidths=[8 * cm, 8 * cm])
        tabla.setStyle(estilo_tabla)
        contenido += [tabla, Spacer(1, 0.5 * cm), Paragraph('Pedidos por día', estilos['Heading3'])]

        grafica = Drawing(16 * cm, 6 * cm)
        barras = VerticalBarChart()
        barras.x, barras.y, barras.width, barras.height = 1 * cm, 1 * cm, 14.5 * cm, 4.5 * cm
        barras.data = [[n for _, n in r.por_dia]]
        barras.bars[0].fillColor = ACENTO
        barras.valueAxis.valueMin = 0
        barras.categoryAxis.categoryNames = [d.strftime('%d/%m') for d, _ in r.por_dia]
        barras.categoryAxis.labels.fontSize = 7 if len(r.por_dia) <= 31 else 0
        barras.categoryAxis.labels.angle = 45 if len(r.por_dia) > 10 else 0
        barras.categoryAxis.labels.boxAnchor = 'ne' if len(r.por_dia) > 10 else 'n'
        grafica.add(barras)
        contenido += [grafica, Spacer(1, 0.4 * cm), Paragraph('Detalle por repartidor', estilos['Heading3'])]

        filas = [[x['nombre'], x['entregas'], f"{x['minutos']} min" if x['minutos'] is not None else '—', x['devoluciones']]
                 for x in r.por_repartidor] or [['Sin entregas en el período', '', '', '']]
        tabla = Table([['Repartidor', 'Entregas', 'Tiempo prom. en camino', 'Devoluciones']] + filas,
                      colWidths=[6 * cm, 2.5 * cm, 4.5 * cm, 3 * cm])
        tabla.setStyle(estilo_tabla)
        contenido.append(tabla)
    contenido += [Spacer(1, 0.5 * cm), Paragraph('Generado por GPizza · Yungla Pizza S.A. de C.V.', estilos['Italic'])]
    documento.build(contenido)
    return salida.getvalue()


def excel(r: Reporte, sucursal: str, repartidor: str | None = None) -> bytes:
    libro = Workbook()
    negrita = Font(bold=True, color='FFFFFF')
    relleno = PatternFill('solid', fgColor='1F1B18')
    titulo, subtitulo = _titulo(sucursal, r, repartidor)

    def encabezados(hoja, fila, *nombres):
        for columna, nombre in enumerate(nombres, start=1):
            celda = hoja.cell(row=fila, column=columna, value=nombre)
            celda.font, celda.fill = negrita, relleno

    resumen = libro.active
    resumen.title = 'Resumen'
    resumen['A1'], resumen['A2'] = titulo, subtitulo
    resumen['A1'].font = Font(bold=True, size=14)
    encabezados(resumen, 4, 'Indicador', 'Valor')
    for i, (nombre, valor) in enumerate(indicadores(r), start=5):
        resumen.cell(row=i, column=1, value=nombre)
        resumen.cell(row=i, column=2, value=valor)
    resumen.column_dimensions['A'].width, resumen.column_dimensions['B'].width = 32, 30

    dias = libro.create_sheet('Pedidos por día')
    encabezados(dias, 1, 'Fecha', 'Pedidos')
    for i, (dia, n) in enumerate(r.por_dia, start=2):
        dias.cell(row=i, column=1, value=dia).number_format = 'DD/MM/YYYY'
        dias.cell(row=i, column=2, value=n)
    dias.column_dimensions['A'].width = 14
    if r.por_dia:
        grafica = BarChart()
        grafica.title, grafica.y_axis.title, grafica.legend = 'Pedidos por día', 'Pedidos', None
        grafica.add_data(Reference(dias, min_col=2, min_row=1, max_row=len(r.por_dia) + 1), titles_from_data=True)
        grafica.set_categories(Reference(dias, min_col=1, min_row=2, max_row=len(r.por_dia) + 1))
        grafica.width, grafica.height = 22, 9
        dias.add_chart(grafica, 'D2')

    detalle = libro.create_sheet('Por repartidor')
    encabezados(detalle, 1, 'Repartidor', 'Entregas', 'Tiempo prom. en camino (min)', 'Devoluciones')
    for i, x in enumerate(r.por_repartidor, start=2):
        for columna, valor in enumerate((x['nombre'], x['entregas'], x['minutos'], x['devoluciones']), start=1):
            detalle.cell(row=i, column=columna, value=valor)
    for letra, ancho in zip('ABCD', (28, 10, 28, 14)):
        detalle.column_dimensions[letra].width = ancho

    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()
