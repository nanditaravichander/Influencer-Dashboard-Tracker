"""Builds influencer-data-template.xlsx and sample-data.xlsx."""
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from sample_data import make_sample

FONT = "Arial"
HEAD_FILL = PatternFill("solid", fgColor="5438DC")
INPUT_FILL = PatternFill("solid", fgColor="FFF8DC")


def style_sheet(ws, widths, n_rows=1):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for c in ws[1]:
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = HEAD_FILL
        c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30
    for row in ws.iter_rows(min_row=2, max_row=max(2, n_rows + 1)):
        for c in row:
            c.font = Font(name=FONT)
    ws.freeze_panes = "A2"


def template(path):
    wb = Workbook()
    rm = wb.active
    rm.title = "Read me"
    lines = [
        ("How to use this workbook", True),
        ("1. Go to the Posts sheet and add one row per piece of creator content. Delete the example row first.", False),
        ("2. Optional: fill in the Community sheet (new creator contacts per month) and the UGC sheet (user-generated posts per month).", False),
        ("3. Upload this file to the dashboard. Everything updates straight away.", False),
        ("", False),
        ("Posts sheet columns", True),
        ("Required: Date, Platform, Reach, and either Engagements or the four Likes / Comments / Shares / Saves columns.", False),
        ("Recommended: Creator, Followers (the dashboard works out the tier), Collaboration (Gifted or Paid), Campaign, Fee, Product Value, Disclosed (Yes or No).", False),
        ("Cost per engagement uses Fee + Product Value. Leave Fee at 0 for gifted posts.", False),
        ("Tier bands from Followers: Nano under 10k, Micro 10k to 50k, Mid 50k to 250k, Macro 250k and over. You can add a Tier column to override this.", False),
        ("", False),
        ("Cells with a cream background are for you to fill in. Rows whose Creator starts with 'Example creator' are ignored.", False),
        ("Use anonymised or rounded figures if your numbers are confidential.", False),
    ]
    for i, (t, bold) in enumerate(lines, 1):
        c = rm.cell(row=i, column=1, value=t)
        c.font = Font(name=FONT, bold=bold, size=12 if bold else 10)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    rm.column_dimensions["A"].width = 110

    ws = wb.create_sheet("Posts")
    heads = ["Date", "Creator", "Platform", "Followers", "Collaboration", "Campaign", "Reach",
             "Likes", "Comments", "Shares", "Saves", "Fee", "Product Value", "Disclosed"]
    ws.append(heads)
    ws.append([pd.Timestamp("2025-10-14").to_pydatetime(), "Example creator (delete this row)", "Instagram", 28000,
               "Paid", "Christmas gift range", 21500, 980, 64, 45, 120, 250, 18, "Yes"])
    style_sheet(ws, [12, 30, 13, 11, 15, 24, 10, 9, 10, 9, 9, 9, 14, 11])
    for r in range(2, 2000):
        ws.cell(row=r, column=1).number_format = "dd/mm/yyyy"
    for r in range(2, 3):
        for c in range(1, 15):
            ws.cell(row=r, column=c).fill = INPUT_FILL
    for col, items in (("C", '"Instagram,TikTok,YouTube"'), ("E", '"Gifted,Paid"'), ("N", '"Yes,No"')):
        dv = DataValidation(type="list", formula1=items, allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"{col}2:{col}1999")

    cm = wb.create_sheet("Community")
    cm.append(["Month", "New Contacts"])
    cm.append([pd.Timestamp("2025-10-01").to_pydatetime(), 38])
    style_sheet(cm, [14, 14])
    for r in range(2, 60):
        cm.cell(row=r, column=1).number_format = "mmm yyyy"
    for c in (1, 2):
        cm.cell(row=2, column=c).fill = INPUT_FILL

    ug = wb.create_sheet("UGC")
    ug.append(["Month", "Platform", "Pieces"])
    ug.append([pd.Timestamp("2025-10-01").to_pydatetime(), "Instagram", 58])
    style_sheet(ug, [14, 14, 10])
    for r in range(2, 200):
        ug.cell(row=r, column=1).number_format = "mmm yyyy"
    for c in (1, 2, 3):
        ug.cell(row=2, column=c).fill = INPUT_FILL
    wb.save(path)


def sample(path):
    posts, community, ugc = make_sample()
    with pd.ExcelWriter(path, engine="openpyxl", datetime_format="dd/mm/yyyy") as w:
        posts.to_excel(w, sheet_name="Posts", index=False)
        community.to_excel(w, sheet_name="Community", index=False)
        ugc.to_excel(w, sheet_name="UGC", index=False)
    wb = load_workbook(path)
    for name, widths in (("Posts", [12, 14, 13, 11, 15, 24, 10, 9, 10, 9, 9, 9, 14, 11]),
                         ("Community", [14, 14]), ("UGC", [14, 14, 10])):
        style_sheet(wb[name], widths, wb[name].max_row)
    wb.save(path)


if __name__ == "__main__":
    template("influencer-data-template.xlsx")
    sample("sample-data.xlsx")
    print("done")
