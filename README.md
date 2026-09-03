# gummietech

Content pipeline for @gummietech — daily science, technology, and engineering
posts on Instagram.

Strategy and source map: `docs/gummietech_content_system.md`

## Pipeline

```
[1] INGEST → [2] SCORE → [3] DRAFT → [4] DESIGN → [5] HUMAN GATE → [6] PUBLISH
  every 2h    Gemini      LLM         HTML→PNG      10 min/day      Business Suite
```

## Layout

| Path | Purpose |
|---|---|
| `src/` | Pipeline scripts |
| `feeds/` | RSS source lists by tier (YAML) |
| `templates/` | HTML/CSS slide templates |
| `output/` | Rendered PNGs (gitignored) |
| `.github/workflows/` | GitHub Actions cron |

## Setup

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then fill in keys
```

## Verify feeds

Feed URLs move. Check which ones are live before relying on them:

```bash
python src/verify_feeds.py
```

## Budget

$0/month. Every dependency is free tier, open source, or self-hosted.
Do not add a paid service without replacing it in `docs/`.
