"""
routes/reports.py — Reports & Settings Blueprint

Beginners Note: This module manages PDF report configurations, supplier branding profiles,
HTML report template rendering, automated Action Bar injection, exact pump curve evaluation,
and 100% pixel-perfect PDF file generation using Headless Chromium.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, make_response
from models import db, Pump, Supplier, ReportConfig
from pump_curves import hq_curve, efficiency_curve, power_curve, npsh_curve, bep_point
import numpy as np
from datetime import datetime
import os, sys, io, re, tempfile, subprocess

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


def render_pdf_with_headless_browser(html_content, output_path):
    """
    Beginners Note: Uses Headless Chromium (Chrome/Edge) to render 100% pixel-perfect PDF files.
    Because Headless Chromium uses the real browser rendering engine, all CSS styles, Tailwind classes,
    fonts, colors, and Plotly/SVG graphs match the browser preview 100% identically!
    """
    executables = [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
    ]
    browser_path = None
    for exe in executables:
        if os.path.exists(exe):
            browser_path = exe
            break
            
    if not browser_path:
        return False
        
    temp_html = None
    try:
        with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_html = f.name
            
        file_uri = 'file:///' + temp_html.replace('\\', '/')
        cmd = [
            browser_path,
            '--headless=new',
            '--disable-gpu',
            '--no-sandbox',
            '--no-pdf-header-footer',
            '--virtual-time-budget=5000',
            f'--print-to-pdf={output_path}',
            file_uri
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        print("Headless browser PDF rendering error:", e)
        return False
    finally:
        if temp_html and os.path.exists(temp_html):
            try:
                os.remove(temp_html)
            except Exception:
                pass


def generate_chart_svg(x_vals, y_vals, x_label="Flow (m³/h)", y_label="Head (m)", stroke_color="#1e3a8a", width=480, height=220, duty_point=None):
    """
    Beginners Note: Generates pure inline SVG XML vector markup for pump performance curves.
    Evaluates exact mathematical points for HQ, Eta, Power, and NPSHr curves.
    """
    if not x_vals or not y_vals or len(x_vals) != len(y_vals):
        return ""

    padding_left = 45
    padding_right = 20
    padding_top = 20
    padding_bottom = 35

    plot_w = width - padding_left - padding_right
    plot_h = height - padding_top - padding_bottom

    x_min, x_max = min(x_vals), max(x_vals)
    y_min, y_max = 0.0, max(y_vals) * 1.12 if max(y_vals) > 0 else 10.0

    if x_max == x_min: x_max = x_min + 1.0
    if y_max == y_min: y_max = y_min + 1.0

    pts = []
    for x, y in zip(x_vals, y_vals):
        px = padding_left + ((x - x_min) / (x_max - x_min)) * plot_w
        py = padding_top + plot_h - ((y - y_min) / (y_max - y_min)) * plot_h
        pts.append((px, py))

    path_d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"
    for px, py in pts[1:]:
        path_d += f" L {px:.1f},{py:.1f}"

    grid_lines = []
    labels = []
    
    for i in range(6):
        val = x_min + (x_max - x_min) * (i / 5.0)
        px = padding_left + (i / 5.0) * plot_w
        grid_lines.append(f'<line x1="{px:.1f}" y1="{padding_top}" x2="{px:.1f}" y2="{padding_top + plot_h}" stroke="#e2e8f0" stroke-dasharray="3,3" />')
        labels.append(f'<text x="{px:.1f}" y="{height - 10}" font-size="9" font-family="Helvetica, Arial, sans-serif" fill="#64748b" text-anchor="middle">{val:.0f}</text>')

    for i in range(5):
        val = y_min + (y_max - y_min) * (i / 4.0)
        py = padding_top + plot_h - (i / 4.0) * plot_h
        grid_lines.append(f'<line x1="{padding_left}" y1="{py:.1f}" x2="{width - padding_right}" y2="{py:.1f}" stroke="#e2e8f0" stroke-dasharray="3,3" />')
        labels.append(f'<text x="{padding_left - 6}" y="{py + 3:.1f}" font-size="9" font-family="Helvetica, Arial, sans-serif" fill="#64748b" text-anchor="end">{val:.1f}</text>')

    duty_svg = ""
    if duty_point and 'q' in duty_point and 'val' in duty_point:
        dq, dv = duty_point['q'], duty_point['val']
        if x_min <= dq <= x_max and y_min <= dv <= y_max:
            dpx = padding_left + ((dq - x_min) / (x_max - x_min)) * plot_w
            dpy = padding_top + plot_h - ((dv - y_min) / (y_max - y_min)) * plot_h
            duty_svg = f'''
            <circle cx="{dpx:.1f}" cy="{dpy:.1f}" r="4.5" fill="#ef4444" stroke="#ffffff" stroke-width="1.5" />
            <text x="{dpx + 6:.1f}" y="{dpy - 4:.1f}" font-size="8.5" font-weight="bold" font-family="Helvetica, Arial, sans-serif" fill="#dc2626">Duty ({dq:.0f}, {dv:.1f})</text>
            '''

    svg_code = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="{height}px" style="background:#ffffff; border-radius:6px;">
  {''.join(grid_lines)}
  <line x1="{padding_left}" y1="{padding_top + plot_h}" x2="{width - padding_right}" y2="{padding_top + plot_h}" stroke="#475569" stroke-width="1.5" />
  <line x1="{padding_left}" y1="{padding_top}" x2="{padding_left}" y2="{padding_top + plot_h}" stroke="#475569" stroke-width="1.5" />
  {''.join(labels)}
  <text x="{width / 2}" y="{height - 1}" font-size="9.5" font-weight="bold" font-family="Helvetica, Arial, sans-serif" fill="#334155" text-anchor="middle">{x_label}</text>
  <text x="12" y="{height / 2}" font-size="9.5" font-weight="bold" font-family="Helvetica, Arial, sans-serif" fill="#334155" text-anchor="middle" transform="rotate(-90 12 {height / 2})">{y_label}</text>
  <path d="{path_d}" fill="none" stroke="{stroke_color}" stroke-width="2.5" stroke-linecap="round" />
  {duty_svg}
</svg>'''
    return svg_code


def _build_report_curve_context(pump, report):
    """
    Beginners Note: Evaluates exact mathematical pump curves using pump_curves.py polynomial math,
    and generates server-side SVG vector graphics for HQ, Efficiency, Power, and NPSHr curves.
    """
    q_max = pump.q_max if hasattr(pump, 'q_max') and pump.q_max and pump.q_max > 0 else 200.0
    q_pts = list(np.linspace(0, q_max, 60))

    h_arr = hq_curve(pump, np.array(q_pts))
    eta_arr = efficiency_curve(pump, np.array(q_pts))
    pow_arr = power_curve(pump, np.array(q_pts))
    npsh_arr = npsh_curve(pump, np.array(q_pts))

    h_pts = [round(float(v), 2) for v in h_arr]
    eta_pts = [round(float(v), 2) for v in eta_arr]
    pow_pts = [round(float(v), 2) for v in pow_arr]
    npsh_pts = [round(float(v), 2) for v in npsh_arr]

    primary_color = report.primary_color if report and report.primary_color else '#1e3a8a'

    svg_hq = generate_chart_svg(q_pts, h_pts, f"Flow ({pump.unit_q or 'm³/h'})", f"Head ({pump.unit_h or 'm'})", stroke_color=primary_color)
    svg_eta = generate_chart_svg(q_pts, eta_pts, f"Flow ({pump.unit_q or 'm³/h'})", "Efficiency (%)", stroke_color="#059669")
    svg_pow = generate_chart_svg(q_pts, pow_pts, f"Flow ({pump.unit_q or 'm³/h'})", f"Power ({pump.unit_pow or 'kW'})", stroke_color="#dc2626")
    svg_npsh = generate_chart_svg(q_pts, npsh_pts, f"Flow ({pump.unit_q or 'm³/h'})", f"NPSHr ({pump.unit_npsh or 'm'})", stroke_color="#0d9488")

    bep_info = None
    try:
        bep_info = bep_point(pump)
    except Exception:
        pass

    return {
        'q_max': q_max,
        'svg_hq': svg_hq,
        'svg_eta': svg_eta,
        'svg_pow': svg_pow,
        'svg_npsh': svg_npsh,
        'bep_info': bep_info
    }


@reports_bp.route('/settings')
def settings():
    reports = ReportConfig.query.order_by(ReportConfig.id.asc()).all()
    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    available_templates = ['standard_datasheet.html', 'compact_datasheet.html', 'slurry_specsheet.html']
    
    return render_template(
        'reports_settings.html',
        reports=reports,
        suppliers=suppliers,
        available_templates=available_templates
    )


@reports_bp.route('/settings/supplier/save', methods=['POST'])
def save_supplier():
    supplier_id = request.form.get('supplier_id')
    name = request.form.get('name', '').strip()
    
    if not name:
        flash('Supplier name is required.', 'error')
        return redirect(url_for('reports.settings'))
        
    if supplier_id and supplier_id.isdigit():
        supplier = Supplier.query.get_or_404(int(supplier_id))
    else:
        supplier = Supplier()
        db.session.add(supplier)

    supplier.name = name
    supplier.logo_url = request.form.get('logo_url', '').strip()
    supplier.contact_email = request.form.get('contact_email', '').strip()
    supplier.phone = request.form.get('phone', '').strip()
    supplier.website = request.form.get('website', '').strip()
    supplier.address = request.form.get('address', '').strip()

    db.session.commit()
    flash(f'Supplier "{supplier.name}" saved successfully.', 'success')
    return redirect(url_for('reports.settings'))


@reports_bp.route('/settings/report/save', methods=['POST'])
def save_report():
    report_id = request.form.get('report_id')
    title = request.form.get('title', '').strip()
    
    if not title:
        flash('Report Title is required.', 'error')
        return redirect(url_for('reports.settings'))

    if report_id and report_id.isdigit():
        report = ReportConfig.query.get_or_404(int(report_id))
    else:
        report = ReportConfig()
        db.session.add(report)

    supplier_id = request.form.get('supplier_id')
    report.supplier_id = int(supplier_id) if supplier_id and supplier_id.isdigit() else None
    report.title = title
    report.description = request.form.get('description', '').strip()
    report.template_name = request.form.get('template_name', 'standard_datasheet.html').strip()
    
    report.show_head_flow_graph = 'show_head_flow_graph' in request.form
    report.show_efficiency_graph = 'show_efficiency_graph' in request.form
    report.show_power_graph = 'show_power_graph' in request.form
    report.show_npsh_graph = 'show_npsh_graph' in request.form

    report.header_text = request.form.get('header_text', 'PUMP MASTER PRO - TECHNICAL DATASHEET').strip()
    report.footer_text = request.form.get('footer_text', 'Generated by Pump Master Pro Engineering Suite').strip()
    report.primary_color = request.form.get('primary_color', '#1e3a8a').strip()
    report.show_duty_point = 'show_duty_point' in request.form
    report.show_materials_table = 'show_materials_table' in request.form
    report.show_extended_specs = 'show_extended_specs' in request.form
    report.show_notes = 'show_notes' in request.form
    report.is_active = 'is_active' in request.form

    db.session.commit()
    flash(f'Report configuration "{report.title}" saved successfully.', 'success')
    return redirect(url_for('reports.settings'))


@reports_bp.route('/settings/report/delete/<int:id>', methods=['POST'])
def delete_report(id):
    report = ReportConfig.query.get_or_404(id)
    title = report.title
    db.session.delete(report)
    db.session.commit()
    flash(f'Report "{title}" deleted.', 'info')
    return redirect(url_for('reports.settings'))


@reports_bp.route('/view/<int:report_id>/pump/<int:pump_id>')
def view_report(report_id, pump_id):
    report = ReportConfig.query.get_or_404(report_id)
    pump = Pump.query.get_or_404(pump_id)
    
    template_file = f"reports/{report.template_name}" if report.template_name else "reports/standard_datasheet.html"
    current_date = datetime.now().strftime("%B %d, %Y")
    
    curves_ctx = _build_report_curve_context(pump, report)

    report_content = render_template(
        template_file,
        report=report,
        pump=pump,
        supplier=report.supplier,
        current_date=current_date,
        curves=curves_ctx,
        is_pdf_export=False
    )

    return render_template(
        'reports/report_wrapper.html',
        report=report,
        pump=pump,
        supplier=report.supplier,
        report_content=report_content
    )


@reports_bp.route('/download/<int:report_id>/pump/<int:pump_id>')
def download_pdf(report_id, pump_id):
    """
    Beginners Note: Converts the report template into a downloadable PDF file.
    First attempts 100% pixel-perfect PDF rendering using Headless Chromium (Chrome/Edge).
    Falls back to xhtml2pdf if Headless Chromium is unavailable. Saves a physical copy to pdf/ folder.
    """
    report = ReportConfig.query.get_or_404(report_id)
    pump = Pump.query.get_or_404(pump_id)
    
    template_file = f"reports/{report.template_name}" if report.template_name else "reports/standard_datasheet.html"
    current_date = datetime.now().strftime("%B %d, %Y")
    
    curves_ctx = _build_report_curve_context(pump, report)

    rendered_html = render_template(
        template_file,
        report=report,
        pump=pump,
        supplier=report.supplier,
        current_date=current_date,
        curves=curves_ctx,
        is_pdf_export=True
    )

    # Format filename e.g. Report_ISF_100x65-200.pdf
    clean_name = re.sub(r'[^\w\-]', '_', pump.name or 'Pump').strip('_')
    filename = f"Report_{clean_name}.pdf"
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pdf_folder = os.path.join(base_dir, 'pdf')
    os.makedirs(pdf_folder, exist_ok=True)
    saved_file_path = os.path.join(pdf_folder, filename)

    # 1. Attempt Headless Browser PDF rendering (100% pixel identical output)
    rendered_success = render_pdf_with_headless_browser(rendered_html, saved_file_path)
    
    if rendered_success and os.path.exists(saved_file_path):
        with open(saved_file_path, 'rb') as f:
            pdf_bytes = f.read()
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    # 2. Fallback to xhtml2pdf if Headless browser rendering is bypassed
    try:
        from xhtml2pdf import pisa
        pdf_stream = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.StringIO(rendered_html), dest=pdf_stream)
        
        if not pisa_status.err:
            pdf_bytes = pdf_stream.getvalue()
            with open(saved_file_path, 'wb') as f:
                f.write(pdf_bytes)
            response = make_response(pdf_bytes)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    except Exception as e:
        print("xhtml2pdf fallback notice:", e)

    response = make_response(rendered_html)
    response.headers['Content-Type'] = 'text/html'
    return response
