from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

def create_memo():
    doc = Document()

    # Set margins to ensure it fits on 2 pages
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Header
    header = doc.add_paragraph()
    header.add_run("MEMORANDUM").bold = True
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    p = doc.add_paragraph()
    p.add_run("TO: ").bold = True
    p.add_run("Fleet Management\n")
    p.add_run("FROM: ").bold = True
    p.add_run("Fleet Analysis Team\n")
    p.add_run("DATE: ").bold = True
    p.add_run("Sunday, 4 October 2026\n")
    p.add_run("SUBJECT: ").bold = True
    p.add_run("Recommendation on Fleet Transition to Battery-Electric Tractors")

    doc.add_paragraph("-" * 50)

    # Executive Recommendation
    doc.add_heading("Executive Recommendation", level=1)
    rec_text = (
        "Recommendation: NO\n\n"
        "Based on the 7-year Total Cost of Ownership (TCO) analysis, it is not financially advisable "
        "to replace the current diesel fleet with battery-electric (BEV) tractors at this time. "
        "The TCO for a BEV tractor is estimated at $532,800, compared to $498,400 for a diesel tractor. "
        "This represents an additional cost of $34,400 per truck, or a total fleet premium of $688,000 "
        "over seven years.\n\n"
        "While the BEV option offers significant operational advantages and cost savings in fuel and "
        "maintenance—reducing energy costs by approximately 63% and maintenance by approximately 33% "
        "per mile—these savings are insufficient to offset the higher initial purchase price and the "
        "substantial investment required for charging infrastructure ($1,000,000 [unverified] for the fleet)."
    )
    doc.add_paragraph(rec_text)

    # Operational Note
    op_para = doc.add_paragraph()
    op_para.add_run("Operational Note:").bold = True
    op_note = (
        " From a technical standpoint, the transition is highly feasible. The regional routes "
        "(< 250 miles/day) are well within the capabilities of 2026 BEV technology. If the organization "
        "prioritizes carbon reduction or anticipates future regulatory penalties for diesel emissions "
        "that exceed $34,400 per truck over seven years, the BEV option remains a viable operational alternative."
    )
    op_para.add_run(op_note)

    # TCO Comparison Table
    doc.add_heading("7-Year TCO Comparison (Per Truck)", level=1)
    table_data = [
        ["Cost Category", "Diesel per Truck", "BEV per Truck", "Notes"],
        ["Purchase Price (Net)", "$175,000 [unverified]", "$340,000", "BEV: $380,000 [unverified] minus $40,000 Federal 45W Credit [S14, S15]"],
        ["Fuel / Energy Cost", "$247,800", "$92,400", "(60,000 * 7) miles; Diesel $0.59/mi [S6], BEV $0.22/mi [S6]"],
        ["Maintenance Cost", "$75,600", "$50,400", "(60,000 * 7) miles; Diesel $0.18/mi [unverified], BEV $0.12/mi [unverified]"],
        ["Charging Infrastructure", "$0", "$50,000", "$1,000,000 total fleet cost [unverified] / 20 trucks"],
        ["Total 7-Year TCO", "$498,400", "$532,800", "BEV is $34,400 more expensive per truck"]
    ]

    table = doc.add_table(rows=len(table_data), cols=len(table_data[0]))
    table.style = 'Table Grid'
    
    for i, row in enumerate(table_data):
        for j, cell_text in enumerate(row):
            cell = table.cell(i, j)
            cell.text = cell_text
            if i == 0:
                cell.paragraphs[0].runs[0].bold = True

    # Key Assumptions
    doc.add_heading("Key Assumptions", level=1)
    assumptions = [
        "Operational Window: 60,000 miles per truck per year for 7 years (Total: 420,000 miles).",
        "Diesel Efficiency: 6.5 MPG [S6] with a fuel price of $3.85/gal [unverified], resulting in $0.59/mile.",
        "BEV Efficiency: 2.0 kWh/mile [S6] with a commercial electricity rate of $0.11/kWh [unverified], resulting in $0.22/mile.",
        "Maintenance: Diesel maintenance is $0.18/mile [unverified]; BEV maintenance is $0.12/mile [unverified].",
        "Infrastructure: Total depot installation cost of $1,000,000 [unverified] for 20 trucks ($50,000 per truck).",
        "Incentives: Federal 45W Credit of $40,000 per truck [S14, S15] is applied. No fixed Indiana state grants are available [S13].",
        "Purchase Price: 2026 projected market pricing of $175,000 for diesel and $380,000 for BEV [unverified]."
    ]
    for assumption in assumptions:
        doc.add_paragraph(assumption, style='List Bullet')

    # Citations
    doc.add_heading("Citations", level=1)
    citations_text = (
        "[S6] Fuel/Energy Efficiency and Pricing Data\n"
        "[S13] Indiana State Incentive Data\n"
        "[S14, S15] Federal 45W Commercial Clean Vehicle Credit Data\n"
        "[unverified] Market projections and internal maintenance estimates"
    )
    doc.add_paragraph(citations_text)

    doc.save("TCO_Memo.docx")

if __name__ == "__main__":
    create_memo()
