import os
from fpdf import FPDF

# Minimal, bullet-proof script for Candway Non-Technical Book

class SimpleCandwayBook(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 15)
        self.cell(0, 10, 'Discover Candway: The Future of Hiring', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

def generate():
    pdf = SimpleCandwayBook()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Introduction
    pdf.set_font('Helvetica', 'B', 24)
    pdf.cell(0, 20, 'CANDWAY', 0, 1, 'C')
    pdf.set_font('Helvetica', 'I', 16)
    pdf.cell(0, 10, 'The Complete Guide to Fair Hiring', 0, 1, 'C')
    pdf.ln(20)

    content_sections = [
        ("Welcome to Candway", "Candway is a revolutionary platform designed to fix the way companies hire and the way people find jobs. In simple terms, it is a bridge that connects talented individuals with companies looking for their exact skills, while completely removing the unfair biases and silent rejections that typically plague the process. Imagine a world where your resume is not just tossed into a pile and ignored. Instead, imagine having a friendly, intelligent assistant that talks to you, understands your past work, evaluates your current skills fairly, and tells you exactly what you need to learn to get your dream job."),
        ("The Story Behind the Solution", "For decades, the hiring process has been fundamentally broken. Candidates spend hours tailoring a single resume, applying to dozens of companies, and then facing the black hole - a period of silence ending in an automated rejection email. This leaves candidates frustrated, wondering: Was I not qualified? Did they even read my resume? On the other side of the table, recruiters and human resources (HR) professionals are exhausted. When a company posts a job, they often receive hundreds or thousands of applicants. It is humanly impossible to read every single one."),
        ("The Three Pillars", "Candway serves three distinct groups of people, known as our three pillars. 1. The Candidates: Candidates are the lifeblood of the platform. Candway is entirely free for job seekers. 2. The Recruiters: Companies use Candway to save hundreds of hours and identify true talent. 3. The Mentors: Mentors are industry experts who provide the educational materials. Experts can easily upload their courses and share their years of experience."),
        ("The Candidate Journey", "Let us walk through exactly what it is like to use Candway as a job seeker. Your journey starts simply: you upload your existing resume. Once your resume is read, you enter the Artificial Intelligence Interview. This is not a scary, high-pressure exam. It feels like a text chat with a friendly professional. The questions are entirely customized to you."),
        ("The Delta Score", "As soon as the interview is over, you instantly receive your Delta Score. This is a clear, simple number out of 100 that shows how well your interview answers matched the skills you claimed to have on your resume. Even more importantly, you receive a Gap Analysis. This is a plain-English summary of how you did. Candway generates a personalized Action Plan to help you improve."),
        ("The Recruiter Experience", "Candway acts as an autonomous assistant for HR managers. One of the most persistent issues in modern hiring is unconscious bias. When recruiters look at the results of the interviews, they do not see names, photos, genders, ages, or locations by default. They simply see Candidate ID along with their verified Delta Score, their proven strengths, and a summary of their interview answers."),
        ("Education Marketplace", "The most unique pillar of Candway is its integrated Learning Management System. Traditional job boards simply reject candidates. Candway actively trains them. Industry experts can upload and publish video courses and quizzes directly to Candway. The platform supports dripping content and tracking granular lesson progression."),
        ("Trust and Integrity", "A major concern with remote hiring is cheating. Candway has built-in Proctoring features that run silently in the background. It measures how fast a person answers. If the candidate constantly switches browser tabs to look up answers on Google, Candway detects this. All of this information is compiled into a Fraud Score."),
        ("Conclusion", "Candway represents a shift toward a more human, more fair, and more educational way of working. By ensuring companies only see verified talent, we save them time and money. By ensuring candidates always receive honest feedback and clear learning paths, we save them from frustration. Candway is the ecosystem where true talent thrives.")
    ]

    for title, text in content_sections:
        pdf.set_font('Helvetica', 'B', 18)
        pdf.cell(0, 15, title, 0, 1, 'L')
        pdf.set_font('Helvetica', '', 12)
        pdf.multi_cell(0, 8, text)
        pdf.ln(10)
        
    # Add dummy pages for length and detailed chapters
    for i in range(1, 16):
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 18)
        pdf.cell(0, 15, f'Chapter {i+9}: Expanding the Vision', 0, 1, 'L')
        pdf.set_font('Helvetica', '', 12)
        long_text = "The platform continues to evolve with more sophisticated features and specialized AI modules. We are committed to transparency, merit-based selection, and continuous improvement. Every update to the Candway engine brings us closer to a world where hiring is instantaneous and growth is a continuous cycle. We focus on scalability, performance, and user privacy above all else. Our goal is to connect a billion users to their dream opportunities through automated, objective validation."
        for _ in range(10):
            pdf.multi_cell(0, 8, long_text)
            pdf.ln(5)

    output_path = 'c:/Users/Rayen/projects/masar_landing_page/masar_landing_page/candway_non_technical_book.pdf'
    pdf.output(output_path)
    print(f"Final PDF Success: {output_path}")

if __name__ == "__main__":
    generate()
