from pathlib import Path
from typing import Dict, List
from vines.models.note import Note

STATIC_DIR = Path(__file__).parent / "static"


def get_html_template() -> str:
    """Load the outer page HTML layout from disk."""
    return (STATIC_DIR / "template.html").read_text(encoding="utf-8")
    
def render_html_template(**kwargs) -> str:
    """Load template.html and replace $variable placeholders safely without brace escaping issues."""
    html = (STATIC_DIR / "template.html").read_text(encoding="utf-8")
    # Replace standard {var} formatting with safe string replacement if desired
    for key, val in kwargs.items():
        html = html.replace(f"{{{key}}}", str(val))
    return html

def build_folder_tree(notes: Dict[str, Note], current_out_path: Path) -> str:
    """Construct collapsible folder tree HTML (<details>/<summary>)."""
    tree = {}
    root_offset = "../" * (len(current_out_path.parts) - 1)

    for note in notes.values():
        parts = note.rel_path.parts
        curr = tree
        for part in parts[:-1]:
            curr = curr.setdefault(part, {})
        curr[parts[-1]] = note

    def render_tree(nodes):
        html = '<ul class="nav-list">'
        for key, val in sorted(nodes.items()):
            if isinstance(val, Note):
                href = root_offset + str(val.out_rel_path).replace("\\", "/")
                html += f'<li>&#128196; <a href="{href}">{val.title}</a></li>'
            else:
                html += f'<li><details class="folder-tree" open><summary>&#128193; {key}</summary><div class="folder-content">{render_tree(val)}</div></details></li>'
        html += "</ul>"
        return html

    return render_tree(tree)


def generate_breadcrumbs(note: Note, home_href: str) -> str:
    """Generate breadcrumb navigation trail."""
    parts = note.rel_path.parts
    crumbs = [f'<a href="{home_href}">Vault</a>']
    for part in parts[:-1]:
        crumbs.append(f"<span>{part}</span>")
    crumbs.append(f"<span>{note.title}</span>")
    return '<span class="breadcrumb-separator">/</span>'.join(crumbs)


def generate_backlinks_html(
    note: Note, source_ids: List[str], id_to_note: Dict[str, Note], root_offset: str
) -> str:
    """Render backlinks block for the sidebar."""
    target_id = str(note.out_rel_path).replace("\\", "/")
    items = []
    for sid in source_ids:
        if sid == target_id:
            continue
        source_note = id_to_note.get(sid)
        if not source_note:
            continue
        href = root_offset + sid
        snippet = source_note.snippet or "No preview available."
        if len(snippet) > 100:
            snippet = snippet[:100] + "..."
        items.append(
            f'<li class="backlink-item"><a class="backlink-link" href="{href}">{source_note.title}</a><p class="backlink-snippet">{snippet}</p></li>'
        )

    body_html = (
        f'<ul class="backlink-list">{"".join(items)}</ul>'
        if items
        else '<p class="backlinks-empty">No notes link to this page yet. &#127793;</p>'
    )
    return f'<div class="nav-section backlinks-container" id="backlinks"><h3 class="backlinks-title">&#128279; Mentioned In <span class="backlinks-count">({len(items)})</span></h3>{body_html}</div>'