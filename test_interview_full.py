"""Full AI interview E2E test — app 121, rubric 16 (Marketing Manager)."""
import httpx, json, time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

c = httpx.Client(follow_redirects=True, timeout=120)
r = c.post("http://127.0.0.1:8003/api/v1/auth/login", json={"email": "rayenteck8@gmail.com", "password": "Test@2026!"})
print("login:", r.status_code)
token = r.json()["access_token"]
c.get("http://127.0.0.1:8003/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
csrf = None
for k, v in c.cookies.items():
    if k == "csrf_token":
        csrf = v
h = {"Authorization": "Bearer " + token}
if csrf:
    h["X-CSRF-Token"] = csrf

print("\n" + "=" * 80)
print("FULL INTERVIEW TEST - Marketing Manager (Rubric 16)")
print("=" * 80)

questions = []
start = time.time()

ANSWER = (
    "I would approach this with a structured framework. First, I'd conduct a data audit "
    "to establish baselines using Google Analytics and platform-native tools. Then I'd "
    "segment the audience, create a content calendar aligned with business objectives, "
    "and set clear KPIs. For execution, I'd use a mix of organic and paid channels - "
    "SEO for long-term traffic, PPC for immediate conversions, and email nurture sequences "
    "for retention. I'd run weekly A/B tests on headlines and CTAs, build dashboards in "
    "Looker Studio for stakeholder reporting, and hold bi-weekly optimization sprints "
    "to reallocate budget based on ROAS. Post-campaign, I'd conduct a full attribution "
    "analysis using multi-touch models to inform future strategy."
)

for turn in range(16):
    msg = "ready" if turn == 0 else ANSWER

    if turn > 0:
        wait = 32
        print("  ... waiting %ds ..." % wait)
        time.sleep(wait)

    t0 = time.time()
    r = c.post("http://127.0.0.1:8003/api/v1/ai/interview/chat",
               headers=h,
               json={"candidate_id": 121, "message": msg, "language": "English", "current_score": 0},
               timeout=120)
    elapsed = time.time() - t0

    if r.status_code == 429:
        print("\n  RATE LIMITED - waiting 120s then retrying...")
        time.sleep(120)
        r = c.post("http://127.0.0.1:8003/api/v1/ai/interview/chat",
                   headers=h,
                   json={"candidate_id": 121, "message": msg, "language": "English", "current_score": 0},
                   timeout=120)
        elapsed = time.time() - t0
        if r.status_code != 200:
            print("  Retry failed: %d - %s" % (r.status_code, r.text[:200]))
            break

    if r.status_code != 200:
        print("\nTURN %d FAILED: %d" % (turn + 1, r.status_code))
        break

    data = r.json()
    reply = data.get("reply", "")
    q_type = data.get("type", "")
    score = data.get("current_score", 0)
    time_left = data.get("time_left", 0)
    progress = data.get("progress", {})
    is_complete = data.get("is_complete", False)
    sb = data.get("score_breakdown")
    hint = data.get("hint_text", "")
    feedback = data.get("feedback", "")

    questions.append({
        "turn": turn + 1, "question": reply, "type": q_type, "score": score,
        "time_left": time_left, "api_time": round(elapsed, 1), "hint": hint,
        "feedback": feedback,
    })

    print("\nQ%d [%s] (API: %.1fs)" % (turn + 1, q_type, elapsed))
    print("  Q: %s" % reply[:300])
    if feedback:
        print("  Feedback: %s" % feedback[:150])
    if sb:
        print("  Score=%s Breakdown: final=%s base=%s" % (score, sb.get('final_score', '?'), sb.get('base_score', '?')))
    else:
        print("  Score=%s | Time left: %ds (%dm%ds)" % (score, time_left, time_left // 60, time_left % 60))
    print("  Progress: %s/%s (%s%%)" % (progress.get('current', '?'), progress.get('total', '?'), progress.get('percentage', 0)))

    if is_complete or q_type == "complete":
        print("\n*** INTERVIEW COMPLETE ***")
        break

total = time.time() - start

print("\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)
print("Total questions: %d" % len(questions))
print("Total time: %.1fs" % total)
if questions:
    print("Final score: %s" % questions[-1]['score'])

print("\n--- Duration Tracking ---")
for q in questions:
    print("  Q%d: time_left=%ds, API=%.1fs" % (q['turn'], q['time_left'], q['api_time']))

print("\n--- Question Quality ---")
for q in questions:
    print("  Q%d: %s" % (q['turn'], q['question'][:250]))

if len(questions) > 1:
    from difflib import SequenceMatcher
    pairs = 0
    for i in range(len(questions)):
        for j in range(i + 1, len(questions)):
            ratio = SequenceMatcher(None, questions[i]["question"], questions[j]["question"]).ratio()
            if ratio > 0.5:
                print("\n  WARNING: Q%d & Q%d are %.0f%% similar" % (i + 1, j + 1, ratio * 100))
                pairs += 1
    if pairs == 0:
        print("\n  All questions have good diversity")

name_tokens = [q for q in questions if "[NAME_" in q["question"]]
print("\n  Masked tokens: %s" % ('YES (BUG!)' if name_tokens else 'None (clean)'))

print("\n--- Resume Test ---")
r_resume = c.post("http://127.0.0.1:8003/api/v1/ai/interview/resume",
                  headers=h, json={"application_id": 121}, timeout=30)
print("Resume: %d" % r_resume.status_code)
try:
    rd = r_resume.json()
    print("  time_left: %s" % rd.get('time_left', 'N/A'))
    print("  current_question: %s" % rd.get('current_question', 'N/A'))
except:
    print(r_resume.text[:300])
