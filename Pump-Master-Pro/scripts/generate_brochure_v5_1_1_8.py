"""
scripts/generate_brochure_v5_1_1_8.py

Generates the updated, comprehensive Microsoft Word (.docx) marketing and technical brochure:
"Pump Master Pro™ — Next-Generation Industrial Pump Sizing, Schematic Pipe Network Modeling, Fire Protection & Submittal Automation"

Features added:
- Fire Protection Pump Sizing & NFPA 20 / 13 / 14 / EN 12845 / AS 2941 compliance module and screenshot
- Schematic View image for pipeline network (screenshot_pipe_schematic.png)
- Fire Protection Engineers & MEP Contractors audience row
- Fire Code Compliance ROI metric
- Seamless 8-page layout with perfectly balanced ending page
- Converts to publication-grade vector PDF using Microsoft Word COM automation
"""

import os
import sys
import subprocess

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def build_brochure():
    doc = docx.Document()

    # ── Page Setup ─────────────────────────────────────────────────────────────
    # Standard Letter 8.5 x 11.0 in, 0.7in top/bottom, 0.75in left/right margins (exact match with original)
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11.0)
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    # Palette
    C_PRIMARY_NAVY = RGBColor(30, 58, 138)    # #1E3A8A
    C_CYAN_ACCENT  = RGBColor(2, 132, 199)    # #0284C7
    C_SLATE_DARK   = RGBColor(30, 41, 59)     # #1E293B
    C_SLATE_MUTED  = RGBColor(100, 116, 139)  # #64748B
    C_WHITE        = RGBColor(255, 255, 255)  # #FFFFFF
    C_GREEN        = RGBColor(22, 101, 52)    # #166534

    HEX_NAVY       = "1E3A8A"
    HEX_CYAN       = "0284C7"
    HEX_CALLOUT_BG = "F0F9FF"
    HEX_DARK_CARD  = "0D1117"
    HEX_CAPTION_BG = "F8FAFC"
    HEX_BORDER     = "CBD5E1"
    HEX_ZEBRA      = "F8FAFC"

    # Default Normal Style
    normal = doc.styles['Normal']
    normal.font.name = 'Segoe UI'
    normal.font.size = Pt(10)
    normal.font.color.rgb = C_SLATE_DARK
    normal.paragraph_format.line_spacing = 1.15
    normal.paragraph_format.space_after = Pt(4)

    # ── XML Helper Utilities ──────────────────────────────────────────────────
    def set_cell_margins(cell, top=100, bottom=100, left=120, right=120):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
        tcPr.append(tcMar)

    def set_cell_shading(cell, color_hex):
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
        cell._tc.get_or_add_tcPr().append(shading)

    def set_table_borders(table, color="CBD5E1", sz="4"):
        tblPr = table._tbl.tblPr
        borders = parse_xml(
            f'<w:tblBorders {nsdecls("w")}>'
            f'<w:top w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
            f'<w:bottom w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
            f'<w:insideH w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
            f'<w:insideV w:val="none"/>'
            f'<w:left w:val="none"/>'
            f'<w:right w:val="none"/>'
            f'</w:tblBorders>'
        )
        tblPr.append(borders)

    def add_page_break():
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        run = p.add_run()
        run.add_break(docx.enum.text.WD_BREAK.PAGE)

    def add_section_heading(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(12)
        run.font.color.rgb = C_PRIMARY_NAVY
        return p

    def add_module_heading(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(11)
        run.font.color.rgb = C_CYAN_ACCENT
        return p

    def add_figure_box(image_path, fig_title, fig_desc, img_width_inches=6.2):
        tbl = doc.add_table(rows=2, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        # Row 0: Image in dark card container
        c0 = tbl.rows[0].cells[0]
        c0.width = Inches(7.0)
        set_cell_shading(c0, HEX_DARK_CARD)
        set_cell_margins(c0, top=100, bottom=100, left=100, right=100)
        p0 = c0.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p0.paragraph_format.space_before = Pt(0)
        p0.paragraph_format.space_after = Pt(0)
        r0 = p0.add_run()
        r0.add_picture(image_path, width=Inches(img_width_inches))

        # Row 1: Caption
        c1 = tbl.rows[1].cells[0]
        c1.width = Inches(7.0)
        set_cell_shading(c1, HEX_CAPTION_BG)
        set_cell_margins(c1, top=80, bottom=80, left=140, right=140)
        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_before = Pt(0)
        p1.paragraph_format.space_after = Pt(0)
        
        rt = p1.add_run(fig_title + " — ")
        rt.bold = True
        rt.font.size = Pt(9.0)
        rt.font.color.rgb = C_PRIMARY_NAVY

        rd = p1.add_run(fig_desc)
        rd.font.size = Pt(8.5)
        rd.font.color.rgb = C_SLATE_MUTED

        # Add space after table
        sp = doc.add_paragraph()
        sp.paragraph_format.space_before = Pt(0)
        sp.paragraph_format.space_after = Pt(6)

    # ── PATHS TO SCREENSHOTS & DIRECTORIES ────────────────────────────────────
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Pump-Master-Pro directory
    sub_repo_dir = os.path.dirname(script_dir)
    # Root workspace directory
    repo_root = os.path.dirname(sub_repo_dir)

    pump_app_dir = os.path.join(sub_repo_dir, "pump-app")
    screenshots_dir = os.path.join(pump_app_dir, "static", "screenshots")
    doc_dir = os.path.join(repo_root, "Documentation")
    os.makedirs(doc_dir, exist_ok=True)

    img_pump_selection = os.path.join(screenshots_dir, "screenshot_pump_selection.png")
    img_pipe_schematic = os.path.join(screenshots_dir, "screenshot_pipe_schematic.png")
    img_fire_protection = os.path.join(screenshots_dir, "screenshot_fire_protection.png")
    img_add_pump = os.path.join(screenshots_dir, "screenshot_add_pump.png")
    img_projects = os.path.join(screenshots_dir, "screenshot_projects.png")
    img_reports_settings = os.path.join(screenshots_dir, "screenshot_reports_settings.png")

    # =========================================================================
    # PAGE 1: COVER, VALUE PROPOSITION & TARGET AUDIENCES
    # =========================================================================
    # Header subline
    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(3)
    r_sub = p_sub.add_run("ENTERPRISE HYDRAULIC ENGINEERING SUITE  •  WWW.PUMPMASTERPRO.COM")
    r_sub.bold = True
    r_sub.font.size = Pt(9.0)
    r_sub.font.color.rgb = C_CYAN_ACCENT

    # Main Title
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(2)
    r_title = p_title.add_run("PUMP MASTER PRO™")
    r_title.bold = True
    r_title.font.size = Pt(26.0)
    r_title.font.color.rgb = C_PRIMARY_NAVY

    # Subtitle
    p_sub2 = doc.add_paragraph()
    p_sub2.paragraph_format.space_before = Pt(0)
    p_sub2.paragraph_format.space_after = Pt(10)
    r_sub2 = p_sub2.add_run("Next-Generation Industrial Pump Sizing, Schematic Pipe Network Modeling, Fire Protection & Submittal Automation")
    r_sub2.bold = True
    r_sub2.font.size = Pt(12.0)
    r_sub2.font.color.rgb = C_CYAN_ACCENT

    # Standards Checklist Badges
    p_std = doc.add_paragraph()
    p_std.paragraph_format.space_before = Pt(0)
    p_std.paragraph_format.space_after = Pt(12)
    badges = [
        "[✓] ISO 9906:2012 (Grade 1 & 2)",
        "[✓] ANSI/HI 14.6 Test Methods",
        "[✓] API 610 (11th/12th Edition)",
        "[✓] NFPA 20 / 13 / 14 & EN 12845 Fire",
        "[✓] Pipe Network Solvers",
        "[✓] Pixel-Perfect PDF Engine",
        "[✓] Highly Customizable"
    ]
    for i, b in enumerate(badges):
        rb = p_std.add_run(b)
        rb.bold = True
        rb.font.size = Pt(8.5)
        rb.font.color.rgb = C_PRIMARY_NAVY
        if i < len(badges) - 1:
            rs = p_std.add_run("   ")
            rs.font.size = Pt(8.5)

    # Callout Box (Table 0)
    tbl_callout = doc.add_table(rows=1, cols=1)
    tbl_callout.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_callout = tbl_callout.rows[0].cells[0]
    c_callout.width = Inches(7.0)
    set_cell_shading(c_callout, HEX_CALLOUT_BG)
    set_cell_margins(c_callout, top=140, bottom=140, left=200, right=200)
    # Left accent border
    tcPr = c_callout._tc.get_or_add_tcPr()
    tcBorders = parse_xml(f'<w:tcBorders {nsdecls("w")}><w:left w:val="single" w:sz="24" w:space="0" w:color="{HEX_CYAN}"/><w:top w:val="none"/><w:right w:val="none"/><w:bottom w:val="none"/></w:tcBorders>')
    tcPr.append(tcBorders)

    p_c1 = c_callout.paragraphs[0]
    p_c1.paragraph_format.space_after = Pt(4)
    r_c1 = p_c1.add_run('“From Raw Operating Duty Point to Publication-Grade Customer Submittal in Under 3 Minutes.”')
    r_c1.bold = True
    r_c1.italic = True
    r_c1.font.size = Pt(11.0)
    r_c1.font.color.rgb = C_PRIMARY_NAVY

    p_c2 = c_callout.add_paragraph()
    p_c2.paragraph_format.space_after = Pt(0)
    r_c2 = p_c2.add_run(
        'Pump Master Pro is the cloud-native hydraulic sizing, curve-fitting, project management, and pipe network analysis '
        'platform built specifically for Pump Manufacturers (OEMs), EPC Contractors, Consulting Engineers, Fire Protection '
        'Designers, and Heavy Industrial Plants (Mining, Water & Slurry). Designed for complete flexibility, users can add '
        'their own pump models and test bench curves, organize tender quotations into dedicated project folders, customize '
        'PDF submittal templates with corporate branding, and execute complex hydraulic friction and code compliance solving '
        'with zero desktop installations.'
    )
    r_c2.font.size = Pt(9.5)
    r_c2.font.color.rgb = C_SLATE_DARK

    # Section 1 Heading
    add_section_heading("1. Target Audiences & Value Delivered")

    # Target Audiences Table
    tbl_aud = doc.add_table(rows=6, cols=3)
    tbl_aud.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(tbl_aud, color=HEX_BORDER, sz="4")

    headers_aud = ["Industry / Stakeholder", "Traditional Bottleneck", "Pump Master Pro Solution"]
    widths_aud = [Inches(1.8), Inches(2.5), Inches(2.7)]

    # Header row
    for j, (h_text, w) in enumerate(zip(headers_aud, widths_aud)):
        cell = tbl_aud.rows[0].cells[j]
        cell.width = w
        set_cell_shading(cell, HEX_NAVY)
        set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(h_text)
        r.bold = True
        r.font.size = Pt(9.0)
        r.font.color.rgb = C_WHITE

    rows_aud_data = [
        (
            "Pump OEMs & Sales Distributors",
            "Slow quotation turnaround (2–4 hours per quote) and risk of sales reps recommending off-design pumps.",
            "Instant duty point matching, automated impeller trims, branded submittal generation, and multi-tenant catalog hosting."
        ),
        (
            "EPC & Consulting Engineers",
            "Error-prone spreadsheet friction formulas, lost project files, and tedious manual NPSHa safety margin checks.",
            "Interactive orthogonal CAD pipe network modeling, automated Colebrook-White friction solving, and project versioning."
        ),
        (
            "Mining & Slurry Plants",
            "Unpredicted pipe sanding, line blockage, or catastrophic pump wear due to incorrect slurry settling physics.",
            "Native Durand critical deposition velocity (Vc) and Ferguson & Church particle settling velocity algorithms."
        ),
        (
            "Water & Wastewater Utilities",
            "Operating off Best Efficiency Point (BEP), uncontrolled energy waste, and cavitation damage in parallel pumps.",
            "Comprehensive POR/AOR envelope visualization, VFD speed affinity curves, and multi-pump side-by-side comparison."
        ),
        (
            "Fire Protection & MEP Engineers",
            "Manual NFPA 20 curve tolerance verification, cumbersome NFPA 13/14 hazard calculations, and disconnected jockey pump sizing.",
            "Dedicated NFPA 20 / EN 12845 / AS 2941 modules with certified curve envelope checks, automated jockey pump & tank duration sizing."
        )
    ]

    for i, row_data in enumerate(rows_aud_data):
        row = tbl_aud.rows[i + 1]
        for j, (text, w) in enumerate(zip(row_data, widths_aud)):
            cell = row.cells[j]
            cell.width = w
            if i % 2 == 1:
                set_cell_shading(cell, HEX_ZEBRA)
            set_cell_margins(cell, top=90, bottom=90, left=120, right=120)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(text)
            r.font.size = Pt(8.5)
            if j == 0:
                r.bold = True
                r.font.color.rgb = C_PRIMARY_NAVY
            else:
                r.font.color.rgb = C_SLATE_DARK

    # =========================================================================
    # PAGE 2: 100% CUSTOMIZABLE & MODULE 1 (SELECTION ENGINE)
    # =========================================================================
    add_page_break()

    add_section_heading("2. 100% Customizable: Add Your Own Pumps & Catalogues")

    p_cust_intro = doc.add_paragraph()
    p_cust_intro.paragraph_format.space_before = Pt(0)
    p_cust_intro.paragraph_format.space_after = Pt(6)
    r_ci = p_cust_intro.add_run(
        "Unlike rigid legacy tools that lock you into static third-party databases, Pump Master Pro is built to be fully customizable "
        "by the user. Whether you are an equipment manufacturer introducing a new product line, or an engineering consultancy "
        "managing bespoke client assets, you have full ownership of your data."
    )
    r_ci.font.size = Pt(9.5)

    bullets_cust = [
        ("✔  Add & Manage Your Own Pumps: ", "Easily register any centrifugal or slurry pump model. Define pump family, series, discharge/suction flange ratings, impeller trim diameter ranges (min, rated, max), design speeds, and motor configurations."),
        ("✔  Automated Test Bench Curve Fitting: ", "Simply enter discrete performance test points (Flow, Head, Efficiency, Power, NPSHr). The system's mathematical engine automatically generates high-order polynomial regression curves (R² > 0.998) and affinity law speed/trim variations."),
        ("✔  Custom Branding & White-Labeling: ", "Fully customize PDF datasheets and client proposals with your corporate logo, custom primary banner colors, report headers, engineering notes, and warranty disclaimers."),
        ("✔  Custom Fluid, Slurry & Pipe Profiles: ", "Create bespoke fluid libraries: define custom slurry specific gravities, d50 particle sizes, non-Newtonian viscosities, pipe materials, roughness factors (ε), and proprietary fitting K-values.")
    ]

    for b_title, b_desc in bullets_cust:
        p_b = doc.add_paragraph()
        p_b.paragraph_format.space_before = Pt(0)
        p_b.paragraph_format.space_after = Pt(2)
        rb_t = p_b.add_run(b_title)
        rb_t.bold = True
        rb_t.font.size = Pt(9.5)
        rb_t.font.color.rgb = C_CYAN_ACCENT
        rb_d = p_b.add_run(b_desc)
        rb_d.font.size = Pt(9.5)
        rb_d.font.color.rgb = C_SLATE_DARK

    add_section_heading("3. Core Engineering Modules & Software Walkthrough")

    add_module_heading("■ Module 1: Intelligent Pump Sizing & BEP Operating Envelope")

    p_m1 = doc.add_paragraph()
    p_m1.paragraph_format.space_before = Pt(0)
    p_m1.paragraph_format.space_after = Pt(6)
    r_m1 = p_m1.add_run(
        "Filters pump models by target Flow (Q), Head (H), and available NPSH. Ranks selections by proximity to Best "
        "Efficiency Point (BEP), displaying Preferred Operating Regions (POR) and Allowable Operating Regions (AOR) "
        "with automated Karassik trim corrections and multi-speed affinity law scaling."
    )
    r_m1.font.size = Pt(9.5)

    add_figure_box(
        img_pump_selection,
        "▲ Figure 1: Pump Selection & Sizing Tool",
        "Interactive duty point matching showing superimposed Head (H-Q), Efficiency (η-Q), Power (P-Q), and NPSHr curves with BEP proximity rating.",
        img_width_inches=6.0
    )

    # =========================================================================
    # PAGE 3: MODULE 2 (PIPE NETWORK & SCHEMATIC VIEW)
    # =========================================================================
    add_page_break()

    add_module_heading("■ Module 2: Interactive CAD Pipe Network Designer & Schematic Solver")

    p_m2 = doc.add_paragraph()
    p_m2.paragraph_format.space_before = Pt(0)
    p_m2.paragraph_format.space_after = Pt(6)
    r_m2 = p_m2.add_run(
        "Design full hydraulic circuits with orthogonal pipe routing, integrated elbows, check valves, foot valves, and inline fittings. "
        "The software provides dual canvas perspectives: an Orthogonal Physical CAD layout and an intuitive Schematic Circuit View. "
        "It iteratively solves Darcy-Weisbach head loss using Colebrook-White friction factors and automatically computes the parabolic "
        "system curve (Hsys = Hstatic + k·Q²) overlaid onto pump performance curves for instant duty intersection verification."
    )
    r_m2.font.size = Pt(9.5)

    add_figure_box(
        img_pipe_schematic,
        "▲ Figure 2: Interactive CAD Pipe Network Designer — Schematic View",
        "Schematic canvas view displaying hydraulic circuit symbols, node elevations, Darcy-Weisbach / Colebrook-White friction factors, and system curve overlays.",
        img_width_inches=6.4
    )

    # =========================================================================
    # PAGE 4: MODULE 3 (FIRE PROTECTION PUMP MODULE)
    # =========================================================================
    add_page_break()

    add_module_heading("■ Module 3: Fire Protection Pump Sizing & NFPA 20 Code Compliance Engine")

    p_m3 = doc.add_paragraph()
    p_m3.paragraph_format.space_before = Pt(0)
    p_m3.paragraph_format.space_after = Pt(6)
    r_m3 = p_m3.add_run(
        "A dedicated, code-certified engineering module for fire protection systems supporting NFPA 20, NFPA 13, NFPA 14, "
        "EN 12845 (LPC), and AS 2941 (AU) standards. Key capabilities include:\n"
        "• Hazard Classification Demand: Automated hydraulic calculation for light, ordinary, and extra hazard occupancies with design density, operating area, and inside/outside hose stream allowances.\n"
        "• NFPA 20 Certified Curve Boundaries: Instant evaluation of mandatory fire curve thresholds: 100% rated duty point, minimum 65% rated head at 150% overload test flow, and maximum 140% shutoff (churn) head limit.\n"
        "• Auxiliary System Sizing: Automated pressure-maintenance jockey pump flow and cut-in/cut-out pressure settings, dedicated fire water storage tank duration volume calculations (30 to 120 min), and code pipe schedules.\n"
        "• Driver Power Sizing: Electric motor and diesel engine driver power sizing with mandated safety overload margins."
    )
    r_m3.font.size = Pt(9.5)

    add_figure_box(
        img_fire_protection,
        "▲ Figure 3: Fire Protection Pump Sizing & Code Compliance Tool",
        "Automated hazard demand sizing (NFPA 13/14, EN 12845, AS 2941), certified NFPA 20 curve boundaries (140% shutoff, 150% overload), auxiliary jockey pump & tank calculations, and duty matching.",
        img_width_inches=6.4
    )

    # =========================================================================
    # PAGE 5: MODULE 4 (CUSTOM PUMP BUILDER) & MODULE 5 (CATALOGUE)
    # =========================================================================
    add_page_break()

    add_module_heading("■ Module 4: Custom Pump Builder — Add Your Own Proprietary Pumps")

    p_m4 = doc.add_paragraph()
    p_m4.paragraph_format.space_before = Pt(0)
    p_m4.paragraph_format.space_after = Pt(6)
    r_m4 = p_m4.add_run(
        "Add custom pump models with ease. Input raw manufacturer test bench points, specify impeller trim diameter "
        "ranges, define motor ratings and flange ratings, and preview fitted curves in real-time with automated regression."
    )
    r_m4.font.size = Pt(9.5)

    add_figure_box(
        img_add_pump,
        "▲ Figure 4: Custom Pump Data Entry & Curve Fitting Form",
        "Add new pump models with live interactive curve fitting, operating limits, and motor specifications.",
        img_width_inches=6.4
    )

    add_module_heading("■ Module 5: Centralized Pump Data Catalogue & Inventory")

    p_m5 = doc.add_paragraph()
    p_m5.paragraph_format.space_before = Pt(0)
    p_m5.paragraph_format.space_after = Pt(6)
    r_m5 = p_m5.add_run(
        "Manage your complete inventory of pumps, series, and multi-speed curves. Search, filter, and organize by "
        "manufacturer, application category (Clean Water, Slurry, Fire Protection, Chemical), and impeller trim configurations. "
        "Perform instant multi-pump comparisons and manage organization-wide equipment permissions across engineering and sales divisions."
    )
    r_m5.font.size = Pt(9.5)

    # =========================================================================
    # PAGE 6: MODULE 6 (PROJECTS MANAGEMENT)
    # =========================================================================
    add_page_break()

    add_module_heading("■ Module 6: Projects & Saved Selections Management")

    p_m6 = doc.add_paragraph()
    p_m6.paragraph_format.space_before = Pt(0)
    p_m6.paragraph_format.space_after = Pt(6)
    r_m6 = p_m6.add_run(
        "The Projects module serves as the commercial and engineering repository for all client tenders and quotations. Key capabilities include:\n"
        "• Complete Selection Snapshot: In a single click, save the selected pump model, operating duty point (Q, H, η, P, NPSHr), fluid rheology, and the COMPLETE CAD pipe network topology directly into a project record.\n"
        "• Up to 10 Custom Organization Attributes: Configure bespoke metadata per organization (e.g. Plant Area, Mine Site, Fluid Stream, Piping Class, Lead Engineer, Tender Reference, Budget Code).\n"
        "• Instant Workspace Reload: Any team member can reopen a past saved selection with 1 click directly back into the live selection tool or CAD pipe canvas to re-simulate, modify parameters, or regenerate updated submittals without re-typing data."
    )
    r_m6.font.size = Pt(9.5)

    add_figure_box(
        img_projects,
        "▲ Figure 5: Projects Directory & Saved Selections Management",
        "Centralized project repository displaying client details, tender references, custom metadata attributes, and saved pump selection histories.",
        img_width_inches=6.0
    )

    # =========================================================================
    # PAGE 7: MODULE 7 (PDF REPORTS ENGINE)
    # =========================================================================
    add_page_break()

    add_module_heading("■ Module 7: Technical Reports & PDF Submittal Engine")

    p_m7 = doc.add_paragraph()
    p_m7.paragraph_format.space_before = Pt(0)
    p_m7.paragraph_format.space_after = Pt(6)
    r_m7 = p_m7.add_run(
        "Generate publication-grade engineering submittals and tender datasheets in seconds. Key capabilities include:\n"
        "• Pixel-Perfect Vector PDF Generation: Utilizes a dedicated Headless Chromium engine to render razor-sharp vector PDF files matching the on-screen browser preview 100% identically—eliminating blurry canvas captures or broken print layouts.\n"
        "• Flexible 1 to 4 Graph Stacking: Configure 1, 2, 3, or 4 stacked performance charts (H-Q, Efficiency, Power, NPSHr) with customizable display sequence and height percentage splits.\n"
        "• Comprehensive Technical Sections: Includes operating duty point badges, rated curve overlays, speed/trim isolines, complete construction & materials specification table, hydraulic design specs, and engineering approval remarks.\n"
        "• Multi-Supplier White-Labeling: Customize header banners, footer notices, corporate logos, and primary brand theme colors per manufacturer or distributor."
    )
    r_m7.font.size = Pt(9.5)

    add_figure_box(
        img_reports_settings,
        "▲ Figure 6: PDF Report Configuration & Graph Layout Settings",
        "Customizable report builder allowing multi-chart sequence ordering, height splits, isoline styling, and corporate white-label branding.",
        img_width_inches=6.0
    )

    # =========================================================================
    # PAGE 8: ROI IMPACT TABLE & CALL TO ACTION
    # =========================================================================
    add_page_break()

    add_section_heading("4. Business Impact & Return on Investment (ROI)")

    tbl_roi = doc.add_table(rows=7, cols=4)
    tbl_roi.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(tbl_roi, color=HEX_BORDER, sz="4")

    headers_roi = ["Key Performance Metric", "Traditional Method (Excel / Desktop)", "With Pump Master Pro", "Net Impact / ROI"]
    widths_roi = [Inches(1.8), Inches(2.2), Inches(2.0), Inches(1.0)]

    for j, (h_text, w) in enumerate(zip(headers_roi, widths_roi)):
        cell = tbl_roi.rows[0].cells[j]
        cell.width = w
        set_cell_shading(cell, HEX_NAVY)
        set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(h_text)
        r.bold = True
        r.font.size = Pt(9.0)
        r.font.color.rgb = C_WHITE

    rows_roi_data = [
        (
            "Quotation Turnaround Time",
            "2 to 4 hours per complex pump quotation.",
            "Under 3 minutes end-to-end.",
            "90% Time Savings"
        ),
        (
            "Fire Protection Compliance",
            "Manual NFPA 20 curve tolerance verification and separate spreadsheet sizing for jockey pumps.",
            "Instant NFPA 13/14/20, EN 12845 & AS 2941 automated verification.",
            "100% Code Compliance"
        ),
        (
            "Project Archiving & Traceability",
            "Scattered Excel files across local drives; impossible to audit.",
            "Centralized database with custom attributes and 1-click reload.",
            "100% Traceability"
        ),
        (
            "Submittal Deliverable Quality",
            "Fragmented screenshots, manual copy-pasting, and uneven styling.",
            "Publication-grade vector PDF datasheets with corporate branding.",
            "Professional Brand Edge"
        ),
        (
            "Calculation & Unit Accuracy",
            "Manual formulas prone to broken cells and unit conversion errors.",
            "Automated server-side Python engineering solvers.",
            "Zero Math Errors"
        ),
        (
            "Field Cavitation & Reliability",
            "Improper NPSHa safety margins leading to early impeller wear.",
            "Explicit POR/AOR checks and NPSH margin validation.",
            "Fewer Warranty Claims"
        )
    ]

    for i, row_data in enumerate(rows_roi_data):
        row = tbl_roi.rows[i + 1]
        for j, (text, w) in enumerate(zip(row_data, widths_roi)):
            cell = row.cells[j]
            cell.width = w
            if i % 2 == 1:
                set_cell_shading(cell, HEX_ZEBRA)
            set_cell_margins(cell, top=80, bottom=80, left=120, right=120)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(text)
            r.font.size = Pt(8.5)
            if j == 0:
                r.bold = True
                r.font.color.rgb = C_PRIMARY_NAVY
            elif j == 3:
                r.bold = True
                r.font.color.rgb = C_GREEN
            else:
                r.font.color.rgb = C_SLATE_DARK

    # Space before Call to Action Box
    sp_cta = doc.add_paragraph()
    sp_cta.paragraph_format.space_before = Pt(14)
    sp_cta.paragraph_format.space_after = Pt(0)

    # Call to Action Box (Table 8)
    tbl_cta = doc.add_table(rows=1, cols=1)
    tbl_cta.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_cta = tbl_cta.rows[0].cells[0]
    c_cta.width = Inches(7.0)
    set_cell_shading(c_cta, HEX_NAVY)
    set_cell_margins(c_cta, top=200, bottom=200, left=240, right=240)

    p_cta1 = c_cta.paragraphs[0]
    p_cta1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cta1.paragraph_format.space_before = Pt(0)
    p_cta1.paragraph_format.space_after = Pt(4)
    r_cta1 = p_cta1.add_run("Ready to Modernize Your Pump Sizing & Quotation Workflow?")
    r_cta1.bold = True
    r_cta1.font.size = Pt(14.0)
    r_cta1.font.color.rgb = C_WHITE

    p_cta2 = c_cta.add_paragraph()
    p_cta2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cta2.paragraph_format.space_before = Pt(0)
    p_cta2.paragraph_format.space_after = Pt(8)
    r_cta2 = p_cta2.add_run("Experience automated pump curves, schematic pipe network analysis, fire protection code compliance, project tracking, and instant engineering submittals today.")
    r_cta2.font.size = Pt(10.0)
    r_cta2.font.color.rgb = RGBColor(224, 231, 255)

    p_cta3 = c_cta.add_paragraph()
    p_cta3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cta3.paragraph_format.space_before = Pt(0)
    p_cta3.paragraph_format.space_after = Pt(0)
    r_cta3 = p_cta3.add_run("🌐 Website: https://www.pumpmasterpro.com    |    ✉ Contact & Access: admin@pumpmasterpro.com")
    r_cta3.bold = True
    r_cta3.font.size = Pt(9.5)
    r_cta3.font.color.rgb = C_WHITE

    # ── OUTPUT PATHS ──────────────────────────────────────────────────────────
    out_docx_doc = os.path.join(doc_dir, "Pump_Master_Pro_Brochure_V5_1_1_8.docx")
    out_docx_doc_standard = os.path.join(doc_dir, "Pump_Master_Pro_Brochure.docx")
    out_docx_app = os.path.join(pump_app_dir, "Pump_Master_Pro_Brochure.docx")

    doc.save(out_docx_doc)
    doc.save(out_docx_app)
    doc.save(out_docx_doc_standard)
    print(f"[✓] Saved updated brochure DOCX:")
    print(f"    - {out_docx_doc}")
    print(f"    - {out_docx_app}")
    print(f"    - {out_docx_doc_standard}")

    # ── CONVERT TO PDF VIA WORD COM ───────────────────────────────────────────
    out_pdf_doc = os.path.join(doc_dir, "Pump_Master_Pro_Brochure_V5_1_1_8.pdf")
    out_pdf_doc_standard = os.path.join(doc_dir, "Pump_Master_Pro_Brochure.pdf")

    # Double backslashes for powershell script string
    p_in = out_docx_doc.replace('\\', '\\\\')
    p_out1 = out_pdf_doc.replace('\\', '\\\\')
    p_out2 = out_pdf_doc_standard.replace('\\', '\\\\')

    ps_script = f"""$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {{
    $doc = $word.Documents.Open("{p_in}")
    $doc.SaveAs2("{p_out1}", 17)
    $doc.SaveAs2("{p_out2}", 17)
    $doc.Close()
    Write-Output "PDF conversion successful"
}} finally {{
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}}
"""
    ps_file = os.path.join(pump_app_dir, "scratch", "convert_brochure_to_pdf.ps1")
    os.makedirs(os.path.dirname(ps_file), exist_ok=True)
    with open(ps_file, "w", encoding="utf-8") as f:
        f.write(ps_script)

    try:
        res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_file], capture_output=True, text=True)
        print("Word PDF Conversion output:", res.stdout.strip())
        if res.stderr.strip():
            print("Word PDF Conversion stderr:", res.stderr.strip())
        if os.path.exists(out_pdf_doc):
            print(f"[✓] Successfully generated PDF: {out_pdf_doc} ({os.path.getsize(out_pdf_doc)} bytes)")
    finally:
        if os.path.exists(ps_file):
            os.remove(ps_file)

if __name__ == "__main__":
    build_brochure()
