import re
from typing import List, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False


def parse_frontmatter(content: str) -> Tuple[dict, str]:
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


def extract_tags(metadata: dict, body: str) -> List[str]:
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
    lines = md.split("\n")
    out = []
    in_callout = False
    for line in lines:
        callout_match = re.match(r"^>\s*\[!(?P<type>\w+)\](?P<title>.*)", line)
        if callout_match:
            in_callout = True
            ctype = callout_match.group("type").lower()
            title = callout_match.group("title").strip() or ctype.capitalize()
            out.append(f'!!! {ctype} "{title}"')
        elif in_callout:
            if line.startswith(">"):
                inner_text = line[1:].lstrip(" ")
                out.append("    " + inner_text)
            else:
                in_callout = False
                out.append(line)
        else:
            out.append(line)
    return "\n".join(out)


def parse_markdown_to_html(md_content: str) -> Tuple[str, str, str]:
    """Convert Markdown to HTML with extensions for footnotes, syntax highlighting, callouts, math, and task lists."""
    toc_items = []

    def replace_heading(match):
        level = len(match.group(1))
        title = match.group(2).strip()
        slug = re.sub(r"[^\w\-]", "", title.lower().replace(" ", "-"))
        if level in (2, 3):
            toc_items.append((level, title, slug))
        return f'<h{level} id="{slug}">{title}</h{level}>'

    md_content = convert_obsidian_callouts(md_content)
    md_content = re.sub(
        r"^(\s*)-\s+\[ \]\s+",
        r'\1* <input type="checkbox" disabled style="margin-right: 0.5rem; margin-top: 0.3rem;"> ',
        md_content,
        flags=re.MULTILINE,
    )
    md_content = re.sub(
        r"^(\s*)-\s+\[x\]\s+",
        r'\1* <input type="checkbox" checked disabled style="margin-right: 0.5rem; margin-top: 0.3rem;"> ',
        md_content,
        flags=re.MULTILINE | re.IGNORECASE,
    )

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
                items = "".join(
                    f"<li>{item[2:]}</li>"
                    for item in p.split("\n")
                    if item.startswith("- ") or item.startswith("* ")
                )
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