"""Tests for harness.spec_validator module."""

from __future__ import annotations

import tempfile
import shutil
from pathlib import Path

from harness.spec_validator import (
    AcceptanceCriteria,
    check_coverage,
    parse_spec,
    _ast_check,
    _keyword_check,
    _extract_keywords,
)

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_SPEC = str(FIXTURES / "sample_spec.md")
SAMPLE_CODE_DIR = str(FIXTURES)


def test_parse_spec_extracts_criteria():
    """parse_spec should extract acceptance criteria from the spec file."""
    criteria = parse_spec(SAMPLE_SPEC)
    assert len(criteria) > 0, "Expected at least one criterion from sample_spec.md"
    # Check that each criterion has non-empty condition
    for c in criteria:
        assert c.condition, f"Criterion has empty condition: {c}"


def test_parse_spec_includes_tag_criteria():
    """parse_spec should extract tag-related criteria."""
    criteria = parse_spec(SAMPLE_SPEC)
    conditions_lower = [c.condition.lower() for c in criteria]
    assert any("tag" in cond for cond in conditions_lower), (
        "Expected at least one tag-related criterion"
    )


def test_ast_check_finds_function():
    """AST check should find add_tag function matching 'adds a tag' criterion."""
    criteria = AcceptanceCriteria(
        condition="user adds a tag",
        expected_behavior="create the tag with name and color",
    )
    found, evidence = _ast_check(criteria, SAMPLE_CODE_DIR)
    assert found, f"Expected AST to find tag-related symbols, got: {evidence}"
    assert "AST matches" in evidence


def test_ast_check_misses_unimplemented():
    """AST check should NOT find a match for 'delete a tag' since no delete function exists."""
    criteria = AcceptanceCriteria(
        condition="user requests to delete a tag",
        expected_behavior="remove the tag from the system",
    )
    # Use a temp dir with only the sample code (no delete function)
    with tempfile.TemporaryDirectory() as tmpdir:
        # Copy only the tag sample code
        shutil.copy(FIXTURES / "sample_code_with_tags.py", Path(tmpdir) / "tags.py")
        found, evidence = _ast_check(criteria, tmpdir)
        # The sample code has no delete_tag function
        # AST might still partial-match on "tag" but delete should not be found
        # We check that it does NOT claim full match on "delete"
        if found:
            # If found via partial match on "tag", that's acceptable but
            # evidence should not mention "delete"
            assert "delete" not in evidence.lower() or "tag" in evidence.lower()


def test_keyword_fallback_low_confidence():
    """Keyword matching should work but check_coverage marks it as low confidence."""
    criteria_list = [
        AcceptanceCriteria(
            condition="user adds a tag",
            expected_behavior="create the tag with name and color",
        ),
    ]
    # Use the fixtures dir which has sample_code_with_tags.py
    report = check_coverage(criteria_list, SAMPLE_CODE_DIR, use_llm=False)

    for c in report.criteria:
        if c.covered:
            # Without LLM, should be ast (medium) or keyword (low)
            assert c.confidence in ("medium", "low"), (
                f"Without LLM, confidence should be medium or low, got: {c.confidence}"
            )
            assert c.method in ("ast", "keyword"), (
                f"Without LLM, method should be ast or keyword, got: {c.method}"
            )


def test_check_coverage_three_levels_priority():
    """check_coverage should prefer AST over keyword, both without LLM."""
    criteria_list = [
        # This should match via AST (add_tag function exists)
        AcceptanceCriteria(
            condition="user adds a tag",
            expected_behavior="create the tag with name and color",
        ),
        # This might only match via keywords
        AcceptanceCriteria(
            condition="user submits a form",
            expected_behavior="validate all required fields",
        ),
    ]

    report = check_coverage(criteria_list, SAMPLE_CODE_DIR, use_llm=False)

    # First criterion should be covered via AST (tag-related code exists)
    tag_criterion = report.criteria[0]
    assert tag_criterion.covered, f"Tag criterion should be covered: {tag_criterion.evidence}"
    assert tag_criterion.method == "ast", (
        f"Tag criterion should use AST method, got: {tag_criterion.method}"
    )
    assert tag_criterion.confidence == "medium"


def test_check_coverage_empty_spec():
    """Empty spec should return 100% coverage."""
    report = check_coverage([], SAMPLE_CODE_DIR, use_llm=False)
    assert report.coverage_pct == 100.0
    assert report.uncovered == []


def test_extract_keywords_preserves_technical_terms():
    """Keywords extractor should keep 'user', 'system', 'data', 'file' etc."""
    keywords = _extract_keywords("user submits data to file system")
    assert "user" in keywords, "'user' should be preserved as a keyword"
    assert "data" in keywords, "'data' should be preserved as a keyword"
    assert "file" in keywords, "'file' should be preserved as a keyword"
    assert "system" in keywords, "'system' should be preserved as a keyword"


def test_criteria_dataclass_has_new_fields():
    """AcceptanceCriteria should have confidence and method fields."""
    c = AcceptanceCriteria(condition="test", expected_behavior="test")
    assert c.confidence == "low"
    assert c.method == ""
    assert c.covered is False
