# কাকের ঠ্যাং · Kaker Theng

Turn your handwriting into a Bangla + English font. Draw the letters one at
a time in the browser (finger, stylus or mouse), or print a template, write
in the boxes and photograph the pages, or mix the two. Download a working
font (TTF and WOFF2) with correct Bangla vowel-sign placement, reph, phala
and conjuncts.

The name comes from the idiom কাকের ঠ্যাং বকের ঠ্যাং, said of messy handwriting.

## Run it locally

One command, with Docker:

```sh
docker compose up
```

Then open http://localhost:3000. The API runs on http://localhost:8000.

To run exactly what Render runs (site and API on one address):

```sh
docker build -t kaker-theng .
docker run --rm -p 8000:8000 kaker-theng     # then open http://localhost:8000
```

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

Tests: `cd backend && .venv/Scripts/python -m pytest tests`.

## How it works

- `backend/` (Python, FastAPI) makes the printable template, reads page
  photos (ArUco corners, darkness-based ink extraction that works for colour
  and black-and-white prints), traces each cell with potrace and builds the
  font on top of Noto Sans Bengali's layout tables, so HarfBuzz in the
  browser handles reordering, reph, phala and conjuncts.
- Drawn letters skip the photo entirely: each stroke arrives as points in
  millimetres inside the same cell box the template prints, is widened to
  the pen width and merged (`app/strokes.py`, pyclipper), and goes through
  the same transform, glyph map, derived parts and font build. The drawing
  screen asks for the most useful letters first (`app/draworder.py`).
- `frontend/` (Next.js, static export) is the one-page site. In production
  the backend serves it at `/` and the API under `/api` from the same
  address, so it needs no settings. `NEXT_PUBLIC_API_URL` is only for
  development and for hosting the site elsewhere.

## Deploy (free)

One free **Render** web service runs everything: the website at `/` and the
API under `/api`, from one address. **cron-job.org** keeps it awake.

### 0. Put the code on GitHub

Render deploys from a GitHub repository. Push this repository (including
`Dockerfile`, `render.yaml`, `frontend/bun.lock` and `backend/assets/`) to
GitHub, on the `main` branch.

### 1. Render: the site and the API

1. Sign in at <https://dashboard.render.com> (sign up with GitHub).
2. Click **New** (top right) and choose **Blueprint**.
3. Under **Connect a repository**, pick this repository. (The first time,
   click **Configure account** and give Render access to it.)
4. Render reads `render.yaml` and shows one service, **kaker-theng-api**
   (Docker, plan Free). Give the Blueprint a name, e.g. `kaker-theng`.
5. Click **Apply** (or **Deploy Blueprint**). Nothing needs filling in. The
   first build takes about 5 to 10 minutes: it builds the website, then the
   Python image.
6. When the service shows **Live**, open it and copy its address at the top,
   e.g. `https://kaker-theng-api.onrender.com`. That address *is* the site.
   Open it; `<address>/health` should say `{"ok":true}`.

Every push to `main` that changes `Dockerfile`, `backend/` or `frontend/`
redeploys by itself.

**Already deployed the earlier API-only Blueprint?** Push, then in Render
open the Blueprint and click **Manual sync** (or wait for the automatic
sync). The service keeps its name and address and is rebuilt from the root
`Dockerfile`. An `ALLOWED_ORIGINS` variable set earlier can stay: it only
matters for the optional Cloudflare setup below.

Render free services sleep after 15 minutes without requests and take about
a minute to wake. While asleep, the **site itself** waits too, not just the
API, so step 2 matters.

### 2. cron-job.org: keep it awake

1. Sign up at <https://cron-job.org> and confirm your email.
2. In the dashboard open **Cronjobs** and click **Create cronjob**.
3. **Title**: `kaker-theng keep-alive`.
4. **URL**: your address with `/health`, e.g.
   `https://kaker-theng-api.onrender.com/health`.
5. **Execution schedule**: every **10** minutes.
6. Click **Create**. After 10 minutes, the job's **History** should show
   successful runs (status 200).

One always-on service uses about 744 of the 750 free instance hours Render
gives a workspace each month, so don't run a second free service 24/7 in the
same workspace.

### 3. After deploy: check it

From any computer with Python 3.9+ (no packages needed), in this repository:

```sh
python backend/scripts/after_deploy.py https://kaker-theng-api.onrender.com
```

It wakes the service and checks:
- `/health`
- that the site loads, and that its scripts arrive compressed and cached
- both copies of the template PDF
- that other websites get no CORS access (none is needed)
- that the site and the API use the same template version
- one real page upload through to the preview font

All checks should say `ok`. You can pass your own page photo as a second
argument.

Then by hand, on a desktop browser:

1. Open the site. The template link opens a 3-page PDF ("template v2" in the
   footer).
2. In section ২ / 2, add a photo of a filled page 1 (or
   `backend/tests/data/sample-page1.jpg`). You should see "হাতের লেখা পড়ছি…",
   then the straightened page and "৭৬টার মধ্যে … ঘর পড়া গেছে".
3. Section ৩ / 3: the try-it box and the name at the top switch to the
   handwriting; **TTF** downloads a zip with the font, `OFL.txt` and
   `README.txt`.

How long things take on the free plan (0.1 CPU, 512 MB), measured locally
under the same limits: the service answers about 15 s after waking and
finishes loading in the background about 20 s later; reading page 1 takes
about 20 s, page 2 about 45 s (it also builds the Bangla font), page 3 about
35 s, and a download about 20 s. One page is read at a time. Everyone else
waits in line and sees their place and an estimated wait. The estimate starts
from these times and then follows how long pages really take on the server.

### Environment variables

| Where | Variable | Example | Needed | What it does |
|---|---|---|---|---|
| Render | `MAX_QUEUE` | `5` | no (5) | Uploads that may wait in line before people are asked to retry. At about 35 s a page, 5 is already a 3-minute wait. |
| Render | `PORT` | `10000` | set by Render | Port the service listens on. |
| Render | `KT_DATA_DIR` | `/tmp/kaker-theng` | no | Where session files go. They are deleted after an hour and need not survive a restart. |
| Render | `ALLOWED_ORIGINS` | `https://kaker-theng.pages.dev` | only for the optional setup | Other website addresses allowed to call the API, comma-separated. |
| Image | `KT_SITE_DIR` | `/srv/site` | set by the `Dockerfile` | Where the built website is; when set, it is served at `/`. |
| Local | `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | for `next dev` | In `frontend/.env.local`. `http://localhost:3000` may call the API whenever it runs without the built site. |

### Optional: the website on Cloudflare Pages

You don't need this. It puts the website on Cloudflare's static hosting
while Render keeps the API. Then the page itself loads at once even while
the free API is asleep, and the site shows "কাক ঘুম থেকে উঠছে… / waking up
the crow…" while the API wakes. The cost is a second service to set up and
the CORS setting below. The Render steps above stay the same.

1. Sign in at <https://dash.cloudflare.com>. In **Workers & Pages** click
   **Create**, choose the **Pages** tab, then **Connect to Git**, pick this
   repository and click **Begin setup**.
2. Fill in **Set up builds and deployments**:

   | Setting | Value |
   |---|---|
   | Project name | e.g. `kaker-theng` (address `https://kaker-theng.pages.dev`) |
   | Production branch | `main` |
   | Framework preset | `Next.js (Static HTML Export)` |
   | Build command | `bun install && bun run build` |
   | Build output directory | `out` |
   | Root directory (under *Advanced*) | `frontend` |

3. Under **Environment variables** add:

   | Variable | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | your Render address, e.g. `https://kaker-theng-api.onrender.com` (no trailing slash) |
   | `BUN_VERSION` | `1.3.12` |
   | `NODE_VERSION` | `22` |

   If `NEXT_PUBLIC_API_URL` is missing, the build stops with a message saying
   so. The address is baked in at build time; if you change it, redeploy
   (**Deployments** → **⋯** → **Retry deployment**).
4. Click **Save and Deploy** (2 to 3 minutes).
5. In Render open **kaker-theng-api** → **Environment**, add
   **ALLOWED_ORIGINS** = the Pages address, e.g.
   `https://kaker-theng.pages.dev` (several separated by commas), and click
   **Save Changes**. Preview builds of other branches get their own addresses
   and are refused unless you add them too.
6. Check with both addresses:
   `python backend/scripts/after_deploy.py https://kaker-theng-api.onrender.com https://kaker-theng.pages.dev`

`frontend/public/_headers` sets caching for Pages. In the one-service image
`backend/app/site.py` does the same job.

## Changing the template

The template, the scanner and the website share one layout:

1. Change `backend/app/charset.py` or the layout code, then run
   `python -m scripts.make_template` in `backend/`. If a page's cells moved,
   it stops and asks you to bump `TEMPLATE_VERSION` in `app/config.py`:
   old prints of that page are then refused with a link to the new template
   instead of being read with the wrong cells.
2. Run `python -m scripts.export_frontend_assets` to refresh the site's copy
   of the layout, thumbnails and PDF. A test fails if you forget.
3. Push: Render rebuilds the site and the API together, so they always match.
   The after-deploy check confirms it.

## Credits and licences

- This project's code is under the [MIT License](LICENSE).
- **Fonts made with Kaker Theng are under the SIL Open Font License 1.1**, not
  MIT, because they are built from Noto Sans Bengali (below). Every download
  includes `OFL.txt`. You may use, share and sell them, but not sell the font
  files on their own, and modified versions must stay under the OFL.
- The bundled font files keep their own licences: `backend/assets/OFL.txt`
  for Noto Sans Bengali, `backend/tests/fonts/OFL-*.txt` for the test fonts.
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
