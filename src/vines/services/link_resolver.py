import re
from pathlib import Path
from typing import Dict, List, Tuple
from vines.models.note import Note


def process_links_and_embeds(
    note: Note, wikilink_map: Dict[str, Path]
) -> Tuple[str, List[str]]:
    """Resolve [[Wikilinks]] and ![[Embeds]] to HTML, extracting target graph links."""
    current_out = note.out_rel_path
    links_found = []
    root_offset = "../" * (len(current_out.parts) - 1)

    def replace_embed(match):
        target = match.group(1).strip()
        meta = match.group(2)
        width_attr = ""
        if meta and meta.strip().isdigit():
            width_attr = f' width="{meta.strip()}"'

        asset_url = f"{root_offset}assets/{target}"
        ext = Path(target).suffix.lower()

        if ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]:
            return f'<img src="{asset_url}" alt="{target}" class="obsidian-embed"{width_attr}>'
        elif ext == ".pdf":
            return f'<embed src="{asset_url}" type="application/pdf" class="obsidian-embed-pdf">'
        elif ext in [".mp4", ".webm"]:
            return f'<video src="{asset_url}" controls class="obsidian-embed-video"{width_attr}></video>'
        return f'<a href="{asset_url}" class="asset-link">&#128206; {target}</a>'

    embed_pattern = r"!\[\[([^\]\x7c]+)(?:\x7c([^\]]+))?\]\]"
    body = re.sub(embed_pattern, replace_embed, note.html_body)

    def replace_link(match):
        target = match.group(1).strip()
        display = match.group(3).strip() if match.group(3) else target

        lookup_key = target.lower()
        if lookup_key in wikilink_map:
            target_out = wikilink_map[lookup_key]
            links_found.append(str(target_out).replace("\\", "/"))
            href = root_offset + str(target_out).replace("\\", "/")
            return f'<a class="wikilink" href="{href}">{display}</a>'
        return f'<span class="wikilink-broken">{display}</span>'

    wikilink_pattern = r"\[\[([^\x7c\]]+)(\x7c([^\]]+))?\]\]"
    final_body = re.sub(wikilink_pattern, replace_link, body)
    return final_body, links_found