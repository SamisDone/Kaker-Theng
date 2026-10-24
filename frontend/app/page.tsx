"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Coverage } from "@/components/Coverage";
import { Download } from "@/components/Download";
import { DrawPad } from "@/components/DrawPad";
import { FragmentExamples } from "@/components/FragmentExamples";
import { Masthead } from "@/components/Masthead";
import { ModeChoice } from "@/components/ModeChoice";
import { PrintSection } from "@/components/PrintSection";
import { Specimen } from "@/components/Specimen";
import { TryIt } from "@/components/TryIt";
import { type SlotState, UploadSlot } from "@/components/UploadSlot";
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
import { loadDrawn, loadMode, type Mode, type Saved, saveDrawn, saveMode } from "@/lib/drawstore";
import { shrinkPhoto } from "@/lib/image";
import { cellsById, type Layout, loadLayout } from "@/lib/layout";
import type { Stroke } from "@/lib/strokes";

const SESSION_KEY = "kaker-theng-session";

function remember(id: string | null) {
  try {
    if (id) sessionStorage.setItem(SESSION_KEY, id);
    else sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // private mode etc.: the session just won't survive a reload
  }
}

function recall(): string | null {
  try {
    return sessionStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

type Note = { bn: string; en: string } | null;

export default function Home() {
  const [layout, setLayout] = useState<Layout | null>(null);
  const [session, setSession] = useState<string | null>(null);
  const [meta, setMeta] = useState<SessionMeta | null>(null);
  const [userFont, setUserFont] = useState<string | null>(null);
  const [slots, setSlots] = useState<Record<number, SlotState>>({ 1: { kind: "idle" }, 2: { kind: "idle" }, 3: { kind: "idle" } });
  const [notes, setNotes] = useState<Record<number, Note>>({});
  const sessionRef = useRef<string | null>(null);

  // Drawing: the letters live in this browser (saved), the server gets a copy.
  const [mode, setMode] = useState<Mode | null>(null);
  const [saved, setSaved] = useState<Saved | null>(null);
  const [building, setBuilding] = useState(false);
  const [syncNote, setSyncNote] = useState<string | null>(null);
  const [recalled, setRecalled] = useState(false);
  const savedRef = useRef<Saved | null>(null);
  const unsynced = useRef<Set<string>>(new Set());
  const syncing = useRef(false);
  const preview = useRef({ running: false, again: false });

  useEffect(() => {
    wake();
    setMode(loadMode());
    loadLayout().then(setLayout).catch(() => undefined);
    const id = recall();
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
      void syncDrawn();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layout, recalled]);

  const cells = useMemo(() => (layout ? cellsById(layout) : null), [layout]);
  const fromPaper = useMemo(() => {
    const out = new Set<string>();
    for (const p of Object.values(meta?.pages ?? {})) for (const c of p.cells) if (c.status !== "missing") out.add(c.id);
    return out;
  }, [meta]);

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
  // us), then ask for a new preview font.
  async function syncDrawn() {
    if (syncing.current) return;
    syncing.current = true;
    try {
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
          setSyncNote("সার্ভারে পাঠানো গেল না। অক্ষরগুলো এখানে রাখা আছে, পরেরটার সাথে আবার পাঠাব। · Couldn't reach the server. Your letters are kept here and go with the next one.");
          return;
        }
      }
    } finally {
      syncing.current = false;
    }
    void rebuildPreview();
  }

  // One preview build at a time; letters drawn meanwhile get one more after.
  async function rebuildPreview() {
    if (!sessionRef.current) return;
    if (preview.current.running) {
      preview.current.again = true;
      return;
    }
    preview.current.running = true;
    setBuilding(true);
    try {
      do {
        preview.current.again = false;
        setMeta(await requestPreview(sessionRef.current!));
      } while (preview.current.again && sessionRef.current);
    } catch (err) {
      if (err instanceof ApiError && err.code === "session_gone") {
        forgetSession();
        for (const id of Object.keys(savedRef.current?.cells ?? {})) unsynced.current.add(id);
        preview.current.running = false;
        setBuilding(false);
        void syncDrawn();
        return;
      }
    } finally {
      preview.current.running = false;
      setBuilding(false);
    }
  }

  function updateSaved(change: (s: Saved) => Saved) {
    if (!savedRef.current) return;
    const next = change(savedRef.current);
    savedRef.current = next;
    setSaved(next);
    if (!saveDrawn(next)) setSyncNote("এই ব্রাউজারে আঁকা জমানো যাচ্ছে না; ট্যাব বন্ধ করলে হারাবে। · This browser won't store the drawing; it's lost if you close the tab.");
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
  }

  function chooseMode(m: Mode) {
    setMode(m);
    saveMode(m);
  }

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
        void syncDrawn();
      }
      setMeta(result.session);
      setSlot(page, { kind: "idle" });
      if (result.page !== page) {
        setSlot(result.page, { kind: "idle" });
        setNotes((n) => ({
          ...n,
          [page]: {
            bn: `এটা পাতা ${bnNum(result.page)}-এর ছবি, ওখানেই রাখলাম।`,
            en: `That was a photo of page ${result.page}, so it went there.`,
          },
        }));
      }
    } catch (err) {
      const e =
        err instanceof ApiError
          ? err
          : new ApiError("error", "That photo couldn't be read. Please try another.", "ছবিটা পড়া গেল না। আরেকটা ছবি দিয়ে দেখুন।");
      setSlot(page, { kind: "error", bn: e.bn, en: e.message, code: e.code });
    }
  }

  const targets = meta?.coverage_targets ?? layout?.coverage_targets ?? null;

  const lastNo = mode === "draw" ? 3 : mode === "paper" ? 4 : 2;

  return (
    <main className="sheet">
      <Masthead userFont={userFont} />

      <section className="section" aria-labelledby="mode-title">
        <div className="section-head">
          <span className="section-no">১ / 1</span>
          <h2 id="mode-title">
            কীভাবে লিখবেন?
            <span className="en-sub" lang="en">
              How do you want to write?
            </span>
          </h2>
        </div>
        <ModeChoice mode={mode} onMode={chooseMode} />
      </section>

      {mode === "draw" && (
        <section className="section" aria-labelledby="draw-title">
          <div className="section-head">
            <span className="section-no">২ / 2</span>
            <h2 id="draw-title">
              আঁকুন
              <span className="en-sub" lang="en">
                Draw your letters
              </span>
            </h2>
          </div>
          {layout && cells && saved ? (
            <DrawPad
              layout={layout}
              cells={cells}
              drawn={saved.cells}
              at={saved.at}
              fromPaper={fromPaper}
              coverage={meta?.font ? (meta.coverage ?? 0) : null}
              building={building}
              userFont={userFont}
              syncNote={syncNote}
              draft={saved.draft ?? null}
              onDraft={(draft) => {
                if (JSON.stringify(draft) !== JSON.stringify(savedRef.current?.draft ?? null)) updateSaved((s) => ({ ...s, draft }));
              }}
              onSave={onDrawn}
              onAt={(id) => updateSaved((s) => ({ ...s, at: id }))}
            />
          ) : (
            <p>
              খাতা খুলছি…
              <span className="en-sub" lang="en">
                opening the notebook…
              </span>
            </p>
          )}
        </section>
      )}

      {mode === "paper" && <PrintSection layout={layout} number={2} />}

      {mode === "paper" && (
      <section className="section" aria-labelledby="write-title">
        <div className="section-head">
          <span className="section-no">৩ / 3</span>
          <h2 id="write-title">
            লিখুন, ছবি তুলুন
            <span className="en-sub" lang="en">
              Write and photograph each page
            </span>
          </h2>
        </div>
        <p>
          গাঢ় কলমে, ঘরের ভেতরে লিখুন। পুরো পাতা আর চার কোণের কালো চৌকো ছবিতে রাখুন।
          <span className="en-sub" lang="en">
            Write in a dark pen, inside the boxes. Keep the whole page and its four black corner squares in the photo.
          </span>
        </p>
        <p>
          ছবিগুলো এক ঘণ্টা পর মুছে যায়।
          <span className="en-sub" lang="en">
            Photos are deleted after an hour.
          </span>
        </p>
        {[1, 2, 3].map((n) => {
          const page = layout?.pages[n];
          return (
            <UploadSlot
              key={n}
              page={n}
              titleBn={page?.title_bn ?? ""}
              titleEn={page?.title_en ?? ""}
              optional={Boolean(page?.optional)}
              session={session}
              info={meta?.pages[String(n)]}
              state={slots[n]}
              note={notes[n] ?? null}
              onPhoto={(f) => onPhoto(n, f)}
            >
              {n === 3 && layout && <FragmentExamples fragments={layout.fragments} headline={layout.headline} />}
            </UploadSlot>
          );
        })}
        <Coverage meta={meta} targets={targets} />
        <p>
          কিছু ঘর খালি বা পড়া যায়নি? সেগুলো এখানেই এঁকে নিতে পারেন।
          <span className="en-sub" lang="en">
            Some boxes empty or unreadable? You can draw those here instead.
          </span>
        </p>
        <p>
          <button type="button" className="button" onClick={() => chooseMode("draw")}>
            বাকিগুলো আঁকুন <span className="en">· draw the rest</span>
          </button>
        </p>
      </section>
      )}

      <section className="section" id="download" aria-labelledby="try-title">
        <div className="section-head">
          <span className="section-no">
            {bnNum(lastNo)} / {lastNo}
          </span>
          <h2 id="try-title">
            দেখুন, নামান
            <span className="en-sub" lang="en">
              Try it and download
            </span>
          </h2>
        </div>
        <TryIt userFont={userFont} />
        {layout && <Specimen layout={layout} meta={meta} userFont={userFont} />}
        <Download session={session} ready={Boolean(meta?.font)} />
      </section>

      <footer className="footer">
        <p>
          Built on Noto Sans Bengali (SIL Open Font License 1.1). Conjunct frequencies from Bangla Wikipedia (CC BY-SA 4.0).
        </p>
      </footer>
    </main>
  );
}
