from typing import Optional


def parse_source_tables(raw: Optional[str]) -> list[str]:
    """Split source_tables text into entries, skipping blank and `#` comment lines."""
    if not raw:
        return []
    out: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out
