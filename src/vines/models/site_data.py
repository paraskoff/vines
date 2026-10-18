from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from vines.models.note import Note


@dataclass
class SiteData:
    notes: Dict[str, Note] = field(default_factory=dict)
    wikilink_map: Dict[str, Path] = field(default_factory=dict)
    tag_map: Dict[str, List[Note]] = field(default_factory=dict)
    backlink_map: Dict[str, List[str]] = field(default_factory=dict)
    has_custom_index: bool = False

    def clear(self):
        self.notes.clear()
        self.wikilink_map.clear()
        self.tag_map.clear()
        self.backlink_map.clear()
        self.has_custom_index = False