"""
Build a single-file explorer that opens by double-clicking.

The served explorer fetches `data.json` alongside itself, which browsers block
for pages opened from the filesystem. That is fine for GitHub Pages and useless
for emailing someone a file.

This inlines the bundle into the page, so the result is one self-contained HTML
file that needs no server, no install and no network beyond the Chart.js CDN.
"""

from __future__ import annotations

import json
import os

from engine.model import run_all

from . import json_bundle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "explorer", "index.html")

# Injected immediately before the page's own script, so DataSource finds it.
ANCHOR = '<script>\n"use strict";'


def build(out_path: str, results=None) -> str:
    results = results or run_all()
    bundle = json_bundle.build(results)

    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()

    if ANCHOR not in html:
        raise RuntimeError(
            "could not find the script anchor in explorer/index.html -- the "
            "standalone build needs to inject the data before it"
        )

    # </script> inside a JSON string would end the block early; escaping the
    # slash is the standard defence and is still valid JSON.
    payload = json.dumps(bundle, separators=(",", ":")).replace("</", r"<\/")
    injected = (
        f'<script>window.__SLC_DATA = {payload};</script>\n'
        f'{ANCHOR}'
    )
    html = html.replace(ANCHOR, injected, 1)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


if __name__ == "__main__":
    path = build(os.path.join(ROOT, "dist", "SLC_Explorer.html"))
    print(f"{path}  ({os.path.getsize(path) / 1024:,.0f} KB)")
