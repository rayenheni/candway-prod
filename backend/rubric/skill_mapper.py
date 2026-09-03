from typing import Dict, List

SKILL_SYNONYMS: Dict[str, str] = {
    "python3": "python",
    "py": "python",
    "node": "node.js",
    "nodejs": "node.js",
    "express.js": "express",
    "react.js": "react",
    "reactjs": "react",
    "vue.js": "vue",
    "vuejs": "vue",
    "angular.js": "angular",
    "angularjs": "angular",
    "postgres": "postgresql",
    "psql": "postgresql",
    "mysql": "sql",
    "mongodb": "no-sql",
    "mongo": "no-sql",
    "k8s": "kubernetes",
    "gcp": "google cloud",
    "aws": "amazon web services",
    "restful": "rest api",
    "rest": "rest api",
    "oop": "object oriented programming",
    "ci/cd": "ci/cd pipeline",
    "ci": "ci/cd pipeline",
    "cd": "ci/cd pipeline",
    # Domain Synonyms & Acronyms
    "sales growth": "revenue growth",
    "reduced churn": "customer retention",
    "churn": "customer retention",
    "cross-functional alignment": "stakeholder management",
    "stakeholder alignment": "stakeholder management",
    "delivery management": "project management",
    "analyzed customer behavior": "data analysis",
    "customer analytics": "data analysis",
    "led a cross-functional team": "leadership",
    "team leadership": "leadership",
    "identified root cause and fixed it": "problem solving",
    "root cause analysis": "problem solving",
    "crm": "customer relationship management",
    "erp": "enterprise resource planning",
    "kpi": "key performance indicator",
    "okr": "objectives and key results",
    "saas": "software as a service",
    "b2b": "business to business",
    "b2c": "business to consumer",
    "ux": "user experience",
    "ui": "user interface",
}


def map_extracted_skills(
    extracted_skills: List[Dict],
    rubric_lookup: Dict[str, object],
) -> List[Dict]:
    mapped = []

    for ext in extracted_skills:
        raw_name = ext.get("skill_name", "").strip().lower()
        if not raw_name:
            continue

        if raw_name in rubric_lookup:
            ext["rubric_match"] = rubric_lookup[raw_name]
            mapped.append(ext)
            continue

        canonical = SKILL_SYNONYMS.get(raw_name)
        if canonical and canonical in rubric_lookup:
            ext["skill_name"] = canonical
            ext["rubric_match"] = rubric_lookup[canonical]
            mapped.append(ext)
            continue

        for rubric_skill_name, rubric_skill in rubric_lookup.items():
            if raw_name in rubric_skill_name or rubric_skill_name in raw_name:
                ext["skill_name"] = rubric_skill_name
                ext["rubric_match"] = rubric_skill
                mapped.append(ext)
                break

    return mapped
