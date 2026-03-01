from pathlib import Path

DOC_PATTERNS = [
    "**/*.md",
    "**/ADR-*.md",
    "**/CLAUDE.md",
    "**/CONTRIBUTING.md",
    "**/ARCHITECTURE.md",
]


def find_docs(project_root: Path) -> list[tuple[str, str]]:
    seen: set[Path] = set()
    results: list[tuple[str, str]] = []
    for pattern in DOC_PATTERNS:
        for match in project_root.glob(pattern):
            resolved = match.resolve()
            if resolved in seen or not match.is_file():
                continue
            seen.add(resolved)
            try:
                content = match.read_text(errors="replace")
                rel = str(match.relative_to(project_root))
                results.append((rel, content))
            except OSError:
                continue
    return results
