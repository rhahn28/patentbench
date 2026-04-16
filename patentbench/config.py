"""Configuration constants for PatentBench.

Defines enums, tiers, domains, metrics, and rejection types used throughout
the benchmark framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any


BENCHMARK_VERSION = "0.2.0"
BENCHMARK_NAME = "PatentBench"
MINI_SUBSET_SIZE = 300
FULL_BENCHMARK_SIZE = 7200

# Default LLM judge model for rubric-based evaluation
DEFAULT_JUDGE_MODEL = "claude-sonnet-4-20250514"
DEFAULT_JUDGE_TEMPERATURE = 0.0
DEFAULT_JUDGE_MAX_TOKENS = 4096


class Domain(str, Enum):
    """The five patent prosecution domains tested by PatentBench."""

    ADMINISTRATION = "administration"
    DRAFTING = "drafting"
    PROSECUTION = "prosecution"
    ANALYTICS = "analytics"
    PRIOR_ART = "prior_art"

    @property
    def display_name(self) -> str:
        return self.value.replace("_", " ").title()


class DifficultyTier(IntEnum):
    """Difficulty tiers mapping to practitioner experience levels."""

    PARALEGAL = 1        # 0-1 years: deadlines, fees, forms
    JUNIOR_ASSOCIATE = 2  # 1-3 years: OA parsing, simple 112 responses
    SENIOR_ASSOCIATE = 3  # 3-6 years: 103 arguments, claim amendments
    JUNIOR_PARTNER = 4    # 6-10 years: complex multi-rejection OAs
    SENIOR_PARTNER = 5    # 10+ years: portfolio strategy, IPR defense

    @property
    def display_name(self) -> str:
        return self.name.replace("_", " ").title()

    @property
    def experience_range(self) -> str:
        ranges = {1: "0-1 years", 2: "1-3 years", 3: "3-6 years",
                  4: "6-10 years", 5: "10+ years"}
        return ranges[self.value]


class RejectionType(str, Enum):
    """USPTO rejection types under Title 35 of the United States Code."""

    SEC_101 = "101"          # Patent-eligible subject matter
    SEC_102 = "102"          # Novelty (anticipation)
    SEC_102_A = "102(a)"     # Prior art before effective filing date
    SEC_102_B = "102(b)"     # Statutory bar
    SEC_103 = "103"          # Obviousness
    SEC_112_A = "112(a)"     # Written description / enablement
    SEC_112_B = "112(b)"     # Definiteness
    SEC_112_D = "112(d)"     # Dependent claim requirements
    SEC_112_F = "112(f)"     # Means-plus-function
    DOUBLE_PATENTING = "dp"  # Obviousness-type double patenting
    RESTRICTION = "restriction"  # Restriction requirement

    @property
    def display_name(self) -> str:
        labels = {
            "101": "35 U.S.C. 101 (Subject Matter Eligibility)",
            "102": "35 U.S.C. 102 (Novelty)",
            "102(a)": "35 U.S.C. 102(a) (Prior Art)",
            "102(b)": "35 U.S.C. 102(b) (Statutory Bar)",
            "103": "35 U.S.C. 103 (Obviousness)",
            "112(a)": "35 U.S.C. 112(a) (Written Description)",
            "112(b)": "35 U.S.C. 112(b) (Definiteness)",
            "112(d)": "35 U.S.C. 112(d) (Dependent Claims)",
            "112(f)": "35 U.S.C. 112(f) (Means-Plus-Function)",
            "dp": "Double Patenting",
            "restriction": "Restriction Requirement",
        }
        return labels[self.value]


class MetricType(str, Enum):
    """Types of metrics computed in evaluation."""

    ACCURACY = "accuracy"
    F1_SCORE = "f1_score"
    COHENS_KAPPA = "cohens_kappa"
    LEGAL_ACCURACY = "legal_accuracy"
    FACTUAL_ACCURACY = "factual_accuracy"
    ARGUMENT_STRENGTH = "argument_strength"
    COMPLETENESS = "completeness"
    FORMAT_COMPLIANCE = "format_compliance"
    CITATION_ACCURACY = "citation_accuracy"
    ANTI_HALLUCINATION = "anti_hallucination"
    COMPOSITE_SCORE = "composite_score"


class EvaluationLayer(str, Enum):
    """The four evaluation layers in PatentBench."""

    DETERMINISTIC = "deterministic"
    LLM_JUDGE = "llm_judge"
    COMPARATIVE = "comparative"
    HUMAN_CALIBRATION = "human_calibration"


@dataclass(frozen=True)
class TaskConfig:
    """Configuration for a specific task type within a domain."""

    domain: Domain
    tier: DifficultyTier
    task_type: str
    description: str
    evaluation_layers: list[EvaluationLayer] = field(default_factory=list)
    applicable_rejections: list[RejectionType] = field(default_factory=list)
    weight: float = 1.0


# ---- Task Registry ----

TASK_REGISTRY: list[TaskConfig] = [
    # Administration tasks (Tier 1)
    TaskConfig(
        domain=Domain.ADMINISTRATION,
        tier=DifficultyTier.PARALEGAL,
        task_type="deadline_calculation",
        description="Calculate response deadlines from Office Action mailing dates",
        evaluation_layers=[EvaluationLayer.DETERMINISTIC],
        weight=1.0,
    ),
    TaskConfig(
        domain=Domain.ADMINISTRATION,
        tier=DifficultyTier.PARALEGAL,
        task_type="fee_computation",
        description="Compute USPTO fees based on entity status and filing type",
        evaluation_layers=[EvaluationLayer.DETERMINISTIC],
        weight=1.0,
    ),
    TaskConfig(
        domain=Domain.ADMINISTRATION,
        tier=DifficultyTier.PARALEGAL,
        task_type="entity_status",
        description="Determine entity status (micro, small, large) from applicant data",
        evaluation_layers=[EvaluationLayer.DETERMINISTIC],
        weight=1.0,
    ),
    # Prosecution tasks (Tiers 2-5)
    TaskConfig(
        domain=Domain.PROSECUTION,
        tier=DifficultyTier.JUNIOR_ASSOCIATE,
        task_type="oa_parsing",
        description="Parse Office Action to extract rejections, claims, and grounds",
        evaluation_layers=[EvaluationLayer.DETERMINISTIC, EvaluationLayer.LLM_JUDGE],
        applicable_rejections=[
            RejectionType.SEC_101, RejectionType.SEC_102, RejectionType.SEC_103,
            RejectionType.SEC_112_A, RejectionType.SEC_112_B,
        ],
        weight=1.5,
    ),
    TaskConfig(
        domain=Domain.PROSECUTION,
        tier=DifficultyTier.SENIOR_ASSOCIATE,
        task_type="103_argument",
        description="Draft arguments traversing 35 U.S.C. 103 obviousness rejection",
        evaluation_layers=[
            EvaluationLayer.DETERMINISTIC, EvaluationLayer.LLM_JUDGE,
            EvaluationLayer.COMPARATIVE,
        ],
        applicable_rejections=[RejectionType.SEC_103],
        weight=2.0,
    ),
    TaskConfig(
        domain=Domain.PROSECUTION,
        tier=DifficultyTier.SENIOR_ASSOCIATE,
        task_type="101_argument",
        description="Draft arguments traversing 35 U.S.C. 101 subject matter eligibility rejection",
        evaluation_layers=[
            EvaluationLayer.DETERMINISTIC, EvaluationLayer.LLM_JUDGE,
            EvaluationLayer.COMPARATIVE,
        ],
        applicable_rejections=[RejectionType.SEC_101],
        weight=2.0,
    ),
    TaskConfig(
        domain=Domain.PROSECUTION,
        tier=DifficultyTier.JUNIOR_PARTNER,
        task_type="multi_rejection_response",
        description="Draft complete response to OA with multiple rejection types",
        evaluation_layers=[
            EvaluationLayer.DETERMINISTIC, EvaluationLayer.LLM_JUDGE,
            EvaluationLayer.COMPARATIVE, EvaluationLayer.HUMAN_CALIBRATION,
        ],
        applicable_rejections=[
            RejectionType.SEC_101, RejectionType.SEC_102, RejectionType.SEC_103,
            RejectionType.SEC_112_A, RejectionType.SEC_112_B,
        ],
        weight=3.0,
    ),
    # Drafting tasks (Tiers 2-4)
    TaskConfig(
        domain=Domain.DRAFTING,
        tier=DifficultyTier.JUNIOR_ASSOCIATE,
        task_type="claim_amendment",
        description="Draft claim amendments to overcome rejections",
        evaluation_layers=[EvaluationLayer.LLM_JUDGE, EvaluationLayer.COMPARATIVE],
        weight=1.5,
    ),
    TaskConfig(
        domain=Domain.DRAFTING,
        tier=DifficultyTier.SENIOR_ASSOCIATE,
        task_type="independent_claim_drafting",
        description="Draft independent claims from invention disclosure",
        evaluation_layers=[
            EvaluationLayer.LLM_JUDGE, EvaluationLayer.COMPARATIVE,
            EvaluationLayer.HUMAN_CALIBRATION,
        ],
        weight=2.0,
    ),
    # Analytics tasks (Tiers 3-5)
    TaskConfig(
        domain=Domain.ANALYTICS,
        tier=DifficultyTier.SENIOR_ASSOCIATE,
        task_type="claim_mapping",
        description="Map claims to prior art elements",
        evaluation_layers=[EvaluationLayer.LLM_JUDGE, EvaluationLayer.COMPARATIVE],
        weight=1.5,
    ),
    # Prior Art tasks (Tiers 2-4)
    TaskConfig(
        domain=Domain.PRIOR_ART,
        tier=DifficultyTier.JUNIOR_ASSOCIATE,
        task_type="reference_relevance",
        description="Rank prior art references by relevance to claims",
        evaluation_layers=[EvaluationLayer.DETERMINISTIC, EvaluationLayer.LLM_JUDGE],
        weight=1.5,
    ),
]

# ---- Scoring Weights ----

LAYER_WEIGHTS: dict[EvaluationLayer, float] = {
    EvaluationLayer.DETERMINISTIC: 0.30,
    EvaluationLayer.LLM_JUDGE: 0.35,
    EvaluationLayer.COMPARATIVE: 0.25,
    EvaluationLayer.HUMAN_CALIBRATION: 0.10,
}

DOMAIN_WEIGHTS: dict[Domain, float] = {
    Domain.ADMINISTRATION: 0.10,
    Domain.DRAFTING: 0.25,
    Domain.PROSECUTION: 0.35,
    Domain.ANALYTICS: 0.15,
    Domain.PRIOR_ART: 0.15,
}

# ---- USPTO Fee Schedule (2026 estimates) ----

USPTO_FEES: dict[str, dict[str, float]] = {
    "filing_utility": {"micro": 80.0, "small": 160.0, "large": 320.0},
    "search": {"micro": 165.0, "small": 330.0, "large": 660.0},
    "examination": {"micro": 191.0, "small": 382.0, "large": 764.0},
    "issue_fee": {"micro": 260.0, "small": 520.0, "large": 1040.0},
    "extension_1_month": {"micro": 52.0, "small": 104.0, "large": 208.0},
    "extension_2_month": {"micro": 152.0, "small": 304.0, "large": 608.0},
    "extension_3_month": {"micro": 356.0, "small": 712.0, "large": 1424.0},
    "rce": {"micro": 320.0, "small": 640.0, "large": 1280.0},
    "appeal_notice": {"micro": 200.0, "small": 400.0, "large": 800.0},
}

# ---- MPEP Reference Sections ----

MPEP_SECTIONS: dict[str, str] = {
    "2106": "Patent Subject Matter Eligibility (101)",
    "2111": "Claim Interpretation - Broadest Reasonable Interpretation",
    "2131": "Anticipation (102)",
    "2141": "Obviousness (103) - Examination Guidelines",
    "2143": "Obviousness - Exemplary Rationales",
    "2144": "Obviousness - Supporting a Rejection Under 35 U.S.C. 103",
    "2161": "Written Description Requirement (112(a))",
    "2163": "Guidelines for the Examination of Patent Applications Under 112(a)",
    "2171": "Definiteness Requirement (112(b))",
    "2173": "Claims Must Particularly Point Out and Distinctly Claim",
    "2181": "Means-Plus-Function (112(f))",
    "706.03": "Rejections Under 35 U.S.C. 102",
    "706.04": "Rejections Under 35 U.S.C. 103",
    "804": "Double Patenting",
    "710.02": "Time Periods for Reply",
}

# ---- Anti-Hallucination Poison Pills ----

POISON_PILL_MPEP_SECTIONS: list[str] = [
    "2199",   # Does not exist
    "2156",   # Does not exist
    "706.08(z)",  # Fabricated subsection
    "2143.07",    # Fabricated subsection
    "2181.05",    # Fabricated subsection
]

POISON_PILL_CASE_LAW: list[str] = [
    "Smith v. USPTO, 999 F.3d 1 (Fed. Cir. 2025)",
    "TechCorp v. InnovateCo, 888 F.3d 222 (Fed. Cir. 2024)",
    "Digital Innovations LLC v. Patent Office, 777 F.3d 333 (Fed. Cir. 2023)",
]
