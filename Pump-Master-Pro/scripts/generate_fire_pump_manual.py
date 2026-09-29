"""
scripts/generate_fire_pump_manual.py

Generates a comprehensive, professional Microsoft Word (.docx) technical manual:
"Pump Master Pro — Fire Protection Pump Sizing & Selection Engineering Manual"
Covering all standards (NFPA 20, NFPA 13, NFPA 14, EN 12845, AS 2941, AS 2419.1),
all scenarios, equations, auxiliary sizing, and worked numerical examples.
"""

import os
import sys
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def create_manual():
    doc = docx.Document()

    # ── Page Setup ───────────────────────────────────────────────────────────
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.different_first_page_header_footer = True
        
        # Header for normal pages
        header = section.header
        hp = header.paragraphs[0]
        hp.text = "Pump Master Pro | Fire Protection Pump Sizing & Engineering Manual"
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hp.style.font.name = "Calibri"
        hp.style.font.size = Pt(8.5)
        hp.style.font.color.rgb = RGBColor(100, 116, 139)

        # Footer for normal pages
        footer = section.footer
        fp = footer.paragraphs[0]
        fp.text = "Confidential & Proprietary — Pump Master Pro Engineering Systems"
        fp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        fp.style.font.name = "Calibri"
        fp.style.font.size = Pt(8.5)
        fp.style.font.color.rgb = RGBColor(100, 116, 139)

    # Color Palette Definitions
    COLOR_PRIMARY = RGBColor(27, 54, 93)      # Navy #1B365D
    COLOR_SECONDARY = RGBColor(43, 84, 126)   # Slate Blue #2B547E
    COLOR_ACCENT = RGBColor(13, 148, 136)     # Teal #0D9488
    COLOR_DARK = RGBColor(30, 41, 59)         # Slate 800 #1E293B
    COLOR_MUTED = RGBColor(100, 116, 139)     # Slate 500 #64748B
    HEX_PRIMARY = "1B365D"
    HEX_SECONDARY = "2B547E"
    HEX_LIGHT_BG = "F8FAFC"
    HEX_CALLOUT_BG = "F0FDF4"
    HEX_CALLOUT_BORDER = "0D9488"
    HEX_ALERT_BG = "FFFBEB"
    HEX_ALERT_BORDER = "F59E0B"
    HEX_GRID_BORDER = "CBD5E1"

    # ── Style Configurations ────────────────────────────────────────────────
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = COLOR_DARK
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(6)

    def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
        tcPr.append(tcMar)

    def set_cell_shading(cell, color_hex):
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
        cell._tc.get_or_add_tcPr().append(shading)

    def set_table_borders(table, color="CBD5E1", sz="4", val="single"):
        tblPr = table._tbl.tblPr
        borders = parse_xml(
            f'<w:tblBorders {nsdecls("w")}>'
            f'<w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
            f'<w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
            f'<w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
            f'<w:insideV w:val="none"/>'
            f'<w:left w:val="none"/>'
            f'<w:right w:val="none"/>'
            f'</w:tblBorders>'
        )
        tblPr.append(borders)

    def add_title(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(36)
        p.paragraph_format.space_after = Pt(8)
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(28)
        run.font.bold = True
        run.font.color.rgb = COLOR_PRIMARY
        return p

    def add_subtitle(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(24)
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(14)
        run.font.color.rgb = COLOR_SECONDARY
        return p

    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(20)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(18)
        run.font.bold = True
        run.font.color.rgb = COLOR_PRIMARY
        return p

    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(14)
        run.font.bold = True
        run.font.color.rgb = COLOR_SECONDARY
        return p

    def add_h3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(12)
        run.font.bold = True
        run.font.color.rgb = COLOR_DARK
        return p

    def add_body(text, bold_prefix=None):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(5)
        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.font.bold = True
            r_pre.font.color.rgb = COLOR_DARK
        r = p.add_run(text)
        r.font.color.rgb = COLOR_DARK
        return p

    def add_bullet(text, bold_prefix=None, level=0):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.left_indent = Inches(0.25 * (level + 1))
        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.font.bold = True
            r_pre.font.color.rgb = COLOR_DARK
        r = p.add_run(text)
        r.font.color.rgb = COLOR_DARK
        return p

    def add_formula_box(title, formula_text, variable_explanations=None):
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        cell.width = Inches(6.5)
        set_cell_shading(cell, HEX_LIGHT_BG)
        set_cell_margins(cell, top=140, bottom=140, left=200, right=200)

        # Left border only (slate accent)
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{HEX_SECONDARY}"/>'
            f'<w:top w:val="none"/><w:right w:val="none"/><w:bottom w:val="none"/>'
            f'</w:tcBorders>'
        )
        tcPr.append(borders)

        cp = cell.paragraphs[0]
        cp.paragraph_format.space_after = Pt(4)
        r_title = cp.add_run(f"FORMULA: {title}\n")
        r_title.font.name = 'Calibri'
        r_title.font.size = Pt(10.5)
        r_title.font.bold = True
        r_title.font.color.rgb = COLOR_SECONDARY

        r_form = cp.add_run(formula_text)
        r_form.font.name = 'Consolas'
        r_form.font.size = Pt(11)
        r_form.font.bold = True
        r_form.font.color.rgb = COLOR_PRIMARY

        if variable_explanations:
            cp_var = cell.add_paragraph()
            cp_var.paragraph_format.space_before = Pt(4)
            cp_var.paragraph_format.space_after = Pt(0)
            r_where = cp_var.add_run("Where:\n")
            r_where.font.bold = True
            r_where.font.size = Pt(9.5)
            r_where.font.color.rgb = COLOR_MUTED
            for var_item in variable_explanations:
                r_item = cp_var.add_run(f" • {var_item}\n")
                r_item.font.size = Pt(9.5)
                r_item.font.color.rgb = COLOR_DARK

        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    def add_callout(text, title="ENGINEERING PRACTICE NOTE", kind="tip"):
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        cell.width = Inches(6.5)
        bg_hex = HEX_CALLOUT_BG if kind == "tip" else HEX_ALERT_BG
        border_hex = HEX_CALLOUT_BORDER if kind == "tip" else HEX_ALERT_BORDER
        set_cell_shading(cell, bg_hex)
        set_cell_margins(cell, top=120, bottom=120, left=180, right=180)

        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{border_hex}"/>'
            f'<w:top w:val="none"/><w:right w:val="none"/><w:bottom w:val="none"/>'
            f'</w:tcBorders>'
        )
        tcPr.append(borders)

        cp = cell.paragraphs[0]
        cp.paragraph_format.space_after = Pt(3)
        r_title = cp.add_run(f"[{title}]\n")
        r_title.font.name = 'Calibri'
        r_title.font.size = Pt(10)
        r_title.font.bold = True
        r_title.font.color.rgb = RGBColor(13, 148, 136) if kind == "tip" else RGBColor(180, 83, 9)

        r_text = cp.add_run(text)
        r_text.font.size = Pt(10)
        r_text.font.color.rgb = COLOR_DARK

        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # ── COVER / TITLE HEADER ─────────────────────────────────────────────────
    add_title("PUMP MASTER PRO")
    add_subtitle("Fire Protection Pump Sizing, Hydraulic Calculations & Code Compliance Manual\nComprehensive Technical Guide across NFPA 20, NFPA 13, NFPA 14, EN 12845, and AS 2941")

    # Document Metadata Block
    meta_table = doc.add_table(rows=4, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("Software Platform:", "Pump Master Pro (PMP) Hydraulic Sizing & Selection Suite"),
        ("Module Reference:", "services/fire_protection.py & routes/fire_pumps.py"),
        ("Standards Covered:", "NFPA 20 (2025), NFPA 13 (2025), NFPA 14 (2023), EN 12845:2020, AS 2941-2013, AS 2419.1:2021"),
        ("Author / Organization:", "Lytrose Engineering Hydraulics Team | Technical Documentation"),
    ]
    for idx, (lbl, val) in enumerate(meta_data):
        row = meta_table.rows[idx]
        cell_lbl, cell_val = row.cells[0], row.cells[1]
        cell_lbl.width, cell_val.width = Inches(2.2), Inches(4.3)
        set_cell_margins(cell_lbl, 60, 60, 100, 100)
        set_cell_margins(cell_val, 60, 60, 100, 100)
        set_cell_shading(cell_lbl, "F1F5F9")
        set_cell_shading(cell_val, "FAFAFA")
        p0 = cell_lbl.paragraphs[0]
        r0 = p0.add_run(lbl)
        r0.font.bold = True
        r0.font.size = Pt(9.5)
        p1 = cell_val.paragraphs[0]
        r1 = p1.add_run(val)
        r1.font.size = Pt(9.5)
    set_table_borders(meta_table, "CBD5E1")

    doc.add_page_break()

    # ── TABLE OF CONTENTS OUTLINE ────────────────────────────────────────────
    add_h1("Table of Contents")
    toc_items = [
        "1. Executive Summary & Purpose",
        "2. Fundamental Differences: Fire Pumps vs. Commercial Process Pumps",
        "3. Core Sizing Architecture & Seven-Step Selection Procedure",
        "4. Standard 1: NFPA 13 Automatic Sprinkler Demand Calculations",
        "5. Standard 2: NFPA 14 Standpipe & Fire Hose Systems",
        "6. Standard 3: EN 12845 / LPC Fixed Firefighting Sprinkler Systems",
        "7. Standard 4: AS 2941 & AS 2419.1 Australian Fire Protection Systems",
        "8. Standard 5: Custom Engineering Direct Demand Sizing",
        "9. NFPA 20 Hydraulic Performance Limits & Curve Compliance Analysis",
        "10. Auxiliary System Sizing (Jockey Pump, Storage Tank & Pressure Switches)",
        "11. NFPA 20 Table 4.27 Pipe & Equipment Sizing Schedule",
        "12. Driver Sizing & Non-Overloading Motor Selection",
        "13. Step-by-Step Worked Numerical Engineering Examples",
        "14. Software Integration in Pump Master Pro & Automated Rating Score",
    ]
    for item in toc_items:
        add_body(item)

    doc.add_page_break()

    # ── SECTION 1: EXECUTIVE SUMMARY ─────────────────────────────────────────
    add_h1("1. Executive Summary & Purpose")
    add_body(
        "Fire pumps are dedicated, critical life-safety and property-protection equipment. Their primary function is to deliver "
        "enormous hydraulic power immediately upon fire alarm activation to suppress or control flames before structural failure occurs. "
        "Unlike commercial HVAC, municipal, or chemical process pumps—which are designed for continuous 24/7 duty and optimized solely for the "
        "Best Efficiency Point (BEP)—fire protection pumps must satisfy rigorous international life-safety standards that mandate performance across "
        "their complete operating spectrum, from zero flow (shutoff/churn) through 150% rated overload capacity."
    )
    add_body(
        "Pump Master Pro integrates a high-precision fire protection hydraulic engine implementing the latest editions of: "
        "NFPA 20 (Standard for the Installation of Stationary Pumps for Fire Protection), NFPA 13 (Standard for the Installation of Sprinkler Systems), "
        "NFPA 14 (Standard for the Installation of Standpipe and Hose Systems), EN 12845 (Fixed Firefighting Systems - Automatic Sprinkler Systems), "
        "and AS 2941 / AS 2419.1 (Fixed Fire Protection Installations - Pumpset Systems / Fire Hydrant Installations). "
        "This manual documents every mathematical formula, governing rule, code constraint, auxiliary equipment sizing method, and "
        "practical selection algorithm utilized within the software."
    )

    # ── SECTION 2: FIRE PUMPS VS PROCESS PUMPS ───────────────────────────────
    add_h1("2. Fundamental Differences: Fire Pumps vs. Commercial Process Pumps")
    add_body(
        "To properly size and evaluate fire pumps, an engineer must grasp why standard pump selection practices cannot be applied directly:"
    )

    comp_table = doc.add_table(rows=6, cols=3)
    comp_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Evaluation Metric", "Commercial / Industrial Process Pump", "NFPA 20 / EN 12845 Certified Fire Pump"]
    for i, h in enumerate(headers):
        cell = comp_table.rows[0].cells[i]
        set_cell_shading(cell, HEX_PRIMARY)
        set_cell_margins(cell, 100, 100, 120, 120)
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(10)

    rows_data = [
        ("Primary Sizing Goal", "Continuous high efficiency at BEP; minimum operating energy cost (LCC).", "Unfailing reliability at life-safety demand; maximum flow stability across 0% to 150% flow."),
        ("Shutoff / Churn Head", "Often steep (140% to 180% of rated head) to achieve steep H-Q controllability.", "Strictly capped: Maximum 140% of rated head (typically 101% to 140%) to protect piping from burst pressure."),
        ("Overload Flow Performance", "Pumps may drop sharply in head past BEP; cavitation and surging may occur.", "Mandatory capability: Must deliver at least 65% of rated head at 150% rated flow without cavitation breakoff."),
        ("Driver (Motor/Diesel) Sizing", "Sized for BEP duty point plus small service factor (1.10). Motor may trip on overload.", "Must be non-overloading across the entire pump curve or sized for maximum power draw + 1.15 service factor."),
        ("Suction Sizing & Piping", "Sized for standard velocity (1.5 to 2.0 m/s); standard butterfly valves common.", "Strict NFPA 20 Table 4.27 pipe sizes; suction velocity restricted to prevent air vortex; OS&Y gate valves mandatory."),
    ]
    for row_idx, r_data in enumerate(rows_data, start=1):
        for col_idx, text in enumerate(r_data):
            cell = comp_table.rows[row_idx].cells[col_idx]
            set_cell_margins(cell, 80, 80, 100, 100)
            if row_idx % 2 == 1:
                set_cell_shading(cell, "F8FAFC")
            p = cell.paragraphs[0]
            r = p.add_run(text)
            r.font.size = Pt(9.5)
            if col_idx == 0:
                r.font.bold = True
    set_table_borders(comp_table, "CBD5E1")

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # ── SECTION 3: SEVEN-STEP SELECTION PROCEDURE ────────────────────────────
    add_h1("3. Core Sizing Architecture & Seven-Step Selection Procedure")
    add_body(
        "Pump Master Pro executes an automated 7-step engineering procedure when sizing and selecting fire pumps. "
        "The workflow is illustrated below:"
    )

    steps = [
        ("Step 1: Hazard Classification & Code Selection", "Identify the governing standard (NFPA 13, NFPA 14, EN 12845, AS 2941, or Custom) and select the occupancy hazard classification (e.g., Ordinary Hazard 1, ESFR Storage, Class I Standpipe)."),
        ("Step 2: Calculate System Flow Demand (Q_total)", "Compute the primary automatic suppression demand (sprinkler density × area or standpipe riser flow) and sum it with the prescribed interior/exterior hose stream allowance."),
        ("Step 3: Calculate Total Dynamic Head (TDH)", "Sum the static elevation height (vertical distance from pump discharge to hydraulically most remote outlet), the piping friction loss, and the minimum required residual nozzle pressure."),
        ("Step 4: Establish the NFPA 20 Hydraulic Performance Limits", "Calculate the three regulatory test coordinates: 0% flow (churn head <= 140% rated head), 100% rated flow (head >= 100% rated head), and 150% overload flow (head >= 65% rated head)."),
        ("Step 5: Size Auxiliary Systems", "Calculate the Jockey Pump flow (1% of fire pump rated flow, min 10 GPM), Jockey rated head (+10 PSI), start/stop pressure switch settings, water storage tank volume (Flow × Duration), and NFPA 20 Table 4.27 pipe diameters."),
        ("Step 6: Automated Catalog Evaluation & 5th-Order Polynomial Fitting", "Scan visible centrifugal pumps in the database, compute pump head, efficiency, and shaft power using high-order polynomials, test NFPA 20 pass/fail criteria, and compute a multi-parameter compliance rating score."),
        ("Step 7: Driver Sizing & Engineering Verification", "Determine the required electric motor or diesel engine rating with a minimum 1.15 service factor across the full pump envelope, verifying that the driver cannot trip on thermal overload during 150% flow."),
    ]
    for title, desc in steps:
        add_body(desc, bold_prefix=f"{title}: ")

    doc.add_page_break()

    # ── SECTION 4: NFPA 13 SPRINKLER CALCULATIONS ────────────────────────────
    add_h1("4. Standard 1: NFPA 13 Automatic Sprinkler Demand Calculations")
    add_body(
        "NFPA 13 utilizes the Density/Area Method for standard occupancies, and specialized design points for Early Suppression Fast Response (ESFR) storage systems."
    )

    add_formula_box(
        "NFPA 13 Density/Area Sprinkler Flow Demand",
        "Q_sprinkler (GPM) = Density (GPM/ft²) × Design_Area (ft²)\n"
        "Q_total (GPM)     = Q_sprinkler + Q_hose_stream\n"
        "Q_total (m³/h)    = Q_total (GPM) × 0.227125",
        [
            "Density (GPM/ft²): Discharge density prescribed by NFPA 13 Chapter 19 for the hazard class.",
            "Design_Area (ft²): Operating area representing the hydraulically most demanding sprinkler group (typically 1,500 ft² for Light/Ordinary Hazard, 2,500 ft² for Extra Hazard).",
            "Q_hose_stream (GPM): Combined interior and exterior fire hose allowance reserved for firefighter use.",
            "0.227125: Exact SI conversion factor from US GPM to m³/h."
        ]
    )

    add_h2("NFPA 13 Hazard Classification Reference Table")
    add_body("Pump Master Pro embeds the following certified NFPA 13 hazard parameters:")

    nfpa13_table = doc.add_table(rows=7, cols=7)
    nfpa13_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    h_13 = ["Hazard Class", "Design Density", "Design Area", "Hose Stream", "Duration", "Min Nozzle Press.", "Total Flow (GPM)"]
    for i, h in enumerate(h_13):
        c = nfpa13_table.rows[0].cells[i]
        set_cell_shading(c, HEX_PRIMARY)
        set_cell_margins(c, 80, 80, 80, 80)
        p = c.paragraphs[0]
        r = p.add_run(h)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(9)

    hazards_13_data = [
        ("Light Hazard (LH)", "0.10 GPM/ft² (4.1 mm/min)", "1,500 ft² (139.4 m²)", "100 GPM (22.7 m³/h)", "30 min", "7.0 psi (0.48 bar)", "250 GPM (56.8 m³/h)"),
        ("Ordinary Hazard Group 1 (OH1)", "0.15 GPM/ft² (6.1 mm/min)", "1,500 ft² (139.4 m²)", "250 GPM (56.8 m³/h)", "60 min", "10.0 psi (0.69 bar)", "475 GPM (107.9 m³/h)"),
        ("Ordinary Hazard Group 2 (OH2)", "0.20 GPM/ft² (8.2 mm/min)", "1,500 ft² (139.4 m²)", "250 GPM (56.8 m³/h)", "90 min", "15.0 psi (1.03 bar)", "550 GPM (124.9 m³/h)"),
        ("Extra Hazard Group 1 (EH1)", "0.30 GPM/ft² (12.2 mm/min)", "2,500 ft² (232.3 m²)", "500 GPM (113.6 m³/h)", "90 min", "20.0 psi (1.38 bar)", "1,250 GPM (283.9 m³/h)"),
        ("Extra Hazard Group 2 (EH2)", "0.40 GPM/ft² (16.3 mm/min)", "2,500 ft² (232.3 m²)", "500 GPM (113.6 m³/h)", "120 min", "25.0 psi (1.72 bar)", "1,500 GPM (340.7 m³/h)"),
        ("High-Bay Storage / ESFR", "12 Heads @ K-14/K-25", "12 Operating Heads", "250 GPM (56.8 m³/h)", "60 min", "65.0 psi (4.48 bar)", "1,450 GPM (329.3 m³/h)"),
    ]
    for r_idx, row_vals in enumerate(hazards_13_data, start=1):
        for c_idx, val in enumerate(row_vals):
            c = nfpa13_table.rows[r_idx].cells[c_idx]
            set_cell_margins(c, 60, 60, 80, 80)
            if r_idx % 2 == 1:
                set_cell_shading(c, "F8FAFC")
            p = c.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(8.5)
            if c_idx == 0:
                r.font.bold = True
    set_table_borders(nfpa13_table, "CBD5E1")

    add_callout(
        "For ESFR (Early Suppression Fast Response) sprinklers, NFPA 13 §20 mandates that the hydraulic calculation assume "
        "a minimum of 12 operating sprinkler heads (4 heads on 3 adjacent branch lines) operating at designated pressures "
        "(typically 50-75 psi for K-14.0 or K-25.2 heads). This results in a base sprinkler flow of approximately 1,200 GPM, "
        "plus a 250 GPM hose stream, totaling 1,450 GPM.",
        title="NFPA 13 ESFR STORAGE DESIGN CRITERIA"
    )

    # ── SECTION 5: NFPA 14 STANDPIPE SYSTEMS ─────────────────────────────────
    add_h1("5. Standard 2: NFPA 14 Standpipe & Fire Hose Systems")
    add_body(
        "NFPA 14 governs stationary fire pumps serving vertical standpipe risers for manual firefighting operations. "
        "It categorizes standpipes into three distinct classes:"
    )

    add_bullet("Class I System: Provided with 2.5\" (65 mm) hose connections for trained firefighters. Minimum residual pressure is 100 psi (6.9 bar) at the hydraulically most remote 2.5\" outlet.")
    add_bullet("Class II System: Provided with 1.5\" (38 mm) hose stations for building occupant initial first-aid fire attack. Flow is 100 GPM at 65 psi (4.5 bar) residual pressure.")
    add_bullet("Class III System: Combined 2.5\" firefighter connections and 1.5\" occupant hose stations. Sized identically to Class I demand.")

    add_formula_box(
        "NFPA 14 Class I & Class III Flow Demand",
        "Q_calc (GPM)  = Q_1st_riser + (N_additional_risers × 250 GPM)\n"
        "Q_total (GPM) = min( Q_calc, Q_max )\n\n"
        "Where:\n"
        " • Q_1st_riser = 500 GPM\n"
        " • Q_max = 1,000 GPM (for non-sprinklered buildings)\n"
        " • Q_max = 1,250 GPM (for fully sprinklered buildings)",
        [
            "N_additional_risers: Number of standpipe risers beyond the first (max(0, Risers_Count - 1)).",
            "Residual Pressure: Minimum 100 psi (6.89 bar / 70.3 m) at the roof / highest standpipe outlet.",
            "Water Supply Duration: Minimum 30 minutes continuous operation."
        ]
    )

    # ── SECTION 6: EN 12845 EUROPEAN STANDARD ────────────────────────────────
    add_h1("6. Standard 3: EN 12845 / LPC Fixed Firefighting Sprinkler Systems")
    add_body(
        "EN 12845:2015+A1:2020 (and the LPC Rules in the UK) define sprinkler pump sizing across European jurisdictions. "
        "Rather than relying strictly on the imperial Density/Area method, EN 12845 defines standardized nominal flow "
        "and pressure operating points for certified sprinkler pumpsets:"
    )

    en_table = doc.add_table(rows=7, cols=6)
    en_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    h_en = ["Hazard Class", "Design Density", "Design Area", "Nominal Flow", "Nominal Head", "Duration"]
    for i, h in enumerate(h_en):
        c = en_table.rows[0].cells[i]
        set_cell_shading(c, HEX_PRIMARY)
        set_cell_margins(c, 80, 80, 80, 80)
        p = c.paragraphs[0]
        r = p.add_run(h)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(9)

    en_data = [
        ("Light Hazard (LH)", "2.25 mm/min", "84 m²", "225 L/min (13.5 m³/h)", "1.5 bar (15.3 m)", "30 min"),
        ("Ordinary Hazard Group 1 (OH1)", "5.0 mm/min", "72 m²", "1,000 L/min (60.0 m³/h)", "1.5 bar (15.3 m)", "60 min"),
        ("Ordinary Hazard Group 2 (OH2)", "5.0 mm/min", "144 m²", "1,400 L/min (84.0 m³/h)", "2.0 bar (20.4 m)", "60 min"),
        ("Ordinary Hazard Group 3 (OH3)", "5.0 mm/min", "216 m²", "1,800 L/min (108.0 m³/h)", "2.5 bar (25.5 m)", "60 min"),
        ("Ordinary Hazard Group 4 (OH4)", "5.0 mm/min", "360 m²", "2,200 L/min (132.0 m³/h)", "2.8 bar (28.6 m)", "60 min"),
        ("High Hazard Process (HHP)", "10.0 mm/min", "260 m²", "3,000 L/min (180.0 m³/h)", "3.5 bar (35.7 m)", "90 min"),
    ]
    for r_idx, row_vals in enumerate(en_data, start=1):
        for c_idx, val in enumerate(row_vals):
            c = en_table.rows[r_idx].cells[c_idx]
            set_cell_margins(c, 60, 60, 80, 80)
            if r_idx % 2 == 1:
                set_cell_shading(c, "F8FAFC")
            p = c.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(8.5)
            if c_idx == 0:
                r.font.bold = True
    set_table_borders(en_table, "CBD5E1")

    doc.add_page_break()

    # ── SECTION 7: AS 2941 & AS 2419.1 AUSTRALIAN STANDARDS ─────────────────
    add_h1("7. Standard 4: AS 2941 & AS 2419.1 Australian Fire Protection Systems")
    add_body(
        "In Australia and New Zealand, stationary fire pump installations are governed by AS 2941 (Fixed Fire Protection Installations - "
        "Pumpset Systems) in conjunction with AS 2118 (Automatic Fire Sprinkler Systems) and AS 2419.1 (Fire Hydrant Installations)."
    )

    add_body("The software implements the standard Australian sizing presets:")
    add_bullet("AS 2118 Light Hazard Sprinkler: 500 L/min (30.0 m³/h) at 400 kPa (40.8 m head); 30-minute duration.")
    add_bullet("AS 2118 Ordinary Hazard Sprinkler: 1,500 L/min (90.0 m³/h) at 600 kPa (61.2 m head); 60-minute duration.")
    add_bullet("AS 2419.1 Single Hydrant Attack (10 L/s): 600 L/min (36.0 m³/h) at 700 kPa (71.4 m head); 120-minute duration.")
    add_bullet("AS 2419.1 Dual Hydrant Attack (20 L/s): 1,200 L/min (72.0 m³/h) at 700 kPa (71.4 m head); 120-minute duration.")
    add_bullet("AS 2419.1 Triple Hydrant Attack (30 L/s): 1,800 L/min (108.0 m³/h) at 700 kPa (71.4 m head); 240-minute duration for large industrial complexes.")

    add_callout(
        "AS 2419.1 Clause 8.2 mandates that the fire hydrant booster pumpset maintain a minimum residual pressure of 700 kPa (7.0 bar / 71.4 m) "
        "at the hydraulically most disadvantaged fire hydrant outlet when delivering the required simultaneous fire attack flow.",
        title="AS 2419.1 MINIMUM RESIDUAL PRESSURE REQUIREMENT"
    )

    # ── SECTION 8: TOTAL DYNAMIC HEAD FORMULAS ───────────────────────────────
    add_h1("8. Total Dynamic Head (TDH) Governing Formulas")
    add_body(
        "Regardless of the selected flow standard, the fire pump must overcome three distinct hydraulic head components to satisfy code requirements:"
    )

    add_formula_box(
        "Total Dynamic Head (TDH) Equation",
        "TDH (m)   = ΔZ_static + H_friction + H_residual\n"
        "TDH (psi) = TDH (m) × 1.42233\n"
        "TDH (bar) = TDH (m) × 0.0980665",
        [
            "ΔZ_static (m): Net static elevation difference between the minimum suction water level and the highest discharge nozzle/sprinkler head.",
            "H_friction (m): Total piping friction loss through suction pipe, discharge pipe, check valves, OS&Y valves, backflow preventers, and riser fittings calculated via Darcy-Weisbach or Hazen-Williams.",
            "H_residual (m): Required residual pressure at the hydraulically most remote nozzle (e.g., 7-25 psi for sprinklers, 100 psi for Class I standpipes, 700 kPa for AS 2419.1 hydrants)."
        ]
    )

    # ── SECTION 9: NFPA 20 CHARACTERISTIC CURVE LIMITS ───────────────────────
    add_h1("9. NFPA 20 Characteristic Curve Limits & Compliance Evaluation")
    add_body(
        "NFPA 20 Chapter 4 strictly defines the acceptable shape of a certified fire pump's Head-Capacity (H-Q) characteristic curve. "
        "Every pump in Pump Master Pro is verified against the three regulatory test points:"
    )

    add_formula_box(
        "NFPA 20 Three-Point Hydraulic Curve Compliance",
        "1. Churn / Shutoff (0% Flow):    H(0)           <= 1.40 × H_rated  (Typically 101% - 140%)\n"
        "2. Rated Duty Point (100% Flow): H(Q_rated)     >= 1.00 × H_rated  (Delivery at full capacity)\n"
        "3. Overload Point (150% Flow):   H(1.5×Q_rated) >= 0.65 × H_rated  (Maintain pressure at overload)",
        [
            "H(0): Total dynamic head produced by the pump at zero discharge flow (churn/shutoff).",
            "1.40 Limit: Prevents excessive overpressure that could rupture sprinkler pipe fittings, valves, or underground mains.",
            "1.5 × Q_rated: Safety margin allowing firefighters to draw additional flow without the pump collapsing into cavitation or experiencing steep head collapse."
        ]
    )

    add_body("Pump Master Pro evaluates the full polynomial characteristic curves:")
    add_formula_box(
        "5th-Order Polynomial Hydraulic Modeling",
        "H(Q)   = a0 + a1·Q + a2·Q² + a3·Q³ + a4·Q⁴ + a5·Q⁵\n"
        "η(Q)   = b0 + b1·Q + b2·Q² + b3·Q³ + b4·Q⁴ + b5·Q⁵\n"
        "P(Q)   = p0 + p1·Q + p2·Q² + p3·Q³ + p4·Q⁴ + p5·Q⁵",
        [
            "a0...a5: Rigorous least-squares polynomial coefficients fitted to manufacturer certified test curves.",
            "H(Q): Pump Total Head in meters at flow rate Q in m³/h.",
            "η(Q): Pump Hydraulic Efficiency (%) at flow rate Q.",
            "P(Q): Shaft Power (kW) absorbed by the pump at flow rate Q."
        ]
    )

    doc.add_page_break()

    # ── SECTION 10: AUXILIARY SYSTEM SIZING ──────────────────────────────────
    add_h1("10. Auxiliary System Sizing: Jockey Pump, Storage Tank & Switches")
    add_body(
        "A compliant fire pump installation requires three critical auxiliary subsystems: a Jockey Pump to maintain system static pressure, "
        "calibrated pressure switches to coordinate automatic staging, and an on-site dedicated water storage reservoir."
    )

    add_h2("10.1 Jockey Pump (Pressure Maintenance Pump) Sizing")
    add_body(
        "The Jockey Pump prevents the main fire pump from starting needlessly due to minor pressure fluctuations, temperature expansion, "
        "or small packing gland weeping. It is sized according to NFPA 20 §4.26:"
    )

    add_formula_box(
        "Jockey Pump Flow & Head Formulas",
        "Q_jockey (GPM) = max( 10.0 GPM, 0.01 × Q_fire_rated_gpm )\n"
        "Q_jockey (m³/h) = Q_jockey (GPM) × 0.227125\n\n"
        "H_jockey (psi)  = H_fire_rated_psi + 10.0 psi\n"
        "H_jockey (m)    = H_jockey (psi) × 0.70307",
        [
            "1% Capacity Rule: Jockey pump flow is 1% of main fire pump flow (never less than 10 GPM / 2.27 m³/h) to replenish system pressure within 10 minutes.",
            "+10 PSI Differential: Sized to discharge slightly higher than the main pump rated head to maintain full system charge."
        ]
    )

    add_h2("10.2 Pressure Switch Staging Setpoints")
    add_body(
        "Pressure switches in the fire pump controller monitor system pressure via dedicated sensing lines. "
        "NFPA 20 Annex A recommends the following calibrated setpoints:"
    )

    add_formula_box(
        "Pressure Switch Staging Hierarchy",
        "P_jockey_stop  (psi) = P_churn + 5.0 psi\n"
        "P_jockey_start (psi) = P_jockey_stop - 10.0 psi\n"
        "P_main_fire_start (psi) = P_jockey_start - 10.0 psi",
        [
            "P_jockey_stop: Shuts off the jockey pump once the system is fully recharged to churn pressure.",
            "P_jockey_start: Starts the jockey pump when pressure drops by 10 psi due to minor leakage.",
            "P_main_fire_start: Starts the primary fire pump when pressure drops further by 10 psi, confirming a true fire demand event."
        ]
    )

    add_h2("10.3 Dedicated Fire Water Storage Tank Sizing")
    add_body(
        "Where municipal water supplies cannot guarantee 100% of required flow and residual pressure at all times, "
        "NFPA 22 and NFPA 20 require a dedicated on-site suction storage tank sized for the full design duration:"
    )

    add_formula_box(
        "Fire Water Storage Reservoir Volume",
        "Volume (m³)     = ( Q_total (m³/h) / 60.0 ) × Duration (min)\n"
        "Volume (US Gal) = Volume (m³) × 264.172",
        [
            "Duration (min): Prescribed by standard (30 min for Light Hazard, 60-90 min for Ordinary Hazard, 120 min for Extra Hazard / Hydrants).",
            "Effective Volume: Excludes unusable vortex-prevention dead storage at the tank bottom."
        ]
    )

    # ── SECTION 11: NFPA 20 TABLE 4.27 PIPE SIZING ───────────────────────────
    add_h1("11. NFPA 20 Table 4.27 Pipe & Equipment Sizing Schedule")
    add_body(
        "NFPA 20 Table 4.27 specifies the minimum nominal pipe and accessory diameters based on rated pump flow capacity. "
        "Pump Master Pro cross-references this schedule automatically:"
    )

    pipe_table = doc.add_table(rows=12, cols=7)
    pipe_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    h_p = ["Rated GPM", "Rated m³/h", "Min Suction", "Min Discharge", "Relief Valve", "Flow Meter", "Hose Valves (2.5\")"]
    for i, h in enumerate(h_p):
        c = pipe_table.rows[0].cells[i]
        set_cell_shading(c, HEX_PRIMARY)
        set_cell_margins(c, 80, 80, 80, 80)
        p = c.paragraphs[0]
        r = p.add_run(h)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(8.5)

    pipe_schedule_data = [
        ("100 GPM", "22.7 m³/h", "2.0 in (50 mm)", "2.0 in (50 mm)", "1.5 in", "2.0 in", "0"),
        ("250 GPM", "56.8 m³/h", "3.5 in (90 mm)", "3.0 in (80 mm)", "2.0 in", "3.5 in", "1"),
        ("500 GPM", "113.6 m³/h", "5.0 in (125 mm)", "5.0 in (125 mm)", "3.0 in", "5.0 in", "2"),
        ("750 GPM", "170.3 m³/h", "6.0 in (150 mm)", "6.0 in (150 mm)", "3.0 in", "5.0 in", "3"),
        ("1,000 GPM", "227.1 m³/h", "8.0 in (200 mm)", "6.0 in (150 mm)", "4.0 in", "6.0 in", "4"),
        ("1,250 GPM", "283.9 m³/h", "8.0 in (200 mm)", "8.0 in (200 mm)", "4.0 in", "6.0 in", "6"),
        ("1,500 GPM", "340.7 m³/h", "8.0 in (200 mm)", "8.0 in (200 mm)", "6.0 in", "8.0 in", "6"),
        ("2,000 GPM", "454.2 m³/h", "10.0 in (250 mm)", "10.0 in (250 mm)", "6.0 in", "8.0 in", "6"),
        ("2,500 GPM", "567.8 m³/h", "10.0 in (250 mm)", "10.0 in (250 mm)", "6.0 in", "8.0 in", "8"),
        ("3,000 GPM", "681.4 m³/h", "12.0 in (300 mm)", "12.0 in (300 mm)", "8.0 in", "8.0 in", "12"),
        ("5,000 GPM", "1,135.6 m³/h", "16.0 in (400 mm)", "14.0 in (350 mm)", "8.0 in", "12.0 in", "20"),
    ]
    for r_idx, row_vals in enumerate(pipe_schedule_data, start=1):
        for c_idx, val in enumerate(row_vals):
            c = pipe_table.rows[r_idx].cells[c_idx]
            set_cell_margins(c, 50, 50, 60, 60)
            if r_idx % 2 == 1:
                set_cell_shading(c, "F8FAFC")
            p = c.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(8.5)
            if c_idx == 0:
                r.font.bold = True
    set_table_borders(pipe_table, "CBD5E1")

    doc.add_page_break()

    # ── SECTION 12: DRIVER SIZING ────────────────────────────────────────────
    add_h1("12. Driver Sizing & Non-Overloading Motor Sizing")
    add_body(
        "NFPA 20 §9.5.1 mandates that electric motors and diesel engines powering fire pumps must be sized such that "
        "the driver is non-overloading across the entire pump curve up to 150% rated flow, or sized to satisfy the maximum "
        "brake horsepower (BHP) required by the pump at any flow rate on its certified characteristic curve."
    )

    add_formula_box(
        "Hydraulic & Driver Power Equations",
        "P_hydraulic (kW) = ( Q (m³/h) × H (m) × ρ (kg/m³) × g ) / ( 3,600 × 1,000 )\n"
        "P_shaft (kW)     = P_hydraulic (kW) / ( η_pump / 100 )\n"
        "P_driver_min (kW)= max( P_shaft(Q_rated), P_shaft(1.5×Q_rated) ) × 1.15\n"
        "P_driver_min (HP)= P_driver_min (kW) × 1.34102",
        [
            "ρ: Density of water (1,000 kg/m³).",
            "g: Gravitational acceleration (9.80665 m/s²).",
            "1.15 Factor: NFPA 20 safety / service factor ensuring continuous non-overloading motor operation.",
            "1.34102: Conversion factor from kW to Electric Horsepower (HP)."
        ]
    )

    # ── SECTION 13: FIVE DETAILED WORKED NUMERICAL EXAMPLES ──────────────────
    add_h1("13. Step-by-Step Worked Numerical Engineering Examples")
    add_body("Below are five complete worked engineering examples covering every scenario and standard within Pump Master Pro:")

    # Example 1
    add_h2("Example 1: NFPA 13 Ordinary Hazard Group 1 (Commercial Office & Parking)")
    add_body("Design a fire pump system for a 6-story commercial office building with basement parking (NFPA 13 OH1).")
    add_bullet("Standard & Hazard: NFPA 13 — Ordinary Hazard Group 1 (OH1)")
    add_bullet("Design Density: 0.15 GPM/ft² (6.1 mm/min); Design Area: 1,500 ft² (139.4 m²)")
    add_bullet("Hose Stream Allowance: 250 GPM (56.8 m³/h); Duration: 60 minutes")
    add_bullet("Elevation Height (ΔZ): 24.0 m; Friction Loss: 15.0 m; Residual Head: 10.0 psi (7.03 m)")

    add_body("Calculations:", bold_prefix="Step-by-Step ")
    add_bullet("1. Sprinkler Flow: Q_spk = 0.15 × 1,500 = 225.0 GPM (51.10 m³/h)")
    add_bullet("2. Hose Stream Flow: Q_hose = 250.0 GPM (56.78 m³/h)")
    add_bullet("3. Total System Flow: Q_total = 225.0 + 250.0 = 475.0 GPM (107.88 m³/h)")
    add_bullet("4. Total Dynamic Head: TDH = 24.0 m + 15.0 m + 7.03 m = 46.03 m (65.5 psi / 4.51 bar)")
    add_bullet("5. Churn Head Limit: H_churn_max = 46.03 × 1.40 = 64.44 m (91.7 psi)")
    add_bullet("6. 150% Overload Test: Q_150 = 475.0 × 1.50 = 712.5 GPM (161.82 m³/h); H_150_min = 46.03 × 0.65 = 29.92 m (42.6 psi)")
    add_bullet("7. Jockey Pump: Q_jockey = max(10, 475 × 0.01) = 10.0 GPM (2.27 m³/h); H_jockey = 65.5 + 10 = 75.5 psi (53.06 m)")
    add_bullet("8. Pressure Switches: Stop = 91.7 + 5 = 96.7 psi; Jockey Start = 86.7 psi; Fire Pump Start = 76.7 psi")
    add_bullet("9. Water Storage Tank: Volume = (107.88 / 60) × 60 = 107.9 m³ (28,500 US Gallons)")
    add_bullet("10. Recommended Piping: Suction = 5.0 in (125 mm); Discharge = 5.0 in (125 mm); Relief = 3.0 in; Meter = 5.0 in")
    add_bullet("11. Estimated Motor: P_hyd = (107.88 × 46.03 × 9.807) / 3600 = 13.53 kW; Driver = (13.53 / 0.70) × 1.15 = 22.2 kW (30 HP)")

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Example 2
    add_h2("Example 2: NFPA 13 ESFR High-Bay Warehouse Storage")
    add_body("Design a fire pump for a high-piled palletized logistics warehouse utilizing K-14.0 ESFR ceiling sprinklers.")
    add_bullet("Standard & Hazard: NFPA 13 — High-Bay Storage / ESFR (K-14 / K-25)")
    add_bullet("Prescribed Design: 12 ESFR heads operating simultaneously = 1,200 GPM (272.5 m³/h)")
    add_bullet("Hose Stream Allowance: 250 GPM (56.8 m³/h); Total Flow: 1,450 GPM (329.3 m³/h); Duration: 60 minutes")
    add_bullet("Elevation Height (ΔZ): 14.0 m; Friction Loss: 22.0 m; Residual Head: 65.0 psi (45.70 m for ESFR head)")

    add_body("Calculations:", bold_prefix="Step-by-Step ")
    add_bullet("1. Total System Flow: Q_total = 1,200 + 250 = 1,450.0 GPM (329.33 m³/h)")
    add_bullet("2. Total Dynamic Head: TDH = 14.0 m + 22.0 m + 45.70 m = 81.70 m (116.2 psi / 8.01 bar)")
    add_bullet("3. Churn Head Limit: H_churn_max = 81.70 × 1.40 = 114.38 m (162.7 psi)")
    add_bullet("4. 150% Overload Test: Q_150 = 1,450 × 1.50 = 2,175.0 GPM (494.0 m³/h); H_150_min = 81.70 × 0.65 = 53.11 m (75.5 psi)")
    add_bullet("5. Jockey Pump: Q_jockey = 1,450 × 0.01 = 14.5 GPM (3.29 m³/h); H_jockey = 116.2 + 10 = 126.2 psi (88.7 m)")
    add_bullet("6. Water Storage Tank: Volume = (329.33 / 60) × 60 = 329.3 m³ (87,000 US Gallons)")
    add_bullet("7. Recommended Piping: Suction = 8.0 in (200 mm); Discharge = 8.0 in (200 mm); Relief = 6.0 in; Meter = 8.0 in")
    add_bullet("8. Estimated Motor: P_hyd = (329.33 × 81.70 × 9.807) / 3600 = 73.29 kW; Driver = (73.29 / 0.72) × 1.15 = 117.1 kW (160 HP)")

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Example 3
    add_h2("Example 3: NFPA 14 Class I Multi-Riser Standpipe High-Rise")
    add_body("Design a fire pump for a 20-story fully sprinklered residential tower with 3 standpipe risers.")
    add_bullet("Standard: NFPA 14 — Class I Standpipe System (2.5\" Firefighter Connections)")
    add_bullet("Risers Count: 3; Building Sprinklered: Yes (Q_max = 1,250 GPM)")
    add_bullet("Elevation Height (ΔZ): 65.0 m; Friction Loss: 18.0 m; Residual Head: 100.0 psi (70.31 m)")

    add_body("Calculations:", bold_prefix="Step-by-Step ")
    add_bullet("1. Standpipe Flow: Q_calc = 500 GPM (1st riser) + (3 - 1) × 250 GPM = 1,000 GPM (227.12 m³/h)")
    add_bullet("2. Maximum Check: 1,000 GPM < 1,250 GPM max allowed -> Q_total = 1,000 GPM (227.12 m³/h)")
    add_bullet("3. Total Dynamic Head: TDH = 65.0 m + 18.0 m + 70.31 m = 153.31 m (218.1 psi / 15.03 bar)")
    add_bullet("4. Churn Head Limit: H_churn_max = 153.31 × 1.40 = 214.63 m (305.3 psi)")
    add_bullet("5. 150% Overload Test: Q_150 = 1,000 × 1.50 = 1,500 GPM (340.7 m³/h); H_150_min = 153.31 × 0.65 = 99.65 m (141.7 psi)")
    add_bullet("6. Water Storage Tank: Duration = 30 min; Volume = (227.12 / 60) × 30 = 113.6 m³ (30,000 US Gallons)")
    add_bullet("7. Recommended Piping: Suction = 8.0 in (200 mm); Discharge = 6.0 in (150 mm); Relief = 4.0 in; Meter = 6.0 in")
    add_bullet("8. Estimated Motor: P_hyd = (227.12 × 153.31 × 9.807) / 3600 = 94.85 kW; Driver = (94.85 / 0.72) × 1.15 = 151.5 kW (200 HP)")

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Example 4
    add_h2("Example 4: EN 12845 European Ordinary Hazard Group 2 (Car Workshop)")
    add_body("Design an automatic sprinkler pumpset for a European car maintenance facility complying with EN 12845.")
    add_bullet("Standard & Hazard: EN 12845 — Ordinary Hazard Group 2 (OH2)")
    add_bullet("Design Density: 5.0 mm/min; Design Area: 144 m²; Duration: 60 minutes")
    add_bullet("Nominal Prescribed Flow: 1,400 L/min = 84.0 m³/h (369.8 GPM)")
    add_bullet("Nominal Prescribed Pressure: 2.0 bar = 20.39 m head")
    add_bullet("Elevation Height (ΔZ): 8.0 m; Friction Loss: 12.0 m; Residual Head: 2.0 bar (20.39 m)")

    add_body("Calculations:", bold_prefix="Step-by-Step ")
    add_bullet("1. Total Flow: Q_total = 84.0 m³/h (1,400 L/min / 369.8 GPM)")
    add_bullet("2. Total Dynamic Head: TDH = 8.0 m + 12.0 m + 20.39 m = 40.39 m (57.5 psi / 3.96 bar)")
    add_bullet("3. Churn Head Limit: H_churn_max = 40.39 × 1.40 = 56.55 m (80.4 psi)")
    add_bullet("4. Water Storage Tank: Volume = (84.0 / 60) × 60 = 84.0 m³ (22,190 US Gallons)")
    add_bullet("5. Recommended Piping: Nearest standard flow = 400 GPM -> Suction = 4.0 in (100 mm); Discharge = 4.0 in (100 mm)")
    add_bullet("6. Estimated Motor: P_hyd = (84.0 × 40.39 × 9.807) / 3600 = 9.24 kW; Driver = (9.24 / 0.70) × 1.15 = 15.2 kW (20 HP)")

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Example 5
    add_h2("Example 5: AS 2419.1 Dual Fire Hydrant Attack (20 L/s @ 700 kPa)")
    add_body("Design an Australian fire hydrant booster pumpset for an industrial warehouse requiring two simultaneous 10 L/s hydrant streams.")
    add_bullet("Standard: AS 2941-2013 / AS 2419.1-2021 — Dual Hydrant Attack (20 L/s)")
    add_bullet("Required Flow: 20 L/s = 1,200 L/min = 72.0 m³/h (317.0 GPM)")
    add_bullet("Duration: 120 minutes (2 hours)")
    add_bullet("Minimum Residual Pressure: 700 kPa = 7.0 bar = 71.38 m head")
    add_bullet("Elevation Height (ΔZ): 6.0 m; Friction Loss: 14.0 m")

    add_body("Calculations:", bold_prefix="Step-by-Step ")
    add_bullet("1. Total Flow: Q_total = 72.0 m³/h (1,200 L/min / 317.0 GPM)")
    add_bullet("2. Total Dynamic Head: TDH = 6.0 m + 14.0 m + 71.38 m = 91.38 m (129.9 psi / 8.96 bar)")
    add_bullet("3. Churn Head Limit: H_churn_max = 91.38 × 1.40 = 127.93 m (181.9 psi)")
    add_bullet("4. 150% Overload Test: Q_150 = 72.0 × 1.50 = 108.0 m³/h; H_150_min = 91.38 × 0.65 = 59.40 m")
    add_bullet("5. Water Storage Tank: Volume = (72.0 / 60) × 120 = 144.0 m³ (38,040 US Gallons)")
    add_bullet("6. Recommended Piping: Nearest standard flow = 400 GPM -> Suction = 4.0 in (100 mm); Discharge = 4.0 in (100 mm)")
    add_bullet("7. Estimated Motor: P_hyd = (72.0 × 91.38 × 9.807) / 3600 = 17.92 kW; Driver = (17.92 / 0.72) × 1.15 = 28.6 kW (40 HP)")

    doc.add_page_break()

    # ── SECTION 14: SOFTWARE INTEGRATION IN PUMP MASTER PRO ──────────────────
    add_h1("14. Software Integration in Pump Master Pro & Automated Rating Score")
    add_body(
        "Pump Master Pro implements this entire engineering workflow inside the dedicated blueprint routes/fire_pumps.py. "
        "The software provides an intelligent multi-parameter ranking score out of 100 points for every candidate pump:"
    )

    add_formula_box(
        "Pump Master Pro NFPA 20 Compliance Rating Algorithm",
        "Score = 100.0\n"
        "IF NOT pass_rated:    Score = Score - 50.0  (H(Q_rated) < H_duty)\n"
        "IF NOT pass_churn:    Score = Score - 30.0  (H(0) > 1.40 × H_duty)\n"
        "IF NOT pass_overload: Score = Score - 30.0  (H(1.5×Q_rated) < 0.65 × H_duty)\n"
        "Score = Score + ( η_rated × 0.20 )          (Efficiency bonus up to +20 pts)",
        [
            "pass_rated: Pump delivered head at duty flow >= 98% of required head (2% tolerance).",
            "pass_churn: Shutoff head <= 140.5% of rated head.",
            "pass_overload: 150% overload head >= 64.5% of rated head.",
            "Rank 1: The highest scoring pump satisfies all three NFPA 20 curve envelope rules with the highest hydraulic efficiency."
        ]
    )

    add_body("User Interface & Operation within Pump Master Pro:")
    add_bullet("Navigation: Click 'Fire Pumps' in the main navigation bar or visit /fire-pumps.")
    add_bullet("Preset Selection: Select Standard from the dropdown (NFPA 13, NFPA 14, EN 12845, AS 2941, Custom).")
    add_bullet("Interactive Inputs: Tweak design area, hose stream allowance, static height, friction losses, and risers count in real time.")
    add_bullet("Instant Calculation: The calculation engine dynamically updates the duty point, NFPA 20 envelope, jockey pump, water tank, and pipe sizing.")
    add_bullet("One-Click Selection: Click 'Select Pump' on any compliant pump card to sync the duty point and pump model into your project session for curve graphing and reporting.")

    # Save document
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    static_docs_dir = os.path.join(output_dir, 'pump-app', 'static', 'docs')
    os.makedirs(static_docs_dir, exist_ok=True)

    root_path = os.path.join(output_dir, 'Fire_Pump_Sizing_and_Selection_Manual.docx')
    web_path = os.path.join(static_docs_dir, 'Fire_Pump_Sizing_and_Selection_Manual.docx')

    doc.save(root_path)
    doc.save(web_path)
    print(f"Manual successfully saved to:\n 1. {root_path}\n 2. {web_path}")

if __name__ == '__main__':
    create_manual()
