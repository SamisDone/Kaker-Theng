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

Tests: `cd backend && .venv/Scripts/python -m pytest tests`.

## How it works

- `backend/` (Python, FastAPI) makes the printable template, reads page
  photos (ArUco corners, darkness-based ink extraction that works for colour
  and black-and-white prints), traces each cell with potrace and builds the
  font on top of Noto Sans Bengali's layout tables, so HarfBuzz in the
  browser handles reordering, reph, phala and conjuncts.
- `frontend/` (Next.js, static export) is the one-page site. It talks to the
  backend at `NEXT_PUBLIC_API_URL`.

## Deploy (free)

The website goes on **Cloudflare Pages** (static files), the API on
**Render** (a free Docker web service), and **cron-job.org** keeps the free
API awake. Do the steps in this order: the website needs the API's address,
and the API needs the website's.

### 0. Put the code on GitHub

Both services deploy from a GitHub repository. Push this repository
(including `frontend/bun.lock`, `render.yaml` and `backend/assets/`) to
GitHub, on the `main` branch.

### 1. Pick the website's name

Cloudflare Pages gives the site the address `https://<project-name>.pages.dev`.
Choose the project name now, for example `kaker-theng`, so the address is
`https://kaker-theng.pages.dev`. (If that name is taken, Cloudflare adds a
suffix; step 4 fixes the API's setting if it does.)

### 2. Render: the API

1. Sign in at <https://dashboard.render.com> (sign up with GitHub).
2. Click **New** (top right) and choose **Blueprint**.
3. Under **Connect a repository**, pick this repository. (The first time,
   click **Configure account** and give Render access to it.)
4. Render reads `render.yaml` and shows one service, **kaker-theng-api**
   (Docker, plan Free). Give the Blueprint a name, e.g. `kaker-theng`.
5. It asks for **ALLOWED_ORIGINS**: enter the website address from step 1,
   e.g. `https://kaker-theng.pages.dev` (no trailing slash).
6. Click **Apply** (or **Deploy Blueprint**). The first build takes about
   5 minutes.
7. When the service shows **Live**, open it and copy its address at the top,
   e.g. `https://kaker-theng-api.onrender.com`. Open
   `<that address>/health` in a browser: it should say `{"ok":true}`.

Render free services sleep after 15 minutes without requests and take
about a minute to wake. Step 5 keeps it awake.

### 3. Cloudflare Pages: the website

1. Sign in at <https://dash.cloudflare.com>.
2. In the left menu open **Workers & Pages**, click **Create**, choose the
   **Pages** tab, then **Connect to Git** (Import an existing Git repository).
3. Connect GitHub if asked, pick this repository, click **Begin setup**.
4. Fill in **Set up builds and deployments**:

   | Setting | Value |
   |---|---|
   | Project name | `kaker-theng` (the name from step 1) |
   | Production branch | `main` |
   | Framework preset | `Next.js (Static HTML Export)` |
   | Build command | `bun install && bun run build` |
   | Build output directory | `out` |
   | Root directory (under *Advanced*) | `frontend` |

5. Under **Environment variables** add:

   | Variable | Example value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://kaker-theng-api.onrender.com` (from step 2, no trailing slash) |
   | `BUN_VERSION` | `1.3.12` |
   | `NODE_VERSION` | `22` |

6. Click **Save and Deploy**. The build takes 2 to 3 minutes. If
   `NEXT_PUBLIC_API_URL` is missing the build stops with a message saying so.
7. Open the address Cloudflare shows (e.g. `https://kaker-theng.pages.dev`).

`NEXT_PUBLIC_API_URL` is baked in when the site is built. If you change it,
redeploy: **Deployments** → **⋯** on the latest → **Retry deployment**.

### 4. Tell the API the website's real address

If the Pages address differs from what you entered in step 2.5 (a suffix
was added, or you add a custom domain): in Render open **kaker-theng-api** →
**Environment** → edit **ALLOWED_ORIGINS** → **Save Changes**. Render
redeploys by itself. Several addresses are separated by commas, e.g.
`https://kaker-theng.pages.dev,https://font.example.com`.

Preview builds of other branches get their own addresses
(`https://<hash>.kaker-theng.pages.dev`); the API refuses them unless you add
them too.

### 5. cron-job.org: keep the API awake

1. Sign up at <https://cron-job.org> and confirm your email.
2. In the dashboard open **Cronjobs** and click **Create cronjob**.
3. **Title**: `kaker-theng keep-alive`.
4. **URL**: your API address with `/health`, e.g.
   `https://kaker-theng-api.onrender.com/health`.
5. **Execution schedule**: every **10** minutes.
6. Click **Create**. After 10 minutes, the job's **History** should show
   successful runs (status 200).

One always-on service uses about 744 of the 750 free instance hours Render
gives a workspace each month, so don't run a second free service 24/7 in the
same workspace.

### 6. After deploy: check it

From any computer with Python 3.9+ (no packages needed), in this repository:

```sh
python backend/scripts/after_deploy.py https://kaker-theng-api.onrender.com https://kaker-theng.pages.dev
```

It wakes the API and checks `/health`, that the site loads, both copies of
the template PDF, CORS from the site's address, that the site and the API use
the same template version, and one real page upload through to the preview
font. All checks should say `ok`. You can pass your own page photo as a
third argument.

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
under the same limits: the API answers about 15 s after waking and finishes
loading in the background about 20 s later; reading page 1 takes about 20 s,
page 2 about 45 s (it also builds the Bangla font), page 3 about 35 s, and a
download about 20 s. One page is read at a time. Everyone else waits in line
and sees their place and an estimated wait. The estimate starts from these
times and then follows how long pages really take on the server.

### Environment variables

| Where | Variable | Example | Needed | What it does |
|---|---|---|---|---|
| Render | `ALLOWED_ORIGINS` | `https://kaker-theng.pages.dev` | yes | Website addresses allowed to call the API, comma-separated. `http://localhost:3000` is always allowed. |
| Render | `MAX_QUEUE` | `5` | no (5) | Uploads that may wait in line before people are asked to retry. At about 35 s a page, 5 is already a 3-minute wait. |
| Render | `PORT` | `10000` | set by Render | Port the API listens on. |
| Render | `KT_DATA_DIR` | `/tmp/kaker-theng` | no | Where session files go. They are deleted after an hour and need not survive a restart. |
| Pages | `NEXT_PUBLIC_API_URL` | `https://kaker-theng-api.onrender.com` | yes | The API address, built into the site. |
| Pages | `BUN_VERSION` | `1.3.12` | yes | Bun version for `bun install` and the scripts. |
| Pages | `NODE_VERSION` | `22` | yes | Node for Next.js (Next.js runs on Node; Bun installs and runs the scripts). |
| Local | `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | yes | In `frontend/.env.local`. |

## Changing the template

The template, the scanner and the website share one layout:

1. Change `backend/app/charset.py` or the layout code, then run
   `python -m scripts.make_template` in `backend/`. If a page's cells moved,
   it stops and asks you to bump `TEMPLATE_VERSION` in `app/config.py`:
   old prints of that page are then refused with a link to the new template
   instead of being read with the wrong cells.
2. Run `python -m scripts.export_frontend_assets` to refresh the site's copy
   of the layout, thumbnails and PDF. A test fails if you forget.
3. Deploy both. The after-deploy check confirms they match.

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
