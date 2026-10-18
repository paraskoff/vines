import re
import shutil
from datetime import datetime
from pathlib import Path

from vines.config import STATUS_BADGES
from vines.models.note import Note
from vines.models.site_data import SiteData
from vines.services.link_resolver import process_links_and_embeds
from vines.services.parser import (
    extract_css_classes,
    extract_tags,
    parse_frontmatter,
    parse_markdown_to_html,
)
from vines.views.css import generate_base_css
from vines.views.js import generate_app_js
from vines.views.templates import (
    render_html_template,
    build_folder_tree,
    generate_backlinks_html,
    generate_breadcrumbs,
)


class WikiBuilder:
    def __init__(self, input_dir: Path, output_dir: Path, theme_name: str = "default"):
        self.input_dir = input_dir.resolve()
        self.output_dir = output_dir.resolve()
        self.theme_name = theme_name
        self.data = SiteData()

    def scan_notes(self):
        """Scan markdown notes, extracting frontmatter, tags, and titles."""
        self.data.clear()

        for md_path in self.input_dir.rglob("*.md"):
            rel_path = md_path.relative_to(self.input_dir)
            out_rel_path = rel_path.with_suffix(".html")

            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"[Warning] Unable to read file {md_path}: {e}")
                continue

            metadata, body = parse_frontmatter(content)

            if metadata.get("draft") is True or metadata.get("published") is False:
                continue

            title = metadata.get("title", md_path.stem.replace("-", " ").title())
            tags = extract_tags(metadata, body)
            html_body, toc_html, plain_snippet = parse_markdown_to_html(body)

            if md_path.stem.lower() in ("index", "readme") or str(rel_path) in ("index.md", "README.md"):
                self.data.has_custom_index = True

            word_count = len(re.findall(r"\w+", body))
            read_minutes = max(1, round(word_count / 200)) if word_count > 0 else 1

            note = Note(
                key=str(rel_path).replace("\\", "/"),
                input_path=md_path,
                rel_path=rel_path,
                out_rel_path=out_rel_path,
                title=title,
                tags=tags,
                metadata=metadata,
                body=body,
                html_body=html_body,
                toc_html=toc_html,
                snippet=plain_snippet,
                created=str(metadata.get("created", "")),
                updated=str(metadata.get("updated", "")),
                reading_time=f"{read_minutes} min read",
                word_count=word_count,
                pinned=bool(
                    metadata.get("pinned") is True
                    or str(metadata.get("pinned")).lower() == "true"
                    or metadata.get("featured") is True
                ),
                description=metadata.get("description", f"Note regarding {title}"),
            )

            self.data.notes[str(rel_path)] = note

            for t in tags:
                self.data.tag_map.setdefault(t, []).append(note)

            self.data.wikilink_map[title.lower()] = out_rel_path
            self.data.wikilink_map[md_path.stem.lower()] = out_rel_path
            for alias in metadata.get("aliases", []):
                self.data.wikilink_map[str(alias).lower()] = out_rel_path

    def generate_default_index(self, pinned_html: str, has_custom_css: bool):
        recent_notes = sorted(
            self.data.notes.values(),
            key=lambda x: str(x.updated or x.created or ""),
            reverse=True,
        )[:8]
        recent_items = "".join(
            f'<li>&#128196; <a href="{n.out_rel_path}">{n.title}</a> <span style="font-size:0.75rem; opacity:0.6;">{n.updated or n.created}</span></li>'
            for n in recent_notes
        )
        tag_items = "".join(
            f'<a href="tags.html#{t}" class="tag-badge">#{t} ({len(notes)})</a>'
            for t, notes in sorted(self.data.tag_map.items())
        )

        dashboard_html = f"""
        <div class="dashboard-grid">
            <div class="dashboard-card">
                <h3>&#128202; Vault Stats</h3>
                <ul style="list-style:none; margin-top:0.5rem; font-size:0.9rem;">
                    <li><strong>Total Notes:</strong> {len(self.data.notes)}</li>
                    <li><strong>Total Tags:</strong> {len(self.data.tag_map)}</li>
                </ul>
            </div>
            <div class="dashboard-card">
                <h3>&#127991;&#65039; Tag Overview</h3>
                <div style="margin-top:0.5rem;">{tag_items or '<p style="font-size:0.85rem; opacity:0.6;">No tags found.</p>'}</div>
            </div>
        </div>
        <div style="margin-top: 2rem;">
            <h2>&#128338; Recent Updates</h2>
            <ul class="nav-list" style="margin-top: 0.8rem;">
                {recent_items or '<li>No notes available.</li>'}
            </ul>
        </div>
        """

        page_html = render_html_template(
            title="Digital Garden Home",
            description="Automatic Landing Page Index",
            root_offset="",
            home_href="index.html",
            custom_css_link='<link rel="stylesheet" href="custom.css">' if has_custom_css else "",
            body_classes="index-dashboard",
            pinned_section=pinned_html.format(root_offset="") if pinned_html else "",
            folder_tree_html=build_folder_tree(self.data.notes, Path("index.html")),
            breadcrumb_html='<span>Vault</span> <span class="breadcrumb-separator">/</span> Home',
            status_badge="",
            tags_html="",
            date_meta="",
            toc_content="<p style='font-size:0.85rem; opacity:0.6;'>Dashboard Overview</p>",
            content=dashboard_html,
            backlinks_section="",
        )
        with open(self.output_dir / "index.html", "w", encoding="utf-8") as f:
            f.write(page_html)

    def generate_tag_browser(self, has_custom_css: bool):
        tag_sections = []
        for tag in sorted(self.data.tag_map.keys()):
            notes = self.data.tag_map[tag]
            items = "".join(f'<li><a href="{n.out_rel_path}">{n.title}</a></li>' for n in notes)
            tag_sections.append(
                f'<div style="margin-bottom: 1.5rem;"><h2 id="{tag}">#{tag}</h2><ul style="padding-left:1.2rem; margin-top:0.5rem;">{items}</ul></div>'
            )

        content_html = (
            "<h1>&#127991;&#65039; Tag Browser</h1><hr style='margin:1rem 0; border:0; border-top:1px solid var(--border-color);'>"
            + "".join(tag_sections)
        )

        page_html = render_html_template(
            title="Tag Browser",
            description="Browse notes by tag",
            root_offset="",
            home_href="index.html",
            custom_css_link='<link rel="stylesheet" href="custom.css">' if has_custom_css else "",
            body_classes="",
            pinned_section="",
            folder_tree_html=build_folder_tree(self.data.notes, Path("tags.html")),
            breadcrumb_html='<a href="index.html">Vault</a> <span class="breadcrumb-separator">/</span> Tag Browser',
            status_badge="",
            tags_html="",
            date_meta="",
            toc_content="<p style='font-size:0.85rem; opacity:0.6;'>Tag Index</p>",
            content=content_html,
            backlinks_section="",
        )
        with open(self.output_dir / "tags.html", "w", encoding="utf-8") as f:
            f.write(page_html)

    def build(self):
        """Run full site compilation."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.scan_notes()

        # Copy non-markdown referenced assets
        assets_out = self.output_dir / "assets"
        assets_out.mkdir(parents=True, exist_ok=True)
        asset_exts = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".mp4", ".webm", ".webp"}
        for asset_path in self.input_dir.rglob("*"):
            if asset_path.is_file() and asset_path.suffix.lower() in asset_exts:
                shutil.copy2(asset_path, assets_out / asset_path.name)

        custom_css_src = self.input_dir / "custom.css"
        has_custom_css = custom_css_src.exists()
        if has_custom_css:
            shutil.copy(custom_css_src, self.output_dir / "custom.css")

        with open(self.output_dir / "style.css", "w", encoding="utf-8") as f:
            f.write(generate_base_css(self.theme_name))

        pinned_notes = [n for n in self.data.notes.values() if n.pinned]
        pinned_html = ""
        if pinned_notes:
            items = "".join(
                f'<li><a href="{{root_offset}}{n.out_rel_path}">{n.title}</a></li>'
                for n in pinned_notes
            )
            pinned_html = f'<div class="nav-section"><h3>Pinned</h3><ul class="nav-list">{items}</ul></div>'

        search_index, graph_nodes, graph_links = [], [], []

        for note in self.data.notes.values():
            root_offset = "../" * (len(note.out_rel_path.parts) - 1)
            clean_url = root_offset + str(note.out_rel_path).replace("\\", "/")
            search_index.append({"title": note.title, "url": clean_url, "snippet": note.snippet})
            graph_nodes.append(
                {"id": str(note.out_rel_path).replace("\\", "/"), "title": note.title, "url": clean_url}
            )

        id_to_note = {str(note.out_rel_path).replace("\\", "/"): note for note in self.data.notes.values()}
        self.data.backlink_map.clear()
        resolved_bodies = {}

        for note in self.data.notes.values():
            source_id = str(note.out_rel_path).replace("\\", "/")
            final_body, connected_targets = process_links_and_embeds(note, self.data.wikilink_map)
            resolved_bodies[source_id] = final_body
            for target_id in connected_targets:
                graph_links.append({"source": source_id, "target": target_id})
                sources = self.data.backlink_map.setdefault(target_id, [])
                if source_id not in sources:
                    sources.append(source_id)

        for note in self.data.notes.values():
            dest_path = self.output_dir / note.out_rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            root_offset = "../" * (len(note.out_rel_path.parts) - 1)
            home_href = f"{root_offset}index.html" if root_offset else "index.html"

            meta = note.metadata
            status_key = str(meta.get("status", "")).lower()
            status_badge = (
                f'<span class="status-badge {STATUS_BADGES[status_key][1]}">{STATUS_BADGES[status_key][0]}</span>'
                if status_key in STATUS_BADGES
                else ""
            )
            tags_html = "".join(f'<a href="{root_offset}tags.html#{t}" class="tag-badge">#{t}</a>' for t in note.tags)

            date_str = note.updated or note.created
            meta_items = []
            if date_str:
                meta_items.append(f"Updated: {date_str}")
            meta_items.append(f"&#9201;&#65039; {note.reading_time}")

            date_meta = f'<p style="font-size:0.85rem; opacity:0.7;">{" &bull; ".join(meta_items)}</p>'
            source_id = str(note.out_rel_path).replace("\\", "/")

            page_html = render_html_template(
                title=note.title,
                description=note.description,
                root_offset=root_offset,
                home_href=home_href,
                custom_css_link=f'<link rel="stylesheet" href="{root_offset}custom.css">' if has_custom_css else "",
                body_classes=extract_css_classes(meta),
                pinned_section=pinned_html.format(root_offset=root_offset) if pinned_html else "",
                folder_tree_html=build_folder_tree(self.data.notes, note.out_rel_path),
                breadcrumb_html=generate_breadcrumbs(note, home_href),
                status_badge=status_badge,
                tags_html=tags_html,
                date_meta=date_meta,
                toc_content=note.toc_html if meta.get("toc", True) else "<p style='font-size:0.85rem; opacity:0.6;'>ToC Disabled</p>",
                content=resolved_bodies[source_id],
                backlinks_section=generate_backlinks_html(
                    note, self.data.backlink_map.get(source_id, []), id_to_note, root_offset
                ),
            )
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(page_html)

        if not self.data.has_custom_index:
            self.generate_default_index(pinned_html, has_custom_css)
        self.generate_tag_browser(has_custom_css)
        with open(self.output_dir / "app.js", "w", encoding="utf-8") as f:
            f.write(generate_app_js(search_index, {"nodes": graph_nodes, "links": graph_links}))

        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] Generated site ({len(self.data.notes)} notes, custom_index={self.data.has_custom_index}) -> '{self.output_dir}'"
        )