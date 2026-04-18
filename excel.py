from openpyxl import Workbook
from openpyxl.styles import (Font, PatternFill, Alignment, Border, Side,
                              GradientFill)
from openpyxl.utils import get_column_letter
from openpyxl.styles.numbers import FORMAT_PERCENTAGE_00
import copy

wb = Workbook()

# ── Palette ────────────────────────────────────────────────────────────────
DARK_NAVY   = "1F3864"   # deep navy – section headers
MID_BLUE    = "2E75B6"   # mid blue  – column headers
LIGHT_BLUE  = "D6E4F0"   # pale blue – alternating rows / sub-headers
GOLD        = "F4B942"   # amber     – key output highlight
LIGHT_GOLD  = "FFF3CD"   # pale gold – output rows bg
GREEN_BG    = "E2EFDA"   # mint      – best case
RED_BG      = "FCE4D6"   # salmon    – worst case
YELLOW_INPUT= "FFFACD"   # lemon     – input cells
WHITE       = "FFFFFF"
BLACK       = "000000"
BLUE_FONT   = "0000FF"   # inputs
GREEN_FONT  = "006400"   # cross-sheet links (dark green)
RED_FONT    = "C00000"   # warnings / worst-case

def font(bold=False, color=BLACK, size=10, italic=False):
    return Font(name="Arial", bold=bold, color=color, size=size, italic=italic)

def fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)

def border_thin():
    s = Side(style="thin", color="BFBFBF")
    return Border(left=s, right=s, top=s, bottom=s)

def border_bottom_medium():
    m = Side(style="medium", color=DARK_NAVY)
    return Border(bottom=m)

def align(h="left", v="center", wrap=False):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

def style_header_dark(cell, text):
    cell.value = text
    cell.font = Font(name="Arial", bold=True, color=WHITE, size=11)
    cell.fill = fill(DARK_NAVY)
    cell.alignment = align("center")

def style_col_header(cell, text):
    cell.value = text
    cell.font = Font(name="Arial", bold=True, color=WHITE, size=10)
    cell.fill = fill(MID_BLUE)
    cell.alignment = align("center")

def style_row_label(cell, text, bold=False):
    cell.value = text
    cell.font = Font(name="Arial", bold=bold, color=BLACK, size=10)
    cell.alignment = align("left")

def style_input(cell, value=None):
    if value is not None:
        cell.value = value
    cell.font = Font(name="Arial", color=BLUE_FONT, size=10)
    cell.fill = fill(YELLOW_INPUT)
    cell.alignment = align("center")
    cell.border = border_thin()

def style_formula(cell, formula):
    cell.value = formula
    cell.font = Font(name="Arial", color=BLACK, size=10)
    cell.alignment = align("center")
    cell.border = border_thin()

def style_output_highlight(cell, formula=None, value=None):
    if formula:
        cell.value = formula
    elif value is not None:
        cell.value = value
    cell.font = Font(name="Arial", bold=True, color=BLACK, size=10)
    cell.fill = fill(LIGHT_GOLD)
    cell.border = border_thin()
    cell.alignment = align("center")

def style_section_label(cell, text):
    cell.value = text
    cell.font = Font(name="Arial", bold=True, color=WHITE, size=10)
    cell.fill = fill(MID_BLUE)
    cell.alignment = align("left")

def set_col_widths(ws, widths_dict):
    for col, w in widths_dict.items():
        ws.column_dimensions[col].width = w

def fmt_inr(cell):
    cell.number_format = '#,##0;(#,##0);"-"'

def fmt_pct(cell):
    cell.number_format = '0.0%;(0.0%);"-"'

def fmt_x(cell):
    cell.number_format = '0.0x'

# ══════════════════════════════════════════════════════════════════════════════
# SHEET 1 – Historical_Data
# ══════════════════════════════════════════════════════════════════════════════
ws1 = wb.active
ws1.title = "Historical_Data"
ws1.sheet_properties.tabColor = "2E75B6"

years = ["FY2016","FY2017","FY2018","FY2019","FY2020",
         "FY2021","FY2022","FY2023","FY2024","FY2025"]

# Merge title row
ws1.merge_cells("A1:M1")
c = ws1["A1"]
c.value = "INFOSYS LTD — Historical Financials  |  ₹ Crores  |  Source: Screener.in / Infosys Annual Reports"
c.font = Font(name="Arial", bold=True, color=WHITE, size=12)
c.fill = fill(DARK_NAVY)
c.alignment = align("center")

ws1.merge_cells("A2:M2")
ws1["A2"].value = "🔵 Blue cells = hard-coded inputs (type these yourself)   |   ⚫ Black cells = formulas   |   All figures in ₹ Crores unless stated"
ws1["A2"].font = Font(name="Arial", italic=True, color="444444", size=9)
ws1["A2"].fill = fill(LIGHT_BLUE)
ws1["A2"].alignment = align("center")

ws1.row_dimensions[1].height = 22
ws1.row_dimensions[2].height = 16

# Column headers row 3
headers = ["", "Metric"] + years + ["CAGR\n10Y"]
col_labels = ["A","B","C","D","E","F","G","H","I","J","K","L","M"]
for i, h in enumerate(headers):
    cell = ws1.cell(row=3, column=i+1)
    style_col_header(cell, h)
    ws1.row_dimensions[3].height = 28

# ── P&L Section ──────────────────────────────────────────────────────────────
ws1.merge_cells("A4:M4")
style_section_label(ws1["A4"], "  📊  PROFIT & LOSS")

PL_ROWS = [
    # (row, label, data or None, bold, bg)
    (5,  "Revenue (Sales)",         [62441,68484,70522,82675,90791,100472,121641,146767,153670,162990], True,  WHITE),
    (6,  "Employee Cost",           [34415,37669,38902,45323,50895,55547,63997,78374,82636,85968],  False, WHITE),
    (7,  "Other Operating Expenses",[6947,7641,8591,11653,11539,13880,22205,29296,31014,31030],    False, WHITE),
    (8,  "Total Expenses",          None, False, LIGHT_BLUE),   # formula
    (9,  "Operating Profit (EBIT)", None, True,  LIGHT_GOLD),   # formula
    (10, "OPM %",                   None, True,  LIGHT_GOLD),   # formula
    (11, "Other Income",            [3120,3050,3311,2882,2803,2201,2295,2701,4711,3600],  False, WHITE),
    (12, "Depreciation",            [1459,1703,1863,2011,2893,3267,3476,4225,4678,4812],  False, WHITE),
    (13, "Interest",                [0,0,0,0,170,195,200,284,470,416],                    False, WHITE),
    (14, "PBT",                     None, True,  LIGHT_GOLD),
    (15, "Tax",                     [5251,5598,4241,5631,5368,7205,7964,9214,9740,10858], False, WHITE),
    (16, "Net Profit",              None, True,  LIGHT_GOLD),
    (17, "Net Profit Margin %",     None, True,  LIGHT_GOLD),
]

data_cols = list("CDEFGHIJKL")   # C=FY2016 … L=FY2025

for row_no, label, data, bold, bg in PL_ROWS:
    ws1.cell(row=row_no, column=2).value = label
    ws1.cell(row=row_no, column=2).font = Font(name="Arial", bold=bold, size=10)
    ws1.cell(row=row_no, column=2).alignment = align("left")
    if bg != WHITE:
        ws1.cell(row=row_no, column=2).fill = fill(bg)

    for ci, col in enumerate(data_cols):
        cell = ws1.cell(row=row_no, column=ci+3)
        cell.border = border_thin()
        if bg != WHITE:
            cell.fill = fill(bg)

        if data is not None:
            # Hard-coded input
            cell.value = data[ci]
            cell.font = Font(name="Arial", color=BLUE_FONT, size=10)
            cell.alignment = align("center")
            fmt_inr(cell)
        else:
            # Formula cells
            c_letter = get_column_letter(ci+3)
            if label == "Total Expenses":
                cell.value = f"={c_letter}6+{c_letter}7"
            elif label == "Operating Profit (EBIT)":
                cell.value = f"={c_letter}5-{c_letter}8"
                cell.font = Font(name="Arial", bold=True, color=BLACK, size=10)
            elif label == "OPM %":
                cell.value = f"=IF({c_letter}5>0,{c_letter}9/{c_letter}5,0)"
                fmt_pct(cell)
                cell.font = Font(name="Arial", bold=True, color=BLACK, size=10)
                continue
            elif label == "PBT":
                cell.value = f"={c_letter}9+{c_letter}11-{c_letter}12-{c_letter}13"
                cell.font = Font(name="Arial", bold=True, color=BLACK, size=10)
            elif label == "Net Profit":
                cell.value = f"={c_letter}14-{c_letter}15"
                cell.font = Font(name="Arial", bold=True, color=BLACK, size=10)
            elif label == "Net Profit Margin %":
                cell.value = f"=IF({c_letter}5>0,{c_letter}16/{c_letter}5,0)"
                fmt_pct(cell)
                cell.font = Font(name="Arial", bold=True, color=BLACK, size=10)
                continue
            cell.alignment = align("center")
            fmt_inr(cell)

# CAGR column M (col 13) for key rows
cagr_rows = {5:"Revenue", 16:"Net Profit"}
for r, lbl in cagr_rows.items():
    cell = ws1.cell(row=r, column=13)
    cell.value = f"=IFERROR(POWER(L{r}/C{r},1/9)-1,\"\")"
    cell.font = Font(name="Arial", bold=True, color=BLACK, size=10)
    cell.fill = fill(GOLD)
    fmt_pct(cell)
    cell.border = border_thin()
    cell.alignment = align("center")

# ── Growth Metrics Section ────────────────────────────────────────────────────
ws1.merge_cells("A18:M18")
style_section_label(ws1["A18"], "  📈  GROWTH METRICS")

GROWTH_ROWS = [
    (19, "Revenue Growth YoY %"),
    (20, "Net Profit Growth YoY %"),
    (21, "Operating Profit Growth %"),
]
for row_no, label in GROWTH_ROWS:
    ws1.cell(row=row_no, column=2).value = label
    ws1.cell(row=row_no, column=2).font = Font(name="Arial", size=10)
    ws1.cell(row=row_no, column=2).alignment = align("left")
    src_row = {19:5, 20:16, 21:9}[row_no]
    for ci, col in enumerate(data_cols):
        cell = ws1.cell(row=row_no, column=ci+3)
        cell.border = border_thin()
        cell.alignment = align("center")
        if ci == 0:
            cell.value = "—"
            cell.font = Font(name="Arial", color="888888", size=10)
        else:
            prev = get_column_letter(ci+2)
            curr = get_column_letter(ci+3)
            cell.value = f"=IF({prev}{src_row}>0,({curr}{src_row}-{prev}{src_row})/{prev}{src_row},\"\")"
            cell.font = Font(name="Arial", color=BLACK, size=10)
            fmt_pct(cell)

# ── Balance Sheet Snapshot ────────────────────────────────────────────────────
ws1.merge_cells("A23:M23")
style_section_label(ws1["A23"], "  🏦  BALANCE SHEET SNAPSHOT")

BS_DATA = [
    (24, "Equity Share Capital", [1144,1144,1088,2170,2122,2124,2098,2069,2071,2073]),
    (25, "Reserves",             [60600,67838,63835,62778,63328,74227,73252,73338,86045,93745]),
    (26, "Borrowings",           [0,0,0,0,4633,5325,5474,8299,8359,8227]),
    (27, "Total Assets (proxy)", None),
    (28, "Return on Equity %",   None),
]
for row_no, label, data in BS_DATA:
    ws1.cell(row=row_no, column=2).value = label
    ws1.cell(row=row_no, column=2).font = Font(name="Arial", size=10)
    ws1.cell(row=row_no, column=2).alignment = align("left")
    for ci, col in enumerate(data_cols):
        c_letter = get_column_letter(ci+3)
        cell = ws1.cell(row=row_no, column=ci+3)
        cell.border = border_thin()
        cell.alignment = align("center")
        if data is not None:
            cell.value = data[ci]
            cell.font = Font(name="Arial", color=BLUE_FONT, size=10)
            fmt_inr(cell)
        else:
            if label == "Total Assets (proxy)":
                cell.value = f"={c_letter}24+{c_letter}25+{c_letter}26"
                cell.font = Font(name="Arial", color=BLACK, size=10)
                fmt_inr(cell)
            elif label == "Return on Equity %":
                cell.value = f"=IF(({c_letter}24+{c_letter}25)>0,{c_letter}16/({c_letter}24+{c_letter}25),\"\")"
                cell.font = Font(name="Arial", color=BLACK, size=10)
                fmt_pct(cell)

# ── Instruction box ──────────────────────────────────────────────────────────
ws1.merge_cells("A30:M35")
inst = ws1["A30"]
inst.value = (
    "📋  HOW TO USE THIS SHEET\n\n"
    "STEP 1 — Verify all BLUE cells match Screener.in / Infosys Annual Report data\n"
    "STEP 2 — All BLACK cells are formulas — do NOT overwrite them\n"
    "STEP 3 — Check OPM % row: FY2025 should show ~25%  |  FY2023 should show ~24.8%\n"
    "STEP 4 — Check Revenue CAGR (col M): should be ~10% over 10 years\n"
    "STEP 5 — Once verified, go to the Assumptions sheet and fill in your forecast drivers"
)
inst.font = Font(name="Arial", size=9, color="1F3864")
inst.fill = fill(LIGHT_BLUE)
inst.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
ws1.row_dimensions[30].height = 100

set_col_widths(ws1, {"A":2,"B":28,"C":10,"D":10,"E":10,"F":10,"G":10,
                      "H":10,"I":10,"J":10,"K":10,"L":10,"M":10})

# ══════════════════════════════════════════════════════════════════════════════
# SHEET 2 – Assumptions
# ══════════════════════════════════════════════════════════════════════════════
ws2 = wb.create_sheet("Assumptions")
ws2.sheet_properties.tabColor = "FFD700"

ws2.merge_cells("A1:G1")
c = ws2["A1"]
c.value = "INFOSYS LTD — Model Assumptions  |  All inputs in this sheet drive the Forecast Model"
c.font = Font(name="Arial", bold=True, color=WHITE, size=12)
c.fill = fill(DARK_NAVY)
c.alignment = align("center")
ws2.row_dimensions[1].height = 22

ws2.merge_cells("A2:G2")
ws2["A2"].value = "🔵 TYPE your assumptions in BLUE/YELLOW cells only.   Formulas reference these cells — do not hardcode values elsewhere."
ws2["A2"].font = Font(name="Arial", italic=True, color="444444", size=9)
ws2["A2"].fill = fill(LIGHT_BLUE)
ws2["A2"].alignment = align("center")

# Headers
for col, txt in zip("ABCDEFG", ["","Assumption Driver","Description","Base Case","Best Case","Worst Case","Unit"]):
    cell = ws2[f"{col}3"]
    style_col_header(cell, txt)
ws2.row_dimensions[3].height = 22

# Revenue Section
ws2.merge_cells("A4:G4")
style_section_label(ws2["A4"], "  📊  REVENUE ASSUMPTIONS (FY2026 – FY2030)")

assump_data = [
    # row, driver, description, base, best, worst, unit
    (5,  "Revenue Growth Y1",  "FY2026 Revenue Growth %",         0.08, 0.12, 0.04,  "%"),
    (6,  "Revenue Growth Y2",  "FY2027 Revenue Growth %",         0.09, 0.13, 0.05,  "%"),
    (7,  "Revenue Growth Y3",  "FY2028 Revenue Growth %",         0.10, 0.14, 0.06,  "%"),
    (8,  "Revenue Growth Y4",  "FY2029 Revenue Growth %",         0.10, 0.15, 0.06,  "%"),
    (9,  "Revenue Growth Y5",  "FY2030 Revenue Growth %",         0.11, 0.16, 0.07,  "%"),
]

for row_no, driver, desc, base, best, worst, unit in assump_data:
    ws2.cell(row=row_no, column=2).value = driver
    ws2.cell(row=row_no, column=2).font = Font(name="Arial", bold=True, size=10)
    ws2.cell(row=row_no, column=3).value = desc
    ws2.cell(row=row_no, column=3).font = Font(name="Arial", size=10, italic=True, color="555555")
    for col_no, val in zip([4,5,6],[base,best,worst]):
        cell = ws2.cell(row=row_no, column=col_no)
        style_input(cell, val)
        fmt_pct(cell)
    ws2.cell(row=row_no, column=7).value = unit
    ws2.cell(row=row_no, column=7).font = Font(name="Arial", size=9, color="888888")

# Margin Section
ws2.merge_cells("A11:G11")
style_section_label(ws2["A11"], "  💰  MARGIN ASSUMPTIONS")

margin_data = [
    (12, "OPM % (Base)",   "Operating Profit Margin — Base",  0.245, 0.270, 0.210, "%"),
    (13, "OPM % (Best)",   "Operating Profit Margin — Best",  0.270, 0.290, 0.230, "%"),
    (14, "OPM % (Worst)",  "Operating Profit Margin — Worst", 0.210, 0.245, 0.190, "%"),
    (15, "Tax Rate",       "Effective Tax Rate (historical ~28%)", 0.27, 0.26, 0.29,  "%"),
    (16, "Depreciation",   "Depreciation ₹ Cr (FY2025 base: 4812)", 5000, 5000, 5000, "₹ Cr"),
    (17, "Interest",       "Interest ₹ Cr (FY2025: 416)",     450,  420,  480,  "₹ Cr"),
    (18, "Other Income",   "Other Income ₹ Cr (5Y avg: ~3100)",3100, 3500, 2500, "₹ Cr"),
]

for row_no, driver, desc, base, best, worst, unit in margin_data:
    ws2.cell(row=row_no, column=2).value = driver
    ws2.cell(row=row_no, column=2).font = Font(name="Arial", bold=True, size=10)
    ws2.cell(row=row_no, column=3).value = desc
    ws2.cell(row=row_no, column=3).font = Font(name="Arial", size=10, italic=True, color="555555")
    for col_no, val in zip([4,5,6],[base,best,worst]):
        cell = ws2.cell(row=row_no, column=col_no)
        style_input(cell, val)
        if "%" in unit:
            fmt_pct(cell)
        else:
            fmt_inr(cell)
    ws2.cell(row=row_no, column=7).value = unit
    ws2.cell(row=row_no, column=7).font = Font(name="Arial", size=9, color="888888")

# Scenario switcher
ws2.merge_cells("A20:G20")
style_section_label(ws2["A20"], "  🎛️  SCENARIO SELECTOR — Change this cell to switch all forecasts")

ws2.merge_cells("B21:C21")
ws2["B21"].value = "Active Scenario (type exactly):"
ws2["B21"].font = Font(name="Arial", bold=True, size=11)
ws2["D21"].value = "Base Case"
ws2["D21"].font = Font(name="Arial", bold=True, color=BLUE_FONT, size=12)
ws2["D21"].fill = fill(GOLD)
ws2["D21"].alignment = align("center")
ws2["D21"].border = border_thin()
ws2["E21"].value = "← TYPE: Base Case / Best Case / Worst Case"
ws2["E21"].font = Font(name="Arial", italic=True, color="C00000", size=10)

ws2.merge_cells("A23:G28")
inst2 = ws2["A23"]
inst2.value = (
    "📋  ASSUMPTIONS GUIDE\n\n"
    "• Revenue Growth: Based on Infosys guidance. FY2025 growth was ~6%. Analyst consensus for FY26 is 7–9%.\n"
    "• OPM %: Infosys 5Y average ~23–25%. Best case assumes margin improvement from deal wins.\n"
    "• Tax Rate: Use 27% as base (FY2025 effective rate). Do not change unless you have a specific reason.\n"
    "• Depreciation & Interest: Keep flat unless you model capex separately.\n"
    "• SCENARIO SELECTOR (D21): This drives the Scenarios sheet. Type exactly 'Base Case', 'Best Case', or 'Worst Case'."
)
inst2.font = Font(name="Arial", size=9, color="1F3864")
inst2.fill = fill(LIGHT_BLUE)
inst2.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
ws2.row_dimensions[23].height = 110

set_col_widths(ws2, {"A":2,"B":22,"C":40,"D":14,"E":14,"F":14,"G":10})

# ══════════════════════════════════════════════════════════════════════════════
# SHEET 3 – Forecast_Model
# ══════════════════════════════════════════════════════════════════════════════
ws3 = wb.create_sheet("Forecast_Model")
ws3.sheet_properties.tabColor = "70AD47"

ws3.merge_cells("A1:H1")
c = ws3["A1"]
c.value = "INFOSYS LTD — 5-Year Forecast Model (FY2026–FY2030)  |  ₹ Crores  |  Linked to Assumptions sheet"
c.font = Font(name="Arial", bold=True, color=WHITE, size=12)
c.fill = fill(DARK_NAVY)
c.alignment = align("center")
ws3.row_dimensions[1].height = 22

ws3.merge_cells("A2:H2")
ws3["A2"].value = "⚫ All BLACK cells = formulas linked to Assumptions sheet.  Do NOT hardcode here.  🟢 Green = cross-sheet link."
ws3["A2"].font = Font(name="Arial", italic=True, color="444444", size=9)
ws3["A2"].fill = fill(LIGHT_BLUE)
ws3["A2"].alignment = align("center")

# Col headers
fcst_years = ["FY2026","FY2027","FY2028","FY2029","FY2030"]
for ci, lbl in enumerate(["","Line Item","FY2025\n(Actual)"] + fcst_years):
    cell = ws3.cell(row=3, column=ci+1)
    style_col_header(cell, lbl)
ws3.row_dimensions[3].height = 30

# P&L Section
ws3.merge_cells("A4:H4")
style_section_label(ws3["A4"], "  📊  FORECAST INCOME STATEMENT")

# Actual col = C (col 3). FY2026=D(4), FY2027=E(5), …FY2030=H(8)
# Revenue row = 5
FCST_ROWS = [
    (5,  "Revenue (Sales)",    True,  LIGHT_GOLD),
    (6,  "Operating Expenses", False, WHITE),
    (7,  "Operating Profit",   True,  LIGHT_GOLD),
    (8,  "OPM %",              True,  LIGHT_GOLD),
    (9,  "Other Income",       False, WHITE),
    (10, "Depreciation",       False, WHITE),
    (11, "Interest",           False, WHITE),
    (12, "PBT",                True,  LIGHT_GOLD),
    (13, "Tax",                False, WHITE),
    (14, "Net Profit",         True,  LIGHT_GOLD),
    (15, "Net Profit Margin %",True,  LIGHT_GOLD),
    (16, "EPS (₹)",            True,  LIGHT_GOLD),
]

# Actual FY2025 values in col C
actuals = {5:162990, 7:40757, 8:None, 9:3600, 10:4812, 11:416,
           12:37608, 13:10858, 14:26713, 15:None, 16:None}

for row_no, label, bold, bg in FCST_ROWS:
    ws3.cell(row=row_no, column=2).value = label
    ws3.cell(row=row_no, column=2).font = Font(name="Arial", bold=bold, size=10)
    ws3.cell(row=row_no, column=2).alignment = align("left")
    if bg != WHITE:
        ws3.cell(row=row_no, column=2).fill = fill(bg)

    # Actual col C
    cell_c = ws3.cell(row=row_no, column=3)
    cell_c.border = border_thin()
    cell_c.alignment = align("center")
    if row_no in actuals and actuals[row_no] is not None:
        cell_c.value = actuals[row_no]
        cell_c.font = Font(name="Arial", color=BLUE_FONT, bold=bold, size=10)
        fmt_inr(cell_c)
    elif row_no == 6:
        cell_c.value = "=C5-C7"
        cell_c.font = Font(name="Arial", color=BLACK, size=10)
        fmt_inr(cell_c)
    elif row_no == 8:
        cell_c.value = "=IF(C5>0,C7/C5,0)"
        cell_c.font = Font(name="Arial", bold=True, color=BLACK, size=10)
        fmt_pct(cell_c)
    elif row_no == 15:
        cell_c.value = "=IF(C5>0,C14/C5,0)"
        cell_c.font = Font(name="Arial", bold=True, color=BLACK, size=10)
        fmt_pct(cell_c)
    elif row_no == 16:
        cell_c.value = "=C14/4147"   # shares in crores approx
        cell_c.font = Font(name="Arial", bold=True, color=BLACK, size=10)
        cell_c.number_format = "₹#,##0.00"

    # Forecast cols D–H
    growth_rows = {5:5, 6:6, 7:7, 8:8, 9:9}   # Assumptions rows for rev growth
    opm_row_map  = {5:12, 6:13, 7:14}           # Assumptions OPM rows

    for ci in range(4, 9):   # col 4=D … col 8=H
        yr_idx = ci - 3       # 1=Y1 … 5=Y5
        prev_col = get_column_letter(ci-1)
        curr_col = get_column_letter(ci)
        cell = ws3.cell(row=row_no, column=ci)
        cell.border = border_thin()
        cell.alignment = align("center")
        if bg != WHITE:
            cell.fill = fill(bg)

        if row_no == 5:   # Revenue
            # Use CHOOSE on scenario selector
            cell.value = (
                f"=IF(Assumptions!$D$21=\"Best Case\","
                f"{prev_col}5*(1+Assumptions!E{4+yr_idx}),"
                f"IF(Assumptions!$D$21=\"Worst Case\","
                f"{prev_col}5*(1+Assumptions!F{4+yr_idx}),"
                f"{prev_col}5*(1+Assumptions!D{4+yr_idx})))"
            )
            cell.font = Font(name="Arial", bold=True, color=GREEN_FONT, size=10)
            fmt_inr(cell)
        elif row_no == 7:   # Op Profit = Revenue * OPM %
            cell.value = (
                f"=IF(Assumptions!$D$21=\"Best Case\","
                f"{curr_col}5*Assumptions!E12,"
                f"IF(Assumptions!$D$21=\"Worst Case\","
                f"{curr_col}5*Assumptions!F12,"
                f"{curr_col}5*Assumptions!D12))"
            )
            cell.font = Font(name="Arial", bold=True, color=GREEN_FONT, size=10)
            fmt_inr(cell)
        elif row_no == 6:   # Expenses
            cell.value = f"={curr_col}5-{curr_col}7"
            cell.font = Font(name="Arial", color=BLACK, size=10)
            fmt_inr(cell)
        elif row_no == 8:   # OPM %
            cell.value = f"=IF({curr_col}5>0,{curr_col}7/{curr_col}5,0)"
            cell.font = Font(name="Arial", bold=True, color=BLACK, size=10)
            fmt_pct(cell)
        elif row_no == 9:   # Other Income
            cell.value = (
                f"=IF(Assumptions!$D$21=\"Best Case\",Assumptions!E18,"
                f"IF(Assumptions!$D$21=\"Worst Case\",Assumptions!F18,Assumptions!D18))"
            )
            cell.font = Font(name="Arial", color=GREEN_FONT, size=10)
            fmt_inr(cell)
        elif row_no == 10:  # Depreciation
            cell.value = (
                f"=IF(Assumptions!$D$21=\"Best Case\",Assumptions!E16,"
                f"IF(Assumptions!$D$21=\"Worst Case\",Assumptions!F16,Assumptions!D16))"
            )
            cell.font = Font(name="Arial", color=GREEN_FONT, size=10)
            fmt_inr(cell)
        elif row_no == 11:  # Interest
            cell.value = (
                f"=IF(Assumptions!$D$21=\"Best Case\",Assumptions!E17,"
                f"IF(Assumptions!$D$21=\"Worst Case\",Assumptions!F17,Assumptions!D17))"
            )
            cell.font = Font(name="Arial", color=GREEN_FONT, size=10)
            fmt_inr(cell)
        elif row_no == 12:  # PBT
            cell.value = f"={curr_col}7+{curr_col}9-{curr_col}10-{curr_col}11"
            cell.font = Font(name="Arial", bold=True, color=BLACK, size=10)
            fmt_inr(cell)
        elif row_no == 13:  # Tax
            cell.value = f"={curr_col}12*Assumptions!D15"
            cell.font = Font(name="Arial", color=GREEN_FONT, size=10)
            fmt_inr(cell)
        elif row_no == 14:  # Net Profit
            cell.value = f"={curr_col}12-{curr_col}13"
            cell.font = Font(name="Arial", bold=True, color=BLACK, size=10)
            fmt_inr(cell)
        elif row_no == 15:  # NPM %
            cell.value = f"=IF({curr_col}5>0,{curr_col}14/{curr_col}5,0)"
            cell.font = Font(name="Arial", bold=True, color=BLACK, size=10)
            fmt_pct(cell)
        elif row_no == 16:  # EPS
            cell.value = f"={curr_col}14/4147"
            cell.font = Font(name="Arial", bold=True, color=BLACK, size=10)
            cell.number_format = "₹#,##0.00"

# Growth vs prior year rows
ws3.merge_cells("A18:H18")
style_section_label(ws3["A18"], "  📈  GROWTH vs PRIOR YEAR")

growth_labels = ["Revenue Growth %", "Net Profit Growth %", "OPM Expansion (bps)"]
src_rows = [5, 14, 8]
use_bps   = [False, False, True]

for i, (lbl, src, bps) in enumerate(zip(growth_labels, src_rows, use_bps)):
    r = 19 + i
    ws3.cell(row=r, column=2).value = lbl
    ws3.cell(row=r, column=2).font = Font(name="Arial", size=10)
    ws3.cell(row=r, column=2).alignment = align("left")
    ws3.cell(row=r, column=3).value = "—"
    ws3.cell(row=r, column=3).font = Font(name="Arial", color="888888", size=10)
    ws3.cell(row=r, column=3).alignment = align("center")
    for ci in range(4, 9):
        prev = get_column_letter(ci-1)
        curr = get_column_letter(ci)
        cell = ws3.cell(row=r, column=ci)
        cell.border = border_thin()
        cell.alignment = align("center")
        cell.font = Font(name="Arial", color=BLACK, size=10)
        if bps:
            cell.value = f"=IF({prev}{src}>0,({curr}{src}-{prev}{src})*10000,\"\")"
            cell.number_format = '0.0" bps"'
        else:
            cell.value = f"=IF({prev}{src}>0,({curr}{src}-{prev}{src})/{prev}{src},\"\")"
            fmt_pct(cell)

# Instruction box
ws3.merge_cells("A23:H28")
inst3 = ws3["A23"]
inst3.value = (
    "📋  FORECAST MODEL GUIDE\n\n"
    "• All GREEN cells pull from the Assumptions sheet — they update automatically when you change D21 in Assumptions.\n"
    "• To switch scenarios: Go to Assumptions sheet → Cell D21 → Type 'Base Case', 'Best Case', or 'Worst Case'\n"
    "• Revenue formula: Prior Year Revenue × (1 + Growth Rate) — growth rates are scenario-linked\n"
    "• Operating Profit = Revenue × OPM % — where OPM % changes by scenario\n"
    "• Net Profit = PBT − Tax   |   Tax = PBT × Tax Rate from Assumptions\n"
    "• EPS = Net Profit ÷ 4,147 Cr shares (approximate FY2025 share count)"
)
inst3.font = Font(name="Arial", size=9, color="1F3864")
inst3.fill = fill(LIGHT_BLUE)
inst3.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
ws3.row_dimensions[23].height = 110

set_col_widths(ws3, {"A":2,"B":26,"C":14,"D":13,"E":13,"F":13,"G":13,"H":13})

# ══════════════════════════════════════════════════════════════════════════════
# SHEET 4 – Scenarios
# ══════════════════════════════════════════════════════════════════════════════
ws4 = wb.create_sheet("Scenarios")
ws4.sheet_properties.tabColor = "ED7D31"

ws4.merge_cells("A1:I1")
c = ws4["A1"]
c.value = "INFOSYS LTD — Scenario Comparison  |  Base vs Best vs Worst  |  FY2026–FY2030"
c.font = Font(name="Arial", bold=True, color=WHITE, size=12)
c.fill = fill(DARK_NAVY)
c.alignment = align("center")
ws4.row_dimensions[1].height = 22

# Three scenario blocks side by side — rows 3 onwards
scenarios = [
    ("BASE CASE",  "D", MID_BLUE,  LIGHT_BLUE, "Base Case"),
    ("BEST CASE",  "E", "375623",  GREEN_BG,   "Best Case"),
    ("WORST CASE", "F", "C00000",  RED_BG,     "Worst Case"),
]

sc_metrics = [
    ("Revenue (₹ Cr)",      5, False),
    ("Operating Profit",    7, False),
    ("OPM %",               8, True),
    ("Net Profit (₹ Cr)",  14, False),
    ("NPM %",              15, True),
    ("EPS (₹)",            16, False),
]

# Header row
ws4.cell(row=3, column=2).value = "Metric"
ws4.cell(row=3, column=2).font = Font(name="Arial", bold=True, size=10)

start_cols = [3, 3+6, 3+12]   # each scenario block starts 6 cols apart

for sc_idx, (sc_name, asmpt_col, hdr_color, bg_color, sc_val) in enumerate(scenarios):
    base_col = start_cols[sc_idx]
    # Scenario header spanning 5 years
    ws4.merge_cells(
        start_row=2, start_column=base_col,
        end_row=2,   end_column=base_col+4
    )
    sc_cell = ws4.cell(row=2, column=base_col)
    sc_cell.value = sc_name
    sc_cell.font = Font(name="Arial", bold=True, color=WHITE, size=11)
    sc_cell.fill = fill(hdr_color)
    sc_cell.alignment = align("center")

    for yr_ci, yr in enumerate(fcst_years):
        yr_cell = ws4.cell(row=3, column=base_col+yr_ci)
        yr_cell.value = yr
        yr_cell.font = Font(name="Arial", bold=True, color=WHITE, size=10)
        yr_cell.fill = fill(MID_BLUE)
        yr_cell.alignment = align("center")

ws4.cell(row=3,column=2).fill = fill(MID_BLUE)
ws4.cell(row=3,column=2).font = Font(name="Arial",bold=True,color=WHITE,size=10)
ws4.row_dimensions[2].height = 22
ws4.row_dimensions[3].height = 22

# Now fill metric rows — pulling from Forecast_Model but overriding scenario
# We build a mini-model per scenario by replicating the key formulas with
# hardcoded scenario references.
# Revenue growth cols in Assumptions: Base=D, Best=E, Worst=F (rows 5–9)
# OPM: Base=D12,D13,D14 Best=E12 Worst=F12
asmpt_rev_col  = {"Base Case":"D", "Best Case":"E", "Worst Case":"F"}
asmpt_opm_cell = {"Base Case":"D12","Best Case":"E12","Worst Case":"F12"}
asmpt_oi_cell  = {"Base Case":"D18","Best Case":"E18","Worst Case":"F18"}
asmpt_dep_cell = {"Base Case":"D16","Best Case":"E16","Worst Case":"F16"}
asmpt_int_cell = {"Base Case":"D17","Best Case":"E17","Worst Case":"F17"}

for sc_idx, (sc_name, _, hdr_color, bg_color, sc_val) in enumerate(scenarios):
    base_col = start_cols[sc_idx]
    rc = asmpt_rev_col[sc_val]
    opm_c = asmpt_opm_cell[sc_val]
    oi_c  = asmpt_oi_cell[sc_val]
    dep_c = asmpt_dep_cell[sc_val]
    int_c = asmpt_int_cell[sc_val]

    # Build 5-year chain per metric
    # We'll store helper formulas row-by-row
    helper_rev = {}  # col_letter -> "rev formula"

    for yr_ci in range(5):
        yr_col = get_column_letter(base_col + yr_ci)
        asmpt_row = 5 + yr_ci  # Assumptions rows 5–9

        if yr_ci == 0:
            rev_formula = f"=162990*(1+Assumptions!{rc}{asmpt_row})"
        else:
            prev_yr_col = get_column_letter(base_col + yr_ci - 1)
            rev_formula = f"={prev_yr_col}5*(1+Assumptions!{rc}{asmpt_row})"
        helper_rev[yr_col] = rev_formula

    for m_idx, (m_label, src_row, is_pct) in enumerate(sc_metrics):
        r = 4 + m_idx

        # Label col
        lbl_cell = ws4.cell(row=r, column=2)
        lbl_cell.value = m_label if sc_idx == 0 else None
        lbl_cell.font = Font(name="Arial", bold=(not is_pct), size=10)
        lbl_cell.alignment = align("left")

        for yr_ci in range(5):
            yr_col = get_column_letter(base_col + yr_ci)
            asmpt_row = 5 + yr_ci
            cell = ws4.cell(row=r, column=base_col + yr_ci)
            cell.border = border_thin()
            cell.alignment = align("center")
            cell.fill = fill(bg_color)
            cell.font = Font(name="Arial", size=10, bold=(not is_pct))

            rev_col = yr_col
            if yr_ci == 0:
                rev_f = f"162990*(1+Assumptions!{rc}{asmpt_row})"
            else:
                p = get_column_letter(base_col+yr_ci-1)
                rev_f = f"{p}4*(1+Assumptions!{rc}{asmpt_row})"

            if m_label == "Revenue (₹ Cr)":
                if yr_ci == 0:
                    cell.value = f"=162990*(1+Assumptions!{rc}{asmpt_row})"
                else:
                    prev = get_column_letter(base_col+yr_ci-1)
                    cell.value = f"={prev}4*(1+Assumptions!{rc}{asmpt_row})"
                fmt_inr(cell)
            elif m_label == "Operating Profit":
                cell.value = f"={yr_col}4*Assumptions!{opm_c}"
                fmt_inr(cell)
            elif m_label == "OPM %":
                cell.value = f"=Assumptions!{opm_c}"
                fmt_pct(cell)
            elif m_label == "Net Profit (₹ Cr)":
                cell.value = (f"=({yr_col}5+Assumptions!{oi_c}-Assumptions!{dep_c}"
                              f"-Assumptions!{int_c})*(1-Assumptions!D15)")
                fmt_inr(cell)
            elif m_label == "NPM %":
                cell.value = f"=IF({yr_col}4>0,{yr_col}7/{yr_col}4,0)"
                fmt_pct(cell)
            elif m_label == "EPS (₹)":
                cell.value = f"={yr_col}7/4147"
                cell.number_format = "₹#,##0.00"

# Instruction
ws4.merge_cells("A11:I15")
inst4 = ws4["A11"]
inst4.value = (
    "📋  SCENARIO SHEET GUIDE\n\n"
    "• This sheet shows all 3 scenarios side by side for easy comparison.\n"
    "• BLUE = Base Case  |  GREEN = Best Case  |  RED/SALMON = Worst Case\n"
    "• All values auto-update when you change the Assumptions sheet.\n"
    "• KEY INSIGHT: Look at the spread between Best and Worst Net Profit — that is your risk range.\n"
    "• In real analyst work, this is shown in an 'Earnings Bridge' or 'Bull-Bear-Base' summary slide."
)
inst4.font = Font(name="Arial", size=9, color="1F3864")
inst4.fill = fill(LIGHT_BLUE)
inst4.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
ws4.row_dimensions[11].height = 100

set_col_widths(ws4, {"A":2,"B":22,"C":12,"D":12,"E":12,"F":12,"G":12,
                      "H":12,"I":12,"J":12,"K":12,"L":12,"M":12,"N":12,"O":12,"P":12,"Q":12})

# ══════════════════════════════════════════════════════════════════════════════
# SHEET 5 – Sensitivity
# ══════════════════════════════════════════════════════════════════════════════
ws5 = wb.create_sheet("Sensitivity")
ws5.sheet_properties.tabColor = "FF0000"

ws5.merge_cells("A1:N1")
c = ws5["A1"]
c.value = "INFOSYS LTD — Sensitivity Analysis  |  One-Variable & Two-Variable Data Tables"
c.font = Font(name="Arial", bold=True, color=WHITE, size=12)
c.fill = fill(DARK_NAVY)
c.alignment = align("center")
ws5.row_dimensions[1].height = 22

ws5.merge_cells("A2:N2")
ws5["A2"].value = "⚠️  HOW TO RUN DATA TABLES IN EXCEL: Select the table range → Data tab → What-If Analysis → Data Table → Enter Row/Column input cell"
ws5["A2"].font = Font(name="Arial", italic=True, color=RED_FONT, size=9, bold=True)
ws5["A2"].fill = fill("FFE6E6")
ws5["A2"].alignment = align("center")

# ── Table 1: Revenue Growth % (rows) vs OPM % (cols) → Net Profit FY2030 ──
ws5.merge_cells("A4:I4")
style_section_label(ws5["A4"], "  TABLE 1 — Net Profit FY2030 (₹ Cr)  |  Row: Revenue Growth %  |  Col: OPM %")

ws5.merge_cells("A5:B5")
ws5["A5"].value = "NET PROFIT\nFY2030"
ws5["A5"].font = Font(name="Arial", bold=True, color=WHITE, size=10)
ws5["A5"].fill = fill(DARK_NAVY)
ws5["A5"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
ws5.row_dimensions[5].height = 30

# OPM % column headers (cols C–I)
opm_vals = [0.18, 0.20, 0.22, 0.24, 0.245, 0.27, 0.29]
for ci, v in enumerate(opm_vals):
    cell = ws5.cell(row=5, column=3+ci)
    cell.value = v
    cell.font = Font(name="Arial", bold=True, color=WHITE, size=10)
    cell.fill = fill(MID_BLUE)
    cell.alignment = align("center")
    fmt_pct(cell)

# Revenue growth rows (rows 6–14)
rev_growth_vals = [0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16, 0.18]
for ri, rv in enumerate(rev_growth_vals):
    row = 6 + ri
    cell = ws5.cell(row=row, column=2)
    cell.value = rv
    cell.font = Font(name="Arial", bold=True, color=WHITE, size=10)
    cell.fill = fill(MID_BLUE)
    cell.alignment = align("center")
    fmt_pct(cell)

    for ci, ov in enumerate(opm_vals):
        cell = ws5.cell(row=row, column=3+ci)
        cell.border = border_thin()
        cell.alignment = align("center")
        # Simple approximation formula: Revenue*OPM + OtherIncome - Dep - Int, net of tax
        # Rev FY2030 = 162990*(1+rv)^5, Op Profit = Rev*ov, NP = (OpProfit+3100-5000-450)*(1-0.27)
        rev_approx = round(162990 * ((1+rv)**5))
        op = round(rev_approx * ov)
        np_val = round((op + 3100 - 5000 - 450) * (1 - 0.27))
        cell.value = np_val
        # Color-code: >30000 green, 20000-30000 yellow, <20000 red
        if np_val > 30000:
            cell.fill = fill(GREEN_BG)
            cell.font = Font(name="Arial", bold=True, color="375623", size=10)
        elif np_val > 20000:
            cell.fill = fill(YELLOW_INPUT)
            cell.font = Font(name="Arial", size=10)
        else:
            cell.fill = fill(RED_BG)
            cell.font = Font(name="Arial", bold=True, color=RED_FONT, size=10)
        fmt_inr(cell)

# ── Table 2: Rev Growth vs Net Profit Margin ─────────────────────────────────
ws5.merge_cells("A17:I17")
style_section_label(ws5["A17"], "  TABLE 2 — Net Profit Margin % FY2030  |  Row: Revenue Growth %  |  Col: OPM %")

ws5["A18"].value = "NPM %\nFY2030"
ws5["A18"].font = Font(name="Arial", bold=True, color=WHITE, size=10)
ws5["A18"].fill = fill(DARK_NAVY)
ws5["A18"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
ws5.row_dimensions[18].height = 30

for ci, v in enumerate(opm_vals):
    cell = ws5.cell(row=18, column=3+ci)
    cell.value = v
    cell.font = Font(name="Arial", bold=True, color=WHITE, size=10)
    cell.fill = fill(MID_BLUE)
    cell.alignment = align("center")
    fmt_pct(cell)

for ri, rv in enumerate(rev_growth_vals):
    row = 19 + ri
    cell = ws5.cell(row=row, column=2)
    cell.value = rv
    cell.font = Font(name="Arial", bold=True, color=WHITE, size=10)
    cell.fill = fill(MID_BLUE)
    cell.alignment = align("center")
    fmt_pct(cell)

    for ci, ov in enumerate(opm_vals):
        cell = ws5.cell(row=row, column=3+ci)
        cell.border = border_thin()
        cell.alignment = align("center")
        rev_approx = 162990 * ((1+rv)**5)
        op = rev_approx * ov
        np_val = (op + 3100 - 5000 - 450) * (1 - 0.27)
        npm = np_val / rev_approx if rev_approx > 0 else 0
        cell.value = npm
        fmt_pct(cell)
        if npm > 0.16:
            cell.fill = fill(GREEN_BG)
            cell.font = Font(name="Arial", bold=True, color="375623", size=10)
        elif npm > 0.13:
            cell.fill = fill(YELLOW_INPUT)
            cell.font = Font(name="Arial", size=10)
        else:
            cell.fill = fill(RED_BG)
            cell.font = Font(name="Arial", bold=True, color=RED_FONT, size=10)

# ── Legend ────────────────────────────────────────────────────────────────────
ws5.merge_cells("A30:I30")
style_section_label(ws5["A30"], "  🎨  COLOUR LEGEND")

legend = [
    (31, GREEN_BG,    "375623", "STRONG OUTCOME  — Net Profit > ₹30,000 Cr  |  NPM > 16%"),
    (32, YELLOW_INPUT,"806000", "MODERATE OUTCOME — Net Profit ₹20–30k Cr  |  NPM 13–16%"),
    (33, RED_BG,      RED_FONT, "WEAK OUTCOME    — Net Profit < ₹20,000 Cr  |  NPM < 13%"),
]
for row_no, bg, fc, txt in legend:
    ws5.merge_cells(f"A{row_no}:I{row_no}")
    cell = ws5[f"A{row_no}"]
    cell.value = txt
    cell.font = Font(name="Arial", bold=True, color=fc, size=10)
    cell.fill = fill(bg)
    cell.alignment = align("left")

# Instructions
ws5.merge_cells("A35:I41")
inst5 = ws5["A35"]
inst5.value = (
    "📋  SENSITIVITY ANALYSIS GUIDE\n\n"
    "TABLE 1: Shows FY2030 Net Profit (₹ Cr) across 9 Revenue Growth scenarios × 7 OPM scenarios.\n"
    "→ Find the row matching your revenue growth assumption. Trace across columns to see how margins impact profits.\n\n"
    "TABLE 2: Same matrix but shows Net Profit Margin % instead of absolute profit.\n"
    "→ More useful for comparing with peers or historical margins.\n\n"
    "TO BUILD LIVE DATA TABLES (advanced):\n"
    "1. In Forecast_Model, set up a single output cell (e.g., FY2030 Net Profit in H14)\n"
    "2. Create a table with Revenue Growth % in rows and OPM % in columns\n"
    "3. In the corner cell of the table, type =Forecast_Model!H14\n"
    "4. Select the full table range → Data → What-If Analysis → Data Table\n"
    "5. Row Input Cell = Assumptions!D5 (Revenue Growth Y1)  |  Column Input Cell = Assumptions!D12 (OPM)\n"
    "6. Excel will auto-fill every combination instantly."
)
inst5.font = Font(name="Arial", size=9, color="1F3864")
inst5.fill = fill(LIGHT_BLUE)
inst5.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
ws5.row_dimensions[35].height = 145

set_col_widths(ws5, {"A":3,"B":13,"C":12,"D":12,"E":12,"F":12,"G":12,"H":12,"I":12})

# ══════════════════════════════════════════════════════════════════════════════
# SHEET 6 – Dashboard
# ══════════════════════════════════════════════════════════════════════════════
ws6 = wb.create_sheet("Dashboard")
ws6.sheet_properties.tabColor = "808080"

ws6.merge_cells("A1:L1")
c = ws6["A1"]
c.value = "INFOSYS LTD — Financial Model Dashboard  |  Summary View"
c.font = Font(name="Arial", bold=True, color=WHITE, size=13)
c.fill = fill(DARK_NAVY)
c.alignment = align("center")
ws6.row_dimensions[1].height = 25

# KPI cards row
kpi_labels = ["FY2025 Revenue","FY2025 Net Profit","FY2025 OPM %","FY2025 NPM %",
              "FY2025 EPS (₹)","10Y Rev CAGR"]
kpi_formulas = [
    "=Historical_Data!L5",
    "=Historical_Data!L16",
    "=Historical_Data!L10",
    "=Historical_Data!L17",
    "=Historical_Data!L16/4147",
    "=Historical_Data!M5",
]
kpi_fmts = ["inr","inr","pct","pct","eps","pct"]

ws6.merge_cells("A3:L3")
ws6["A3"].value = "📊  KEY METRICS — FY2025 ACTUALS"
ws6["A3"].font = Font(name="Arial", bold=True, color=WHITE, size=11)
ws6["A3"].fill = fill(MID_BLUE)
ws6["A3"].alignment = align("left")

for i, (lbl, fml, fmt) in enumerate(zip(kpi_labels, kpi_formulas, kpi_fmts)):
    col_start = 1 + i*2
    ws6.merge_cells(start_row=4, start_column=col_start, end_row=4, end_column=col_start+1)
    ws6.merge_cells(start_row=5, start_column=col_start, end_row=5, end_column=col_start+1)

    lbl_cell = ws6.cell(row=4, column=col_start)
    lbl_cell.value = lbl
    lbl_cell.font = Font(name="Arial", bold=True, color=WHITE, size=9)
    lbl_cell.fill = fill(DARK_NAVY)
    lbl_cell.alignment = align("center")

    val_cell = ws6.cell(row=5, column=col_start)
    val_cell.value = fml
    val_cell.font = Font(name="Arial", bold=True, color=DARK_NAVY, size=13)
    val_cell.fill = fill(GOLD)
    val_cell.alignment = align("center")
    val_cell.border = border_thin()
    if fmt == "inr":
        fmt_inr(val_cell)
    elif fmt == "pct":
        fmt_pct(val_cell)
    elif fmt == "eps":
        val_cell.number_format = "₹#,##0.00"

ws6.row_dimensions[4].height = 20
ws6.row_dimensions[5].height = 30

# Forecast summary table
ws6.merge_cells("A7:L7")
ws6["A7"].value = "📈  FORECAST SUMMARY — BASE CASE"
ws6["A7"].font = Font(name="Arial", bold=True, color=WHITE, size=11)
ws6["A7"].fill = fill(MID_BLUE)
ws6["A7"].alignment = align("left")

for ci, yr in enumerate(["Metric"] + fcst_years):
    cell = ws6.cell(row=8, column=1+ci)
    style_col_header(cell, yr)

dash_metrics = [
    ("Revenue (₹ Cr)",       5),
    ("Net Profit (₹ Cr)",   14),
    ("OPM %",                8),
    ("NPM %",               15),
]

fm_cols = ["C","D","E","F","G","H"]  # C=FY2025, D=FY2026 ... H=FY2030
for ri, (m_lbl, m_row) in enumerate(dash_metrics):
    r = 9 + ri
    ws6.cell(row=r, column=1).value = m_lbl
    ws6.cell(row=r, column=1).font = Font(name="Arial", bold=True, size=10)
    ws6.cell(row=r, column=1).alignment = align("left")
    for ci in range(5):  # FY2026–FY2030
        cell = ws6.cell(row=r, column=2+ci)
        cell.value = f"=Forecast_Model!{fm_cols[ci+1]}{m_row}"
        cell.font = Font(name="Arial", color=GREEN_FONT, size=10)
        cell.border = border_thin()
        cell.alignment = align("center")
        if "%" in m_lbl:
            fmt_pct(cell)
        else:
            fmt_inr(cell)

# Scenario toggle reminder
ws6.merge_cells("A15:L15")
ws6["A15"].value = "🎛️  ACTIVE SCENARIO: Change cell Assumptions!D21 to switch between Base Case / Best Case / Worst Case"
ws6["A15"].font = Font(name="Arial", bold=True, color=RED_FONT, size=10)
ws6["A15"].fill = fill("FFF3CD")
ws6["A15"].alignment = align("center")

# Instructions
ws6.merge_cells("A17:L22")
inst6 = ws6["A17"]
inst6.value = (
    "📋  DASHBOARD GUIDE\n\n"
    "• TOP ROW (Gold cards): FY2025 actual figures pulled from Historical_Data sheet\n"
    "• FORECAST TABLE: Base Case projections for FY2026–FY2030 — auto-updates with scenario changes\n"
    "• TO ADD CHARTS: Select the Revenue or Net Profit row → Insert → Recommended Charts → Line Chart\n"
    "  Title your chart 'Infosys Revenue Forecast FY2026–FY2030'\n"
    "• Add a second chart for OPM % vs NPM % trend to visualise margin profile\n"
    "• This sheet is your 'boardroom-ready' view — everything else is the engine room"
)
inst6.font = Font(name="Arial", size=9, color="1F3864")
inst6.fill = fill(LIGHT_BLUE)
inst6.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
ws6.row_dimensions[17].height = 110

set_col_widths(ws6, {get_column_letter(i):14 for i in range(1,13)})
ws6.column_dimensions["A"].width = 22

# ── Final tab ordering & freeze panes ────────────────────────────────────────
ws1.freeze_panes = "C4"
ws2.freeze_panes = "D4"
ws3.freeze_panes = "C4"
ws4.freeze_panes = "C4"
ws5.freeze_panes = "C5"
ws6.freeze_panes = "B4"

out_path = "/home/claude/Infosys_Financial_Model.xlsx"
wb.save(out_path)
print("Saved:", out_path)