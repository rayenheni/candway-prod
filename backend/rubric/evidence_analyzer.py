import re
from typing import List, Tuple

IMPLEMENTATION_SIGNALS = [
    "built",
    "build",
    "building",
    "developed",
    "develop",
    "developing",
    "implemented",
    "implementing",
    "deployed",
    "deploying",
    "architected",
    "architecting",
    "designed",
    "design",
    "designing",
    "redesigned",
    "redesign",
    "redesigning",
    "created",
    "create",
    "creating",
    "wrote",
    "writing",
    "coded",
    "coding",
    "configured",
    "configuring",
    "migrated",
    "migrating",
    "integrated",
    "integrating",
    "refactored",
    "refactoring",
    "optimized",
    "optimizing",
    "scaled",
    "scaling",
    "reduced",
    "reduce",
    "reducing",
    "increased",
    "increasing",
    "improved",
    "improving",
    "solved",
    "solving",
    "lead",
    "leading",
    "managed",
    "managing",
]

METRIC_PATTERN = re.compile(
    r"\b\d+%|\b\d+\s*(?:k|m|b|K|M|B|million|billion|thousand|percent|users|req|rps|qps|ms|s|hours|days|weeks)\b"
)

TECHNOLOGY_NAMES = [
    "kubernetes",
    "k8s",
    "docker",
    "aws",
    "gcp",
    "azure",
    "redis",
    "postgresql",
    "postgres",
    "mongodb",
    "mongo",
    "kafka",
    "rabbitmq",
    "terraform",
    "ansible",
    "jenkins",
    "gitlab",
    "github actions",
    "circleci",
    "fastapi",
    "django",
    "flask",
    "react",
    "vue",
    "angular",
    "node.js",
    "node",
    "graphql",
    "grpc",
    "rest",
    "celery",
    "rabbitmq",
    "nginx",
    "apache",
    "linux",
    "helm",
]


def classify_evidence_quality(
    evidence_sentences: List[str],
    skill_name: str,
) -> Tuple[str, str]:
    if not evidence_sentences:
        return ("weak", "No evidence provided")

    all_text = " ".join(evidence_sentences).lower()
    clean_text = all_text.strip()

    has_implementation = any(signal in clean_text for signal in IMPLEMENTATION_SIGNALS)
    has_metrics = bool(METRIC_PATTERN.search(clean_text))
    has_technology = any(tech in clean_text for tech in TECHNOLOGY_NAMES)
    has_skill_name = skill_name.lower() in clean_text

    avg_sentence_len = sum(len(s.split()) for s in evidence_sentences) / max(
        len(evidence_sentences), 1
    )
    is_detailed = avg_sentence_len > 15

    if has_implementation and has_metrics:
        return ("strong", "Direct implementation experience with concrete metrics")
    elif has_implementation and (has_technology or is_detailed):
        return ("strong", "Direct implementation with specific technologies")
    elif has_implementation:
        return ("medium", "Implementation mentioned but lacks metrics")
    elif (has_technology and has_skill_name) or is_detailed:
        return ("medium", "Familiar with tooling or detailed explanation")
    else:
        return ("weak", "Generic or vague statement without implementation detail")
