# Candway Onboarding & AI Interview Enhancement Plan

## Overview
This document outlines the strategic recommendations to improve both the onboarding flow and the AI interview system, enabling the LLM to generate better, more personalized questions for candidates.

---

## Current Flow Issues

### Onboarding
1. Skill extraction is single-pass (no confidence scoring)
2. Intelligence layer lacks evidence from CV
3. Calibration questions sometimes generic

### AI Interview
4. Doesn't use onboarding calibration data effectively
5. Question difficulty not adaptive to candidate skill level
6. No integration between onboarding results and interview generation

---

## Phase 1: Onboarding Improvements

### 1.1 Multi-Pass Skill Extraction

**Current**: Single extraction pass produces a list of skills.

**Recommended**: Multi-pass extraction with confidence scoring.

```python
# Pass 1: Technical skills (Python, Java, React...)
# Pass 2: Tools (Docker, AWS, Figma...)
# Pass 3: Soft skills (Leadership, communication...)

# Each skill should have:
{
    "skill": "React",
    "confidence": 0.85,  # 0-100 score
    "evidence": "Built Redux dashboard for Company X",  # Quote from CV
    "source": "experience_section"
}
```

### 1.2 Enhanced Intelligence Layer

**Current** (weak):
```python
intelligence_layer = {
    "strengths": ["React"],
    "gaps": ["Docker"]
}
```

**Recommended** (rich):
```python
intelligence_layer = {
    "cv_quality_score": 72,
    "extracted_strengths": [
        {
            "skill": "React",
            "evidence": "Built dashboard using Redux (Company X, 2023)",
            "confidence": 0.9
        },
        {
            "skill": "Python", 
            "evidence": "Data analysis with Pandas",
            "confidence": 0.85
        }
    ],
    "missing_critical_skills": [
        {
            "skill": "Docker",
            "reason": "Not in CV but required for Senior role",
            "priority": "high"
        }
    ],
    "recommended_focus": "DevOps and system design",
    "experience_level_detected": "Mid"
}
```

### 1.3 CV-Based Calibration Questions

**Current** (generic):
```
❌ "Tell me about your React experience"
❌ "Describe a project you've worked on"
```

**Recommended** (specific):
```
✅ "You built the dashboard at Company X using Redux. 
    How did you handle state persistence when the user refreshed the page?"

✅ "In your Python project, you worked with Pandas. 
    How did you handle the 40% missing values in your dataset?"

✅ "Your CV mentions leading a team of 4. What was your biggest 
    challenge in coordinating deliverables?"
```

---

## Phase 2: AI Interview Improvements

### 2.1 Use Calibration Data

The AI interview should load and use calibration results from onboarding:

```python
# In ai_interview.py
calibration_data = json.loads(app.calibration_json)

# If calibration exists:
- question_difficulty = adapt_based_on(calibration_data["score"])
- focus_areas = calibration_data.get("weaknesses", [])
- strengths_to_build = calibration_data.get("strengths", [])
```

### 2.2 Adaptive Question Difficulty

| Calibration Score | Interview Approach |
|-----------------|-----------------|
| >80 (High) | Push advanced scenarios, ask about edge cases, assume deep knowledge |
| 60-80 (Good) | Standard depth + some challenges, balanced |
| 40-60 (Low) | Easier foundational questions, give chance to recover |
| <40 (Weak) | Focus on basics, verify fundamentals |

### 2.3 Question Generation Rules

```python
# promt structure example:
"""
<CANDIDATE_PROFILE>
Role: {declared_role}
Calibration Score: {cal_score}/100
Strengths: {strengths_from_calibration}
Gaps to Probe: {weaknesses_from_calibration}
</CANDIDATE_PROFILE>

🚨 ADAPTIVE RULES:
- If cal_score > 80: Challenge with advanced scenarios
- If cal_score < 50: Ask easier foundational questions
- Focus on their calibration GAPS first
- Build on their calibration STRENGTHS
```

---

## Phase 3: Implementation Checklist

### Database
- [x] Add `calibration_json` column
- [x] Add `calibration_score` column  
- [x] Add `calibration_verified_skills` column

### Backend
- [x] Add `/save-calibration` endpoint
- [x] Update `get_candidate_summary()` to use calibration
- [x] Update question generator prompt with calibration context

### Frontend
- [x] Track `application_id` in onboarding state
- [x] Save calibration results after step 5

### To Do (Next Steps)
- [ ] Implement multi-pass skill extraction with confidence
- [ ] Add evidence quotes to intelligence layer
- [ ] Make calibration questions CV-specific
- [ ] Implement adaptive difficulty in interview
- [ ] Add "calibration score" weighting to final decision

---

## Technical Details

### Database Model Addition

```python
# backend/database.py
class Application(Base):
    # ... existing columns ...
    
    calibration_json = deferred(Column(Text, nullable=True))
    calibration_score = Column(Float, nullable=True)
    calibration_verified_skills = deferred(Column(Text, nullable=True))
```

### New Endpoint

```python
# backend/routers/onboarding.py
@router.post("/save-calibration")
async def save_calibration_results(request: dict, ...):
    # Saves calibration Q&A, score, verified skills to application
    # This data is then used for AI interview generation
```

### Enhanced Prompt

```python
# backend/ai/prompts.py
def get_question_generator_prompt(..., calibration_data: dict = None):
    
    calibration_context = ""
    if calibration_data:
        cal_score = calibration_data.get("score")
        calibration_context = f"""
<onboarding_calibration>
Score: {cal_score}/100
Strengths: {cal_data.get('strengths')}
Gaps: {cal_data.get('weaknesses')}
</onboarding_calibration>

🚨 CALIBRATION AWARE:
- High score = push harder
- Low score = give recovery questions
"""
```

---

## Expected Outcomes

### For Candidates
- More personalized, relevant questions
- Difficulty matched to their skill level
- Questions that feel like the interviewer read their CV
- Fair assessment based on actual background

### For System
- Better quality hire/no-hire decisions
- More accurate scoring through multiple signals
- Reduced generic answer success rate
- Better alignment between CV and interview

---

## Priority Order

1. **High Priority**: Save calibration data to DB + use in interview (DONE)
2. **High Priority**: CV-specific calibration questions
3. **Medium**: Multi-pass skill extraction with confidence
4. **Medium**: Adaptive difficulty in interview
5. **Low**: Evidence quotes in intelligence layer

---

## Notes

- Calibration answers should be stored and evaluated, not just scored
- The AI interview should remember what was tested in onboarding
- Final decision should weight both CV analysis + calibration + interview
- Tunisian/MENA context should influence question scenarios

---

*Generated: April 2026*