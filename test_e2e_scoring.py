"""
E2E Scoring Validation Test - Marketing Manager Rubric 16
Tests 5 answer types across 10 questions to validate the scoring pipeline.
"""
import httpx, json, time, sys, io, re
from difflib import SequenceMatcher

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

c = httpx.Client(follow_redirects=True, timeout=120)
r = c.post("http://127.0.0.1:8003/api/v1/auth/login",
           json={"email": "rayenteck8@gmail.com", "password": "Test@2026!"})
print("Login:", r.status_code)
token = r.json()["access_token"]
c.get("http://127.0.0.1:8003/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
csrf = None
for k, v in c.cookies.items():
    if k == "csrf_token":
        csrf = v
h = {"Authorization": "Bearer " + token}
if csrf:
    h["X-CSRF-Token"] = csrf

STRONG = {
    "market research": "I would design a mixed-methods research program. First, conduct quantitative surveys with at least 500 target consumers using stratified sampling across Midwest demographics, measuring brand awareness, purchase intent, and willingness-to-pay through Likert scales. Then run 6-8 focus groups segmented by age and lifestyle to uncover emotional drivers. I would use TAM/SAM/SOM analysis to size the opportunity, conduct conjoint analysis to optimize product attributes and pricing, and deploy a competitive landscape study using Porters Five Forces framework.",
    "campaign planning": "I would build a full-funnel campaign with three phases over 12 weeks. Phase 1: Awareness with teaser video series on Instagram Reels and TikTok with influencer partnerships, targeting a 40% awareness lift. Phase 2: Consideration with Google Ads search campaigns, retargeting via Meta pixel, and email nurture sequences. Phase 3: Conversion with promotional offers, abandoned cart recovery, and referral program. I would set ROAS targets of 4:1 and track CAC against our $25 target.",
    "budgeting and forecasting": "I would allocate the $200,000 budget using zero-based budgeting: 35% paid media, 25% content production, 20% influencer partnerships, 10% email platform, 10% contingency. I would forecast monthly spend with 15% buffer and project revenue using a conservative 3:1 ROAS yielding $600K. I would track actual vs plan weekly using a variance threshold of plus or minus 10% to trigger reallocation.",
    "competitor analysis": "I would build a comprehensive competitive intelligence framework. Map the competitive landscape using a feature comparison matrix covering 8-10 competitors across price, ingredients, distribution, brand positioning, and digital presence. Use SimilarWeb and SEMrush to benchmark organic traffic and paid keywords. Conduct win/loss analysis of top competitors campaigns. Monthly competitive dashboards tracking share of voice, pricing changes, and new product launches.",
    "social media marketing": "I would build a platform-specific social strategy. Instagram with 5 posts weekly mixing lifestyle photography, UGC reposts, and carousel education posts. TikTok with 3-4 short-form videos weekly. LinkedIn with 2 posts weekly for B2B partnerships. Allocate 60% of social budget to paid social across Instagram Reels ads, TikTok Spark ads, and Facebook retargeting. Work with 8-10 micro-influencers in the wellness space.",
    "search engine optimization (seo)": "I would execute a three-pillar SEO strategy. Technical: fix Core Web Vitals, implement structured data markup, create XML sitemap, fix crawl errors. On-page: build content cluster strategy with pillar page linking to 15 supporting articles targeting long-tail keywords. Optimize title tags and meta descriptions. Off-page: pursue guest posting on health publications, build relationships with nutrition bloggers for natural backlinks. Track organic traffic growth weekly using Ahrefs.",
    "pay-per-click (ppc) advertising": "I would structure a full-funnel PPC campaign across Google Ads and Meta Ads. Google: brand campaigns at 10%, non-brand search at 40% with tROAS bidding, Shopping ads at 15%. Meta: prospecting with lookalike audiences at 20%, retargeting with dynamic product ads at 15%. Run creative A/B tests every 2 weeks, pause underperforming ad groups. Use data-driven attribution for cross-channel budget allocation.",
    "email marketing": "I would build a lifecycle email program with 5 automated flows: welcome series over 10 days with brand story and first-purchase offer, abandoned cart with reminder and urgency discount, post-purchase with review request and replenishment reminder, re-engagement for 30-day inactive subscribers, and weekly newsletter. A/B test subject lines, send times, and CTA placement. Target 25% open rate and 3% CTR.",
    "google analytics": "I would set up GA4 with a comprehensive measurement plan. Configure custom dimensions for user segments and engagement metrics. Build funnel analysis tracking from landing page through checkout to identify drop-off points. Create cohort analysis to measure 30-day retention curves. Set up UTM parameter conventions for campaign attribution. Build automated dashboards in Looker Studio for weekly stakeholder reporting with key metrics: sessions, engagement rate, conversions, and revenue.",
    "data analysis and interpretation": "I would implement a data-driven decision framework. Build SQL queries to segment customer cohorts by acquisition channel and engagement level. Run regression analysis to identify the key drivers of conversion and customer lifetime value. Create A/B test analysis dashboards with statistical significance calculations. Use cohort analysis to track retention curves and identify at-risk segments. Present findings through data visualization in Tableau dashboards.",
    "reporting and dashboard creation": "I would design a three-tier reporting architecture. Executive dashboard: high-level KPIs with MoM trends, revenue attribution, and marketing ROI. Operational dashboard: channel-level performance with real-time spend pacing, ROAS by campaign, and conversion funnel metrics. Ad-hoc analysis: monthly deep dives with cohort analysis, attribution modeling, and competitive benchmarking. Use Looker Studio for automated weekly reports distributed to stakeholders.",
}

PARTIAL = {
    "market research": "I would start by looking at existing market data and industry reports to understand the health beverage landscape. I would survey some customers to get basic feedback on what they want, and look at what competitors are doing to identify gaps.",
    "campaign planning": "I would create a campaign timeline with awareness, consideration, and conversion phases. I would use social media and email to reach customers, and track key metrics like engagement and sales.",
    "budgeting and forecasting": "I would split the budget across different channels based on what has worked before. I would track spending monthly and adjust if some channels are underperforming.",
    "competitor analysis": "I would look at what our main competitors are doing in terms of pricing and marketing. I would check their websites and social media to understand their positioning.",
    "social media marketing": "I would post regularly on Instagram and TikTok with product photos and health tips. I would also run some paid ads to reach more people.",
    "search engine optimization (seo)": "I would make sure our website has good keywords in the titles and descriptions. I would also write some blog posts about health topics to drive organic traffic.",
    "pay-per-click (ppc) advertising": "I would run Google Ads for brand keywords and some non-brand keywords related to health beverages. I would set a daily budget and monitor performance.",
    "email marketing": "I would send a weekly newsletter with product updates and health tips. I would also set up a welcome email for new subscribers.",
    "google analytics": "I would check Google Analytics regularly to see how many visitors we get and which pages are popular. I would set up basic conversion tracking.",
    "data analysis and interpretation": "I would look at the data in spreadsheets and create some charts to show trends. I would share findings with the team in weekly meetings.",
    "reporting and dashboard creation": "I would create a simple dashboard in Google Sheets showing traffic, conversions, and spend. I would share it with the team weekly.",
}

IRRELEVANT = {
    "market research": "I would focus on creating great content for our blog about healthy recipes and wellness tips. Content marketing is key to building brand awareness and trust with our audience.",
    "campaign planning": "I would hire a celebrity endorsement deal to boost brand credibility. Celebrity partnerships can create massive buzz and drive immediate awareness for new product launches.",
    "budgeting and forecasting": "I would invest heavily in a brand refresh with new packaging design and logo. Visual identity is crucial for standing out on shelves and creating premium brand perception.",
    "competitor analysis": "I would run a customer loyalty program with points and rewards. Retention programs are more cost-effective than acquisition and build long-term customer relationships.",
    "social media marketing": "I would produce a branded podcast about health and wellness trends. Podcasts build deep audience engagement and position the brand as a thought leader in the space.",
    "search engine optimization (seo)": "I would create a referral program where existing customers earn rewards for bringing friends. Word-of-mouth is the most trusted form of marketing for health products.",
    "pay-per-click (ppc) advertising": "I would sponsor local fitness events and farmers markets. Experiential marketing creates authentic brand connections and generates user-generated content.",
    "email marketing": "I would develop a YouTube channel with product reviews and healthy lifestyle vlogs. Video content drives the highest engagement rates across all digital platforms.",
    "google analytics": "I would partner with nutritionists and dietitians for co-branded content. Professional endorsements build credibility in the health beverage space.",
    "data analysis and interpretation": "I would launch a sustainability initiative with eco-friendly packaging. Environmental responsibility resonates strongly with health-conscious consumers.",
    "reporting and dashboard creation": "I would create a community forum where health enthusiasts can share recipes and wellness tips. Community building drives organic engagement and brand loyalty.",
}

def get_focused_skill(question_text):
    q = question_text.lower()
    skill_keywords = {
        "market research": ["market research", "market analysis", "research methods", "survey", "target audience", "consumer insight", "market sizing", "tamm", "sam", "som"],
        "campaign planning": ["campaign", "launch", "phases", "awareness", "consideration", "conversion", "full-funnel", "campaign plan"],
        "budgeting and forecasting": ["budget", "allocate", "spend", "forecast", "financial", "$200,000", "cost", "roi"],
        "competitor analysis": ["competitor", "competitive", "landscape", "benchmark", "positioning", "market position"],
        "social media marketing": ["social media", "instagram", "tiktok", "facebook", "social strategy", "influencer", "engagement"],
        "search engine optimization (seo)": ["seo", "search engine", "organic", "keyword", "backlink", "ranking", "on-page", "technical seo"],
        "pay-per-click (ppc) advertising": ["ppc", "pay-per-click", "google ads", "paid search", "bidding", "ad group", "impression"],
        "email marketing": ["email", "newsletter", "subscriber", "open rate", "drip", "email campaign"],
        "google analytics": ["analytics", "ga4", "tracking", "dashboard", "metrics", "traffic", "funnel analysis"],
        "data analysis and interpretation": ["data analysis", "data-driven", "sql", "regression", "cohort", "statistical"],
        "reporting and dashboard creation": ["report", "dashboard", "visualization", "kpi", "stakeholder reporting"],
    }
    for skill, keywords in skill_keywords.items():
        for kw in keywords:
            if kw in q:
                return skill
    return None

def pick_skill_for_cross(current_focused):
    all_skills = list(STRONG.keys())
    others = [s for s in all_skills if s != current_focused]
    import random
    random.seed(42)
    return random.choice(others)

print("=" * 90)
print("E2E SCORING VALIDATION TEST - Marketing Manager (Rubric 16)")
print("=" * 90)

results = []
start = time.time()
next_answer = "ready"
last_question = ""
last_focused = None

for turn in range(16):
    msg = next_answer

    if turn > 0:
        wait = 35
        print("  ... waiting %ds ..." % wait)
        time.sleep(wait)

    t0 = time.time()
    r = c.post("http://127.0.0.1:8003/api/v1/ai/interview/chat",
               headers=h,
               json={"candidate_id": 121, "message": msg, "language": "English", "current_score": 0},
               timeout=120)
    elapsed = time.time() - t0

    if r.status_code == 429:
        retry = r.json().get("detail", "")
        print("\n  RATE LIMITED - %s" % retry)
        wait_match = re.search(r"wait (\d+) seconds", retry)
        wait_s = int(wait_match.group(1)) + 5 if wait_match else 130
        print("  Waiting %ds then retrying..." % wait_s)
        time.sleep(wait_s)
        r = c.post("http://127.0.0.1:8003/api/v1/ai/interview/chat",
                   headers=h,
                   json={"candidate_id": 121, "message": msg, "language": "English", "current_score": 0},
                   timeout=120)
        elapsed = time.time() - t0
        if r.status_code != 200:
            print("  Retry failed: %d - %s" % (r.status_code, r.text[:200]))
            break

    if r.status_code != 200:
        print("\nTURN %d FAILED: %d - %s" % (turn + 1, r.status_code, r.text[:300]))
        break

    data = r.json()
    reply = data.get("reply", "")
    q_type = data.get("type", "")
    score = data.get("current_score", 0)
    time_left = data.get("time_left", 0)
    progress = data.get("progress", {})
    is_complete = data.get("is_complete", False)
    sb = data.get("score_breakdown") or {}
    feedback = data.get("feedback", "")
    skills = data.get("skills", {})
    confidence = data.get("confidence_score", 0)
    momentum = data.get("momentum", 0)
    hire_decision = data.get("hiring_decision", "")

    if q_type == "complete" or is_complete:
        print("\nQ%d [complete] Score=%s (API: %.1fs)" % (turn + 1, score, elapsed))
        print("  Final score: %s" % score)
        print("  Breakdown: %s" % sb)
        print("\n*** INTERVIEW COMPLETE ***")
        break

    focused = get_focused_skill(last_question) if last_question else None
    if not focused:
        focused = last_focused or get_focused_skill(reply) or "market research"

    answer_type = ["A", "B", "C", "D", "E"][turn % 5]

    if answer_type == "A":
        next_answer = STRONG.get(focused, STRONG["market research"])
    elif answer_type == "B":
        next_answer = PARTIAL.get(focused, PARTIAL["market research"])
    elif answer_type == "C":
        next_answer = IRRELEVANT.get(focused, IRRELEVANT["market research"])
    elif answer_type == "D":
        cross_skill = pick_skill_for_cross(focused)
        next_answer = STRONG.get(cross_skill, STRONG["market research"])
    else:
        next_answer = STRONG.get(focused, STRONG["market research"])

    if turn == 0:
        print("\nQ%d [%s] (API: %.1fs)" % (turn + 1, q_type, elapsed))
        print("  Q: %s" % reply[:300])
        print("  Progress: %s/%s" % (progress.get('current', '?'), progress.get('total', '?')))
        detected = get_focused_skill(reply)
        if detected:
            print("  Detected focus: %s" % detected)
            last_focused = detected
        last_question = reply
        continue

    entry = {
        "turn": turn,
        "question": last_question[:200],
        "focused_skill": focused,
        "answer_type": answer_type,
        "answer_preview": next_answer[:100],
        "current_score": score,
        "base_score": sb.get("base_score"),
        "final_score": sb.get("final_score"),
        "momentum_bonus": sb.get("momentum_bonus"),
        "completeness_bonus": sb.get("completeness_bonus"),
        "integrity_penalty": sb.get("integrity_penalty"),
        "skills": skills,
        "confidence": confidence,
        "feedback": feedback[:200] if feedback else "",
        "time_left": time_left,
        "progress": progress,
        "type": q_type,
        "api_time": round(elapsed, 1),
    }
    results.append(entry)

    print("\nQ%d [%s] Focus=%s (API: %.1fs)" % (turn, answer_type, focused, elapsed))
    print("  Q: %s" % last_question[:200])
    print("  A: %s..." % next_answer[:100])
    print("  Score: base=%s final=%s live=%s" % (sb.get("base_score"), sb.get("final_score"), score))
    print("  Skills: %s" % {k: v for k, v in skills.items() if v > 0})
    print("  Feedback: %s" % (feedback[:150] if feedback else "none"))
    print("  Breakdown: momentum=+%.1f complete=+%.1f integrity=-%.1f" % (
        sb.get("momentum_bonus", 0), sb.get("completeness_bonus", 0), sb.get("integrity_penalty", 0)))

    last_question = reply
    last_focused = focused

total_time = time.time() - start

print("\n" + "=" * 90)
print("RESULTS TABLE")
print("=" * 90)
print("| %-3s | %-30s | %-6s | %-6s | %-6s | %-6s |" % (
    "Q#", "Focused Skill", "Type", "Base", "Final", "Live"))
print("|" + "-" * 5 + "|" + "-" * 32 + "|" + "-" * 8 + "|" + "-" * 8 + "|" + "-" * 8 + "|" + "-" * 8 + "|")
for r in results:
    print("| %-3d | %-30s | %-6s | %-6s | %-6s | %-6s |" % (
        r["turn"], r["focused_skill"][:30], r["answer_type"],
        r["base_score"] if r["base_score"] is not None else "?",
        r["final_score"] if r["final_score"] is not None else "?",
        r["current_score"] if r["current_score"] is not None else "?"))

print("\n" + "=" * 90)
print("CRITICAL INVARIANT CHECKS")
print("=" * 90)

issues = []

for r in results:
    t = r["turn"]
    focused = r["focused_skill"]
    skills_dict = r.get("skills", {})
    non_zero_skills = {k: v for k, v in skills_dict.items() if v > 0}

    if r["answer_type"] == "D":
        cross_skill = pick_skill_for_cross(focused)
        if cross_skill in non_zero_skills:
            issues.append("Q%d: CROSS-SKILL LEAKAGE - %s scored %d when focus was %s" % (
                t, cross_skill, non_zero_skills[cross_skill], focused))

    if r["answer_type"] in ("A", "E") and r.get("base_score") is not None and r["base_score"] == 0:
        issues.append("Q%d: base_score is 0 for strong answer on %s" % (t, focused))

    if r["answer_type"] in ("A", "E") and r.get("final_score") is not None and r["final_score"] == 50:
        issues.append("Q%d: final_score defaulted to 50 for %s" % (t, focused))

if issues:
    print("\nISSUES FOUND:")
    for i in issues:
        print("  - %s" % i)
else:
    print("\nNo issues detected!")

print("\nTotal time: %.1fs" % total_time)
print("Questions answered: %d" % len(results))

scores_by_type = {}
for r in results:
    t = r["answer_type"]
    if t not in scores_by_type:
        scores_by_type[t] = []
    if r["current_score"] is not None:
        scores_by_type[t].append(r["current_score"])

print("\nScore by answer type:")
for t in ["A", "B", "C", "D", "E"]:
    vals = scores_by_type.get(t, [])
    if vals:
        print("  %s: avg=%.1f min=%s max=%s values=%s" % (
            t, sum(vals) / len(vals), min(vals), max(vals), vals))
