"""
Fallback Question Bank - Scenario-based questions when all AI providers fail.
Covers 12+ roles with Tunisian tech market context.
"""

FALLBACK_QUESTIONS = {
    "software": [
        {
            "question": "You're at a Tunisian fintech company and your payment API starts returning 500 errors for 20% of transactions during a Friday deployment. The offshore client in Paris calls urgently. What's your first step?",
            "options": [
                "A. Roll back the deployment immediately",
                "B. Check the error logs and identify the failing endpoint",
                "C. Add more servers to handle the load",
                "D. Tell the client you'll fix it Monday",
            ],
            "correct_answer": "B. Check the error logs and identify the failing endpoint",
            "evaluation": "Good incident response — diagnose before acting.",
            "cv_reference": "Backend Experience",
        },
        {
            "question": "Your team inherited a legacy PHP monolith with no tests, serving 50K daily users. The client wants microservices in 6 months. What do you prioritize first?",
            "options": [
                "A. Rewrite everything from scratch in Node.js",
                "B. Add integration tests to critical paths, then extract services one by one",
                "C. Hire more developers to speed up",
                "D. Switch to a no-code platform",
            ],
            "correct_answer": "B. Add integration tests to critical paths, then extract services one by one",
            "evaluation": "Excellent — strangler fig pattern is the safe approach.",
            "cv_reference": "Architecture",
        },
        {
            "question": "A Tunisian e-commerce site experiences 12-second page loads during a sale. Stack: Spring Boot + PostgreSQL + React. Where do you investigate first?",
            "options": [
                "A. Check database slow queries",
                "B. Rewrite the frontend in Vue.js",
                "C. Add more RAM to all servers",
                "D. Disable all JavaScript",
            ],
            "correct_answer": "A. Check database slow queries",
            "evaluation": "Database is usually the bottleneck — good instinct.",
            "cv_reference": "Performance",
        },
        {
            "question": "Your Tunisian startup needs payment integration but Stripe doesn't work in Tunisia. Which approach makes the most sense?",
            "options": [
                "A. Build your own payment system from scratch",
                "B. Integrate with local providers like Flouci, D17, or Konnect",
                "C. Wait for Stripe to launch in Tunisia",
                "D. Only accept cash on delivery",
            ],
            "correct_answer": "B. Integrate with local providers like Flouci, D17, or Konnect",
            "evaluation": "Good market awareness — local payment providers are essential.",
            "cv_reference": "Payment Integration",
        },
        {
            "question": "A production bug exposes user passwords in plain text in the logs. 10,000 users affected. What's your immediate response?",
            "options": [
                "A. Fix quietly and hope nobody notices",
                "B. Patch the bug, purge logs, force password resets, notify affected users",
                "C. Wait for the next sprint",
                "D. Shut down the entire system",
            ],
            "correct_answer": "B. Patch the bug, purge logs, force password resets, notify affected users",
            "evaluation": "Excellent security awareness and professional crisis handling.",
            "cv_reference": "Security",
        },
    ],
    "data": [
        {
            "question": "A Tunisian telecom operator asks you to predict customer churn. Your data is 70% French, 20% Arabic (Derja), 10% English. What's your first preprocessing challenge?",
            "options": [
                "A. Translate everything to English",
                "B. Build a multilingual NLP pipeline with language detection",
                "C. Only use the English data",
                "D. Remove all text features",
            ],
            "correct_answer": "B. Build a multilingual NLP pipeline with language detection",
            "evaluation": "Good approach — multilingual handling is critical in Tunisia.",
            "cv_reference": "NLP / Data Processing",
        },
        {
            "question": "Your ML model has 98% accuracy on training data but 65% on test data. What's the most likely diagnosis?",
            "options": [
                "A. Underfitting",
                "B. Overfitting",
                "C. Perfect model — test data is bad",
                "D. Wrong programming language",
            ],
            "correct_answer": "B. Overfitting",
            "evaluation": "Good ML fundamentals — classic overfitting symptoms.",
            "cv_reference": "ML Models",
        },
        {
            "question": "A Tunisian bank (BIAT) wants a credit scoring model. Many applicants have no formal credit history but have mobile money data. The regulator demands explainability. Best approach?",
            "options": [
                "A. Deep neural network for maximum accuracy",
                "B. Gradient boosting with SHAP explanations",
                "C. Simple if/else rules",
                "D. Ask customers to self-report scores",
            ],
            "correct_answer": "B. Gradient boosting with SHAP explanations",
            "evaluation": "Excellent — balances accuracy with regulatory explainability.",
            "cv_reference": "Financial ML",
        },
        {
            "question": "Your NLP sentiment model works well on MSA (Modern Standard Arabic) but fails on Tunisian Derja. You have 5,000 labeled Derja tweets. What's your strategy?",
            "options": [
                "A. Fine-tune a multilingual BERT model on the Derja data",
                "B. Translate Derja to English then analyze",
                "C. Use only MSA and ignore Derja",
                "D. Build a rule-based system with keywords",
            ],
            "correct_answer": "A. Fine-tune a multilingual BERT model on the Derja data",
            "evaluation": "Transfer learning with fine-tuning is the best approach for low-resource languages.",
            "cv_reference": "NLP / Arabic NLP",
        },
    ],
    "community": [
        {
            "question": "A delivery driver posts a viral TikTok showing poor working conditions at your Tunisian food delivery company. 100K views in 2 hours. Twitter starts a boycott hashtag. First action?",
            "options": [
                "A. Delete the TikTok",
                "B. Acknowledge publicly, investigate internally, respond within 4 hours",
                "C. Ignore it — it will blow over",
                "D. Sue the driver",
            ],
            "correct_answer": "B. Acknowledge publicly, investigate internally, respond within 4 hours",
            "evaluation": "Professional crisis management — transparency wins.",
            "cv_reference": "Crisis Management",
        },
        {
            "question": "Your Tunisian fashion brand needs a content strategy for Instagram/TikTok targeting 18-25 year olds. Budget: 5,000 TND/month. Best content language mix?",
            "options": [
                "A. 100% English — it's international",
                "B. 60% French, 30% Derja, 10% English — matching how young Tunisians actually speak",
                "C. 100% Arabic (MSA)",
                "D. Post without text — only images",
            ],
            "correct_answer": "B. 60% French, 30% Derja, 10% English — matching how young Tunisians actually speak",
            "evaluation": "Excellent market awareness — Tunisian youth speak a mix.",
            "cv_reference": "Social Media Strategy",
        },
        {
            "question": "Your client's Facebook page gets 200+ angry comments in Derja after delayed Ramadan deliveries. Some comments include personal attacks on staff. Moderation strategy?",
            "options": [
                "A. Delete all negative comments",
                "B. Reply empathetically to legitimate complaints, hide personal attacks (not delete), escalate threats",
                "C. Disable comments",
                "D. Create a new Facebook page",
            ],
            "correct_answer": "B. Reply empathetically to legitimate complaints, hide personal attacks (not delete), escalate threats",
            "evaluation": "Professional moderation that protects staff while respecting customers.",
            "cv_reference": "Community Moderation",
        },
    ],
    "manager": [
        {
            "question": "You're PM at a Tunisian SaaS startup serving French SMEs. NPS dropped from 45 to 28 this quarter. Customer feedback says onboarding is too complex. Your dev team's roadmap is full. What do you do?",
            "options": [
                "A. Add features faster — more features = more value",
                "B. Negotiate with engineering to reprioritize — fix onboarding as a P0, scope down planned features",
                "C. Ignore NPS — focus on revenue",
                "D. Hire more customer support staff",
            ],
            "correct_answer": "B. Negotiate with engineering to reprioritize — fix onboarding as a P0, scope down planned features",
            "evaluation": "Good PM instinct — onboarding impacts all downstream metrics.",
            "cv_reference": "Product Strategy",
        },
        {
            "question": "A Tunisian bank wants to launch a digital wallet competing with D17 and Flouci. You need to define the MVP. What's most important for v1?",
            "options": [
                "A. Every feature competitors have",
                "B. Seamless money transfers + bill payment + strong security — the 80/20 of daily use",
                "C. AI-powered financial advice",
                "D. NFT marketplace",
            ],
            "correct_answer": "B. Seamless money transfers + bill payment + strong security — the 80/20 of daily use",
            "evaluation": "Excellent MVP thinking — focus on core value, not feature parity.",
            "cv_reference": "MVP Definition",
        },
    ],
    "devops": [
        {
            "question": "A Tunisian offshore company deploys Spring Boot apps via SSH and FTP. No CI/CD, no staging. 15 developers. Where do you start?",
            "options": [
                "A. Kubernetes immediately",
                "B. Set up GitLab CI with automated builds + staging environment first",
                "C. Keep FTP but add more steps",
                "D. Move everything to serverless",
            ],
            "correct_answer": "B. Set up GitLab CI with automated builds + staging environment first",
            "evaluation": "Right priority — CI/CD and staging before containerization.",
            "cv_reference": "CI/CD",
        },
        {
            "question": "Your Kubernetes pods hosting a Tunisian fintech's services crash during 10AM-12PM (EU business hours). CPU is normal, memory keeps spiking. First diagnostic step?",
            "options": [
                "A. Add more pods (horizontal scaling)",
                "B. Check pod resource limits and analyze memory leak patterns with kubectl top + heap dumps",
                "C. Restart all pods every hour",
                "D. Switch to VMs",
            ],
            "correct_answer": "B. Check pod resource limits and analyze memory leak patterns with kubectl top + heap dumps",
            "evaluation": "Correct diagnostic approach — find root cause before scaling.",
            "cv_reference": "Kubernetes",
        },
        {
            "question": "A startup asks you to design infra from scratch. Expected growth: 10K users in month 1, 500K by year end. Budget: $5,000/month. Best approach?",
            "options": [
                "A. Buy physical servers",
                "B. Start with managed services (AWS RDS, ECS) — auto-scaling, pay-as-you-go, minimal ops overhead",
                "C. Build a private data center",
                "D. Use free tier only",
            ],
            "correct_answer": "B. Start with managed services (AWS RDS, ECS) — auto-scaling, pay-as-you-go, minimal ops overhead",
            "evaluation": "Smart — managed services minimize ops for small teams.",
            "cv_reference": "Cloud Architecture",
        },
    ],
    "designer": [
        {
            "question": "A Tunisian banking app needs redesign. 60% of users are 40+, many switch between French and Arabic mid-session, 30% use low-end Android phones. Most critical design decision?",
            "options": [
                "A. Trendy animations and dark mode",
                "B. Large touch targets, clear typography, seamless RTL/LTR switching, and lightweight assets for slow phones",
                "C. Copy the design of a Western banking app",
                "D. Text-only interface",
            ],
            "correct_answer": "B. Large touch targets, clear typography, seamless RTL/LTR switching, and lightweight assets for slow phones",
            "evaluation": "Excellent — designing for real users, not design awards.",
            "cv_reference": "UX Design",
        },
        {
            "question": "An e-government portal must serve citizens from university students in Tunis to farmers in Sidi Bouzid. How do you handle the digital literacy gap?",
            "options": [
                "A. Design only for tech-savvy users",
                "B. Progressive disclosure + guided wizards + visual cues + tested with both demographics",
                "C. Make two separate websites",
                "D. Paper-only for rural areas",
            ],
            "correct_answer": "B. Progressive disclosure + guided wizards + visual cues + tested with both demographics",
            "evaluation": "Right approach — inclusive design with real user testing.",
            "cv_reference": "Inclusive Design",
        },
    ],
    "marketing": [
        {
            "question": "A Tunisian tech startup raised 2M TND seed and needs 1,000 B2B customers in Tunisia and francophone Africa. Budget: 50K TND for 6 months. Google Ads is too expensive. Best channel?",
            "options": [
                "A. TV advertising",
                "B. LinkedIn + content marketing + partnerships with local business associations + referral program",
                "C. Billboard ads on Tunis highways",
                "D. Wait for word of mouth",
            ],
            "correct_answer": "B. LinkedIn + content marketing + partnerships with local business associations + referral program",
            "evaluation": "Smart B2B strategy for limited budget markets.",
            "cv_reference": "Go-to-Market",
        },
        {
            "question": "You're launching a Tunisian SaaS in France. Main objection: 'We prefer European vendors for data sovereignty.' How do you counter?",
            "options": [
                "A. Lower the price more",
                "B. Offer EU data hosting (AWS Paris), SOC2 compliance roadmap, and position as a EU-integrated nearshore partner, not just 'cheap offshore'",
                "C. Ignore the concern",
                "D. Fake a European headquarters",
            ],
            "correct_answer": "B. Offer EU data hosting (AWS Paris), SOC2 compliance roadmap, and position as a EU-integrated nearshore partner, not just 'cheap offshore'",
            "evaluation": "Professional objection handling with concrete solutions.",
            "cv_reference": "SaaS Sales",
        },
    ],
    "qa": [
        {
            "question": "You join a Tunisian offshore team building a banking API for a French client. Zero test coverage, 50 endpoints. Client wants 80% coverage in 6 weeks. How do you prioritize?",
            "options": [
                "A. Write unit tests for all endpoints alphabetically",
                "B. Test highest-risk endpoints first (payments, auth, user data), then expand with integration tests",
                "C. Only do manual testing",
                "D. Tell the client it's impossible",
            ],
            "correct_answer": "B. Test highest-risk endpoints first (payments, auth, user data), then expand with integration tests",
            "evaluation": "Risk-based testing is the professional approach.",
            "cv_reference": "Test Strategy",
        },
        {
            "question": "A payment bug in your Tunisian fintech app charges some BIAT customers twice. It only happens with specific card prefixes. How do you prevent this in the future?",
            "options": [
                "A. Fix the bug and move on",
                "B. Add boundary value tests for all Tunisian bank card formats, parameterized test suites, and regression automation",
                "C. Remove BIAT as a payment option",
                "D. Add a disclaimer in the terms of service",
            ],
            "correct_answer": "B. Add boundary value tests for all Tunisian bank card formats, parameterized test suites, and regression automation",
            "evaluation": "Systematic approach to edge case prevention.",
            "cv_reference": "Edge Case Testing",
        },
    ],
    "mobile": [
        {
            "question": "A Tunisian mobile money app needs to work offline in rural areas with poor connectivity. Data must sync when back online. Best architecture?",
            "options": [
                "A. Require constant internet connection",
                "B. Offline-first with local SQLite + queue-based sync + conflict resolution when online",
                "C. Cache only the last screen viewed",
                "D. Use SMS instead of the app",
            ],
            "correct_answer": "B. Offline-first with local SQLite + queue-based sync + conflict resolution when online",
            "evaluation": "Excellent — offline-first is essential for Tunisian rural coverage.",
            "cv_reference": "Mobile Architecture",
        },
        {
            "question": "Your React Native delivery app crashes on low-end Samsung phones (Galaxy A03/A13) during map rendering for live driver tracking. What do you investigate?",
            "options": [
                "A. Only support iPhones",
                "B. Profile memory usage, reduce map markers with clustering, use lightweight map SDK, test on actual low-end devices",
                "C. Remove the map feature",
                "D. Tell users to buy better phones",
            ],
            "correct_answer": "B. Profile memory usage, reduce map markers with clustering, use lightweight map SDK, test on actual low-end devices",
            "evaluation": "Practical debugging approach for the real Tunisian device landscape.",
            "cv_reference": "Mobile Performance",
        },
    ],
    "frontend": [
        {
            "question": "A Tunisian e-government portal must support RTL Arabic, LTR French, and LTR English with mid-session language switching. Best architectural approach?",
            "options": [
                "A. Build 3 separate websites",
                "B. CSS logical properties (margin-inline-start/end) + i18n framework + dynamic dir attribute + RTL-aware component library",
                "C. Only support French",
                "D. Use Google Translate",
            ],
            "correct_answer": "B. CSS logical properties (margin-inline-start/end) + i18n framework + dynamic dir attribute + RTL-aware component library",
            "evaluation": "Modern approach to bidirectional layout — this works at scale.",
            "cv_reference": "Frontend Architecture",
        },
        {
            "question": "A Tunisian SaaS dashboard needs to render 10,000 rows with real-time filtering and inline editing. Users are on average laptops. React app. How do you prevent UI freezing?",
            "options": [
                "A. Load all 10,000 rows at once",
                "B. Virtual scrolling (react-window/TanStack Virtual) + debounced filtering + Web Workers for heavy computation",
                "C. Limit to 50 rows total",
                "D. Use a spreadsheet embed",
            ],
            "correct_answer": "B. Virtual scrolling (react-window/TanStack Virtual) + debounced filtering + Web Workers for heavy computation",
            "evaluation": "Right tooling — virtual scrolling is the industry standard solution.",
            "cv_reference": "Frontend Performance",
        },
    ],
    "security": [
        {
            "question": "A Tunisian bank discovers unauthorized access from an external IP. 50,000 customer records may be exposed. Tunisia's INPDP requires notification within 72 hours. First action?",
            "options": [
                "A. Cover it up",
                "B. Isolate affected systems, preserve forensic evidence, notify INPDP, begin incident report, then notify customers",
                "C. Immediately delete all logs",
                "D. Wait to see if anyone notices",
            ],
            "correct_answer": "B. Isolate affected systems, preserve forensic evidence, notify INPDP, begin incident report, then notify customers",
            "evaluation": "Professional incident response following legal requirements.",
            "cv_reference": "Incident Response",
        },
        {
            "question": "Security audit of a Tunisian e-commerce platform reveals: SQL injection, no HTTPS on payment page, admin creds in public GitHub, no WAF. What do you fix first?",
            "options": [
                "A. Add a WAF",
                "B. Remove GitHub creds (immediate exposure) → HTTPS on payment → SQL injection fix → WAF",
                "C. Fix everything simultaneously",
                "D. Shut down the site",
            ],
            "correct_answer": "B. Remove GitHub creds (immediate exposure) → HTTPS on payment → SQL injection fix → WAF",
            "evaluation": "Correct priority — exposed credentials are the most immediate threat.",
            "cv_reference": "Security Audit",
        },
    ],
    "sales": [
        {
            "question": "You're selling a Tunisian SaaS to French companies. Conversion is 5%. Main objection: 'We prefer European vendors.' Your product is 50% cheaper. How do you position?",
            "options": [
                "A. Lower price even more",
                "B. Emphasize EU data hosting, nearshore advantages (same timezone, French-speaking), case studies, and free pilot — position as 'European-quality at competitive pricing', not 'cheap'",
                "C. Pretend to be a French company",
                "D. Give up on France",
            ],
            "correct_answer": "B. Emphasize EU data hosting, nearshore advantages (same timezone, French-speaking), case studies, and free pilot — position as 'European-quality at competitive pricing', not 'cheap'",
            "evaluation": "Excellent positioning — value, not price.",
            "cv_reference": "B2B Sales",
        },
    ],
    "scrum": [
        {
            "question": "You're Scrum Master for a Tunisian nearshore team of 8. The French PO expects direct pushback on unrealistic deadlines, but your team says 'yes' to everything then struggles silently. How do you fix this?",
            "options": [
                "A. Tell the team to say no more often",
                "B. Coach the team on assertive communication, create safe spaces for concerns, use sprint planning data to make capacity visible and objective",
                "C. Replace team members who can't push back",
                "D. Let the PO set all deadlines unquestioned",
            ],
            "correct_answer": "B. Coach the team on assertive communication, create safe spaces for concerns, use sprint planning data to make capacity visible and objective",
            "evaluation": "Professional facilitation — data-driven capacity makes pushback objective, not personal.",
            "cv_reference": "Agile Facilitation",
        },
    ],
    "network": [
        {
            "question": "A Tunisian ISP reports packet loss between Tunis and Sfax data centers. VoIP drops 30% of calls. Fiber link is dedicated. First diagnostic step?",
            "options": [
                "A. Replace all fiber immediately",
                "B. Run traceroute + MTR to isolate the hop with packet loss, check SFP transceivers, review switch error counters",
                "C. Switch to satellite",
                "D. Tell customers to use text instead of calls",
            ],
            "correct_answer": "B. Run traceroute + MTR to isolate the hop with packet loss, check SFP transceivers, review switch error counters",
            "evaluation": "Systematic network debugging — isolate the layer, then the device.",
            "cv_reference": "Network Troubleshooting",
        },
    ],
}


def get_fallback_question(skill: str, question_number: int = 1):
    import random

    skill_lower = skill.lower().strip()

    # Match role to question bank
    questions = None
    for key in FALLBACK_QUESTIONS.keys():
        if key in skill_lower or skill_lower in key:
            questions = FALLBACK_QUESTIONS[key]
            break

    # Extended keyword matching
    if not questions:
        keyword_map = {
            "backend": "software",
            "developer": "software",
            "engineer": "software",
            "java": "software",
            "python": "software",
            "data": "data",
            "ml": "data",
            "machine learning": "data",
            "ai": "data",
            "scientist": "data",
            "community": "community",
            "social": "community",
            "product": "manager",
            "pm ": "manager",
            "devops": "devops",
            "sre": "devops",
            "infrastructure": "devops",
            "cloud": "devops",
            "design": "designer",
            "ui": "designer",
            "ux": "designer",
            "market": "marketing",
            "growth": "marketing",
            "qa": "qa",
            "test": "qa",
            "quality": "qa",
            "mobile": "mobile",
            "ios": "mobile",
            "android": "mobile",
            "flutter": "mobile",
            "react native": "mobile",
            "front": "frontend",
            "react": "frontend",
            "vue": "frontend",
            "angular": "frontend",
            "security": "security",
            "cyber": "security",
            "sales": "sales",
            "business development": "sales",
            "scrum": "scrum",
            "agile": "scrum",
            "network": "network",
            "infra": "network",
            "full": "software",
            "fullstack": "software",
        }
        for keyword, mapped_key in keyword_map.items():
            if keyword in skill_lower:
                questions = FALLBACK_QUESTIONS.get(mapped_key)
                if questions:
                    break

    if not questions:
        # Flatten all questions as final fallback
        questions = []
        for q_list in FALLBACK_QUESTIONS.values():
            questions.extend(q_list)

    # Select question by index for progression, fallback to random
    if question_number <= len(questions):
        selected = questions[question_number - 1]
    else:
        selected = random.choice(questions)

    return {
        "evaluation": selected.get("evaluation", "Continuing assessment."),
        "score_impact": 0,
        "metrics_impact": {},
        "reasoning_update": "Using curated scenario-based question bank.",
        "question": selected["question"],
        "options": selected["options"],
        "correct_answer": selected["correct_answer"],
        "cv_reference": selected.get("cv_reference", "General"),
    }
