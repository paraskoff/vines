# vines.py

A zero-dependency (with optional enhancements) static digital garden and wiki builder written in Python. It compiles a folder of Markdown notes (`.md`) into a fully interactive, responsive HTML knowledge base complete with bi-directional wikilinks, a live canvas graph, collapsible folder trees, search, and automated fallback landing pages.

## Features

- **Automated Fallback Dashboard (`index.html`)**: Automatically generates a rich landing page listing vault statistics, recent updates, and tag overviews when no user-created `index.md` or `Index` note is present.
- **Bi-directional `[[Wikilinks]]` & Hover Cards**: Link notes effortlessly using standard Obsidian-style syntax with dynamic hover preview cards featuring collision boundary detection.
- **Interactive Knowledge Graph**: Pure vanilla HTML5 canvas physics simulation mapping out your note connections.
- **Collapsible Vault Hierarchy**: Clean sidebar folder tree view (`<details>` / `<summary>`) that scales across nested subdirectories.
- **Advanced Markdown Support**: Supports KaTeX math rendering, Pygments code syntax highlighting with a one-click copy button, image lightboxes, footnotes, and frontmatter parsing (`yaml` or fallback key-value).
- **Live Dev Server & Watchdog**: Built-in file system watcher for real-time auto-rebuilding and a local static development server.

## Installation & Requirements

Requires **Python 3.8+**. Optional dependencies can be installed for extended features:

```bash
pip install markdown PyYAML watchdog
```

## Usage

Compile your vault notes into a distribution directory:

```bash
python vines.py --input ./notes --output ./dist
```

Start the local development server with live watch mode enabled:

```bash
python vines.py --input ./notes --output ./dist --serve --port 8000
```

## CLI Arguments

- `-i`, `--input`: Source directory containing your Markdown notes (default: `notes`)
- `-o`, `--output`: Target output directory for built HTML files (default: `dist`)
- `-s`, `--serve`: Start a local HTTP development server
- `-w`, `--watch`: Watch the notes directory for continuous file changes and auto-rebuild
- `-p`, `--port`: Port number for the local development server (default: `8000`)
- `-t`, `--theme`: Theme name (check [available themes](src/vines/themes/THEMES.md))
