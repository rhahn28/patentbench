"""Unit tests for PatentBench reference XML parser."""

from __future__ import annotations

import pytest

from patentbench.config import RejectionType
from patentbench.xml_parser import (
    expand_claim_ranges,
    parse_claims_xml,
    parse_oa_xml,
    OAParsedResult,
    ParsedClaim,
    FORM_PARAGRAPH_TO_REJECTION,
)


# ---- Claim Range Expansion Tests ----


class TestExpandClaimRanges:

    def test_simple_range(self) -> None:
        assert expand_claim_ranges("Claims 1-5 are rejected") == [1, 2, 3, 4, 5]

    def test_comma_separated(self) -> None:
        assert expand_claim_ranges("Claims 1, 2, 3 are rejected") == [1, 2, 3]

    def test_mixed_range_and_singles(self) -> None:
        result = expand_claim_ranges("Claims 1-5, 7, and 9-12 are rejected")
        assert result == [1, 2, 3, 4, 5, 7, 9, 10, 11, 12]

    def test_single_claim(self) -> None:
        assert expand_claim_ranges("Claim 3 is rejected") == [3]

    def test_no_claims(self) -> None:
        assert expand_claim_ranges("The examiner notes that...") == []

    def test_en_dash_range(self) -> None:
        assert expand_claim_ranges("Claims 1\u20135 are rejected") == [1, 2, 3, 4, 5]

    def test_multiple_claim_refs(self) -> None:
        text = "Claims 1-3 are rejected under 103. Claims 4, 5 are rejected under 112(b)."
        result = expand_claim_ranges(text)
        assert result == [1, 2, 3, 4, 5]

    def test_dedup(self) -> None:
        text = "Claim 1 is rejected. Claims 1-3 are also rejected."
        result = expand_claim_ranges(text)
        assert result == [1, 2, 3]  # No duplicates


# ---- OA XML Parsing Tests ----


SAMPLE_OA_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<OutgoingDocument createDateTime="2024-03-15T00:00:00">
  <ApplicationNumber>16/789,012</ApplicationNumber>
  <FormParagraph id="07-21">
    <P>Claims 1-5 and 12 are rejected under 35 U.S.C. 103 as being
    unpatentable over Johnson (US 10,555,123) in view of Garcia (US 2022/0111222).</P>
  </FormParagraph>
  <FormParagraph id="07-34">
    <P>Claims 6, 7, 8 are rejected under 35 U.S.C. 112(b) as being
    indefinite for failing to particularly point out and distinctly claim
    the subject matter.</P>
  </FormParagraph>
  <FormParagraph id="07-05">
    <P>Claims 9-11 are rejected under 35 U.S.C. 101 because the claimed
    invention is directed to an abstract idea without significantly more.</P>
  </FormParagraph>
</OutgoingDocument>
"""


class TestParseOAXml:

    def test_basic_extraction(self) -> None:
        result = parse_oa_xml(SAMPLE_OA_XML)
        assert len(result.rejections) == 3
        assert set(result.rejection_types) == {"103", "112(b)", "101"}

    def test_claim_extraction(self) -> None:
        result = parse_oa_xml(SAMPLE_OA_XML)
        assert sorted(result.all_claims) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

    def test_103_rejection_claims(self) -> None:
        result = parse_oa_xml(SAMPLE_OA_XML)
        r103 = [r for r in result.rejections if r.rejection_type == RejectionType.SEC_103]
        assert len(r103) == 1
        assert sorted(r103[0].claims) == [1, 2, 3, 4, 5, 12]

    def test_112b_rejection_claims(self) -> None:
        result = parse_oa_xml(SAMPLE_OA_XML)
        r112b = [r for r in result.rejections if r.rejection_type == RejectionType.SEC_112_B]
        assert len(r112b) == 1
        assert sorted(r112b[0].claims) == [6, 7, 8]

    def test_reference_extraction(self) -> None:
        result = parse_oa_xml(SAMPLE_OA_XML)
        r103 = [r for r in result.rejections if r.rejection_type == RejectionType.SEC_103]
        assert len(r103[0].references) >= 1

    def test_metadata(self) -> None:
        result = parse_oa_xml(SAMPLE_OA_XML)
        assert result.mail_date == "2024-03-15"
        assert result.application_number == "16/789,012"

    def test_form_paragraph_source(self) -> None:
        result = parse_oa_xml(SAMPLE_OA_XML)
        for rej in result.rejections:
            assert rej.source == "form_paragraph"

    def test_to_dict(self) -> None:
        result = parse_oa_xml(SAMPLE_OA_XML)
        d = result.to_dict()
        assert "rejection_types" in d
        assert "claims" in d
        assert "rejections" in d
        assert sorted(d["rejection_types"]) == ["101", "103", "112(b)"]


class TestParseOATextFallback:

    def test_text_only_parsing(self) -> None:
        text = (
            "Claims 1-5 are rejected under 35 U.S.C. 103 as obvious.\n\n"
            "Claims 6-8 are rejected under 35 U.S.C. 112(b) as indefinite."
        )
        result = parse_oa_xml(text)  # Will fail XML parse, fall back to text
        assert "103" in result.rejection_types
        assert "112(b)" in result.rejection_types

    def test_malformed_xml_fallback(self) -> None:
        bad_xml = "<broken><unclosed"
        result = parse_oa_xml(bad_xml)
        assert isinstance(result, OAParsedResult)


# ---- Claims XML Parsing Tests ----


SAMPLE_CLAIMS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<claims>
  <claim num="1">
    <claim-text>A method for processing data, comprising:
    receiving input data from a sensor;
    applying a transformation algorithm to the input data; and
    outputting processed results.</claim-text>
  </claim>
  <claim num="2">
    <claim-text>The method of claim 1, wherein the transformation
    algorithm comprises a neural network.</claim-text>
    <claim-ref idref="1"/>
  </claim>
  <claim num="3">
    <claim-text>The method of claim 1, further comprising storing
    the processed results in a database.</claim-text>
    <claim-ref idref="1"/>
  </claim>
  <claim num="4">
    <claim-text>A system for processing data, comprising:
    a processor configured to execute instructions; and
    a memory storing the instructions.</claim-text>
  </claim>
</claims>
"""


class TestParseClaimsXml:

    def test_basic_extraction(self) -> None:
        claims = parse_claims_xml(SAMPLE_CLAIMS_XML)
        assert len(claims) == 4

    def test_claim_numbers(self) -> None:
        claims = parse_claims_xml(SAMPLE_CLAIMS_XML)
        numbers = [c.number for c in claims]
        assert numbers == [1, 2, 3, 4]

    def test_independent_claims(self) -> None:
        claims = parse_claims_xml(SAMPLE_CLAIMS_XML)
        independent = [c for c in claims if c.is_independent]
        assert len(independent) == 2  # Claims 1 and 4

    def test_dependent_claims(self) -> None:
        claims = parse_claims_xml(SAMPLE_CLAIMS_XML)
        claim_2 = next(c for c in claims if c.number == 2)
        assert claim_2.dependent_on == 1
        assert not claim_2.is_independent

    def test_claim_text(self) -> None:
        claims = parse_claims_xml(SAMPLE_CLAIMS_XML)
        claim_1 = next(c for c in claims if c.number == 1)
        assert "processing data" in claim_1.text

    def test_text_fallback(self) -> None:
        text = "1. A method comprising receiving data.\n2. The method of claim 1, further comprising processing."
        claims = parse_claims_xml(text)
        assert len(claims) == 2
        assert claims[0].number == 1
        assert claims[1].dependent_on == 1


# ---- Form Paragraph Mapping Tests ----


class TestFormParagraphMapping:

    def test_103_mappings(self) -> None:
        for fp in ["07-21", "07-22", "07-23", "07-24", "07-25", "07-26"]:
            assert FORM_PARAGRAPH_TO_REJECTION[fp] == RejectionType.SEC_103

    def test_101_mappings(self) -> None:
        for fp in ["07-04", "07-05"]:
            assert FORM_PARAGRAPH_TO_REJECTION[fp] == RejectionType.SEC_101

    def test_112_differentiation(self) -> None:
        assert FORM_PARAGRAPH_TO_REJECTION["07-31"] == RejectionType.SEC_112_A
        assert FORM_PARAGRAPH_TO_REJECTION["07-34"] == RejectionType.SEC_112_B

    def test_double_patenting(self) -> None:
        assert FORM_PARAGRAPH_TO_REJECTION["08-26"] == RejectionType.DOUBLE_PATENTING
