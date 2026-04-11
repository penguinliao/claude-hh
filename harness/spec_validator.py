"""
Spec Compliance Validator v2

Three-level validation (from precise to fuzzy):
1. LLM semantic judgment (primary): Ask LLM "does this code implement this criterion?"
2. AST structural analysis (middle): Check if functions/classes/routes/tables exist
3. Keyword matching (fallback): Marked as "low confidence"

Each criterion outputs: coverage status + confidence (high/medium/low) + evidence
"""

from __future__ import annotations

import ast
import re
import os
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AcceptanceCriteria:
    """A single acceptance criterion from the spec."""

    condition: str
    expected_behavior: str
    covered: bool = False
    confidence: str = "low"  # "high" (LLM) / "medium" (AST) / "low" (keyword)
    evidence: str = ""
    method: str = ""  # "llm" / "ast" / "keyword" / "none"


@dataclass
class SpecReport:
    """Report of spec coverage."""

    criteria: list[AcceptanceCriteria]
    coverage_pct: float
    uncovered: list[AcceptanceCriteria] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)  # Degradation notices


# ---------------------------------------------------------------------------
# Spec parsing
# ---------------------------------------------------------------------------

# Patterns for matching acceptance criteria
_PATTERNS = [
    # "When X, should Y" / "When X, it should Y"
    re.compile(
        r"[Ww]hen\s+(.+?),\s+(?:it\s+)?should\s+(.+?)(?:\.|$)",
        re.MULTILINE,
    ),
    # "Given X, then Y"
    re.compile(
        r"[Gg]iven\s+(.+?),\s+then\s+(.+?)(?:\.|$)",
        re.MULTILINE,
    ),
    # "If X, then Y"
    re.compile(
        r"[Ii]f\s+(.+?),\s+then\s+(.+?)(?:\.|$)",
        re.MULTILINE,
    ),
    # Markdown checkbox "- [ ] X" or "- [x] X"
    re.compile(
        r"-\s+\[[ x]\]\s+(.+?)(?:\n|$)",
        re.MULTILINE,
    ),
    # "Must X" / "Should X" at start of line or after bullet
    re.compile(
        r"(?:^|\n)\s*[-*]?\s*(?:Must|Should|Shall)\s+(.+?)(?:\.|$)",
        re.MULTILINE,
    ),
]


def parse_spec(spec_path: str) -> list[AcceptanceCriteria]:
    """Parse a spec file and extract acceptance criteria.

    Args:
        spec_path: Path to the spec markdown file.

    Returns:
        List of AcceptanceCriteria found in the spec.
    """
    path = Path(spec_path)
    if not path.exists():
        return []

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    criteria: list[AcceptanceCriteria] = []
    seen: set[str] = set()

    for pattern in _PATTERNS:
        for match in pattern.finditer(content):
            groups = match.groups()
            if len(groups) == 2:
                condition = groups[0].strip()
                behavior = groups[1].strip()
            elif len(groups) == 1:
                # Single-group patterns (checkbox, must/should)
                text = groups[0].strip()
                condition = text
                behavior = text
            else:
                continue

            # Dedup by condition text
            key = condition.lower()
            if key in seen:
                continue
            seen.add(key)

            criteria.append(AcceptanceCriteria(
                condition=condition,
                expected_behavior=behavior,
            ))

    return criteria


# ---------------------------------------------------------------------------
# Level 1: LLM semantic judgment
# ---------------------------------------------------------------------------

def _llm_check(
    criteria: AcceptanceCriteria,
    code_snippets: dict[str, str],
) -> tuple[bool, str] | None:
    """Use LLM to judge whether code implements the acceptance criterion.

    Returns (covered, evidence) or None if LLM is unavailable.
    """
    try:
        import anthropic  # noqa: F811
    except ImportError:
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    # Build code context (truncate to avoid huge prompts)
    code_text_parts: list[str] = []
    total_chars = 0
    max_chars = 15000
    for filename, content in code_snippets.items():
        if total_chars >= max_chars:
            break
        snippet = content[:max_chars - total_chars]
        code_text_parts.append(f"--- {filename} ---\n{snippet}")
        total_chars += len(snippet)
    code_text = "\n\n".join(code_text_parts)

    prompt = (
        f"Acceptance criterion:\n"
        f"  Condition: {criteria.condition}\n"
        f"  Expected behavior: {criteria.expected_behavior}\n\n"
        f"Code:\n{code_text}\n\n"
        f"Does the code implement this acceptance criterion? "
        f"Answer ONLY 'YES' or 'NO' on the first line, then a brief reason on the second line."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key, timeout=10.0)
        response = client.messages.create(
            model="claude-haiku-4-20250414",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        lines = text.split("\n", 1)
        answer = lines[0].strip().upper()
        reason = lines[1].strip() if len(lines) > 1 else ""

        if "YES" in answer:
            return (True, f"LLM: {reason}" if reason else "LLM: criterion implemented")
        elif "NO" in answer:
            return (False, f"LLM: {reason}" if reason else "LLM: criterion not implemented")
        else:
            # Ambiguous answer
            return None
    except Exception as e:
        logger.debug(f"LLM check failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Level 2: AST structural analysis
# ---------------------------------------------------------------------------

def _extract_entities_from_text(text: str) -> list[str]:
    """Extract potential entity names from criteria text.

    Looks for:
    - snake_case identifiers (add_tag, delete_user)
    - CamelCase identifiers (TagModel, UserService)
    - Meaningful words that could be function/class names
    """
    entities: list[str] = []

    # Direct code identifiers (snake_case or camelCase)
    code_ids = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*(?:_[a-zA-Z0-9_]+)+", text)
    entities.extend(code_ids)

    # CamelCase
    camel = re.findall(r"[A-Z][a-z]+(?:[A-Z][a-z]+)+", text)
    entities.extend(camel)

    # Extract meaningful words (excluding true grammar stopwords)
    grammar_stops = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "must", "can", "could", "it", "its",
        "that", "this", "those", "these", "and", "or", "but", "if", "then",
        "when", "where", "who", "what", "which", "how", "not", "no", "all",
        "any", "each", "every", "both", "few", "more", "most", "other",
        "some", "such", "than", "too", "very", "just", "only", "own",
        "same", "so", "with", "for", "from", "into", "to", "of", "in",
        "on", "at", "by", "up", "about", "out", "off", "over", "under",
    }
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
    meaningful = [w for w in words if len(w) > 2 and w not in grammar_stops]
    entities.extend(meaningful)

    return entities


def _collect_ast_symbols(code_dir: str) -> dict[str, set[str]]:
    """Parse all .py files in directory and collect AST symbols.

    Returns dict with keys:
    - "functions": set of function names
    - "classes": set of class names
    - "decorators": set of decorator strings (e.g., "app.get", "router.post")
    - "strings": set of string literals
    - "imports": set of imported module names
    """
    symbols: dict[str, set[str]] = {
        "functions": set(),
        "classes": set(),
        "decorators": set(),
        "strings": set(),
        "imports": set(),
    }

    code_path = Path(code_dir)
    if not code_path.is_dir():
        return symbols

    for py_file in code_path.rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                symbols["functions"].add(node.name.lower())
                # Check decorators
                for dec in node.decorator_list:
                    dec_str = _decorator_to_string(dec)
                    if dec_str:
                        symbols["decorators"].add(dec_str.lower())

            elif isinstance(node, ast.ClassDef):
                symbols["classes"].add(node.name.lower())

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    symbols["imports"].add(alias.name.lower())

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    symbols["imports"].add(node.module.lower())
                for alias in node.names:
                    symbols["imports"].add(alias.name.lower())

            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Store short strings that might be route paths, table names, etc.
                val = node.value.strip()
                if 2 < len(val) < 200:
                    symbols["strings"].add(val.lower())

    return symbols


def _decorator_to_string(node: ast.expr) -> str:
    """Convert a decorator AST node to a readable string."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        value_str = _decorator_to_string(node.value)
        if value_str:
            return f"{value_str}.{node.attr}"
        return node.attr
    elif isinstance(node, ast.Call):
        return _decorator_to_string(node.func)
    return ""


def _ast_check(criteria: AcceptanceCriteria, code_dir: str) -> tuple[bool, str]:
    """Use AST analysis to check if code structure matches the criterion.

    Extracts entity names from criteria text, then searches AST symbols
    for matching functions, classes, decorators, routes, or string literals.

    Returns (found, evidence_str).
    """
    combined_text = f"{criteria.condition} {criteria.expected_behavior}"
    entities = _extract_entities_from_text(combined_text)

    if not entities:
        return (False, "No entities extracted from criteria")

    symbols = _collect_ast_symbols(code_dir)
    all_symbols = set()
    for sym_set in symbols.values():
        all_symbols.update(sym_set)

    matched: list[str] = []
    for entity in entities:
        entity_lower = entity.lower()
        # Direct match in any symbol set
        if entity_lower in all_symbols:
            matched.append(entity)
            continue
        # Partial match: entity is substring of a symbol or vice versa
        for sym in all_symbols:
            if len(entity_lower) > 3 and (entity_lower in sym or sym in entity_lower):
                matched.append(f"{entity}~{sym}")
                break

    if matched:
        unique_matches = list(dict.fromkeys(matched))[:5]  # Dedupe, limit
        evidence = f"AST matches: {', '.join(unique_matches)}"
        return (True, evidence)

    return (False, "No AST symbol matches found")


# ---------------------------------------------------------------------------
# Level 3: Keyword matching (fallback)
# ---------------------------------------------------------------------------

def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from a criteria text.

    Filters out common grammar stop words only. Technical terms like
    'user', 'system', 'data', 'file' are preserved as they are
    meaningful in spec contexts.
    """
    # Only true grammar stopwords - NOT technical terms
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "must", "can", "could", "it", "its",
        "that", "this", "those", "these", "and", "or", "but", "if", "then",
        "when", "where", "who", "what", "which", "how", "not", "no", "all",
        "any", "each", "every", "both", "few", "more", "most", "other",
        "some", "such", "than", "too", "very", "just", "only", "own",
        "same", "so", "with", "for", "from", "into", "to", "of", "in",
        "on", "at", "by", "up", "about", "out", "off", "over", "under",
    }

    # Split on non-alphanumeric, filter
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
    return [w for w in words if len(w) > 2 and w not in stop_words]


def _keyword_check(
    criteria: AcceptanceCriteria,
    all_code: str,
) -> tuple[bool, str]:
    """Keyword matching as final fallback. Always returns low confidence.

    Returns (found, evidence_str).
    """
    combined_text = f"{criteria.condition} {criteria.expected_behavior}"
    keywords = _extract_keywords(combined_text)

    if not keywords:
        return (True, "No extractable keywords")

    found_keywords = [kw for kw in keywords if kw in all_code]
    coverage_ratio = len(found_keywords) / len(keywords)

    if coverage_ratio >= 0.6:
        return (True, f"Keywords found: {', '.join(found_keywords)} ({coverage_ratio:.0%})")
    else:
        missing = [kw for kw in keywords if kw not in all_code]
        return (False, f"Missing keywords: {', '.join(missing)} ({coverage_ratio:.0%})")


# ---------------------------------------------------------------------------
# Scan code directory
# ---------------------------------------------------------------------------

def _scan_code_directory(code_dir: str) -> dict[str, str]:
    """Scan a directory for Python files and return {filename: content}."""
    code_path = Path(code_dir)
    if not code_path.is_dir():
        return {}

    result: dict[str, str] = {}
    for py_file in code_path.rglob("*.py"):
        try:
            result[str(py_file)] = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

    return result


# ---------------------------------------------------------------------------
# Main: Three-level coverage check
# ---------------------------------------------------------------------------

def check_coverage(
    spec: list[AcceptanceCriteria],
    code_dir: str,
    use_llm: bool = True,
) -> SpecReport:
    """Three-level validation: LLM -> AST -> Keyword.

    For each criterion:
    1. Try LLM judgment (if use_llm=True and SDK available)
       - Success: confidence="high", method="llm"
    2. LLM unavailable or failed: try AST analysis
       - Match found: confidence="medium", method="ast"
    3. AST no match: fallback to keyword matching
       - Match found: confidence="low", method="keyword"
    4. All three levels found nothing: covered=False

    Args:
        spec: List of acceptance criteria.
        code_dir: Directory containing source code.
        use_llm: Whether to attempt LLM-based checking.

    Returns:
        SpecReport with coverage percentage and uncovered items.
    """
    if not spec:
        return SpecReport(criteria=[], coverage_pct=100.0, uncovered=[])

    code_files = _scan_code_directory(code_dir)
    # Lowercase version for keyword matching
    all_code_lower = "\n".join(v.lower() for v in code_files.values())

    covered_count = 0
    uncovered: list[AcceptanceCriteria] = []
    warnings: list[str] = []
    llm_attempted = False
    llm_succeeded = False

    for criterion in spec:
        # Level 1: LLM
        if use_llm:
            llm_attempted = True
            llm_result = _llm_check(criterion, code_files)
            if llm_result is not None:
                llm_succeeded = True
                criterion.covered = llm_result[0]
                criterion.confidence = "high"
                criterion.evidence = llm_result[1]
                criterion.method = "llm"
                if criterion.covered:
                    covered_count += 1
                else:
                    uncovered.append(criterion)
                continue

        # Level 2: AST
        ast_found, ast_evidence = _ast_check(criterion, code_dir)
        if ast_found:
            criterion.covered = True
            criterion.confidence = "medium"
            criterion.evidence = ast_evidence
            criterion.method = "ast"
            covered_count += 1
            continue

        # Level 3: Keyword fallback
        kw_found, kw_evidence = _keyword_check(criterion, all_code_lower)
        if kw_found:
            criterion.covered = True
            criterion.confidence = "low"
            criterion.evidence = kw_evidence
            criterion.method = "keyword"
            covered_count += 1
            continue

        # Nothing found
        criterion.covered = False
        criterion.confidence = "low"
        criterion.evidence = f"Not found. AST: {ast_evidence}. KW: {kw_evidence}"
        criterion.method = "none"
        uncovered.append(criterion)

    # Track degradation warnings
    if use_llm and llm_attempted and not llm_succeeded:
        warnings.append(
            "LLM validation unavailable (missing SDK or API key). "
            "Results use AST/keyword matching only (lower confidence)."
        )
    elif not use_llm:
        warnings.append("LLM validation disabled. Using AST/keyword matching only.")

    # Check confidence distribution
    methods = [c.method for c in spec]
    low_conf_count = sum(1 for m in methods if m in ("keyword", "none"))
    if low_conf_count > len(spec) * 0.5:
        warnings.append(
            f"{low_conf_count}/{len(spec)} criteria validated with low confidence. "
            "Consider providing ANTHROPIC_API_KEY for higher accuracy."
        )

    coverage_pct = (covered_count / len(spec)) * 100 if spec else 100.0

    return SpecReport(
        criteria=spec,
        coverage_pct=round(coverage_pct, 1),
        uncovered=uncovered,
        warnings=warnings,
    )
