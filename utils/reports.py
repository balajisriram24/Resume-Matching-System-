import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import csv


def export_csv_report(resumes: list[dict]) -> io.BytesIO:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Candidate", "Match Score", "ATS Score", "Recommendation", "Skills", "Missing Skills"])
    for resume in resumes:
        writer.writerow([resume.get("full_name", ""), "", "", "", "", ""])
    return io.BytesIO(output.getvalue().encode("utf-8"))


def export_pdf_report(resumes: list[dict]) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = [Paragraph("Resume Matching Report", styles["Title"]), Spacer(1, 12)]
    data = [["Candidate", "Recommendation", "Skills"]]
    for resume in resumes:
        data.append([resume.get("full_name", ""), "Pending", ""])
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4f8f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer
