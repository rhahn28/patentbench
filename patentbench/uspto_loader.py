"""USPTO Office Action loader and parser.

Loads real Office Actions from the USPTO Patent Examination Data System (PEDS)
and parses XML office actions into structured data.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from pathlib import Path

import httpx

from patentbench.config import RejectionType


# ---- USPTO PEDS API ----

PEDS_API_BASE = "https://ped.uspto.gov/api/queries"
PEDS_DOCUMENTS_BASE = "https://ped.uspto.gov/api/queries/cms/public"


@dataclass
class USPTOApplication:
    """Metadata for a USPTO patent application."""

    application_number: str
    filing_date: str
    title: str
    applicant_name: str
    status: str
    examiner_name: str | None = None
    art_unit: str | None = None
    entity_status: str | None = None
    patent_number: str | None = None


@dataclass
class OfficeAction:
    """A parsed USPTO Office Action."""

    application_number: str
    mailing_date: str
    action_type: str  # "non-final", "final", "advisory", "restriction"
    rejections: list[Rejection] = field(default_factory=list)
    objections: list[str] = field(default_factory=list)
    examiner_name: str | None = None
    art_unit: str | None = None
    response_deadline: str | None = None
    raw_text: str = ""
    raw_xml: str = ""

    @property
    def rejection_types(self) -> list[RejectionType]:
        """Get unique rejection types across all rejections."""
        seen: set[RejectionType] = set()
        result: list[RejectionType] = []
        for r in self.rejections:
            if r.rejection_type not in seen:
                seen.add(r.rejection_type)
                result.append(r.rejection_type)
        return result

    @property
    def claims_at_issue(self) -> list[int]:
        """Get all claim numbers with rejections."""
        claims: set[int] = set()
        for r in self.rejections:
            claims.update(r.claims)
        return sorted(claims)


@dataclass
class Rejection:
    """A single rejection within an Office Action."""

    rejection_type: RejectionType
    claims: list[int]
    basis: str  # The legal basis / examiner's reasoning
    prior_art_refs: list[PriorArtReference] = field(default_factory=list)
    mpep_sections: list[str] = field(default_factory=list)

    @property
    def display_summary(self) -> str:
        claims_str = ", ".join(str(c) for c in self.claims)
        return f"{self.rejection_type.display_name} - Claims {claims_str}"


@dataclass
class PriorArtReference:
    """A prior art reference cited in a rejection."""

    name: str  # e.g., "Smith" or "US 10,000,000"
    document_number: str | None = None
    publication_date: str | None = None
    relevant_portions: str = ""


class USPTOPedsClient:
    """Client for the USPTO Patent Examination Data System (PEDS) API."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.client = httpx.Client(timeout=timeout)

    def search_applications(
        self,
        query: str,
        start: int = 0,
        rows: int = 20,
    ) -> list[USPTOApplication]:
        """Search for patent applications in PEDS.

        Args:
            query: Search query (application number, patent number, or keyword).
            start: Starting offset for pagination.
            rows: Number of results to return.

        Returns:
            List of matching USPTOApplication objects.
        """
        params = {
            "searchText": query,
            "start": start,
            "rows": rows,
        }
        response = self.client.get(PEDS_API_BASE, params=params)
        response.raise_for_status()
        data = response.json()

        results: list[USPTOApplication] = []
        for doc in data.get("queryResults", {}).get("searchResponse", {}).get("response", {}).get("docs", []):
            results.append(USPTOApplication(
                application_number=doc.get("applId", ""),
                filing_date=doc.get("filingDate", ""),
                title=doc.get("inventionTitle", ""),
                applicant_name=doc.get("firstNamedApplicant", ""),
                status=doc.get("appStatus", ""),
                examiner_name=doc.get("appExamName", None),
                art_unit=doc.get("appGrpArtNumber", None),
                entity_status=doc.get("appEntityStatus", None),
                patent_number=doc.get("patentNumber", None),
            ))
        return results

    def get_documents(self, application_number: str) -> list[dict[str, Any]]:
        """Get document list for an application (includes Office Actions).

        Args:
            application_number: USPTO application number (e.g., "16123456").

        Returns:
            List of document metadata dicts.
        """
        url = f"{PEDS_DOCUMENTS_BASE}/{application_number}"
        response = self.client.get(url)
        response.raise_for_status()
        return response.json().get("documentBag", {}).get("documentList", [])

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> USPTOPedsClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class OfficeActionParser:
    """Parses USPTO Office Actions from XML format.

    Extracts rejections, claims, grounds, and prior art references.
    """

    # Patterns for identifying rejection types in OA text
    REJECTION_PATTERNS: dict[RejectionType, list[re.Pattern[str]]] = {
        RejectionType.SEC_101: [
            re.compile(r"35\s+U\.S\.C\.?\s*§?\s*101", re.IGNORECASE),
            re.compile(r"subject\s+matter\s+eligibility", re.IGNORECASE),
            re.compile(r"abstract\s+idea", re.IGNORECASE),
        ],
        RejectionType.SEC_102: [
            re.compile(r"35\s+U\.S\.C\.?\s*§?\s*102\b", re.IGNORECASE),
            re.compile(r"anticipat(?:ed|ion)", re.IGNORECASE),
        ],
        RejectionType.SEC_103: [
            re.compile(r"35\s+U\.S\.C\.?\s*§?\s*103\b", re.IGNORECASE),
            re.compile(r"obvious(?:ness)?", re.IGNORECASE),
        ],
        RejectionType.SEC_112_A: [
            re.compile(r"35\s+U\.S\.C\.?\s*§?\s*112\s*\(a\)", re.IGNORECASE),
            re.compile(r"written\s+description", re.IGNORECASE),
            re.compile(r"enablement", re.IGNORECASE),
        ],
        RejectionType.SEC_112_B: [
            re.compile(r"35\s+U\.S\.C\.?\s*§?\s*112\s*\(b\)", re.IGNORECASE),
            re.compile(r"indefinit(?:e|eness)", re.IGNORECASE),
        ],
        RejectionType.DOUBLE_PATENTING: [
            re.compile(r"double\s+patenting", re.IGNORECASE),
            re.compile(r"obviousness.type\s+double\s+patenting", re.IGNORECASE),
        ],
    }

    CLAIM_PATTERN = re.compile(
        r"[Cc]laims?\s+([\d,\s]+(?:(?:and|through|-)\s*\d+)*)",
    )

    def parse_xml(self, xml_content: str) -> OfficeAction:
        """Parse an Office Action from USPTO XML format.

        Args:
            xml_content: Raw XML string of the Office Action.

        Returns:
            Parsed OfficeAction object.
        """
        root = ET.fromstring(xml_content)

        # Extract top-level metadata
        app_num = self._get_text(root, ".//us-bibliographic-data-application/application-reference/document-id/doc-number")
        mailing_date = self._get_text(root, ".//date-produced") or self._get_text(root, ".//date")
        examiner = self._get_text(root, ".//examiner/name") or self._get_text(root, ".//primary-examiner/name")
        art_unit = self._get_text(root, ".//art-unit")

        # Determine action type
        action_type = self._determine_action_type(root)

        # Extract rejection paragraphs
        rejections = self._extract_rejections(root)

        # Extract objections
        objections = self._extract_objections(root)

        return OfficeAction(
            application_number=app_num or "",
            mailing_date=mailing_date or "",
            action_type=action_type,
            rejections=rejections,
            objections=objections,
            examiner_name=examiner,
            art_unit=art_unit,
            raw_xml=xml_content,
        )

    def parse_text(self, text: str, application_number: str = "") -> OfficeAction:
        """Parse an Office Action from plain text (fallback for non-XML).

        Args:
            text: Plain text content of the Office Action.
            application_number: Application number if known.

        Returns:
            Parsed OfficeAction object.
        """
        rejections: list[Rejection] = []

        # Split into paragraphs and scan for rejection patterns
        paragraphs = text.split("\n\n")
        current_rejection_type: RejectionType | None = None
        current_text: list[str] = []

        for para in paragraphs:
            detected_type = self._detect_rejection_type(para)
            if detected_type:
                # Save previous rejection
                if current_rejection_type and current_text:
                    full_text = "\n".join(current_text)
                    claims = self._extract_claim_numbers(full_text)
                    rejections.append(Rejection(
                        rejection_type=current_rejection_type,
                        claims=claims,
                        basis=full_text,
                    ))
                current_rejection_type = detected_type
                current_text = [para]
            elif current_rejection_type:
                current_text.append(para)

        # Final rejection
        if current_rejection_type and current_text:
            full_text = "\n".join(current_text)
            claims = self._extract_claim_numbers(full_text)
            rejections.append(Rejection(
                rejection_type=current_rejection_type,
                claims=claims,
                basis=full_text,
            ))

        # Determine action type from text
        action_type = "non-final"
        if re.search(r"final\s+(?:office\s+)?action", text, re.IGNORECASE):
            action_type = "final"
        elif re.search(r"advisory\s+action", text, re.IGNORECASE):
            action_type = "advisory"
        elif re.search(r"restriction\s+requirement", text, re.IGNORECASE):
            action_type = "restriction"

        return OfficeAction(
            application_number=application_number,
            mailing_date="",
            action_type=action_type,
            rejections=rejections,
            raw_text=text,
        )

    def _get_text(self, element: ET.Element, xpath: str) -> str | None:
        """Safely get text from an XML element by xpath."""
        found = element.find(xpath)
        return found.text.strip() if found is not None and found.text else None

    def _determine_action_type(self, root: ET.Element) -> str:
        """Determine Office Action type from XML."""
        action_elem = root.find(".//action-type")
        if action_elem is not None and action_elem.text:
            text = action_elem.text.lower()
            if "final" in text:
                return "final"
            if "advisory" in text:
                return "advisory"
            if "restriction" in text:
                return "restriction"
        return "non-final"

    def _extract_rejections(self, root: ET.Element) -> list[Rejection]:
        """Extract rejections from XML Office Action."""
        rejections: list[Rejection] = []

        # Look for rejection elements
        for rejection_elem in root.findall(".//rejection"):
            text = ET.tostring(rejection_elem, encoding="unicode", method="text")
            rejection_type = self._detect_rejection_type(text)
            if rejection_type:
                claims = self._extract_claim_numbers(text)
                prior_art = self._extract_prior_art_from_element(rejection_elem)
                rejections.append(Rejection(
                    rejection_type=rejection_type,
                    claims=claims,
                    basis=text.strip(),
                    prior_art_refs=prior_art,
                ))

        # If no structured rejections found, try full text parsing
        if not rejections:
            full_text = ET.tostring(root, encoding="unicode", method="text")
            return self.parse_text(full_text).rejections

        return rejections

    def _extract_objections(self, root: ET.Element) -> list[str]:
        """Extract claim objections from XML."""
        objections: list[str] = []
        for obj_elem in root.findall(".//objection"):
            text = ET.tostring(obj_elem, encoding="unicode", method="text")
            if text.strip():
                objections.append(text.strip())
        return objections

    def _detect_rejection_type(self, text: str) -> RejectionType | None:
        """Detect the rejection type from a text passage."""
        for rejection_type, patterns in self.REJECTION_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(text):
                    return rejection_type
        return None

    def _extract_claim_numbers(self, text: str) -> list[int]:
        """Extract claim numbers from text like 'Claims 1-5, 7, and 9-12'."""
        claims: set[int] = set()
        for match in self.CLAIM_PATTERN.finditer(text):
            claim_str = match.group(1)
            # Handle ranges like "1-5"
            for part in re.split(r"[,\s]+(?:and\s+)?", claim_str):
                part = part.strip()
                if not part:
                    continue
                range_match = re.match(r"(\d+)\s*[-\u2013\u2014]\s*(\d+)", part)
                if range_match:
                    start = int(range_match.group(1))
                    end = int(range_match.group(2))
                    claims.update(range(start, end + 1))
                elif part.isdigit():
                    claims.add(int(part))
                else:
                    # Try to extract just the number
                    nums = re.findall(r"\d+", part)
                    claims.update(int(n) for n in nums)
        return sorted(claims)

    def _extract_prior_art_from_element(self, element: ET.Element) -> list[PriorArtReference]:
        """Extract prior art references from a rejection XML element."""
        refs: list[PriorArtReference] = []
        for ref_elem in element.findall(".//reference"):
            name = self._get_text(ref_elem, "name") or ""
            doc_num = self._get_text(ref_elem, "document-number")
            pub_date = self._get_text(ref_elem, "date")
            refs.append(PriorArtReference(
                name=name,
                document_number=doc_num,
                publication_date=pub_date,
            ))
        return refs

    @classmethod
    def from_file(cls, path: str | Path) -> OfficeAction:
        """Parse an Office Action from a file (XML or text)."""
        path = Path(path)
        content = path.read_text(encoding="utf-8")
        parser = cls()
        if content.strip().startswith("<?xml") or content.strip().startswith("<"):
            return parser.parse_xml(content)
        return parser.parse_text(content, application_number=path.stem)
