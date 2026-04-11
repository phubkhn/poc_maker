"""Load BRD files from disk and normalize them into schema objects."""

from pathlib import Path

from brd_agent.schemas.brd import BRDDocument


def _extract_title(markdown_text):
    """Extract first markdown heading as title, fallback to a default."""
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or "Untitled BRD"
    return "Untitled BRD"


def load_brd(input_path):
    """Load a BRD text/markdown file and return a BRDDocument."""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError("BRD file not found: {0}".format(path))

    raw_markdown = path.read_text(encoding="utf-8")
    return BRDDocument(
        source_path=str(path),
        title=_extract_title(raw_markdown),
        raw_markdown=raw_markdown,
    )
