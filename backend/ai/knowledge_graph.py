"""
Knowledge Graph for Concept Mastery Tracking
==============================================

Tracks which concepts a candidate understands vs. guesses at.
Builds a graph of related concepts and measures mastery depth.

Features:
- Concept extraction from Q&A pairs
- Relationship mapping between concepts
- Mastery level tracking (surface, functional, deep)
- Gap identification in knowledge graph
- Confidence scoring per concept

Author: Candway Engineering
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class MasteryLevel(Enum):
    NONE = "none"
    SURFACE = "surface"  # Can define but not apply
    FUNCTIONAL = "functional"  # Can apply in standard scenarios
    DEEP = "deep"  # Can handle edge cases and trade-offs
    EXPERT = "expert"  # Can teach and architect with it


@dataclass
class ConceptNode:
    """A single concept in the knowledge graph"""

    name: str
    category: str  # e.g., "language", "framework", "pattern", "tool"
    mastery_level: MasteryLevel = MasteryLevel.NONE
    confidence: float = 0.0  # 0-1 confidence in mastery assessment
    evidence: List[str] = field(default_factory=list)
    question_indices: List[int] = field(default_factory=list)
    scores: List[float] = field(default_factory=list)
    related_concepts: Set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "mastery_level": self.mastery_level.value,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
            "question_indices": self.question_indices,
            "avg_score": round(sum(self.scores) / len(self.scores), 1)
            if self.scores
            else 0,
            "related_concepts": list(self.related_concepts),
        }


@dataclass
class KnowledgeGraph:
    """Complete knowledge graph for a candidate"""

    concepts: Dict[str, ConceptNode] = field(default_factory=dict)
    relationships: Dict[str, List[str]] = field(default_factory=dict)
    overall_coverage: float = 0.0
    depth_score: float = 0.0
    gaps: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "concepts": {name: node.to_dict() for name, node in self.concepts.items()},
            "relationships": self.relationships,
            "overall_coverage": round(self.overall_coverage, 2),
            "depth_score": round(self.depth_score, 2),
            "gaps": self.gaps,
            "concept_count": len(self.concepts),
            "mastery_distribution": self._get_mastery_distribution(),
        }

    def _get_mastery_distribution(self) -> dict:
        dist = {level.value: 0 for level in MasteryLevel}
        for node in self.concepts.values():
            dist[node.mastery_level.value] += 1
        return dist


# Concept taxonomy by role
ROLE_CONCEPT_MAP = {
    "python developer": {
        "core": ["variables", "functions", "loops", "conditionals", "data types"],
        "intermediate": [
            "decorators",
            "generators",
            "context managers",
            "OOP",
            "exceptions",
        ],
        "advanced": [
            "metaclasses",
            "async/await",
            "GIL",
            "memory management",
            "descriptors",
        ],
        "ecosystem": ["Django", "FastAPI", "SQLAlchemy", "pytest", "pip"],
        "patterns": ["singleton", "factory", "observer", "strategy", "repository"],
    },
    "frontend developer": {
        "core": ["HTML", "CSS", "JavaScript", "DOM", "events"],
        "intermediate": ["React", "state management", "routing", "APIs", "testing"],
        "advanced": [
            "performance optimization",
            "Webpack",
            "SSR",
            "accessibility",
            "PWA",
        ],
        "ecosystem": ["TypeScript", "Tailwind", "Next.js", "Jest", "Cypress"],
        "patterns": ["component composition", "HOC", "render props", "custom hooks"],
    },
    "backend engineer": {
        "core": ["HTTP", "REST", "databases", "authentication", "APIs"],
        "intermediate": [
            "caching",
            "message queues",
            "microservices",
            "ORM",
            "migrations",
        ],
        "advanced": [
            "distributed systems",
            "event sourcing",
            "CQRS",
            "consistency models",
        ],
        "ecosystem": ["Docker", "Kubernetes", "Redis", "PostgreSQL", "Nginx"],
        "patterns": [
            "circuit breaker",
            "saga",
            "CQRS",
            "event sourcing",
            "API gateway",
        ],
    },
    "data scientist": {
        "core": ["statistics", "probability", "linear algebra", "data cleaning", "EDA"],
        "intermediate": [
            "regression",
            "classification",
            "clustering",
            "feature engineering",
        ],
        "advanced": [
            "deep learning",
            "NLP",
            "computer vision",
            "time series",
            "reinforcement learning",
        ],
        "ecosystem": ["pandas", "scikit-learn", "TensorFlow", "PyTorch", "SQL"],
        "patterns": [
            "train/test split",
            "cross-validation",
            "hyperparameter tuning",
            "ensemble",
        ],
    },
}


def extract_concepts_from_answer(
    answer: str, role: str, question_focus: str = None
) -> List[str]:
    """Extract technical concepts mentioned in an answer"""
    answer_lower = answer.lower()
    concepts = []

    # Get concept map for role
    role_key = role.lower()
    concept_map = None
    for key, cmap in ROLE_CONCEPT_MAP.items():
        if key in role_key:
            concept_map = cmap
            break

    if not concept_map:
        # Generic concept extraction
        generic_concepts = [
            "API",
            "database",
            "testing",
            "deployment",
            "security",
            "performance",
            "scalability",
            "architecture",
            "design patterns",
            "algorithms",
            "data structures",
            "version control",
            "CI/CD",
        ]
        for concept in generic_concepts:
            if concept.lower() in answer_lower:
                concepts.append(concept)
        return concepts

    # Extract from role-specific map
    for category, category_concepts in concept_map.items():
        for concept in category_concepts:
            if concept.lower() in answer_lower:
                concepts.append(concept)

    # Add question focus if mentioned
    if question_focus and question_focus.lower() in answer_lower:
        if question_focus not in concepts:
            concepts.append(question_focus)

    return concepts


def assess_mastery_level(
    concept: str, answer: str, score: float, question_complexity: str
) -> Tuple[MasteryLevel, float]:
    """
    Assess mastery level for a concept based on answer quality.
    Returns (mastery_level, confidence)
    """
    answer_lower = answer.lower()
    answer_words = answer.split()
    word_count = len(answer_words)

    # Signals for deep understanding
    deep_signals = [
        "trade-off",
        "however",
        "depends on",
        "in my experience",
        "alternatively",
        "consider",
        "because",
        "therefore",
        "edge case",
        "scalability",
        "performance",
        "maintainability",
    ]

    surface_signals = [
        "is a",
        "used for",
        "it's like",
        "basically",
        "simple",
        "just",
        "easy",
        "you use it to",
    ]

    deep_count = sum(1 for signal in deep_signals if signal in answer_lower)
    surface_count = sum(1 for signal in surface_signals if signal in answer_lower)

    # Determine mastery level
    if score >= 85 and deep_count >= 2 and word_count >= 50:
        level = MasteryLevel.EXPERT
        confidence = 0.85
    elif score >= 75 and (deep_count >= 1 or word_count >= 40):
        level = MasteryLevel.DEEP
        confidence = 0.75
    elif score >= 60 and word_count >= 20:
        level = MasteryLevel.FUNCTIONAL
        confidence = 0.65
    elif score >= 40 and surface_count >= 1:
        level = MasteryLevel.SURFACE
        confidence = 0.50
    else:
        level = MasteryLevel.NONE
        confidence = 0.30

    # Adjust confidence based on answer length
    if word_count < 10:
        confidence *= 0.5  # Short answers are less reliable
    elif word_count > 200:
        confidence *= 0.9  # Very long answers may include filler

    return level, confidence


def build_knowledge_graph(
    qa_pairs: List[dict], role: str, expected_concepts: Optional[List[str]] = None
) -> KnowledgeGraph:
    """
    Build a knowledge graph from interview Q&A pairs.

    Args:
        qa_pairs: List of {question, answer, score, focus, complexity}
        role: Candidate's target role
        expected_concepts: List of concepts expected for this role

    Returns:
        KnowledgeGraph with concept mastery tracking
    """
    graph = KnowledgeGraph()
    concept_evidence: Dict[str, List[str]] = {}
    concept_scores: Dict[str, List[float]] = {}
    concept_questions: Dict[str, List[int]] = {}

    for idx, qa in enumerate(qa_pairs):
        answer = qa.get("answer", "")
        score = qa.get("score", 50)
        focus = qa.get("focus", "")
        complexity = qa.get("complexity", "intermediate")

        # Extract concepts
        concepts = extract_concepts_from_answer(answer, role, focus)

        for concept in concepts:
            # Track evidence
            if concept not in concept_evidence:
                concept_evidence[concept] = []
            concept_evidence[concept].append(answer[:100])

            # Track scores
            if concept not in concept_scores:
                concept_scores[concept] = []
            concept_scores[concept].append(score)

            # Track question indices
            if concept not in concept_questions:
                concept_questions[concept] = []
            concept_questions[concept].append(idx + 1)

    # Build concept nodes
    for concept in concept_evidence:
        avg_score = sum(concept_scores[concept]) / len(concept_scores[concept])

        # Use last answer for mastery assessment
        last_answer = concept_evidence[concept][-1]
        last_qa = (
            qa_pairs[concept_questions[concept][-1] - 1]
            if concept_questions[concept]
            else {}
        )
        complexity = last_qa.get("complexity", "intermediate")

        mastery, confidence = assess_mastery_level(
            concept, last_answer, avg_score, complexity
        )

        # Determine category
        category = _categorize_concept(concept, role)

        node = ConceptNode(
            name=concept,
            category=category,
            mastery_level=mastery,
            confidence=confidence,
            evidence=concept_evidence[concept],
            question_indices=concept_questions[concept],
            scores=concept_scores[concept],
        )

        graph.concepts[concept] = node

    # Build relationships
    graph.relationships = _build_relationships(graph.concepts)

    # Update related concepts
    for concept, related in graph.relationships.items():
        if concept in graph.concepts:
            graph.concepts[concept].related_concepts = set(related)

    # Calculate coverage and depth
    if expected_concepts:
        covered = sum(1 for c in expected_concepts if c in graph.concepts)
        graph.overall_coverage = (
            covered / len(expected_concepts) if expected_concepts else 0
        )
        graph.gaps = [c for c in expected_concepts if c not in graph.concepts]

    # Depth score: weighted average of mastery levels
    mastery_weights = {
        MasteryLevel.NONE: 0,
        MasteryLevel.SURFACE: 0.25,
        MasteryLevel.FUNCTIONAL: 0.5,
        MasteryLevel.DEEP: 0.75,
        MasteryLevel.EXPERT: 1.0,
    }

    if graph.concepts:
        depth_sum = sum(
            mastery_weights[node.mastery_level] * node.confidence
            for node in graph.concepts.values()
        )
        graph.depth_score = depth_sum / len(graph.concepts)

    return graph


def _categorize_concept(concept: str, role: str) -> str:
    """Categorize a concept into a knowledge domain"""
    concept_lower = concept.lower()

    categories = {
        "language": ["python", "java", "javascript", "typescript", "go", "rust", "c++"],
        "framework": [
            "django",
            "flask",
            "react",
            "angular",
            "vue",
            "spring",
            "express",
        ],
        "database": ["sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch"],
        "tool": ["docker", "kubernetes", "git", "jenkins", "terraform", "ansible"],
        "pattern": [
            "singleton",
            "factory",
            "observer",
            "strategy",
            "mvc",
            "repository",
        ],
        "concept": [
            "api",
            "rest",
            "microservices",
            "caching",
            "authentication",
            "testing",
        ],
    }

    for category, keywords in categories.items():
        if any(kw in concept_lower for kw in keywords):
            return category

    return "concept"


def _build_relationships(concepts: Dict[str, ConceptNode]) -> Dict[str, List[str]]:
    """Build relationships between concepts based on co-occurrence and taxonomy"""
    relationships = {}

    # Known concept relationships
    known_relationships = {
        "Python": ["Django", "FastAPI", "SQLAlchemy", "pytest"],
        "JavaScript": ["React", "TypeScript", "Node.js"],
        "React": ["TypeScript", "Redux", "Jest"],
        "SQL": ["PostgreSQL", "MySQL", "database"],
        "Docker": ["Kubernetes", "CI/CD", "deployment"],
        "REST": ["API", "HTTP", "microservices"],
        "testing": ["pytest", "Jest", "unit test", "integration test"],
    }

    for concept in concepts:
        related = []
        for known, related_concepts in known_relationships.items():
            if concept.lower() == known.lower():
                related.extend([r for r in related_concepts if r in concepts])
            elif concept.lower() in [r.lower() for r in related_concepts]:
                if known in concepts:
                    related.append(known)

        relationships[concept] = related

    return relationships


def get_concept_mastery_report(graph: KnowledgeGraph) -> dict:
    """Generate a human-readable mastery report"""
    by_category = {}
    for node in graph.concepts.values():
        if node.category not in by_category:
            by_category[node.category] = []
        by_category[node.category].append(node)

    report = {
        "total_concepts": len(graph.concepts),
        "coverage": round(graph.overall_coverage * 100, 1),
        "depth_score": round(graph.depth_score * 100, 1),
        "by_category": {},
        "gaps": graph.gaps,
    }

    for category, nodes in by_category.items():
        avg_mastery = (
            sum(
                {"none": 0, "surface": 25, "functional": 50, "deep": 75, "expert": 100}[
                    n.mastery_level.value
                ]
                for n in nodes
            )
            / len(nodes)
            if nodes
            else 0
        )

        report["by_category"][category] = {
            "count": len(nodes),
            "avg_mastery": round(avg_mastery, 1),
            "concepts": [
                n.name
                for n in sorted(
                    nodes, key=lambda x: x.mastery_level.value, reverse=True
                )
            ],
        }

    return report
