from datetime import datetime

from fpdf import FPDF


def generate_application_pdf(app, analysis_data: dict) -> bytes:
    """Generates a professional PDF report for an application using fpdf2."""

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(190, 20, "Candway AI Evaluation Report", ln=1, align="C")
    pdf.line(10, 30, 200, 30)
    pdf.ln(10)

    # Candidate Info
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(190, 10, f"Candidate: {app.full_name}", ln=1)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(190, 8, f"Role: {app.declared_role or 'N/A'}", ln=1)
    _er = (
        app.evaluation_sessions[0].evaluation_result
        if app.evaluation_sessions and app.evaluation_sessions[0].evaluation_result
        else None
    )
    pdf.cell(190, 8, f"Final Score: {int(_er.final_score or 0) if _er else 0}%", ln=1)
    pdf.ln(5)

    # Verdict
    verdict = analysis_data.get("verdict", "N/A").upper()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 10, "Final Verdict:", ln=1)
    pdf.set_font("Helvetica", "", 12)
    pdf.multi_cell(190, 8, f"RECRUITER RECOMMENDATION: {verdict}")
    pdf.ln(5)

    # Skill Metrics
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 10, "Technical Talent Graph:", ln=1)
    pdf.set_font("Helvetica", "", 12)
    skill_metrics = analysis_data.get("skill_metrics", {})
    if isinstance(skill_metrics, dict):
        for skill, score in skill_metrics.items():
            pdf.cell(190, 7, f"- {skill}: {int(score)}%", ln=1)
    pdf.ln(5)

    # Strengths
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 10, "Key Strengths:", ln=1)
    pdf.set_font("Helvetica", "", 12)
    strengths = analysis_data.get("strengths", [])
    if isinstance(strengths, str):
        strengths = [strengths]
    for s in strengths:
        pdf.multi_cell(190, 7, f"* {s}")

    pdf.ln(5)

    # Weaknesses
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 10, "Critical Gaps:", ln=1)
    pdf.set_font("Helvetica", "", 12)
    weaknesses = analysis_data.get("weaknesses", [])
    if isinstance(weaknesses, str):
        weaknesses = [weaknesses]
    for w in weaknesses:
        pdf.multi_cell(190, 7, f"* {w}")

    pdf.ln(5)

    # AI Reasoning
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 10, "AI Reasoning & Explainability:", ln=1)
    pdf.set_font("Helvetica", "", 12)
    reasoning = analysis_data.get("explainability", {}).get(
        "reasoning", "No detailed reasoning provided."
    )
    pdf.multi_cell(190, 7, str(reasoning))

    # Footer
    pdf.set_y(-30)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(
        190,
        10,
        f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        align="C",
        ln=1,
    )
    pdf.cell(190, 10, f"Page {pdf.page_no()}", align="C")

    return pdf.output()
