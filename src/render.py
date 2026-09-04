#!/usr/bin/env python3
"""
Render a Drop post to five 1080x1350 PNGs.

Reads a post JSON record, injects it into templates/drop.html with Jinja2,
and screenshots each .slide div individually with Playwright.

Usage:
    python src/render.py posts/2026-09-03-era.json
    python src/render.py posts/2026-09-03-era.json --outdir output/era

Guardrails enforced here, not by convention:
  - refuses to render without `attribution` and `alt_text`
  - forces the preprint flag when `peer_reviewed` is false
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "templates"
DEFAULT_OUT = REPO_ROOT / "output"

SLIDE_W, SLIDE_H = 1080, 1350
SLIDE_IDS = ["slide-1", "slide-2", "slide-3", "slide-4", "slide-5"]

REQUIRED = ["hook", "what_happened", "why_it_matters", "the_catch",
            "attribution", "alt_text", "source_url"]

WORD_LIMIT = 25          # per §1 of the content system
HOOK_WORD_LIMIT = 12


def load_post(path: Path) -> dict:
    """Read and validate a post record."""
    try:
        post = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        sys.exit(f"{path} is not valid JSON: {exc}")

    missing = [f for f in REQUIRED if not post.get(f)]
    if missing:
        sys.exit(
            f"Refusing to render. Missing required field(s): {', '.join(missing)}.\n"
            "attribution and alt_text are mandatory — add them to the JSON and re-run."
        )

    # peer_reviewed must be explicit. Defaulting it to True would let an
    # unlabelled preprint through, which is the exact failure this guards.
    if "peer_reviewed" not in post:
        sys.exit(
            "Refusing to render. `peer_reviewed` is missing.\n"
            "Set it to true or false — an unlabelled preprint is a credibility risk."
        )

    return post


def warn_on_length(post: dict) -> None:
    """Word limits are a style rule, so warn rather than fail."""
    checks = [
        ("hook", HOOK_WORD_LIMIT),
        ("what_happened", WORD_LIMIT),
        ("why_it_matters", WORD_LIMIT),
        ("the_catch", WORD_LIMIT),
    ]
    for field, limit in checks:
        count = len(str(post.get(field, "")).split())
        if count > limit:
            print(f"  warning: {field} is {count} words (limit {limit}) — "
                  f"consider splitting across two slides")


def hook_size_class(hook: str) -> str:
    """Pick a display size so long hooks shrink instead of overflowing."""
    n = len(hook)
    if n < 45:
        return "xl"
    if n < 75:
        return "lg"
    if n < 110:
        return "md"
    return "sm"


def render_html(post: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("drop.html")
    return template.render(
        **post,
        show_preprint_flag=not post.get("peer_reviewed", False),
        hook_size=hook_size_class(post.get("hook", "")),
        font_dir=(REPO_ROOT / "fonts").as_uri(),
    )


def shoot(html: str, outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        # The page has to be loaded from file://, not injected with set_content():
        # Chromium refuses local subresources on an about:blank page ("Not allowed
        # to load local resource"), so the self-hosted fonts drop out silently
        # and the slides render in a fallback face.
        page_file = Path(tmp) / "slides.html"
        page_file.write_text(html)

        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": SLIDE_W, "height": SLIDE_H},
            device_scale_factor=1,
        )
        page.goto(page_file.as_uri(), wait_until="load")
        page.wait_for_timeout(600)          # let webfonts settle

        for i, slide_id in enumerate(SLIDE_IDS, start=1):
            el = page.query_selector(f"#{slide_id}")
            if el is None:
                print(f"  warning: #{slide_id} not found in template, skipping")
                continue
            out = outdir / f"slide-{i}.png"
            el.screenshot(path=str(out))
            written.append(out)
            print(f"  wrote {out.relative_to(REPO_ROOT)}")

        browser.close()
    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("post", help="path to the post JSON")
    ap.add_argument("--outdir", default=None, help="where to write PNGs")
    args = ap.parse_args()

    post_path = Path(args.post)
    if not post_path.is_absolute():
        post_path = REPO_ROOT / post_path
    if not post_path.exists():
        sys.exit(f"No such post file: {post_path}")

    post = load_post(post_path)
    warn_on_length(post)

    outdir = Path(args.outdir) if args.outdir else DEFAULT_OUT / post_path.stem
    if not outdir.is_absolute():
        outdir = REPO_ROOT / outdir

    print(f"Rendering {post_path.name} → {outdir}")
    if not post.get("peer_reviewed"):
        print("  preprint flag ON (peer_reviewed is false)")

    written = shoot(render_html(post), outdir)

    # The caption and alt text are needed at posting time, so drop them
    # next to the images rather than making you dig back into the JSON.
    # Hashtags ride with the caption so the top block pastes into Business Suite
    # in one go, rather than being retyped from the JSON.
    tags = " ".join(post.get("hashtags") or [])
    sidecar = outdir / "caption.txt"
    sidecar.write_text(
        f"{post.get('caption', '')}\n"
        + (f"\n{tags}\n" if tags else "")
        + f"\n--- ALT TEXT ---\n{post['alt_text']}\n\n"
        f"--- ATTRIBUTION ---\n{post['attribution']}\n{post['source_url']}\n"
    )
    print(f"  wrote {sidecar.relative_to(REPO_ROOT)}")
    print(f"\nDone. {len(written)} slides.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
