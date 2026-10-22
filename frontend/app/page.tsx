"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Coverage } from "@/components/Coverage";
import { Download } from "@/components/Download";
import { FragmentExamples } from "@/components/FragmentExamples";
import { Masthead } from "@/components/Masthead";
import { PrintSection } from "@/components/PrintSection";
import { Specimen } from "@/components/Specimen";
import { TryIt } from "@/components/TryIt";
import { type SlotState, UploadSlot } from "@/components/UploadSlot";
import { ApiError, createSession, fileUrl, getSession, type SessionMeta, uploadPage, wake } from "@/lib/api";
import { bnNum } from "@/lib/bn";
import { shrinkPhoto } from "@/lib/image";
import { type Layout, loadLayout } from "@/lib/layout";

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

  useEffect(() => {
    wake();
    loadLayout().then(setLayout).catch(() => undefined);
    const saved = recall();
    if (saved) {
      getSession(saved)
        .then((m) => {
          if (m) {
            sessionRef.current = saved;
            setSession(saved);
            setMeta(m);
          } else remember(null);
        })
        .catch(() => undefined);
    }
  }, []);

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

  async function ensureSession(page: number): Promise<string> {
    if (sessionRef.current) return sessionRef.current;
    const id = await createSession((p) => setSlot(page, { kind: "busy", step: p.waking ? "waking" : "sending" }));
    sessionRef.current = id;
    setSession(id);
    remember(id);
    return id;
  }

  async function onPhoto(page: number, file: File) {
    setNotes((n) => ({ ...n, [page]: null }));
    setSlot(page, { kind: "busy", step: "shrinking" });
    try {
      const photo = await shrinkPhoto(file);
      setSlot(page, { kind: "busy", step: "sending" });
      const progress = (p: { waking: boolean; ahead?: number; working?: boolean }) =>
        setSlot(page, {
          kind: "busy",
          step: p.waking ? "waking" : p.working ? "reading" : p.ahead ? "queued" : "reading",
          ahead: p.ahead,
        });
      let result;
      try {
        result = await uploadPage(await ensureSession(page), photo, progress);
      } catch (err) {
        if (!(err instanceof ApiError && err.code === "session_gone")) throw err;
        // The server forgot us (an hour passed, or it restarted): start over.
        sessionRef.current = null;
        setMeta(null);
        setUserFont(null);
        setNotes((n) => ({ ...n, [page]: { bn: "আগের সেশন শেষ হয়ে গিয়েছিল, নতুন করে শুরু করলাম। অন্য পাতাগুলো আবার দিন।", en: "The earlier session had expired, so this starts a new one. Please add your other pages again." } }));
        result = await uploadPage(await ensureSession(page), photo, progress);
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

  return (
    <main className="sheet">
      <Masthead userFont={userFont} />
      <PrintSection layout={layout} />

      <section className="section" aria-labelledby="write-title">
        <div className="section-head">
          <span className="section-no">২ / 2</span>
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
      </section>

      <section className="section" aria-labelledby="try-title">
        <div className="section-head">
          <span className="section-no">৩ / 3</span>
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
