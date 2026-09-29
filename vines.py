#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vines - Complete Digital Garden & Static Wiki Builder

Features:
- Backlinks Panel Integration: Automatically parses incoming [[Wikilinks]] for every note
  and renders a "Mentioned In" section in the right sidebar panel.
- Encoding-robust icons: every UI icon is emitted as an ASCII-safe HTML numeric character.
- Automatic Fallback Home Page (`generate_default_index`).
- Home Link Resolution (`home_href`).
- KaTeX Math Integration: Inline $...$ and block $$...$$ rendering via CDN.
- Pygments Syntax Highlighting & Code Copy Button.
- Image Lightbox Modal & Markdown Footnotes support.
- Dynamic Breadcrumbs & Dedicated Tag Browser Page (tags.html).
- Collapsible Folder Hierarchy Tree View (<details>/<summary>) in Sidebar.
- Dynamic Hover Card Collision Detection for Wikilinks.
- 3-Column Layout with Sidebar Toggle Buttons.
- Persistent Theme (Light/Dark) and Layout Preferences via localStorage.
- Pure Vanilla Canvas Knowledge Graph & Live Watchdog Dev Server.
- [NEW] Obsidian-style Embeds (![[image.png]]) and Asset Copying.
- [NEW] Obsidian Callouts & Admonitions (> [!NOTE]) support.
- [NEW] Task Lists (- [ ] and - [x]).
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# Optional PyYAML support with standard fallback
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# Optional Markdown support with standard fallback
try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

# Optional Watchdog support for live file system monitoring
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


# ==============================================================================
# 1. CENTRALIZED THEME CONFIGURATION
# ==============================================================================

BASIC_THEME_CONFIG = {
    "font_family": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    "accent_color": "#7c3aed",
    "accent_hover": "#6d28d9",
    "link_color": "#8b5cf6",

    # Dark Mode Palette
    "bg_dark": "#121316",
    "surface_dark": "#1c1d21",
    "text_dark": "#e1e4ea",
    "border_dark": "#2e3038",

    # Light Mode Palette
    "bg_light": "#f8fafc",
    "surface_light": "#ffffff",
    "text_light": "#0f172a",
    "border_light": "#e2e8f0",
}

SOLARIZED_THEME_CONFIG = {
    "font_family": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    "accent_color": "#268bd2",      # Solarized Blue (primary accent)
    "accent_hover": "#2aa198",      # Solarized Cyan (hover accent)
    "link_color": "#268bd2",        # Wikilink / hyperlink color
    
    # Dark Mode Palette (Solarized Dark: Base03 background, Base02 surface)
    "bg_dark": "#002b36",           # Base03 (deep dark teal/blue)
    "surface_dark": "#073642",      # Base02 (slightly lighter dark teal)
    "text_dark": "#839496",         # Base0 (muted content text)
    "border_dark": "#586e75",       # Base01 (structural border tone)
    
    # Light Mode Palette (Solarized Light: Base3 background, Base2 surface)
    "bg_light": "#fdf6e3",          # Base3 (soft warm cream background)
    "surface_light": "#eee8d5",     # Base2 (cream surface panels)
    "text_light": "#657b83",        # Base00 (readable dark-ish grey-cyan text)
    "border_light": "#93a1a1",      # Base1 (crisp border tone)
}

THEME_CONFIG = SOLARIZED_THEME_CONFIG

STATUS_BADGES = {
    "seed": ("&#127793; Seed", "status-seed"),
    "growing": ("&#127807; Growing", "status-growing"),
    "evergreen": ("&#127794; Evergreen", "status-evergreen"),
}


# ==============================================================================
# 2. FRONTMATTER & CONTENT PARSER
# ==============================================================================

def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and raw Markdown body."""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    yaml_text = parts[1].strip()
    body = parts[2].lstrip()

    metadata = {}
    if HAS_YAML:
        try:
            metadata = yaml.safe_load(yaml_text) or {}
        except Exception as e:
            print(f"[Warning] Failed to parse YAML frontmatter: {e}")
    else:
        for line in yaml_text.splitlines():
            line = line.strip()
            if ":" in line and not line.startswith("#"):
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if val.startswith("[") and val.endswith("]"):
                    val = [item.strip().strip("'\"") for item in val[1:-1].split(",")]
                elif val.lower() == "true":
                    val = True
                elif val.lower() == "false":
                    val = False
                metadata[key] = val

    return metadata, body


def extract_css_classes(metadata: dict) -> str:
    """Format cssclasses frontmatter into a space-separated string."""
    classes = metadata.get("cssclasses", [])
    if isinstance(classes, list):
        return " ".join(str(cls).strip() for cls in classes if cls)
    if isinstance(classes, str):
        return classes.strip()
    return ""


def extract_tags(metadata: dict, body: str) -> list[str]:
    """Extract tags from both frontmatter and inline #tag occurrences."""
    tags = set()

    fm_tags = metadata.get("tags", [])
    if isinstance(fm_tags, list):
        for t in fm_tags:
            tags.add(str(t).lstrip("#").strip().lower())
    elif isinstance(fm_tags, str):
        for t in fm_tags.split(","):
            tags.add(t.lstrip("#").strip().lower())

    inline_tags = re.findall(r"(?<!\w)#([a-zA-Z0-9_\-]+)", body)
    for t in inline_tags:
        tags.add(t.lower())

    return sorted(list(filter(None, tags)))


def convert_obsidian_callouts(md: str) -> str:
    """Convert Obsidian blockquote callouts to Python-Markdown admonition syntax."""
    lines = md.split('\n')
    out = []
    in_callout = False
    for line in lines:
        callout_match = re.match(r'^>\s*\[!(?P<type>\w+)\](?P<title>.*)', line)
        if callout_match:
            in_callout = True
            ctype = callout_match.group('type').lower()
            title = callout_match.group('title').strip() or ctype.capitalize()
            out.append(f'!!! {ctype} "{title}"')
        elif in_callout:
            if line.startswith('>'):
                inner_text = line[1:].lstrip(' ')
                out.append('    ' + inner_text)
            else:
                in_callout = False
                out.append(line)
        else:
            out.append(line)
    return '\n'.join(out)


def parse_markdown_to_html(md_content: str) -> tuple[str, str, str]:
    """Convert Markdown to HTML with extensions for footnotes, syntax highlighting, callouts, math, and task lists."""
    toc_items = []

    def replace_heading(match):
        level = len(match.group(1))
        title = match.group(2).strip()
        slug = re.sub(r"[^\w\-]", "", title.lower().replace(" ", "-"))
        if level in (2, 3):
            toc_items.append((level, title, slug))
        return f'<h{level} id="{slug}">{title}</h{level}>'

    # Pre-process callouts and task lists
    md_content = convert_obsidian_callouts(md_content)
    md_content = re.sub(r'^(\s*)-\s+\[ \]\s+', r'\1* <input type="checkbox" disabled style="margin-right: 0.5rem; margin-top: 0.3rem;"> ', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'^(\s*)-\s+\[x\]\s+', r'\1* <input type="checkbox" checked disabled style="margin-right: 0.5rem; margin-top: 0.3rem;"> ', md_content, flags=re.MULTILINE|re.IGNORECASE)

    processed_md = re.sub(r"^(#{1,6})\s+(.+)$", replace_heading, md_content, flags=re.MULTILINE)

    if HAS_MARKDOWN:
        extensions = [
            "fenced_code",
            "tables",
            "nl2br",
            "footnotes",
            "codehilite",
            "admonition",
        ]
        try:
            import pymdownx.arithmatex
            extensions.append("pymdownx.arithmatex")
        except ImportError:
            pass

        html_body = markdown.markdown(processed_md, extensions=extensions)
    else:
        paragraphs = processed_md.split("\n\n")
        html_chunks = []
        for p in paragraphs:
            p = p.strip()
            if p.startswith("<h"):
                html_chunks.append(p)
            elif p.startswith("- ") or p.startswith("* "):
                items = "".join(f"<li>{item[2:]}</li>" for item in p.split("\n") if item.startswith("- ") or item.startswith("* "))
                html_chunks.append(f"<ul>{items}</ul>")
            else:
                html_chunks.append(f"<p>{p.replace('\n', '<br>')}</p>")
        html_body = "\n".join(html_chunks)

    plain_snippet = re.sub(r"<[^>]+>", "", html_body)[:160].replace("\n", " ").strip()

    if not toc_items:
        toc_html = "<p style='font-size:0.85rem; opacity:0.6;'>No headers on this page.</p>"
    else:
        toc_links = []
        for level, title, slug in toc_items:
            indent = "indent-sub" if level == 3 else ""
            toc_links.append(f'<li class="{indent}"><a href="#{slug}">{title}</a></li>')
        toc_html = f'<ul class="toc-list">{"".join(toc_links)}</ul>'

    return html_body, toc_html, plain_snippet


# ==============================================================================
# 3. STYLESHEETS & CLIENT-SIDE SCRIPTS
# ==============================================================================

def generate_base_css() -> str:
    """Generate system CSS with Callouts, Code highlighting, Tree Views, and Lightbox Modal."""
    return f"""
:root {{
    --font-family: {THEME_CONFIG['font_family']};
    --accent-color: {THEME_CONFIG['accent_color']};
    --accent-hover: {THEME_CONFIG['accent_hover']};
    --link-color: {THEME_CONFIG['link_color']};
    --bg-color: {THEME_CONFIG['bg_light']};
    --surface-color: {THEME_CONFIG['surface_light']};
    --text-color: {THEME_CONFIG['text_light']};
    --border-color: {THEME_CONFIG['border_light']};
}}

@media (prefers-color-scheme: dark) {{
    :root {{
        --bg-color: {THEME_CONFIG['bg_dark']};
        --surface-color: {THEME_CONFIG['surface_dark']};
        --text-color: {THEME_CONFIG['text_dark']};
        --border-color: {THEME_CONFIG['border_dark']};
    }}
}}

body[data-theme="dark"] {{
    --bg-color: {THEME_CONFIG['bg_dark']};
    --surface-color: {THEME_CONFIG['surface_dark']};
    --text-color: {THEME_CONFIG['text_dark']};
    --border-color: {THEME_CONFIG['border_dark']};
}}

body[data-theme="light"] {{
    --bg-color: {THEME_CONFIG['bg_light']};
    --surface-color: {THEME_CONFIG['surface_light']};
    --text-color: {THEME_CONFIG['text_light']};
    --border-color: {THEME_CONFIG['border_light']};
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: var(--font-family);
    background-color: var(--bg-color);
    color: var(--text-color);
    line-height: 1.6;
    padding: 1.5rem;
}}

.site-container {{
    max-width: 1400px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: 260px 1fr 220px;
    gap: 2rem;
    transition: grid-template-columns 0.2s ease;
}}

body.hide-left-sidebar .sidebar-left {{ display: none !important; }}
body.hide-right-sidebar .sidebar-right {{ display: none !important; }}

body.hide-left-sidebar .site-container {{ grid-template-columns: 1fr 220px; }}
body.hide-right-sidebar .site-container {{ grid-template-columns: 260px 1fr; }}
body.hide-left-sidebar.hide-right-sidebar .site-container {{ grid-template-columns: 1fr; max-width: 1100px; }}

@media (max-width: 1024px) {{
    .site-container {{ grid-template-columns: 240px 1fr; }}
    .sidebar-right {{ display: none !important; }}
    #toggle-right-btn {{ display: none !important; }}
}}

@media (max-width: 768px) {{
    .site-container {{ grid-template-columns: 1fr; }}
    .sidebar-left {{ border-right: 0; border-bottom: 1px solid var(--border-color); padding-bottom: 1rem; }}
}}

.sidebar-left {{ border-right: 1px solid var(--border-color); padding-right: 1.2rem; }}
.sidebar-right {{ border-left: 1px solid var(--border-color); padding-left: 1.2rem; }}
.main-content {{ min-width: 0; }}

.top-controls {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 1rem;
    padding-bottom: 0.8rem;
    border-bottom: 1px dashed var(--border-color);
}}

.breadcrumb {{ font-size: 0.85rem; opacity: 0.8; margin-bottom: 0.8rem; }}
.breadcrumb a {{ color: var(--link-color); }}
.breadcrumb-separator {{ margin: 0 0.4rem; opacity: 0.5; }}

.control-btn {{
    background: var(--surface-color); border: 1px solid var(--border-color);
    color: var(--text-color); padding: 0.35rem 0.75rem; border-radius: 6px;
    cursor: pointer; font-size: 0.82rem; display: inline-flex; align-items: center; gap: 0.4rem;
}}
.control-btn:hover {{ background: rgba(124, 58, 237, 0.12); }}

.nav-section {{ margin-bottom: 1.5rem; }}
.nav-section h3 {{ font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.7; margin-bottom: 0.5rem; }}
.nav-list {{ list-style: none; }}
.nav-list li {{ margin-bottom: 0.4rem; font-size: 0.92rem; }}

details.folder-tree {{ margin-bottom: 0.4rem; }}
details.folder-tree summary {{ cursor: pointer; font-weight: 600; font-size: 0.9rem; padding: 0.2rem 0; user-select: none; }}
details.folder-tree summary:hover {{ color: var(--link-color); }}
.folder-content {{ padding-left: 0.8rem; border-left: 1px dashed var(--border-color); margin-left: 0.2rem; }}

a {{ color: var(--link-color); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

.wikilink {{ font-weight: 500; border-bottom: 1px dashed var(--link-color); position: relative; }}
.wikilink-broken {{ color: #ef4444; text-decoration: line-through; }}

.hover-preview-card {{
    position: fixed; width: 300px; max-height: 200px;
    background: var(--surface-color); border: 1px solid var(--border-color);
    border-radius: 8px; padding: 0.8rem; box-shadow: 0 8px 24px rgba(0,0,0,0.2);
    overflow: hidden; z-index: 1000; display: none; pointer-events: none; font-size: 0.85rem;
}}

.search-container {{ position: relative; margin-bottom: 1.5rem; }}
.search-input {{
    width: 100%; padding: 0.5rem 0.8rem; border-radius: 6px;
    border: 1px solid var(--border-color); background: var(--surface-color);
    color: var(--text-color); font-size: 0.9rem;
}}
.search-results {{
    position: absolute; top: 100%; left: 0; right: 0;
    background: var(--surface-color); border: 1px solid var(--border-color);
    border-radius: 6px; max-height: 300px; overflow-y: auto; z-index: 100;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15); display: none;
}}
.search-result-item {{ padding: 0.6rem 0.8rem; border-bottom: 1px solid var(--border-color); display: block; }}
.search-result-item:hover {{ background: rgba(124, 58, 237, 0.1); }}
.search-result-title {{ font-weight: 600; font-size: 0.9rem; }}
.search-result-snippet {{ font-size: 0.75rem; opacity: 0.7; max-height: 2.4em; overflow: hidden; }}

.status-badge {{ display: inline-block; padding: 0.2rem 0.6rem; font-size: 0.8rem; border-radius: 12px; font-weight: 600; margin-bottom: 1rem; }}
.status-seed {{ background: #fef3c7; color: #92400e; }}
.status-growing {{ background: #dcfce7; color: #166534; }}
.status-evergreen {{ background: #e0e7ff; color: #3730a3; }}
.tag-badge {{ display: inline-block; background: rgba(124, 58, 237, 0.12); color: var(--link-color); padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.8rem; margin-right: 0.3rem; margin-bottom: 0.3rem; }}

.toc-list {{ list-style: none; font-size: 0.88rem; }}
.toc-list li {{ margin-bottom: 0.4rem; }}
.toc-list .indent-sub {{ margin-left: 0.8rem; font-size: 0.82rem; }}

/* Admonitions / Callouts CSS */
.admonition {{ border-left: 4px solid var(--border-color); background: rgba(0,0,0,0.03); padding: 1rem; margin: 1.2rem 0; border-radius: 4px; }}
body[data-theme="dark"] .admonition {{ background: rgba(255,255,255,0.04); }}
.admonition-title {{ font-weight: 600; margin-bottom: 0.5rem; font-size: 1rem; }}
.admonition.note {{ border-left-color: #3b82f6; }}
.admonition.note .admonition-title {{ color: #3b82f6; }}
.admonition.warning {{ border-left-color: #f59e0b; }}
.admonition.warning .admonition-title {{ color: #f59e0b; }}
.admonition.tip {{ border-left-color: #10b981; }}
.admonition.tip .admonition-title {{ color: #10b981; }}
.admonition.danger, .admonition.error {{ border-left-color: #ef4444; }}
.admonition.danger .admonition-title, .admonition.error .admonition-title {{ color: #ef4444; }}

.article-body img {{ max-width: 100%; height: auto; border-radius: 6px; cursor: zoom-in; margin: 1rem 0; }}
.obsidian-embed-pdf {{ width: 100%; height: 600px; border: 1px solid var(--border-color); border-radius: 6px; }}

pre {{ position: relative; background: var(--surface-color); border: 1px solid var(--border-color); border-radius: 6px; padding: 1rem; overflow-x: auto; margin: 1rem 0; }}
.code-copy-btn {{ position: absolute; top: 0.5rem; right: 0.5rem; background: var(--bg-color); border: 1px solid var(--border-color); color: var(--text-color); padding: 0.2rem 0.5rem; font-size: 0.75rem; border-radius: 4px; cursor: pointer; opacity: 0.7; }}
.code-copy-btn:hover {{ opacity: 1; }}

.lightbox-modal {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0, 0, 0, 0.85); display: flex; align-items: center; justify-content: center; z-index: 2000; opacity: 0; pointer-events: none; transition: opacity 0.2s ease; }}
.lightbox-modal.active {{ opacity: 1; pointer-events: auto; }}
.lightbox-modal img {{ max-width: 90vw; max-height: 90vh; border-radius: 8px; border: 2px solid #fff; }}

.backlinks-container {{ margin-bottom: 1.5rem; }}
.backlinks-title {{ font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.7; margin-bottom: 0.5rem; }}
.backlinks-count {{ font-size: 0.8rem; font-weight: 400; opacity: 0.75; }}
.backlink-list {{ list-style: none; }}
.backlink-item {{ margin-bottom: 0.55rem; font-size: 0.92rem; }}
.backlink-link {{ font-weight: 500; }}
.backlink-item:hover .backlink-link {{ color: var(--accent-hover); }}
.backlink-snippet {{ font-size: 0.75rem; opacity: 0.7; margin-top: 0.15rem; max-height: 2.6em; overflow: hidden; }}
.backlinks-empty {{ font-size: 0.85rem; opacity: 0.6; }}

.graph-container {{ margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--border-color); }}
.graph-canvas {{ width: 100%; height: 260px; background: var(--surface-color); border: 1px solid var(--border-color); border-radius: 8px; }}

/* ==========================================
   1. TABLE STYLING & GRID LINES
   ========================================== */
table {{
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
  margin-bottom: 1.5rem;
  font-size: 0.95rem;
}}

/* Add horizontal lines and padding to cells */
th, td {{
  padding: 10px 14px;
  text-align: left;
  border-bottom: 1px solid #e2e8f0; /* Light horizontal divider line */
  vertical-align: top;
}}

/* Header row styling */
th {{
  font-weight: 600;
  border-bottom: 2px solid #94a3b8; /* Darker line under column headers */
  background-color: var(--surface-color);
}}

/* Subtle background zebra striping for table rows */
tbody tr:nth-child(even) {{
#  background-color: var(--surface-color);
}}

/* Hover effect on table rows */
tbody tr:hover {{
  background-color: var(--surface-color);
}}


/* ==========================================
   2. VERTICAL SECTION SPACING & BREATHING ROOM
   ========================================== */
/* Add margin above headings to separate content sections */
h1, h2, h3, h4, h5, h6 {{
  margin-top: 2rem;
  margin-bottom: 0.75rem;
  font-weight: 600;
  line-height: 1.3;
}}

/* Remove top margin for the very first element in the reading pane */
main > *:first-child,
.content > *:first-child,
article > *:first-child {{
  margin-top: 0;
}}

/* Add bottom spacing to standard text blocks and lists */
p, ul, ol, blockquote, table {{
  margin-top: 0;
  margin-bottom: 1.25rem;
  line-height: 1.6;
}}

/* List spacing */
ul, ol {{
  padding-left: 1.5rem;
}}

li {{
  margin-bottom: 0.35rem;
}}
"""


def generate_app_js(search_index: list, graph_data: dict) -> str:
    """Generate JavaScript for controls, search, hover previews, lightboxes, and graph."""
    search_json = json.dumps(search_index)
    graph_json = json.dumps(graph_data)

    return f"""
const SEARCH_INDEX = {search_json};
const GRAPH_DATA = {graph_json};

function initTheme() {{
    const savedTheme = localStorage.getItem('garden-theme');
    if (savedTheme) document.body.setAttribute('data-theme', savedTheme);
    const btn = document.getElementById('theme-toggle');
    if (btn) {{
        btn.addEventListener('click', () => {{
            const current = document.body.getAttribute('data-theme');
            const target = current === 'dark' ? 'light' : 'dark';
            document.body.setAttribute('data-theme', target);
            localStorage.setItem('garden-theme', target);
        }});
    }}
}}

function initSidebarToggles() {{
    const leftBtn = document.getElementById('toggle-left-btn');
    const rightBtn = document.getElementById('toggle-right-btn');
    if (localStorage.getItem('garden-hide-left') === 'true') document.body.classList.add('hide-left-sidebar');
    if (localStorage.getItem('garden-hide-right') === 'true') document.body.classList.add('hide-right-sidebar');

    if (leftBtn) {{
        leftBtn.addEventListener('click', () => {{
            document.body.classList.toggle('hide-left-sidebar');
            localStorage.setItem('garden-hide-left', document.body.classList.contains('hide-left-sidebar'));
        }});
    }}
    if (rightBtn) {{
        rightBtn.addEventListener('click', () => {{
            document.body.classList.toggle('hide-right-sidebar');
            localStorage.setItem('garden-hide-right', document.body.classList.contains('hide-right-sidebar'));
        }});
    }}
}}

function initSearch() {{
    const input = document.getElementById('search-input');
    const results = document.getElementById('search-results');
    if (!input || !results) return;

    input.addEventListener('input', (e) => {{
        const query = e.target.value.toLowerCase().trim();
        if (!query) {{ results.style.display = 'none'; return; }}
        const matches = SEARCH_INDEX.filter(item =>
            item.title.toLowerCase().includes(query) || item.snippet.toLowerCase().includes(query)
        ).slice(0, 6);

        if (matches.length === 0) {{
            results.innerHTML = '<div style="padding:0.6rem; font-size:0.85rem; opacity:0.6;">No notes found</div>';
        }} else {{
            results.innerHTML = matches.map(m => `
                <a href="${{m.url}}" class="search-result-item">
                    <div class="search-result-title">${{m.title}}</div>
                    <div class="search-result-snippet">${{m.snippet}}</div>
                </a>
            `).join('');
        }}
        results.style.display = 'block';
    }});
    document.addEventListener('click', (e) => {{
        if (!input.contains(e.target) && !results.contains(e.target)) results.style.display = 'none';
    }});
}}

function initCodeCopy() {{
    document.querySelectorAll('pre').forEach(pre => {{
        const btn = document.createElement('button');
        btn.className = 'code-copy-btn';
        btn.innerText = 'Copy';
        btn.addEventListener('click', () => {{
            const code = pre.querySelector('code') ? pre.querySelector('code').innerText : pre.innerText;
            navigator.clipboard.writeText(code).then(() => {{
                btn.innerText = 'Copied!';
                setTimeout(() => btn.innerText = 'Copy', 2000);
            }});
        }});
        pre.appendChild(btn);
    }});
}}

function initLightbox() {{
    const modal = document.createElement('div');
    modal.className = 'lightbox-modal';
    modal.innerHTML = '<img id="lightbox-img" src="" alt="Zoomed view">';
    document.body.appendChild(modal);
    const imgTarget = document.getElementById('lightbox-img');

    document.querySelectorAll('.article-body img:not(.obsidian-embed-pdf)').forEach(img => {{
        img.addEventListener('click', () => {{
            imgTarget.src = img.src;
            modal.classList.add('active');
        }});
    }});
    modal.addEventListener('click', () => modal.classList.remove('active'));
}}

function initHoverCards() {{
    const card = document.createElement('div');
    card.className = 'hover-preview-card';
    document.body.appendChild(card);

    document.querySelectorAll('a.wikilink').forEach(link => {{
        link.addEventListener('mouseenter', (e) => {{
            const targetUrl = link.getAttribute('href');
            const match = SEARCH_INDEX.find(item => item.url.endsWith(targetUrl) || targetUrl.endsWith(item.url));
            if (!match) return;

            card.innerHTML = `<strong>${{match.title}}</strong><p style="margin-top:0.4rem;">${{match.snippet}}...</p>`;
            card.style.display = 'block';

            const rect = link.getBoundingClientRect();
            let left = rect.left;
            let top = rect.bottom + 8;
            if (left + 320 > window.innerWidth) left = window.innerWidth - 330;
            if (top + 210 > window.innerHeight) top = rect.top - 210;
            card.style.left = `${{Math.max(10, left)}}px`;
            card.style.top = `${{Math.max(10, top)}}px`;
        }});
        link.addEventListener('mouseleave', () => {{ card.style.display = 'none'; }});
    }});
}}

function initGraph() {{
    const canvas = document.getElementById('graph-canvas');
    if (!canvas || !GRAPH_DATA.nodes.length) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.parentElement.clientWidth;
    const height = canvas.height = 260;

    const nodes = GRAPH_DATA.nodes.map(n => ({{ ...n, x: Math.random() * (width - 80) + 40, y: Math.random() * (height - 80) + 40, vx: 0, vy: 0 }}));
    const nodeMap = new Map(nodes.map(n => [n.id, n]));
    const links = GRAPH_DATA.links.map(l => ({{ source: nodeMap.get(l.source), target: nodeMap.get(l.target) }})).filter(l => l.source && l.target);

    function stepPhysics() {{
        for (let i = 0; i < nodes.length; i++) {{
            for (let j = i + 1; j < nodes.length; j++) {{
                const dx = nodes[j].x - nodes[i].x;
                const dy = nodes[j].y - nodes[i].y;
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                if (dist < 120) {{
                    const force = (120 - dist) / dist * 0.05;
                    nodes[i].vx -= dx * force; nodes[i].vy -= dy * force;
                    nodes[j].vx += dx * force; nodes[j].vy += dy * force;
                }}
            }}
        }}
        links.forEach(l => {{
            const dx = l.target.x - l.source.x;
            const dy = l.target.y - l.source.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const force = (dist - 60) * 0.01;
            l.source.vx += dx * force; l.source.vy += dy * force;
            l.target.vx -= dx * force; l.target.vy -= dy * force;
        }});
        nodes.forEach(n => {{
            n.vx += (width / 2 - n.x) * 0.002;
            n.vy += (height / 2 - n.y) * 0.002;
            n.vx *= 0.85; n.vy *= 0.85;
            n.x = Math.max(20, Math.min(width - 20, n.x + n.vx));
            n.y = Math.max(20, Math.min(height - 20, n.y + n.vy));
        }});
    }}

    function draw() {{
        ctx.clearRect(0, 0, width, height);
        ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue('--border-color').trim() || '#ccc';
        links.forEach(l => {{ ctx.beginPath(); ctx.moveTo(l.source.x, l.source.y); ctx.lineTo(l.target.x, l.target.y); ctx.stroke(); }});
        const accent = getComputedStyle(document.body).getPropertyValue('--accent-color').trim() || '#7c3aed';
        nodes.forEach(n => {{
            ctx.fillStyle = accent;
            ctx.beginPath(); ctx.arc(n.x, n.y, 6, 0, Math.PI * 2); ctx.fill();
            ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--text-color').trim() || '#000';
            ctx.font = '11px sans-serif';
            ctx.fillText(n.title, n.x + 9, n.y + 4);
        }});
    }}
    let frames = 0;
    function animate() {{
        if (frames < 120) {{ stepPhysics(); draw(); frames++; requestAnimationFrame(animate); }}
        else {{ draw(); }}
    }}
    animate();

    canvas.addEventListener('click', (e) => {{
        const rect = canvas.getBoundingClientRect();
        const hit = nodes.find(n => Math.hypot(n.x - (e.clientX - rect.left), n.y - (e.clientY - rect.top)) < 10);
        if (hit && hit.url) window.location.href = hit.url;
    }});
}}

document.addEventListener('DOMContentLoaded', () => {{
    initTheme(); initSidebarToggles(); initSearch();
    initCodeCopy(); initLightbox(); initHoverCards(); initGraph();
}});
"""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="{description}">
    <link rel="stylesheet" href="{root_offset}style.css">
    {custom_css_link}
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"
        onload="renderMathInElement(document.body);"></script>
</head>
<body class="{body_classes}">
    <div class="site-container">
        <aside class="sidebar-left">
            <div class="search-container">
                <input type="text" id="search-input" class="search-input" placeholder="&#128269; Search notes...">
                <div id="search-results" class="search-results"></div>
            </div>
            <div class="nav-section">
                <h3>Navigation</h3>
                <ul class="nav-list">
                    <li><a href="{home_href}">&#127968; Home</a></li>
                    <li><a href="{root_offset}tags.html">&#127991;&#65039; Tag Browser</a></li>
                </ul>
            </div>
            {pinned_section}
            <div class="nav-section">
                <h3>Vault Hierarchy</h3>
                {folder_tree_html}
            </div>
        </aside>
        <main class="main-content">
            <div class="top-controls">
                <button id="toggle-left-btn" class="control-btn" title="Toggle Sidebar">&#9776; Sidebar</button>
                <button id="theme-toggle" class="control-btn" title="Toggle Theme">&#127763; Theme</button>
                <button id="toggle-right-btn" class="control-btn" title="Toggle Page ToC">&#128209; ToC</button>
            </div>
            <nav class="breadcrumb">{breadcrumb_html}</nav>
            <header>
                {status_badge}
                <h1>{title}</h1>
                {tags_html}
                {date_meta}
            </header>
            <hr style="margin: 1rem 0; border: 0; border-top: 1px solid var(--border-color);">
            <article class="article-body">
                {content}
            </article>
            <section class="graph-container">
                <h3 style="font-size: 1rem; margin-bottom: 0.8rem;">&#128376;&#65039; Knowledge Graph</h3>
                <canvas id="graph-canvas" class="graph-canvas"></canvas>
            </section>
        </main>
        <aside class="sidebar-right">
            <div class="nav-section">
                <h3>On This Page</h3>
                {toc_content}
            </div>
            {backlinks_section}
        </aside>
    </div>
    <script src="{root_offset}app.js"></script>
</body>
</html>
"""


# ==============================================================================
# 4. SITE BUILD ENGINE
# ==============================================================================

class WikiBuilder:
    def __init__(self, input_dir: Path, output_dir: Path):
        self.input_dir = input_dir.resolve()
        self.output_dir = output_dir.resolve()
        self.notes = {}
        self.wikilink_map = {}
        self.tag_map = {}
        self.backlink_map = {}
        self.has_custom_index = False

    def scan_notes(self):
        """Scan markdown notes, extracting frontmatter, tags, and titles."""
        self.notes.clear()
        self.wikilink_map.clear()
        self.tag_map.clear()
        self.backlink_map.clear()
        self.has_custom_index = False

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
                self.has_custom_index = True

            note_info = {
                "key": str(rel_path).replace("\\", "/"),
                "input_path": md_path,
                "rel_path": rel_path,
                "out_rel_path": out_rel_path,
                "title": title,
                "tags": tags,
                "metadata": metadata,
                "body": body,
                "html_body": html_body,
                "toc_html": toc_html,
                "snippet": plain_snippet,
                "created": metadata.get("created", ""),
                "updated": metadata.get("updated", ""),
                "pinned": bool(metadata.get("pinned") is True or str(metadata.get("pinned")).lower() == "true" or metadata.get("featured") is True),
                "description": metadata.get("description", f"Note regarding {title}"),
            }

            self.notes[str(rel_path)] = note_info

            for t in tags:
                self.tag_map.setdefault(t, []).append(note_info)

            self.wikilink_map[title.lower()] = out_rel_path
            self.wikilink_map[md_path.stem.lower()] = out_rel_path
            for alias in metadata.get("aliases", []):
                self.wikilink_map[str(alias).lower()] = out_rel_path

    def build_folder_tree(self, current_out_path: Path) -> str:
        """Construct collapsible folder tree HTML (<details>/<summary>)."""
        tree = {}
        root_offset = "../" * (len(current_out_path.parts) - 1)

        for note in self.notes.values():
            parts = note["rel_path"].parts
            curr = tree
            for part in parts[:-1]:
                curr = curr.setdefault(part, {})
            curr[parts[-1]] = note

        def render_tree(nodes):
            html = '<ul class="nav-list">'
            for key, val in sorted(nodes.items()):
                if "out_rel_path" in val:
                    href = root_offset + str(val["out_rel_path"]).replace("\\", "/")
                    html += f'<li>&#128196; <a href="{href}">{val["title"]}</a></li>'
                else:
                    html += f'<li><details class="folder-tree" open><summary>&#128193; {key}</summary><div class="folder-content">{render_tree(val)}</div></details></li>'
            html += '</ul>'
            return html

        return render_tree(tree)

    def generate_breadcrumbs(self, note: dict, home_href: str) -> str:
        """Generate breadcrumb navigation trail."""
        parts = note["rel_path"].parts
        crumbs = [f'<a href="{home_href}">Vault</a>']
        for part in parts[:-1]:
            crumbs.append(f'<span>{part}</span>')
        crumbs.append(f'<span>{note["title"]}</span>')
        return '<span class="breadcrumb-separator">/</span>'.join(crumbs)

    def generate_default_index(self, pinned_html: str, has_custom_css: bool):
        recent_notes = sorted(self.notes.values(), key=lambda x: str(x.get("updated") or x.get("created") or ""), reverse=True)[:8]
        recent_items = "".join(f'<li>&#128196; <a href="{n["out_rel_path"]}">{n["title"]}</a> <span style="font-size:0.75rem; opacity:0.6;">{n["updated"] or n["created"]}</span></li>' for n in recent_notes)
        tag_items = "".join(f'<a href="tags.html#{t}" class="tag-badge">#{t} ({len(notes)})</a>' for t, notes in sorted(self.tag_map.items()))

        dashboard_html = f"""
        <div class="dashboard-grid">
            <div class="dashboard-card">
                <h3>&#128202; Vault Stats</h3>
                <ul style="list-style:none; margin-top:0.5rem; font-size:0.9rem;">
                    <li><strong>Total Notes:</strong> {len(self.notes)}</li>
                    <li><strong>Total Tags:</strong> {len(self.tag_map)}</li>
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

        page_html = HTML_TEMPLATE.format(
            title="Digital Garden Home", description="Automatic Landing Page Index", root_offset="", home_href="index.html",
            custom_css_link='<link rel="stylesheet" href="custom.css">' if has_custom_css else "", body_classes="index-dashboard",
            pinned_section=pinned_html.format(root_offset="") if pinned_html else "", folder_tree_html=self.build_folder_tree(Path("index.html")),
            breadcrumb_html='<span>Vault</span> <span class="breadcrumb-separator">/</span> Home', status_badge="", tags_html="", date_meta="",
            toc_content="<p style='font-size:0.85rem; opacity:0.6;'>Dashboard Overview</p>", content=dashboard_html, backlinks_section="",
        )
        with open(self.output_dir / "index.html", "w", encoding="utf-8") as f:
            f.write(page_html)

    def generate_tag_browser(self, has_custom_css: bool):
        tag_sections = []
        for tag in sorted(self.tag_map.keys()):
            notes = self.tag_map[tag]
            items = "".join(f'<li><a href="{n["out_rel_path"]}">{n["title"]}</a></li>' for n in notes)
            tag_sections.append(f'<div style="margin-bottom: 1.5rem;"><h2 id="{tag}">#{tag}</h2><ul style="padding-left:1.2rem; margin-top:0.5rem;">{items}</ul></div>')

        content_html = "<h1>&#127991;&#65039; Tag Browser</h1><hr style='margin:1rem 0; border:0; border-top:1px solid var(--border-color);'>" + "".join(tag_sections)

        page_html = HTML_TEMPLATE.format(
            title="Tag Browser", description="Browse notes by tag", root_offset="", home_href="index.html",
            custom_css_link='<link rel="stylesheet" href="custom.css">' if has_custom_css else "", body_classes="",
            pinned_section="", folder_tree_html=self.build_folder_tree(Path("tags.html")),
            breadcrumb_html='<a href="index.html">Vault</a> <span class="breadcrumb-separator">/</span> Tag Browser',
            status_badge="", tags_html="", date_meta="", toc_content="<p style='font-size:0.85rem; opacity:0.6;'>Tag Index</p>",
            content=content_html, backlinks_section="",
        )
        with open(self.output_dir / "tags.html", "w", encoding="utf-8") as f:
            f.write(page_html)

    def process_links_and_embeds(self, note: dict) -> tuple[str, list]:
        """Resolve [[Wikilinks]] and ![[Embeds]] to HTML, extracting graph links."""
        current_out = note["out_rel_path"]
        links_found = []
        root_offset = "../" * (len(current_out.parts) - 1)

        # 1. Process Embeds (![[image.png|300]])
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
        body = re.sub(embed_pattern, replace_embed, note["html_body"])

        # 2. Process Wikilinks ([[Note]])
        def replace_link(match):
            target = match.group(1).strip()
            display = match.group(3).strip() if match.group(3) else target

            lookup_key = target.lower()
            if lookup_key in self.wikilink_map:
                target_out = self.wikilink_map[lookup_key]
                links_found.append(str(target_out).replace("\\", "/"))
                href = root_offset + str(target_out).replace("\\", "/")
                return f'<a class="wikilink" href="{href}">{display}</a>'
            return f'<span class="wikilink-broken">{display}</span>'

        wikilink_pattern = r"\[\[([^\x7c\]]+)(\x7c([^\]]+))?\]\]"
        final_body = re.sub(wikilink_pattern, replace_link, body)
        return final_body, links_found

    def generate_backlinks_html(self, note: dict, source_ids: list, id_to_note: dict, root_offset: str) -> str:
        target_id = str(note["out_rel_path"]).replace("\\", "/")
        items = []
        for sid in source_ids:
            if sid == target_id:
                continue
            source_note = id_to_note.get(sid)
            if not source_note:
                continue
            href = root_offset + sid
            snippet = source_note["snippet"] or "No preview available."
            if len(snippet) > 100:
                snippet = snippet[:100] + "..."
            items.append(f'<li class="backlink-item"><a class="backlink-link" href="{href}">{source_note["title"]}</a><p class="backlink-snippet">{snippet}</p></li>')

        body_html = f'<ul class="backlink-list">{"".join(items)}</ul>' if items else '<p class="backlinks-empty">No notes link to this page yet. &#127793;</p>'
        return f'<div class="nav-section backlinks-container" id="backlinks"><h3 class="backlinks-title">&#128279; Mentioned In <span class="backlinks-count">({len(items)})</span></h3>{body_html}</div>'

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
            f.write(generate_base_css())

        pinned_notes = [n for n in self.notes.values() if n["pinned"]]
        pinned_html = ""
        if pinned_notes:
            items = "".join(f'<li><a href="{{root_offset}}{n["out_rel_path"]}">{n["title"]}</a></li>' for n in pinned_notes)
            pinned_html = f'<div class="nav-section"><h3>Pinned</h3><ul class="nav-list">{items}</ul></div>'

        search_index, graph_nodes, graph_links = [], [], []

        for note in self.notes.values():
            root_offset = "../" * (len(note["out_rel_path"].parts) - 1)
            clean_url = root_offset + str(note["out_rel_path"]).replace("\\", "/")
            search_index.append({"title": note["title"], "url": clean_url, "snippet": note["snippet"]})
            graph_nodes.append({"id": str(note["out_rel_path"]).replace("\\", "/"), "title": note["title"], "url": clean_url})

        id_to_note = {str(note["out_rel_path"]).replace("\\", "/"): note for note in self.notes.values()}
        self.backlink_map.clear()
        resolved_bodies = {}
        for note in self.notes.values():
            source_id = str(note["out_rel_path"]).replace("\\", "/")
            final_body, connected_targets = self.process_links_and_embeds(note)
            resolved_bodies[source_id] = final_body
            for target_id in connected_targets:
                graph_links.append({"source": source_id, "target": target_id})
                sources = self.backlink_map.setdefault(target_id, [])
                if source_id not in sources:
                    sources.append(source_id)

        for note in self.notes.values():
            dest_path = self.output_dir / note["out_rel_path"]
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            root_offset = "../" * (len(note["out_rel_path"].parts) - 1)
            home_href = f"{root_offset}index.html" if root_offset else "index.html"

            meta = note["metadata"]
            status_key = str(meta.get("status", "")).lower()
            status_badge = f'<span class="status-badge {STATUS_BADGES[status_key][1]}">{STATUS_BADGES[status_key][0]}</span>' if status_key in STATUS_BADGES else ""
            tags_html = "".join(f'<a href="{root_offset}tags.html#{t}" class="tag-badge">#{t}</a>' for t in note["tags"])
            date_str = note["updated"] or note["created"]

            source_id = str(note["out_rel_path"]).replace("\\", "/")
            page_html = HTML_TEMPLATE.format(
                title=note["title"],
                description=note["description"],
                root_offset=root_offset,
                home_href=home_href,
                custom_css_link=f'<link rel="stylesheet" href="{root_offset}custom.css">' if has_custom_css else "",
                body_classes=extract_css_classes(meta),
                pinned_section=pinned_html.format(root_offset=root_offset) if pinned_html else "",
                folder_tree_html=self.build_folder_tree(note["out_rel_path"]),
                breadcrumb_html=self.generate_breadcrumbs(note, home_href),
                status_badge=status_badge,
                tags_html=tags_html,
                date_meta=f'<p style="font-size:0.85rem; opacity:0.7;">Updated: {date_str}</p>' if date_str else "",
                toc_content=note["toc_html"] if meta.get("toc", True) else "<p style='font-size:0.85rem; opacity:0.6;'>ToC Disabled</p>",
                content=resolved_bodies[source_id],
                backlinks_section=self.generate_backlinks_html(note, self.backlink_map.get(source_id, []), id_to_note, root_offset),
            )
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(page_html)

        if not self.has_custom_index:
            self.generate_default_index(pinned_html, has_custom_css)
        self.generate_tag_browser(has_custom_css)
        with open(self.output_dir / "app.js", "w", encoding="utf-8") as f:
            f.write(generate_app_js(search_index, {"nodes": graph_nodes, "links": graph_links}))

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Generated site ({len(self.notes)} notes, custom_index={self.has_custom_index}) -> '{self.output_dir}'")


# ==============================================================================
# 5. WATCHDOG FILE LISTENER & DEV SERVER
# ==============================================================================

if HAS_WATCHDOG:
    class NotesWatchHandler(FileSystemEventHandler):
        def __init__(self, builder: WikiBuilder):
            super().__init__()
            self.builder = builder
            self._last_trigger = 0.0

        def on_any_event(self, event):
            if event.is_directory: return
            src_path = str(event.src_path)
            if src_path.endswith(".md") or src_path.endswith(".css"):
                now = time.time()
                if now - self._last_trigger > 0.5:
                    self._last_trigger = now
                    time.sleep(0.1)
                    print(f"\n[Watchdog] Change detected in '{event.src_path}'. Rebuilding...")
                    try: self.builder.build()
                    except Exception as e: print(f"[Error] Rebuild failed: {e}")

def start_watcher(builder: WikiBuilder, input_dir: Path):
    if not HAS_WATCHDOG:
        print("\n[Watchdog] Note: 'watchdog' package is not installed (pip install watchdog)\n")
        return None
    handler = NotesWatchHandler(builder)
    observer = Observer()
    observer.schedule(handler, str(input_dir.resolve()), recursive=True)
    observer.daemon = True
    observer.start()
    print(f"[Watchdog] Active. Watching '{input_dir.resolve()}'...")
    return observer

class NoCacheHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

def serve_site(output_dir: Path, port: int = 8000):
    handler = partial(NoCacheHTTPRequestHandler, directory=str(output_dir.resolve()))
    httpd = HTTPServer(("0.0.0.0", port), handler)
    print(f"Serving local wiki at http://localhost:{port}")
    try: httpd.serve_forever()
    except KeyboardInterrupt: print("\nShutting down server.")

def main():
    parser = argparse.ArgumentParser(description="vines Static Wiki Builder")
    parser.add_argument("--input", "-i", default="notes", help="Source directory containing markdown notes")
    parser.add_argument("--output", "-o", default="dist", help="Target output directory")
    parser.add_argument("--serve", "-s", action="store_true", help="Start development HTTP server with watch mode")
    parser.add_argument("--watch", "-w", action="store_true", help="Watch notes directory for continuous auto-rebuilds")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Dev server port")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    builder = WikiBuilder(input_path, output_path)
    builder.build()

    should_watch = args.watch or args.serve
    observer = start_watcher(builder, input_path) if should_watch else None

    if args.serve:
        serve_site(output_path, args.port)
    elif args.watch:
        print("Press Ctrl+C to stop watching.")
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            if observer: observer.stop()

if __name__ == "__main__":
    main()
