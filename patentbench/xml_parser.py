"""Reference XML parser for USPTO Office Actions and Claims.

Provides basic structural parsing of USPTO OA2XML and Claims XML formats.
This is a reference implementation based on public MPEP and USPTO documentation,
intended to level the playing field for PatentBench participants.

Systems with more sophisticated XML parsers (handling archive formats, image-safe
extraction, multi-tier fallbacks, etc.) will naturally perform better on edge cases.

Public standards used:
- MPEP Form Paragraphs: https://www.uspto.gov/web/offices/pac/mpep/
- USPTO OA2XML schema: https://www.uspto.gov/patents/apply
- 35 U.S.C. statutory sections
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

from patentbench.config import RejectionType


# ---- Public MPEP Form Paragraph → Rejection Type Mapping ----
# These form paragraph numbers are published in the Manual of Patent
# Examining Procedure and used by USPTO examiners in Office Actions.

FORM_PARAGRAPH_TO_REJECTION: dict[str, RejectionType] = {
    # 35 U.S.C. 101 — Subject Matter Eligibility
    "07-04": RejectionType.SEC_101,
    "07-04.01": RejectionType.SEC_101,
    "07-05": RejectionType.SEC_101,
    "07-05.01": RejectionType.SEC_101,
    "07-05.02": RejectionType.SEC_101,
    # 35 U.S.C. 102 — Novelty / Anticipation
    "07-15": RejectionType.SEC_102,
    "07-15.01": RejectionType.SEC_102,
    "07-16": RejectionType.SEC_102,
    "07-17": RejectionType.SEC_102_A,
    "07-18": RejectionType.SEC_102_A,
    "07-19": RejectionType.SEC_102_B,
    # 35 U.S.C. 103 — Obviousness
    "07-21": RejectionType.SEC_103,
    "07-21.01": RejectionType.SEC_103,
    "07-22": RejectionType.SEC_103,
    "07-23": RejectionType.SEC_103,
    "07-24": RejectionType.SEC_103,
    "07-25": RejectionType.SEC_103,
    "07-26": RejectionType.SEC_103,
    # 35 U.S.C. 112(a) — Written Description / Enablement
    "07-31": RejectionType.SEC_112_A,
    "07-31.01": RejectionType.SEC_112_A,
    "07-31.02": RejectionType.SEC_112_A,
    "07-32": RejectionType.SEC_112_A,
    "07-33": RejectionType.SEC_112_A,
    # 35 U.S.C. 112(b) — Indefiniteness
    "07-34": RejectionType.SEC_112_B,
    "07-34.01": RejectionType.SEC_112_B,
    "07-34.02": RejectionType.SEC_112_B,
    "07-35": RejectionType.SEC_112_B,
    # 35 U.S.C. 112(d) — Dependent Claim Requirements
    "07-36": RejectionType.SEC_112_D,
    # 35 U.S.C. 112(f) — Means-Plus-Function
    "07-38": RejectionType.SEC_112_F,
    # Double Patenting
    "08-26": RejectionType.DOUBLE_PATENTING,
    "08-27": RejectionType.DOUBLE_PATENTING,
    "08-33": RejectionType.DOUBLE_PATENTING,
    "08-34": RejectionType.DOUBLE_PATENTING,
    # Restriction Requirement
    "08-13": RejectionType.RESTRICTION,
    "08-14": RejectionType.RESTRICTION,
    "08-20": RejectionType.RESTRICTION,
}

# Regex patterns for statute citation detection in text
_STATUTE_PATTERNS: dict[RejectionType, re.Pattern[str]] = {
    RejectionType.SEC_101: re.compile(
        r'(?:35\s+U\.?S\.?C\.?\s+§?\s*101|§\s*101|section\s+101)', re.IGNORECASE
    ),
    RejectionType.SEC_102: re.compile(
        r'(?:35\s+U\.?S\.?C\.?\s+§?\s*102(?!\s*\()|\b102\b(?!\s*\())', re.IGNORECASE
    ),
    RejectionType.SEC_102_A: re.compile(
        r'(?:35\s+U\.?S\.?C\.?\s+§?\s*102\s*\(a\)|§\s*102\s*\(a\))', re.IGNORECASE
    ),
    RejectionType.SEC_102_B: re.compile(
        r'(?:35\s+U\.?S\.?C\.?\s+§?\s*102\s*\(b\)|§\s*102\s*\(b\))', re.IGNORECASE
    ),
    RejectionType.SEC_103: re.compile(
        r'(?:35\s+U\.?S\.?C\.?\s+§?\s*103|§\s*103|section\s+103)', re.IGNORECASE
    ),
    RejectionType.SEC_112_A: re.compile(
        r'(?:35\s+U\.?S\.?C\.?\s+§?\s*112\s*\(a\)|§\s*112\s*\(a\)|'
        r'written\s+description|enablement)', re.IGNORECASE
    ),
    RejectionType.SEC_112_B: re.compile(
        r'(?:35\s+U\.?S\.?C\.?\s+§?\s*112\s*\(b\)|§\s*112\s*\(b\)|'
        r'indefinite(?:ness)?)', re.IGNORECASE
    ),
    RejectionType.SEC_112_D: re.compile(
        r'(?:35\s+U\.?S\.?C\.?\s+§?\s*112\s*\(d\)|§\s*112\s*\(d\))', re.IGNORECASE
    ),
    RejectionType.SEC_112_F: re.compile(
        r'(?:35\s+U\.?S\.?C\.?\s+§?\s*112\s*\(f\)|§\s*112\s*\(f\)|'
        r'means[- ]plus[- ]function)', re.IGNORECASE
    ),
    RejectionType.DOUBLE_PATENTING: re.compile(
        r'(?:double\s+patenting|obviousness[- ]type\s+double)', re.IGNORECASE
    ),
    RejectionType.RESTRICTION: re.compile(
        r'(?:restriction\s+requirement)', re.IGNORECASE
    ),
}

# Claim number extraction patterns
_CLAIM_PATTERN = re.compile(
    r'(?i)\bclaims?\s+([\d,\s\-–—and]+)', re.IGNORECASE
)
_CLAIM_RANGE = re.compile(r'(\d+)\s*[-–—]\s*(\d+)')
_CLAIM_SINGLE = re.compile(r'(\d+)')


@dataclass
class ParsedRejection:
    """A single rejection extracted from an Office Action."""

    rejection_type: RejectionType
    claims: list[int] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    text: str = ""
    source: str = ""  # "form_paragraph", "statute_regex", "text_fallback"


@dataclass
class OAParsedResult:
    """Complete parsed result from an Office Action."""

    rejections: list[ParsedRejection] = field(default_factory=list)
    all_claims: list[int] = field(default_factory=list)
    rejection_types: list[str] = field(default_factory=list)
    mail_date: str | None = None
    examiner: str | None = None
    application_number: str | None = None
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rejection_types": self.rejection_types,
            "claims": sorted(set(self.all_claims)),
            "rejections": [
                {
                    "type": r.rejection_type.value,
                    "claims": r.claims,
                    "references": r.references,
                }
                for r in self.rejections
            ],
        }


@dataclass
class ParsedClaim:
    """A single claim extracted from a Claims XML document."""

    number: int
    text: str
    dependent_on: int | None = None
    is_independent: bool = True


def expand_claim_ranges(text: str) -> list[int]:
    """Expand claim range expressions into individual claim numbers.

    Handles formats like:
        "1-5, 7, and 9-12" → [1, 2, 3, 4, 5, 7, 9, 10, 11, 12]
        "Claims 1, 2, 3"   → [1, 2, 3]
        "Claim 3"           → [3]

    Args:
        text: Text containing claim number references.

    Returns:
        Sorted list of unique claim numbers.
    """
    claims: set[int] = set()

    # Find all claim references
    for match in _CLAIM_PATTERN.finditer(text):
        claims_text = match.group(1)
        # Expand ranges first
        for range_match in _CLAIM_RANGE.finditer(claims_text):
            start, end = int(range_match.group(1)), int(range_match.group(2))
            claims.update(range(start, end + 1))
        # Then pick up individual numbers (excluding those already in ranges)
        range_spans = {range_match.span() for range_match in _CLAIM_RANGE.finditer(claims_text)}
        for single_match in _CLAIM_SINGLE.finditer(claims_text):
            # Skip numbers that are part of a range
            in_range = any(
                start <= single_match.start() < end
                for start, end in range_spans
            )
            if not in_range:
                claims.add(int(single_match.group(1)))

    return sorted(claims)


def _strip_namespaces(xml_str: str) -> str:
    """Remove XML namespace prefixes for simpler parsing.

    Handles common USPTO namespaces:
    - {urn:us:gov:doc:uspto:common}
    - {http://www.wipo.int/standards/XMLSchema/ST96/...}
    """
    # Remove namespace URIs from tags
    xml_str = re.sub(r'\{[^}]+\}', '', xml_str)
    # Remove namespace prefixes like uscom: oa: pat:
    xml_str = re.sub(r'<(/?)(?:uscom|oa|pat|com):', r'<\1', xml_str)
    return xml_str


def parse_oa_xml(xml_content: str) -> OAParsedResult:
    """Parse a USPTO Office Action XML document.

    Implements a two-tier extraction strategy:
    1. FormParagraph-based: Map MPEP form paragraph numbers to rejection types
    2. Statute regex fallback: Search text content for statutory citations

    This is a reference implementation. Production parsers may add additional
    tiers (section-context enrichment, boundary markers, etc.).

    Args:
        xml_content: Raw XML string of the Office Action.

    Returns:
        OAParsedResult with extracted rejections, claims, and metadata.
    """
    result = OAParsedResult()

    # Strip namespaces for simpler element access
    cleaned = _strip_namespaces(xml_content)

    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError:
        # Fallback to text-based extraction if XML is malformed
        return _parse_oa_text(xml_content, result)

    # Extract full text content for fallback parsing
    result.raw_text = _element_text(root)

    # Extract metadata
    _extract_metadata(root, result)

    # Tier 1: FormParagraph-based extraction
    fp_rejections = _extract_from_form_paragraphs(root)

    # Tier 2: Statute regex on full text (catches rejections without FormParagraphs)
    text_rejections = _extract_from_text(result.raw_text)

    # Merge: FormParagraph results take priority
    seen_types: set[str] = set()
    for rej in fp_rejections:
        result.rejections.append(rej)
        seen_types.add(rej.rejection_type.value)

    for rej in text_rejections:
        if rej.rejection_type.value not in seen_types:
            result.rejections.append(rej)
            seen_types.add(rej.rejection_type.value)

    # Aggregate
    result.rejection_types = sorted(seen_types)
    all_claims: set[int] = set()
    for rej in result.rejections:
        all_claims.update(rej.claims)
    result.all_claims = sorted(all_claims)

    return result


def _element_text(element: ET.Element) -> str:
    """Recursively extract all text from an XML element tree."""
    parts: list[str] = []
    if element.text:
        parts.append(element.text.strip())
    for child in element:
        parts.append(_element_text(child))
        if child.tail:
            parts.append(child.tail.strip())
    return " ".join(p for p in parts if p)


def _extract_metadata(root: ET.Element, result: OAParsedResult) -> None:
    """Extract mail date, examiner, and application number from XML."""
    # Mail date from attributes or elements
    for elem in root.iter():
        if 'createDateTime' in elem.attrib:
            date_str = elem.attrib['createDateTime']
            # Extract YYYY-MM-DD from ISO format
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})', date_str)
            if date_match:
                result.mail_date = date_match.group(1)
                break

    # Application number
    for tag in ('ApplicationNumber', 'applicationNumber', 'PatentApplicationIdentification'):
        for elem in root.iter(tag):
            text = _element_text(elem)
            app_match = re.search(r'(\d{2}/[\d,]+)', text)
            if app_match:
                result.application_number = app_match.group(1)
                break

    # Examiner name
    text = result.raw_text
    examiner_match = re.search(
        r'(?:directed\s+to|contact)\s+([A-Z][A-Z\s]+?)(?:\s+whose|\s+at\s+)',
        text,
    )
    if examiner_match:
        result.examiner = examiner_match.group(1).strip()


def _extract_from_form_paragraphs(root: ET.Element) -> list[ParsedRejection]:
    """Extract rejections by mapping FormParagraph elements to rejection types."""
    rejections: list[ParsedRejection] = []
    current_rejection: ParsedRejection | None = None

    for elem in root.iter():
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

        # Detect FormParagraph elements
        if tag in ('FormParagraph', 'formParagraph', 'FP'):
            fp_num = elem.attrib.get('id', '') or elem.attrib.get('number', '')
            if not fp_num:
                # Try text content
                fp_text = (elem.text or '').strip()
                fp_match = re.match(r'(\d{2}-\d{2}(?:\.\d+)?)', fp_text)
                if fp_match:
                    fp_num = fp_match.group(1)

            if fp_num in FORM_PARAGRAPH_TO_REJECTION:
                rej_type = FORM_PARAGRAPH_TO_REJECTION[fp_num]
                current_rejection = ParsedRejection(
                    rejection_type=rej_type,
                    source="form_paragraph",
                )
                rejections.append(current_rejection)

        # Extract claims from P elements following a rejection
        elif tag == 'P' and current_rejection is not None:
            p_text = _element_text(elem)
            claims = expand_claim_ranges(p_text)
            if claims:
                current_rejection.claims.extend(claims)

            # Extract prior art references
            refs = _extract_references(p_text)
            current_rejection.references.extend(refs)

    # Deduplicate claims per rejection
    for rej in rejections:
        rej.claims = sorted(set(rej.claims))
        rej.references = list(dict.fromkeys(rej.references))

    return rejections


def _extract_from_text(text: str) -> list[ParsedRejection]:
    """Extract rejections from plain text using statute regex patterns."""
    rejections: list[ParsedRejection] = []

    # Split text into paragraphs for context
    paragraphs = re.split(r'\n\s*\n', text)

    for rej_type, pattern in _STATUTE_PATTERNS.items():
        for para in paragraphs:
            if pattern.search(para) and re.search(r'(?i)reject', para):
                claims = expand_claim_ranges(para)
                refs = _extract_references(para)
                rejections.append(ParsedRejection(
                    rejection_type=rej_type,
                    claims=claims,
                    references=refs,
                    text=para[:200],
                    source="statute_regex",
                ))
                break  # One rejection per type

    return rejections


def _extract_references(text: str) -> list[str]:
    """Extract prior art reference citations from text.

    Handles common formats:
    - "Author (US X,XXX,XXX)"
    - "Author (US 20XX/XXXXXXX)"
    - "Author et al." references
    """
    refs: list[str] = []

    # US Patent numbers: (US X,XXX,XXX) or (US XX,XXX,XXX)
    for m in re.finditer(r'(\w[\w\s.]+?)\s*\(US\s*([\d,/]+)\)', text):
        refs.append(f"{m.group(1).strip()} (US {m.group(2)})")

    # US Publication numbers: (US 20XX/XXXXXXX)
    for m in re.finditer(r'(\w[\w\s.]+?)\s*\(US\s*(\d{4}/\d{7})\)', text):
        ref = f"{m.group(1).strip()} (US {m.group(2)})"
        if ref not in refs:
            refs.append(ref)

    return refs


def _parse_oa_text(xml_content: str, result: OAParsedResult) -> OAParsedResult:
    """Fallback: parse Office Action as plain text when XML parsing fails."""
    result.raw_text = xml_content
    text_rejections = _extract_from_text(xml_content)
    for rej in text_rejections:
        result.rejections.append(rej)
    result.rejection_types = sorted(set(r.rejection_type.value for r in result.rejections))
    all_claims: set[int] = set()
    for rej in result.rejections:
        all_claims.update(rej.claims)
    result.all_claims = sorted(all_claims)
    return result


def parse_claims_xml(xml_content: str) -> list[ParsedClaim]:
    """Parse a USPTO Claims XML document.

    Extracts claim text, numbers, and dependency relationships from
    standard USPTO claims XML format.

    Args:
        xml_content: Raw XML string of the claims document.

    Returns:
        List of ParsedClaim objects.
    """
    cleaned = _strip_namespaces(xml_content)

    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError:
        return _parse_claims_text(xml_content)

    claims: list[ParsedClaim] = []

    # Look for claim elements in various formats
    for claim_elem in root.iter('claim'):
        claim_num = None
        claim_text_parts: list[str] = []

        # Get claim number from attributes
        num_attr = claim_elem.attrib.get('num', '') or claim_elem.attrib.get('id', '')
        num_match = re.search(r'(\d+)', num_attr)
        if num_match:
            claim_num = int(num_match.group(1))

        # Extract claim text from child elements
        for child in claim_elem.iter():
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            # Skip dependency reference metadata
            if tag == 'claim-ref' or tag == 'depend-claim-ref':
                continue
            if child.text:
                claim_text_parts.append(child.text.strip())
            if child.tail:
                claim_text_parts.append(child.tail.strip())

        claim_text = " ".join(p for p in claim_text_parts if p)

        if claim_num is None:
            # Try to extract from text
            text_num = re.match(r'(\d+)\.\s', claim_text)
            if text_num:
                claim_num = int(text_num.group(1))

        if claim_num is None:
            continue

        # Detect dependency
        dependent_on = None
        dep_match = re.search(r'(?:claim|claims?)\s+(\d+)', claim_text, re.IGNORECASE)
        if dep_match and 'depend' in claim_text.lower()[:100]:
            dependent_on = int(dep_match.group(1))

        # Also check for dependency elements
        for dep_elem in claim_elem.iter('claim-ref'):
            dep_text = dep_elem.text or dep_elem.attrib.get('idref', '')
            dep_num = re.search(r'(\d+)', dep_text)
            if dep_num:
                dependent_on = int(dep_num.group(1))

        claims.append(ParsedClaim(
            number=claim_num,
            text=claim_text,
            dependent_on=dependent_on,
            is_independent=dependent_on is None,
        ))

    return claims


def _parse_claims_text(text: str) -> list[ParsedClaim]:
    """Fallback: extract claims from plain text."""
    claims: list[ParsedClaim] = []
    # Match "1. A method comprising..." pattern
    for m in re.finditer(r'(\d+)\.\s+(.+?)(?=\n\d+\.\s|\Z)', text, re.DOTALL):
        num = int(m.group(1))
        claim_text = m.group(2).strip()
        dep_match = re.search(r'(?:claim|claims?)\s+(\d+)', claim_text, re.IGNORECASE)
        dependent_on = int(dep_match.group(1)) if dep_match and num > 1 else None
        claims.append(ParsedClaim(
            number=num,
            text=claim_text,
            dependent_on=dependent_on,
            is_independent=dependent_on is None,
        ))
    return claims
