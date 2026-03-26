"""Anti-hallucination verification for PatentBench.

Detects fabricated citations, poison pill references, and verifies legal
accuracy of model outputs against known MPEP sections and case law.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from patentbench.config import (
    MPEP_SECTIONS,
    POISON_PILL_MPEP_SECTIONS,
    POISON_PILL_CASE_LAW,
    get_all_poison_pills,
)


@dataclass
class HallucinationReport:
    """Results of anti-hallucination checks on a model output."""

    cited_mpep_sections: list[str] = field(default_factory=list)
    valid_mpep_sections: list[str] = field(default_factory=list)
    invalid_mpep_sections: list[str] = field(default_factory=list)
    poison_pill_hits: list[str] = field(default_factory=list)
    cited_cases: list[str] = field(default_factory=list)
    verified_cases: list[str] = field(default_factory=list)
    fabricated_cases: list[str] = field(default_factory=list)
    poison_case_hits: list[str] = field(default_factory=list)
    cited_statutes: list[str] = field(default_factory=list)
    invalid_statutes: list[str] = field(default_factory=list)
    score: float = 1.0  # 1.0 = no hallucinations detected

    @property
    def passed(self) -> bool:
        """True if no hallucinations were detected."""
        return (
            len(self.invalid_mpep_sections) == 0
            and len(self.poison_pill_hits) == 0
            and len(self.fabricated_cases) == 0
            and len(self.poison_case_hits) == 0
            and len(self.invalid_statutes) == 0
        )

    def compute_score(self) -> float:
        """Compute anti-hallucination score (1.0 = perfect, 0.0 = all hallucinated)."""
        total_citations = (
            len(self.cited_mpep_sections)
            + len(self.cited_cases)
            + len(self.cited_statutes)
        )
        if total_citations == 0:
            self.score = 1.0
            return self.score

        hallucination_count = (
            len(self.invalid_mpep_sections)
            + len(self.poison_pill_hits)
            + len(self.fabricated_cases)
            + len(self.poison_case_hits)
            + len(self.invalid_statutes)
        )

        # Poison pills are weighted more heavily (2x penalty)
        poison_penalty = len(self.poison_pill_hits) + len(self.poison_case_hits)
        effective_hallucinations = hallucination_count + poison_penalty

        self.score = max(0.0, 1.0 - (effective_hallucinations / total_citations))
        return self.score


# ---- Known valid case law for patent prosecution ----

KNOWN_VALID_CASES: set[str] = {
    # Supreme Court
    "Alice Corp. v. CLS Bank International",
    "Alice Corp. Pty. Ltd. v. CLS Bank Int'l",
    "KSR International Co. v. Teleflex Inc.",
    "KSR Int'l Co. v. Teleflex Inc.",
    "Graham v. John Deere Co.",
    "Bilski v. Kappos",
    "Mayo Collaborative Services v. Prometheus Laboratories",
    "Mayo Collaborative Servs. v. Prometheus Labs., Inc.",
    "Diamond v. Diehr",
    "Markman v. Westview Instruments, Inc.",
    "eBay Inc. v. MercExchange, L.L.C.",
    # Federal Circuit
    "In re Wands",
    "MPEP 2164.01",
    "Nautilus, Inc. v. Biosig Instruments, Inc.",
    "Phillips v. AWH Corp.",
    "Williamson v. Citrix Online, LLC",
    "Berkheimer v. HP Inc.",
    "Enfish, LLC v. Microsoft Corp.",
    "McRO, Inc. v. Bandai Namco Games America Inc.",
    "Ariosa Diagnostics, Inc. v. Sequenom, Inc.",
    "Electric Power Group, LLC v. Alstom S.A.",
    "In re Brana",
    "In re Costello",
    "Ariad Pharmaceuticals, Inc. v. Eli Lilly and Co.",
    "Takeda Chemical Industries, Ltd. v. Alphapharm Pty., Ltd.",
    "Pfizer, Inc. v. Apotex, Inc.",
    "Ortho-McNeil Pharmaceutical, Inc. v. Mylan Laboratories, Inc.",
    "In re Kahn",
    "In re Bigio",
    "Claim Interpretation Under 35 U.S.C. 112(f)",
}


class CitationExtractor:
    """Extracts legal citations from model output text."""

    # MPEP section pattern: "MPEP" followed by section number like 2106, 2141.03, 706.03(a)
    MPEP_PATTERN = re.compile(
        r"MPEP\s*(?:(?:Section|Sec\.?|§)\s*)?(\d{3,4}(?:\.\d{1,2})?(?:\([a-z]\))?)",
        re.IGNORECASE,
    )

    # Case law pattern: captures "Name v. Name" or "In re Name" followed by citation info
    CASE_PATTERN = re.compile(
        r"((?:In re |Ex parte )?[A-Z][A-Za-z\s,.']+?\s+v\.\s+[A-Z][A-Za-z\s,.']+?"
        r"(?:,\s*\d+\s+(?:F\.\s*(?:2d|3d|4th)|U\.S\.|S\.\s*Ct\.)\s*\d+[^)]*)?)"
        r"|"
        r"(In re [A-Z][A-Za-z]+(?:,\s*\d+\s+F\.\s*(?:2d|3d|4th)\s*\d+[^)]*)?)",
        re.MULTILINE,
    )

    # USC statute pattern: "35 U.S.C. § 101" or "35 U.S.C. 103"
    STATUTE_PATTERN = re.compile(
        r"35\s+U\.S\.C\.?\s*§?\s*(\d{3}(?:\([a-z]\))?)",
        re.IGNORECASE,
    )

    VALID_USC_SECTIONS: set[str] = {
        "100", "101", "102", "102(a)", "102(b)", "103",
        "112", "112(a)", "112(b)", "112(d)", "112(f)",
        "119", "120", "121", "122", "131", "132", "133",
        "134", "141", "145", "154", "156", "171", "173",
        "251", "252", "253", "256", "261", "271", "282",
        "283", "284", "285", "287", "301", "302", "303",
        "311", "312", "313", "314", "315", "316", "318",
        "321", "322", "323", "324", "325", "326", "328",
        "351", "365", "371", "375", "376",
    }

    def extract_mpep_citations(self, text: str) -> list[str]:
        """Extract all MPEP section references from text."""
        return list(set(m.group(1) for m in self.MPEP_PATTERN.finditer(text)))

    def extract_case_citations(self, text: str) -> list[str]:
        """Extract all case law citations from text."""
        matches: list[str] = []
        for m in self.CASE_PATTERN.finditer(text):
            citation = (m.group(1) or m.group(2) or "").strip()
            if citation and len(citation) > 5:
                matches.append(citation)
        return list(set(matches))

    def extract_statute_citations(self, text: str) -> list[str]:
        """Extract all 35 U.S.C. section references from text."""
        return list(set(m.group(1) for m in self.STATUTE_PATTERN.finditer(text)))


class AntiHallucinationChecker:
    """Verifies citations and detects hallucinations in model outputs.

    Checks:
    1. MPEP section numbers against known valid sections
    2. Poison pill MPEP sections (fabricated sections that should not appear)
    3. Case law citations against known valid cases
    4. Poison pill case law (fabricated cases that should not appear)
    5. 35 U.S.C. section numbers against valid statute sections
    """

    def __init__(
        self,
        additional_valid_mpep: list[str] | None = None,
        additional_valid_cases: list[str] | None = None,
        poison_pill_files: list[str] | None = None,
    ) -> None:
        self.extractor = CitationExtractor()

        # Build set of valid MPEP sections
        self.valid_mpep: set[str] = set(MPEP_SECTIONS.keys())
        if additional_valid_mpep:
            self.valid_mpep.update(additional_valid_mpep)

        # Build set of valid case law
        self.valid_cases: set[str] = set(KNOWN_VALID_CASES)
        if additional_valid_cases:
            self.valid_cases.update(additional_valid_cases)

        # Merge hardcoded poison pills with any loaded from runtime files
        merged_mpep, merged_cases = get_all_poison_pills(
            extra_files=poison_pill_files,
        )
        self.poison_mpep: set[str] = set(merged_mpep)
        self.poison_cases: set[str] = set(merged_cases)

    def check(self, text: str) -> HallucinationReport:
        """Run all anti-hallucination checks on model output text.

        Args:
            text: The model's output text to verify.

        Returns:
            HallucinationReport with detailed findings.
        """
        report = HallucinationReport()

        # Check MPEP citations
        mpep_cites = self.extractor.extract_mpep_citations(text)
        report.cited_mpep_sections = mpep_cites
        for section in mpep_cites:
            if section in self.poison_mpep:
                report.poison_pill_hits.append(section)
                report.invalid_mpep_sections.append(section)
            elif section in self.valid_mpep:
                report.valid_mpep_sections.append(section)
            else:
                # Unknown section -- could be valid but not in our registry
                # Mark as invalid only if it matches poison pill patterns
                report.invalid_mpep_sections.append(section)

        # Check case law citations
        case_cites = self.extractor.extract_case_citations(text)
        report.cited_cases = case_cites
        for case in case_cites:
            # Check poison pills first (exact match)
            if case in self.poison_cases:
                report.poison_case_hits.append(case)
                report.fabricated_cases.append(case)
            elif self._case_matches_known(case):
                report.verified_cases.append(case)
            else:
                # Unknown case -- not necessarily fabricated, but flagged
                report.fabricated_cases.append(case)

        # Check statute citations
        statute_cites = self.extractor.extract_statute_citations(text)
        report.cited_statutes = statute_cites
        for section in statute_cites:
            if section not in self.extractor.VALID_USC_SECTIONS:
                report.invalid_statutes.append(section)

        report.compute_score()
        return report

    def _case_matches_known(self, cited_case: str) -> bool:
        """Check if a cited case matches any known valid case (fuzzy)."""
        cited_lower = cited_case.lower().strip()
        for known in self.valid_cases:
            known_lower = known.lower()
            # Check if the core case name matches (before the citation details)
            if known_lower in cited_lower or cited_lower.startswith(known_lower):
                return True
            # Check partial match on the "v." portion
            if " v. " in cited_lower and " v. " in known_lower:
                cited_parties = cited_lower.split(" v. ")
                known_parties = known_lower.split(" v. ")
                if (
                    cited_parties[0].strip().startswith(known_parties[0].strip()[:10])
                    and cited_parties[1].strip().startswith(known_parties[1].strip()[:10])
                ):
                    return True
        return False

    def check_with_context(
        self,
        text: str,
        expected_mpep: list[str] | None = None,
        expected_cases: list[str] | None = None,
    ) -> HallucinationReport:
        """Check with additional context about expected citations.

        Args:
            text: Model output text.
            expected_mpep: MPEP sections that should be cited.
            expected_cases: Case law that should be cited.

        Returns:
            HallucinationReport including coverage analysis.
        """
        report = self.check(text)

        if expected_mpep:
            cited_set = set(report.cited_mpep_sections)
            missing = [s for s in expected_mpep if s not in cited_set]
            report.cited_mpep_sections  # already populated
            if missing:
                report.score *= max(
                    0.5,
                    1.0 - (len(missing) / len(expected_mpep)) * 0.5,
                )

        if expected_cases:
            verified_lower = {c.lower() for c in report.verified_cases}
            missing_cases = [
                c for c in expected_cases
                if not any(c.lower() in v for v in verified_lower)
            ]
            if missing_cases:
                report.score *= max(
                    0.5,
                    1.0 - (len(missing_cases) / len(expected_cases)) * 0.5,
                )

        return report
