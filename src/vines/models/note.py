from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class Note:
    key: str
    input_path: Path
    rel_path: Path
    out_rel_path: Path
    title: str
    tags: List[str]
    metadata: Dict[str, Any]
    body: str
    html_body: str
    toc_html: str
    snippet: str
    created: str
    updated: str
    reading_time: str
    word_count: int
    pinned: bool
    description: str