# কাকের ঠ্যাং · Kaker Theng

Turn your handwriting into a Bangla + English font. Print a template, write
the letters in the boxes, photograph the pages, download a working font
(TTF and WOFF2) with correct Bangla vowel-sign placement, reph, phala and
conjuncts.

The name comes from the idiom কাকের ঠ্যাং বকের ঠ্যাং, said of messy handwriting.

## Run it locally

One command, with Docker:

```sh
docker compose up
```

Then open http://localhost:3000. The API runs on http://localhost:8000.

Without Docker:

```sh
# backend (Python 3.13)
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# frontend (Bun 1.3.12; Next.js itself runs on Node 20+)
cd frontend
cp .env.example .env.local
bun install
bun run dev
```

## How it works

- `backend/` (Python, FastAPI) makes the printable template, reads page
  photos (ArUco corners, darkness-based ink extraction that works for colour
  and black-and-white prints), traces each cell with potrace and builds the
  font on top of Noto Sans Bengali's layout tables, so HarfBuzz in the
  browser handles reordering, reph, phala and conjuncts.
- `frontend/` (Next.js, static export) is the one-page site.

Tests: `cd backend && .venv/Scripts/python -m pytest tests`.

Deployment (Cloudflare Pages + Render) is documented in a later step.

## Credits and licences

- Base font: [Noto Sans Bengali](https://github.com/notofonts/bengali),
  Copyright The Noto Project Authors, SIL Open Font License 1.1. Fonts made
  with Kaker Theng are Modified Versions and stay under the OFL; "Noto" is a
  trademark of Google and is not used in their names.
- Conjunct frequencies (which conjuncts get template cells, and the coverage
  figure shown on the site) are counted from
  [Bangla Wikipedia](https://bn.wikipedia.org/), text licensed
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Only
  aggregate counts are kept (`backend/assets/conjunct_counts.json`).
- Test handwriting fonts: Patrick Hand and Galada, SIL Open Font License 1.1.
- Site fonts: Tiro Bangla, Spectral, IBM Plex Mono (Google Fonts, OFL).
