#!/usr/bin/env python3
"""Strip em dashes, en dashes, and ASCII em-dash substitutes from text files.

Removes:
  - U+2014 EM DASH
  - U+2013 EN DASH
  - ASCII " -- " (space-hyphen-hyphen-space) used as em-dash substitute

Preserves:
  - Code blocks (fenced with ``` or indented 4+ spaces)
  - Inline code (wrapped in backticks)
  - CLI flags (--model, --subset, etc.)
  - HTML comments (<!-- -->)
  - Horizontal rule separators (--- on own line)

Context-aware replacement:
  - Before uppercase letter: ". " (sentence break)
  - Otherwise: ", " (clause break)
  - At end of line: "."
"""

from __future__ import annotations

import re
from pathlib import Path


def strip_dashes_in_text(text: str) -> str:
    """Process a full markdown file, preserving code blocks."""
    lines = text.split("\n")
    out: list[str] = []
    in_fenced = False

    for line in lines:
        stripped = line.lstrip()
        # Fenced code block toggle
        if stripped.startswith("```"):
            in_fenced = not in_fenced
            out.append(line)
            continue
        # Inside fenced block: untouched
        if in_fenced:
            out.append(line)
            continue
        # Indented code block (4+ leading spaces, not a list item)
        if line.startswith("    ") and not line.lstrip().startswith(("-", "*", "+", "1.", "2.")):
            out.append(line)
            continue
        # Horizontal rule (a line of 3+ dashes only, possibly with spaces)
        if re.fullmatch(r"\s*-{3,}\s*", line):
            out.append(line)
            continue
        # Markdown table separator row
        if re.fullmatch(r"\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*", line):
            out.append(line)
            continue
        out.append(_process_line(line))

    return "\n".join(out)


def _process_line(line: str) -> str:
    """Process a single non-code line.

    Steps:
      1. Protect inline code (`...`) by replacing with placeholders.
      2. Replace em/en dashes and ASCII " -- " sentence connectors.
      3. Restore inline code.
    """
    # Step 1: protect inline code
    code_spans: list[str] = []

    def save_code(m: re.Match) -> str:
        code_spans.append(m.group(0))
        return f"\x00CODE{len(code_spans) - 1}\x00"

    protected = re.sub(r"`[^`]*`", save_code, line)

    # Step 2: replacements on the protected line
    result = _replace_in_protected(protected)

    # Step 3: restore inline code
    def restore(m: re.Match) -> str:
        return code_spans[int(m.group(1))]

    result = re.sub(r"\x00CODE(\d+)\x00", restore, result)
    return result


def _replace_in_protected(line: str) -> str:
    """Apply dash replacements to a line where inline code is placeholdered."""

    # Replace en dash with em dash so we only handle one Unicode char
    line = line.replace("\u2013", "\u2014")

    # Handle " -- " (ASCII em-dash substitute surrounded by spaces)
    # Context-aware: ". " if next word starts uppercase, else ", "
    def ascii_dd(match: re.Match) -> str:
        after = line[match.end():]
        next_chars = after.lstrip()
        if next_chars and next_chars[0].isupper():
            return ". "
        if not next_chars:
            return "."
        return ", "

    # Apply iteratively since each replacement changes the string
    while " -- " in line:
        idx = line.find(" -- ")
        rest = line[idx + 4:]
        next_char = rest[0] if rest else ""
        if next_char.isupper():
            replacement = ". "
        elif not next_char:
            replacement = "."
        else:
            replacement = ", "
        line = line[:idx] + replacement + line[idx + 4:]

    # Handle Unicode em dash (U+2014)
    while "\u2014" in line:
        idx = line.find("\u2014")
        before_ch = line[idx - 1] if idx > 0 else ""
        after_ch = line[idx + 1] if idx + 1 < len(line) else ""
        space_before = before_ch == " "
        space_after = after_ch == " "

        # Find next non-space character after the dash (and any trailing space)
        rest_idx = idx + 1
        if space_after:
            rest_idx += 1
        while rest_idx < len(line) and line[rest_idx] == " ":
            rest_idx += 1
        next_char = line[rest_idx] if rest_idx < len(line) else ""

        # Decide replacement
        if next_char.isupper():
            replacement = ". "
        elif not next_char:
            replacement = "."
        else:
            replacement = ", "

        # Calculate span to replace (consume surrounding spaces)
        start = idx - 1 if space_before else idx
        end = idx + 2 if space_after else idx + 1
        # Use the space we're consuming to hold the new punctuation
        if space_before and space_after:
            line = line[:start] + replacement + line[end:]
        else:
            # No surrounding space (or only one side)
            line = line[:idx] + (replacement.strip() + (" " if replacement.endswith(" ") else "")) + line[idx + 1:]

    # Handle " --" at end of line (no trailing space)
    line = re.sub(r" -- *$", ".", line)

    # Clean up multiple spaces but not inside code placeholders
    # (placeholders contain only \x00 and digits so safe)
    line = re.sub(r"  +", " ", line)

    # Clean up ". ." and other artifacts
    line = re.sub(r"\. \. ", ". ", line)
    line = re.sub(r", , ", ", ", line)
    line = re.sub(r"\. ,", ".", line)
    line = re.sub(r", \.", ".", line)

    return line


def process_file(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8")
    before = (text.count("\u2014") + text.count("\u2013")
              + len(re.findall(r" -- ", text)))
    if before == 0:
        return 0, 0
    new_text = strip_dashes_in_text(text)
    # Re-measure
    after = (new_text.count("\u2014") + new_text.count("\u2013")
             + len(re.findall(r" -- ", _strip_code_blocks(new_text))))
    path.write_text(new_text, encoding="utf-8")
    return before, after


def _strip_code_blocks(text: str) -> str:
    """Remove code block content for counting purposes."""
    result = []
    in_code = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if line.startswith("    "):
            continue
        result.append(line)
    return "\n".join(result)


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    md_files = []
    for p in repo_root.rglob("*.md"):
        rel = p.relative_to(repo_root).parts
        if rel and rel[0] in (".claude", "node_modules", ".pytest_cache", ".git"):
            continue
        md_files.append(p)

    total_before = 0
    total_after = 0
    changed = 0
    for p in sorted(md_files):
        before, after = process_file(p)
        if before > 0:
            rel = p.relative_to(repo_root)
            marker = "" if after == 0 else f" WARNING: {after} remain"
            print(f"  {rel}: {before} -> {after}{marker}")
            total_before += before
            total_after += after
            changed += 1

    print(f"\n{changed} files changed, {total_before} dashes removed, {total_after} remaining")


if __name__ == "__main__":
    main()
