import os
import tempfile

import qrcode
from fpdf import FPDF


class PDFReport(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 10, "Candway Intelligence Report", 0, 1, "C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")


def _latin1_safe(value) -> str:
    """Coerce a value to a latin-1-safe string.

    FPDF's built-in Helvetica font only supports the latin-1 charset, so
    non-latin-1 characters (e.g. Arabic client names/addresses) crash the
    PDF output. Unsupported characters are replaced so the PDF always
    renders instead of failing with a 500.
    """
    text = str(value if value is not None else "")
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_pdf_report(analysis_data: dict) -> bytes:
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", size=12)

    # Title Section
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Role Analyzed: {analysis_data.get('role', 'N/A')}", ln=True)
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, f"Match Score: {analysis_data.get('score', 0)}/100", ln=True)
    pdf.cell(0, 10, f"Verdict: {analysis_data.get('verdict', 'N/A')}", ln=True)
    pdf.ln(5)

    # Summary
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "Summary", ln=True)
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 10, analysis_data.get("summary", "No summary available."))
    pdf.ln(5)

    # Strengths
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "Key Strengths", ln=True)
    pdf.set_font("Helvetica", size=11)
    for strength in analysis_data.get("strengths", []):
        pdf.cell(0, 8, f"- {strength}", ln=True)
    pdf.ln(5)

    # Weaknesses
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "Areas for Improvement", ln=True)
    pdf.set_font("Helvetica", size=11)
    for weakness in analysis_data.get("weaknesses", []):
        pdf.cell(0, 8, f"- {weakness}", ln=True)
    pdf.ln(5)

    # Action Plan
    if "action_plan" in analysis_data:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Recommended Action Plan", ln=True)
        pdf.set_font("Helvetica", size=11)
        for item in analysis_data["action_plan"]:
            pdf.multi_cell(0, 8, f"- {item}")

    return bytes(pdf.output(dest="S"), "latin-1")


def generate_certificate_pdf(data: dict) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()

    data = {
        key: (_latin1_safe(value) if isinstance(value, str) else value)
        for key, value in data.items()
    }

    # Border
    pdf.set_line_width(2)
    pdf.set_draw_color(79, 70, 229)  # Indigo
    pdf.rect(10, 10, 277, 190)

    # Icon/Logo Placeholder
    pdf.set_fill_color(238, 242, 255)  # Indigo 50
    pdf.rect(128, 20, 40, 40, "F")
    pdf.set_font("Helvetica", "B", 30)
    pdf.set_text_color(79, 70, 229)
    pdf.set_xy(128, 20)
    pdf.cell(40, 40, "M", 0, 0, "C")

    # Title
    pdf.set_y(70)
    pdf.set_text_color(17, 24, 39)  # Slate 900
    pdf.set_font("Helvetica", "B", 40)
    pdf.cell(0, 20, "Certificate of Completion", 0, 1, "C")

    # Subtitle
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(107, 114, 128)  # Slate 500
    pdf.cell(0, 10, "This is to certify that", 0, 1, "C")

    # Recipient
    pdf.set_y(110)
    pdf.set_font("Helvetica", "B", 30)
    pdf.set_text_color(31, 41, 55)
    pdf.cell(0, 15, data.get("recipient_name", "Student Name"), 0, 1, "C")

    # Course
    pdf.set_y(130)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(0, 10, "has successfully completed the course", 0, 1, "C")

    pdf.set_y(140)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(79, 70, 229)  # Indigo 600
    pdf.cell(0, 15, data.get("course_title", "Course Title"), 0, 1, "C")

    # Footer Info
    pdf.set_y(170)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(75, 85, 99)

    # Left: Instructor
    pdf.set_x(40)
    pdf.cell(80, 5, "Instructor", 0, 1, "C")
    pdf.set_x(40)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(80, 10, data.get("instructor_name", "Candway Instructor"), "T", 0, "C")

    # Right: Date & ID
    pdf.set_y(170)
    pdf.set_x(177)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(80, 5, f"Date: {data.get('issued_at', '')}", 0, 1, "C")
    pdf.set_x(177)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(80, 10, f"ID: {data.get('certificate_id', '')}", "T", 0, "C")

    return bytes(pdf.output(dest="S"), "latin-1")


def generate_invoice_pdf(data: dict) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()

    # Sanitize user-provided text (client names/addresses may be Arabic or
    # otherwise non-latin-1) so the built-in Helvetica font never crashes.
    data = {
        key: (_latin1_safe(value) if isinstance(value, str) else value)
        for key, value in data.items()
    }

    # 1. Colors & Branding
    PRIMARY_COLOR = (79, 70, 229)  # Indigo 600
    TEXT_COLOR = (31, 41, 55)  # Slate 800
    MUTED_COLOR = (107, 114, 128)  # Slate 500

    # Header Logo/Title
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(*PRIMARY_COLOR)
    pdf.cell(100, 10, "CANDWAY", 0, 0)

    # Invoice Title (Right aligned)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*TEXT_COLOR)
    pdf.cell(0, 10, "INVOICE", 0, 1, "R")
    pdf.ln(2)

    # Sub-header Line
    pdf.set_draw_color(*PRIMARY_COLOR)
    pdf.set_line_width(0.5)
    pdf.line(10, 25, 200, 25)
    pdf.ln(10)

    # 2. Company & Client Info (Two columns)
    curr_y = pdf.get_y()

    # Left: Seller Details
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*TEXT_COLOR)
    pdf.cell(95, 5, "FROM:", 0, 1)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED_COLOR)
    pdf.multi_cell(
        95,
        5,
        "Candway Intelligence Platform\nTechnopole de Sfax\nSfax, Tunisia\nMF: 1234567/A/M/000",
    )  # Dummy admin MF

    # Right: Client Details
    pdf.set_xy(110, curr_y)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*TEXT_COLOR)
    pdf.cell(0, 5, "BILL TO:", 0, 1)
    pdf.set_x(110)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*TEXT_COLOR)
    pdf.cell(0, 7, data.get("client_name", "Client Name"), 0, 1)
    pdf.set_x(110)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED_COLOR)

    client_address = data.get("client_address") or "N/A"
    client_mf = data.get("client_mf") or "N/A"
    pdf.multi_cell(0, 5, f"Address: {client_address}\nMF: {client_mf}")

    pdf.ln(10)

    # 3. Invoice Summary Grid (Transparent box)
    pdf.set_fill_color(249, 250, 251)  # Gray 50
    pdf.rect(10, pdf.get_y(), 190, 20, "F")

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*MUTED_COLOR)
    pdf.cell(47.5, 8, "INVOICE NUMBER", 0, 0, "C")
    pdf.cell(47.5, 8, "DATE OF ISSUE", 0, 0, "C")
    pdf.cell(47.5, 8, "ORDER ID", 0, 0, "C")
    pdf.cell(47.5, 8, "STATUS", 0, 1, "C")

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*TEXT_COLOR)
    pdf.cell(47.5, 8, data.get("invoice_number", "INV-0000"), 0, 0, "C")
    pdf.cell(47.5, 8, data.get("date", "N/A"), 0, 0, "C")
    pdf.cell(47.5, 8, f"#{data.get('transaction_id', 'N/A')}", 0, 0, "C")

    status = (data.get("status", "PAID")).upper()
    if status == "PAID":
        pdf.set_text_color(16, 185, 129)  # Emerald
    else:
        pdf.set_text_color(245, 158, 11)  # Amber
    pdf.cell(47.5, 8, status, 0, 1, "C")

    pdf.ln(12)

    # 4. Items Table Header
    pdf.set_fill_color(*PRIMARY_COLOR)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(110, 10, " DESCRIPTION", 0, 0, "L", True)
    pdf.cell(40, 10, "UNIT PRICE", 0, 0, "R", True)
    pdf.cell(40, 10, "SUBTOTAL (HT) ", 0, 1, "R", True)

    # Item Row
    pdf.set_text_color(*TEXT_COLOR)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        110,
        15,
        f" {data.get('description', 'Platform Service Subscription')}",
        "B",
        0,
        "L",
    )
    pdf.cell(40, 15, f"{data.get('amount_ht', 0.000):.3f} TND", "B", 0, "R")
    pdf.cell(40, 15, f"{data.get('amount_ht', 0.000):.3f} TND", "B", 1, "R")

    pdf.ln(10)

    # 5. Financial Summary (Aligned to bottom right)
    pdf.set_x(120)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED_COLOR)
    pdf.cell(40, 8, "Total HT:", 0, 0, "L")
    pdf.set_text_color(*TEXT_COLOR)
    pdf.cell(30, 8, f"{data.get('amount_ht', 0.000):.3f} TND", 0, 1, "R")

    pdf.set_x(120)
    pdf.set_text_color(*MUTED_COLOR)
    pdf.cell(40, 8, f"TVA ({data.get('tva_rate', 19)}%):", 0, 0, "L")
    pdf.set_text_color(*TEXT_COLOR)
    pdf.cell(30, 8, f"{data.get('tva_amount', 0.000):.3f} TND", 0, 1, "R")

    pdf.set_x(120)
    pdf.set_text_color(*MUTED_COLOR)
    pdf.cell(40, 8, "Timbre Fiscal:", 0, 0, "L")
    pdf.set_text_color(*TEXT_COLOR)
    pdf.cell(30, 8, f"{data.get('stamp_duty', 1.000):.3f} TND", 0, 1, "R")

    # Grand Total
    pdf.ln(2)
    pdf.set_x(120)
    pdf.set_fill_color(*PRIMARY_COLOR)
    pdf.rect(120, pdf.get_y(), 80, 10, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(40, 10, "TOTAL TTC:", 0, 0, "L")
    pdf.cell(30, 10, f"{data.get('total_ttc', 0.000):.3f} TND", 0, 1, "R")

    # 6. Footer Legal Info
    pdf.set_y(-40)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*MUTED_COLOR)
    pdf.multi_cell(
        0,
        4,
        "Terms & Conditions:\nPlease settle the invoice within the agreed timeframe. This is an electronically generated invoice valid according to Tunisian finance law. Payments can be made via bank transfer or Konnect portal.",
        0,
        "C",
    )

    # Final Stamp Placeholder
    pdf.set_y(-35)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(0, 5, "Candway Intelligence Platform - Digital Signature Valid", 0, 0, "C")

    # 7. EL FATOORA QR CODE (Visible Electronic Stamp)
    # Encode key data: InvoiceNo | Date | TotalTTC | MF
    qr_data = f"MIP:{data.get('invoice_number')}:{data.get('date')}:{data.get('total_ttc')}:{client_mf}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        img.save(tmp.name)
        tmp_path = tmp.name

    # Embed QR Code (Bottom Left)
    pdf.image(tmp_path, x=10, y=250, w=25, h=25)

    # Cleanup
    try:
        os.unlink(tmp_path)
    except Exception:
        pass

    return bytes(pdf.output(dest="S"), "latin-1")
