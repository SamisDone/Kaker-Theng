"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChapterCard } from "@/components/ChapterCard";
import { ChapterList } from "@/components/ChapterList";
import { DrawScreen } from "@/components/DrawScreen";
import { FontScreen } from "@/components/FontScreen";
import { PaperScreen, type PaperStep } from "@/components/PaperScreen";
import { RewardScreen } from "@/components/RewardScreen";
import { StartScreen } from "@/components/StartScreen";
import { HomeContext, TopBar } from "@/components/TopBar";
import type { SlotState } from "@/components/UploadSlot";
import {
  ApiError,
  createSession,
  fileUrl,
  getSession,
  type Progress,
  type ProgressState,
  putDrawn,
  requestPreview,
  type SessionMeta,
  uploadPage,
  wake,
} from "@/lib/api";
import { bnNum } from "@/lib/bn";
import { CHAPTERS, chapterById, type ChapterId, chapterIn, chapterLists } from "@/lib/chapters";
import { loadDrawn, type Saved, saveDrawn } from "@/lib/drawstore";
import { LangProvider, useLang } from "@/lib/i18n";
import { shrinkPhoto } from "@/lib/image";
import { cellsById, type Layout, loadLayout } from "@/lib/layout";
import type { Stroke } from "@/lib/strokes";

const SESSION_KEY = "kaker-theng-session";
const SCREEN_KEY = "kaker-theng-screen";
const REBUILD_EVERY = 5; // letters
// A reload this soon after the last screen change (the phone reloading the
// page after the camera, a pull to refresh) keeps the screen; any later
// visit opens the start screen, with "continue drawing" and "my font".
const KEEP_SCREEN_MS = 30 * 60 * 1000;
const IDLE_MS = 3000;

// One job per screen. Each is a browser history entry, so the phone's back
// button goes back a screen instead of leaving the site.
type Screen =
  | { name: "start" }
  | { name: "chapters" }
  | { name: "card"; chapter: ChapterId }
  | { name: "draw" }
  | { name: "reward"; chapter: ChapterId }
  | { name: "font" }
  | { name: "paper"; step: PaperStep };

type Note = { bn: string; en: string } | null;

function store(kind: "get" | "set" | "remove", key: string, value = ""): string | null {
  try {
    if (kind === "get") return sessionStorage.getItem(key);
    if (kind === "set") sessionStorage.setItem(key, value);
    else sessionStorage.removeItem(key);
  } catch {
    // private mode etc.: it just won't survive a reload
  }
  return null;
}

const remember = (id: string | null) => (id ? store("set", SESSION_KEY, id) : store("remove", SESSION_KEY));
const keepScreen = (s: Screen) => store("set", SCREEN_KEY, JSON.stringify({ screen: s, at: Date.now() }));

export default function Home() {
  return (
    <LangProvider>
      <App />
    </LangProvider>
  );
}

function App() {
  const { t } = useLang();
  const [screen, setScreen] = useState<Screen>({ name: "start" });
  const depth = useRef(0);
  const [layout, setLayout] = useState<Layout | null>(null);
  const [session, setSession] = useState<string | null>(null);
  const [meta, setMeta] = useState<SessionMeta | null>(null);
  const [userFont, setUserFont] = useState<string | null>(null);
  const [slots, setSlots] = useState<Record<number, SlotState>>({ 1: { kind: "idle" }, 2: { kind: "idle" }, 3: { kind: "idle" } });
  const [notes, setNotes] = useState<Record<number, Note>>({});
  const sessionRef = useRef<string | null>(null);

  // Drawing: the letters live in this browser (saved), the server gets a copy.
  const [saved, setSaved] = useState<Saved | null>(null);
  const [building, setBuilding] = useState(false);
  const [syncNote, setSyncNote] = useState<Note>(null);
  const [recalled, setRecalled] = useState(false);
  const savedRef = useRef<Saved | null>(null);
  const unsynced = useRef<Set<string>>(new Set());
  const syncRun = useRef<Promise<void> | null>(null);
  const preview = useRef({ running: false, again: false });
  const pendingLetters = useRef(0); // drawn since the last rebuild
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ---- Screens -------------------------------------------------------------

  const go = useCallback((s: Screen, replace = false) => {
    if (!replace) depth.current += 1;
    const state = { screen: s, depth: depth.current };
    if (replace) history.replaceState(state, "");
    else history.pushState(state, "");
    keepScreen(s);
    setScreen(s);
  }, []);

  // Back a screen; to the start if this one was opened by a reload.
  const back = () => (depth.current > 0 ? history.back() : go({ name: "start" }, true));
  const home = () => go({ name: "start" });

  useEffect(() => {
    let first: Screen = { name: "start" };
    try {
      const kept = JSON.parse(store("get", SCREEN_KEY) ?? "null") as { screen: Screen; at: number } | null;
      if (kept?.screen?.name && Date.now() - kept.at < KEEP_SCREEN_MS) first = kept.screen;
    } catch {
      // unreadable: the start
    }
    history.replaceState({ screen: first, depth: 0 }, "");
    setScreen(first);
    const onPop = (e: PopStateEvent) => {
      const s: Screen = e.state?.screen ?? { name: "start" };
      depth.current = e.state?.depth ?? 0;
      keepScreen(s);
      setScreen(s);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // ---- Session and layout --------------------------------------------------

  useEffect(() => {
    wake();
    loadLayout().then(setLayout).catch(() => undefined);
    const id = store("get", SESSION_KEY);
    if (!id) {
      setRecalled(true);
      return;
    }
    getSession(id)
      .then((m) => {
        if (m) {
          sessionRef.current = id;
          setSession(id);
          setMeta(m);
        } else remember(null);
      })
      .catch(() => undefined)
      .finally(() => setRecalled(true));
  }, []);

  // Once the layout and any old session are known: load the drawing kept in
  // this browser, and send it if the server doesn't have exactly these cells.
  useEffect(() => {
    if (!layout || !recalled || savedRef.current) return;
    const s = loadDrawn(layout.fingerprint);
    savedRef.current = s;
    setSaved(s);
    const local = Object.keys(s.cells).sort().join();
    const remote = Object.keys(meta?.drawn ?? {}).sort().join();
    if (local && (local !== remote || !meta?.font)) {
      for (const id of Object.keys(s.cells)) unsynced.current.add(id);
      void rebuildPreview();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layout, recalled]);

  const cells = useMemo(() => (layout ? cellsById(layout) : null), [layout]);
  const lists = useMemo(() => (layout && cells ? chapterLists(layout, cells) : null), [layout, cells]);
  const fromPaper = useMemo(() => {
    const out = new Set<string>();
    for (const p of Object.values(meta?.pages ?? {})) for (const c of p.cells) if (c.status !== "missing") out.add(c.id);
    return out;
  }, [meta]);
  const done = useCallback((id: string) => Boolean(saved?.cells[id]?.length) || fromPaper.has(id), [saved, fromPaper]);

  // Load the preview font whenever the server has built a new one.
  useEffect(() => {
    if (!session || !meta?.font) return;
    let cancelled = false;
    const family = `KakerThengUser${meta.font_version}`;
    fetch(fileUrl(session, meta.font))
      .then((r) => r.arrayBuffer())
      .then((buf) => new FontFace(family, buf).load())
      .then((face) => {
        if (cancelled) return;
        document.fonts.add(face);
        setUserFont(family);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [session, meta?.font, meta?.font_version]);

  const setSlot = useCallback((page: number, s: SlotState) => setSlots((prev) => ({ ...prev, [page]: s })), []);

  async function ensureSession(progress?: Progress): Promise<string> {
    if (sessionRef.current) return sessionRef.current;
    const id = await createSession(progress);
    sessionRef.current = id;
    setSession(id);
    remember(id);
    return id;
  }

  function forgetSession() {
    sessionRef.current = null;
    setSession(null);
    setMeta(null);
    setUserFont(null);
    remember(null);
  }

  // Send drawn letters that changed (or all of them, after the server forgot
  // us). Only stores them; rebuilding the font is scheduled separately.
  function syncDrawn(): Promise<void> {
    if (syncRun.current) return syncRun.current.then(() => (unsynced.current.size ? syncDrawn() : undefined));
    const run = (async () => {
      while (unsynced.current.size) {
        const ids = [...unsynced.current];
        unsynced.current.clear();
        const cells: Record<string, Stroke[]> = {};
        for (const id of ids) cells[id] = savedRef.current?.cells[id] ?? [];
        try {
          setMeta(await putDrawn(await ensureSession(), cells));
          setSyncNote(null);
        } catch (err) {
          if (err instanceof ApiError && err.code === "session_gone") {
            forgetSession();
            for (const id of Object.keys(savedRef.current?.cells ?? {})) unsynced.current.add(id);
            continue;
          }
          for (const id of ids) unsynced.current.add(id);
          setSyncNote({
            bn: "সার্ভারে পাঠানো গেল না। অক্ষরগুলো এখানে রাখা আছে, পরেরটার সাথে আবার পাঠাব।",
            en: "Couldn't reach the server. Your letters are kept here and go with the next one.",
          });
          return;
        }
      }
    })().finally(() => {
      syncRun.current = null;
    });
    syncRun.current = run;
    return run;
  }

  // Rebuild the preview font after every REBUILD_EVERY letters, or once the
  // pen has rested IDLE_MS, whichever comes first, or when asked. The free
  // server has a tenth of a CPU: a rebuild per letter would keep it busy.
  function scheduleRebuild() {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = null;
    if (pendingLetters.current >= REBUILD_EVERY) void rebuildPreview();
    else if (pendingLetters.current > 0) idleTimer.current = setTimeout(() => void rebuildPreview(), IDLE_MS);
  }

  // One preview build at a time; letters drawn meanwhile get one more after.
  async function rebuildPreview() {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = null;
    pendingLetters.current = 0;
    if (preview.current.running) {
      preview.current.again = true;
      return;
    }
    preview.current.running = true;
    setBuilding(true);
    try {
      do {
        preview.current.again = false;
        await syncDrawn();
        if (!sessionRef.current) break;
        setMeta(await requestPreview(sessionRef.current));
      } while (preview.current.again);
    } catch (err) {
      if (err instanceof ApiError && err.code === "session_gone") {
        forgetSession();
        for (const id of Object.keys(savedRef.current?.cells ?? {})) unsynced.current.add(id);
        pendingLetters.current = REBUILD_EVERY;
      }
    } finally {
      preview.current.running = false;
      setBuilding(false);
    }
    if (pendingLetters.current >= REBUILD_EVERY) void rebuildPreview();
  }

  function updateSaved(change: (s: Saved) => Saved) {
    if (!savedRef.current) return;
    const next = change(savedRef.current);
    savedRef.current = next;
    setSaved(next);
    if (!saveDrawn(next))
      setSyncNote({ bn: "এই ব্রাউজারে আঁকা জমানো যাচ্ছে না; ট্যাব বন্ধ করলে হারাবে।", en: "This browser won't store the drawing; it's lost if you close the tab." });
  }

  function onDrawn(id: string, strokes: Stroke[]) {
    updateSaved((s) => {
      const cells = { ...s.cells };
      if (strokes.length) cells[id] = strokes;
      else delete cells[id];
      return { ...s, cells, draft: null };
    });
    unsynced.current.add(id);
    void syncDrawn();
    pendingLetters.current += 1;
    scheduleRebuild();
  }

  // ---- Moving between chapters ---------------------------------------------

  const setAt = (id: string) => updateSaved((s) => ({ ...s, at: id }));

  // A chapter not started yet opens with its card; one under way goes on
  // where it stopped.
  function openChapter(c: ChapterId) {
    if (!lists) return;
    const ids = lists[c];
    if (!ids.some(done)) return go({ name: "card", chapter: c });
    setAt(ids.find((id) => !done(id)) ?? ids[0]);
    go({ name: "draw" });
  }

  function startChapter(c: ChapterId) {
    if (!lists) return;
    const ids = lists[c];
    setAt(ids.find((id) => !done(id)) ?? ids[0]);
    go({ name: "draw" });
  }

  /** The next chapter after `c` with letters left, wrapping round. */
  function nextChapter(c: ChapterId) {
    if (!lists) return null;
    const i = CHAPTERS.findIndex((x) => x.id === c);
    const order = [...CHAPTERS.slice(i + 1), ...CHAPTERS.slice(0, i)];
    return order.find((x) => lists[x.id].some((id) => !done(id))) ?? null;
  }

  // Draw: on where the last visit stopped, or at the start.
  function startDrawing() {
    if (!lists) return;
    let c: ChapterId = saved?.at && cells?.has(saved.at) ? chapterIn(lists, saved.at) : "vowels";
    if (lists[c].every(done)) c = nextChapter(c)?.id ?? c;
    openChapter(c);
  }

  function openFont() {
    if (pendingLetters.current > 0 || unsynced.current.size) void rebuildPreview();
    go({ name: "font" });
  }

  // Everything needed to rebuild this drawing elsewhere: the strokes exactly
  // as kept here and sent to the server, and what they were drawn on.
  function strokesFile() {
    const s = savedRef.current;
    if (!s) return null;
    const data = {
      kind: "kaker-theng drawn strokes",
      exported: new Date().toISOString(),
      fingerprint: s.fingerprint,
      template_version: layout?.template_version,
      pen_mm: layout?.pen_mm,
      session,
      screen: { width: innerWidth, height: innerHeight, dpr: devicePixelRatio },
      browser: navigator.userAgent,
      at: s.at,
      draft: s.draft ?? null,
      cells: s.cells, // cell id -> strokes: [[x, y], ...] in mm inside the cell box
    };
    const day = data.exported.slice(0, 10);
    return { blob: new Blob([JSON.stringify(data)], { type: "application/json" }), name: `kaker-theng-strokes-${day}.json`, title: "Kaker Theng strokes" };
  }

  function redraw(id: string) {
    setAt(id);
    go({ name: "draw" });
  }

  // ---- Paper ---------------------------------------------------------------

  const sessionProgress = (page: number) => (p: ProgressState) => setSlot(page, { kind: "busy", step: p.waking ? "waking" : "sending" });

  async function onPhoto(page: number, file: File) {
    setNotes((n) => ({ ...n, [page]: null }));
    setSlot(page, { kind: "busy", step: "shrinking" });
    try {
      const photo = await shrinkPhoto(file);
      setSlot(page, { kind: "busy", step: "sending" });
      const progress = (p: ProgressState) =>
        setSlot(page, {
          kind: "busy",
          step: p.waking ? "waking" : p.working ? "reading" : p.ahead ? "queued" : "reading",
          ahead: p.ahead,
          eta: p.eta,
        });
      let result;
      try {
        result = await uploadPage(await ensureSession(sessionProgress(page)), photo, progress);
      } catch (err) {
        if (!(err instanceof ApiError && err.code === "session_gone")) throw err;
        // The server forgot us (an hour passed, or it restarted): start over.
        // Drawn letters are kept in the browser and go to the new session.
        forgetSession();
        setNotes((n) => ({ ...n, [page]: { bn: "আগের সেশন শেষ হয়ে গিয়েছিল, নতুন করে শুরু করলাম। অন্য পাতাগুলো আবার দিন।", en: "The earlier session had expired, so this starts a new one. Please add your other pages again." } }));
        result = await uploadPage(await ensureSession(sessionProgress(page)), photo, progress);
        for (const id of Object.keys(savedRef.current?.cells ?? {})) unsynced.current.add(id);
        void rebuildPreview();
      }
      setMeta(result.session);
      setSlot(page, { kind: "idle" });
      if (result.page !== page) {
        setSlot(result.page, { kind: "idle" });
        setNotes((n) => ({
          ...n,
          [page]: { bn: `এটা পাতা ${bnNum(result.page)}-এর ছবি, ওখানেই রাখলাম।`, en: `That was a photo of page ${result.page}, so it went there.` },
        }));
      }
    } catch (err) {
      const e = err instanceof ApiError ? err : new ApiError("error", "That photo couldn't be read. Please try another.", "ছবিটা পড়া গেল না। আরেকটা ছবি দিয়ে দেখুন।");
      setSlot(page, { kind: "error", bn: e.bn, en: e.message, code: e.code });
    }
  }

  // ---- Render ----------------------------------------------------------------

  const ready = Boolean(layout && cells && lists && saved);
  const words = meta?.font ? (meta.word_coverage ?? 0) : null;
  const note = syncNote ? t(syncNote.bn, syncNote.en) : null;
  const allIds = lists ? CHAPTERS.flatMap((c) => lists[c.id]) : [];
  const progress = ready ? { drawn: allIds.filter(done).length, total: allIds.length } : null;
  const returning = Boolean(progress?.drawn) || Boolean(meta?.font);
  let body: React.ReactNode;

  if (screen.name === "start") {
    body = (
      <StartScreen
        userFont={userFont}
        progress={returning ? progress : null}
        onDraw={startDrawing}
        onPaper={() => go({ name: "paper", step: "print" })}
        onFont={returning ? openFont : undefined}
      />
    );
  } else if (screen.name === "paper") {
    body = (
      <PaperScreen
        step={screen.step}
        layout={layout}
        session={session}
        pages={meta?.pages ?? {}}
        slots={slots}
        notes={notes}
        onPhoto={onPhoto}
        onStep={(step) => go({ name: "paper", step })}
        onBack={back}
        onFont={openFont}
      />
    );
  } else if (!ready) {
    body = (
      <div className="screen">
        <TopBar />
        <p>{t("খাতা খুলছি…", "opening the notebook…")}</p>
      </div>
    );
  } else if (screen.name === "chapters") {
    const at = saved!.at && cells!.has(saved!.at) ? saved!.at : null;
    body = (
      <ChapterList
        lists={lists!}
        done={done}
        progress={progress!}
        current={at ? chapterIn(lists!, at) : null}
        onChapter={openChapter}
        onBack={back}
        onPaper={() => go({ name: "paper", step: "print" })}
        onFont={openFont}
      />
    );
  } else if (screen.name === "card") {
    const c = chapterById(screen.chapter);
    const ids = lists![c.id];
    body = (
      <ChapterCard
        chapter={c}
        example={cells!.get(ids[0])!}
        count={ids.length}
        onStart={() => startChapter(c.id)}
        onSkip={() => {
          const next = nextChapter(c.id);
          if (next) go({ name: "card", chapter: next.id }, true);
          else go({ name: "font" }, true);
        }}
        onChapters={() => go({ name: "chapters" })}
        onFont={openFont}
      />
    );
  } else if (screen.name === "reward") {
    const c = chapterById(screen.chapter);
    const ids = lists![c.id];
    const next = nextChapter(c.id);
    body = (
      <RewardScreen
        chapter={c}
        next={next}
        drawn={ids.filter(done).length}
        total={ids.length}
        progress={progress!}
        words={words}
        writable={meta?.font ? (meta.words ?? []) : []}
        building={building}
        userFont={userFont}
        note={note}
        onContinue={() => next && openChapter(next.id)}
        onSkipped={() => openChapter(c.id)}
        onFont={openFont}
      />
    );
  } else if (screen.name === "font") {
    body = <FontScreen session={session} meta={meta} lists={lists!} cells={cells!} userFont={userFont} building={building} onBack={back} onRedraw={redraw} strokesFile={strokesFile} />;
  } else {
    // Drawing: the letter saved as "at", or the first one not drawn yet.
    const at = saved!.at && cells!.has(saved!.at) ? saved!.at : (layout!.draw_order.find((id) => !done(id)) ?? layout!.draw_order[0]);
    const chapter = chapterIn(lists!, at);
    body = (
      <DrawScreen
        key={chapter}
        chapter={chapter}
        order={lists![chapter]}
        cells={cells!}
        at={at}
        drawn={saved!.cells}
        done={done}
        penMm={layout!.pen_mm}
        draft={saved!.draft ?? null}
        syncNote={note}
        onDraft={(draft) => {
          if (JSON.stringify(draft) !== JSON.stringify(savedRef.current?.draft ?? null)) updateSaved((s) => ({ ...s, draft }));
        }}
        onSave={onDrawn}
        onAt={setAt}
        onChapterEnd={() => {
          void rebuildPreview();
          go({ name: "reward", chapter });
        }}
        onActivity={scheduleRebuild}
        onChapters={() => go({ name: "chapters" })}
        onFont={openFont}
      />
    );
  }

  // Every screen but the start has the name in its top bar, back to the start.
  return (
    <HomeContext.Provider value={screen.name === "start" ? null : home}>
      <main className={`sheet${screen.name === "draw" ? " fit" : ""}`}>{body}</main>
    </HomeContext.Provider>
  );
}
