// Talking to the Python backend. It may be asleep (free server): if nothing
// comes back within WAKE_AFTER_MS we say so and keep trying for up to
// GIVE_UP_MS instead of failing.

import type { Stroke } from "@/lib/strokes";

export const API_URL =(process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

const WAKE_AFTER_MS = 5_000;
const GIVE_UP_MS = 90_000;
const POLL_MS = 1_000;

export type Bilingual = { bn: string; en: string };

export class ApiError extends Error {
  code: string;
  bn: string;
  constructor(code: string, en: string, bn: string) {
    super(en);
    this.code = code;
    this.bn = bn;
  }
}

export type CellStatus = "ok" | "missing" | "touches_edge";

export type PageInfo = {
  page: number;
  cells: { id: string; text: string; glyph: string; status: CellStatus; box: number[] }[];
  missing_corners: string[];
  thumbnail: string;
};

export type SessionMeta = {
  pages: Record<string, PageInfo>;
  drawn?: Record<string, number>; // cell id -> when it was drawn
  font?: string;
  font_version: number;
  coverage?: number;
  coverage_targets?: { pages_1_2: number; all_pages: number };
};

type Job<T> = {
  id: string;
  status: "queued" | "working" | "done" | "error";
  ahead: number;
  eta_s: number | null; // estimated seconds until done; null if the server can't say
  result?: T;
  error?: { code: string; message: string; message_bn: string };
};

export type ProgressState = { waking: boolean; ahead?: number; working?: boolean; eta?: number | null };
export type Progress = (state: ProgressState) => void;

const UNREACHABLE: Bilingual = {
  bn: "সার্ভারের সাথে যোগাযোগ হচ্ছে না। একটু পরে আবার চেষ্টা করুন।",
  en: "Can't reach the server. Please try again in a little while.",
};

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

/** fetch that waits out a sleeping server: retries until GIVE_UP_MS and
 *  reports `waking` once a first answer has taken longer than WAKE_AFTER_MS. */
async function patientFetch(path: string, init: RequestInit, progress?: Progress): Promise<Response> {
  const start = Date.now();
  const timer = setTimeout(() => progress?.({ waking: true }), WAKE_AFTER_MS);
  try {
    let wait = 1_000;
    for (;;) {
      try {
        const res = await fetch(`${API_URL}${path}`, init);
        // Render answers 502/503 from its proxy while the app boots.
        if ((res.status === 502 || res.status === 504) && Date.now() - start < GIVE_UP_MS) throw new Error("booting");
        return res;
      } catch {
        if (Date.now() - start > GIVE_UP_MS) throw new ApiError("unreachable", UNREACHABLE.en, UNREACHABLE.bn);
        progress?.({ waking: Date.now() - start > WAKE_AFTER_MS });
        await sleep(wait);
        wait = Math.min(wait * 1.5, 5_000);
      }
    }
  } finally {
    clearTimeout(timer);
  }
}

async function json<T>(res: Response): Promise<T> {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(body.code ?? "error", body.message ?? res.statusText, body.message_bn ?? "কিছু একটা ঠিক হয়নি।");
  return body as T;
}

export function wake() {
  // Started on page load, so the server is up by the time a photo arrives.
  fetch(`${API_URL}/health`).catch(() => undefined);
}

export async function createSession(progress?: Progress): Promise<string> {
  const res = await patientFetch("/api/sessions", { method: "POST" }, progress);
  return (await json<{ id: string }>(res)).id;
}

export async function getSession(id: string): Promise<SessionMeta | null> {
  const res = await patientFetch(`/api/sessions/${id}`, {}, undefined);
  if (res.status === 404) return null;
  return json<SessionMeta>(res);
}

async function waitForJob<T>(job: Job<T>, progress?: Progress): Promise<T> {
  for (;;) {
    if (job.status === "done") return job.result as T;
    if (job.status === "error") throw new ApiError(job.error!.code, job.error!.message, job.error!.message_bn);
    progress?.({ waking: false, ahead: job.ahead, working: job.status === "working", eta: job.eta_s });
    await sleep(POLL_MS);
    const res = await patientFetch(`/api/jobs/${job.id}`, {}, progress);
    job = await json<Job<T>>(res);
  }
}

export async function uploadPage(session: string, photo: Blob, progress?: Progress) {
  const form = new FormData();
  form.append("photo", photo, "page.jpg");
  const res = await patientFetch(`/api/sessions/${session}/pages`, { method: "POST", body: form }, progress);
  const job = await json<Job<{ page: number; session: SessionMeta }>>(res);
  return waitForJob(job, progress);
}

export async function requestDownload(session: string, name: string, format: "ttf" | "woff2", progress?: Progress) {
  const res = await patientFetch(
    `/api/sessions/${session}/download`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, format }) },
    progress,
  );
  const job = await json<Job<{ file: string }>>(res);
  return waitForJob(job, progress);
}

/** Store drawn letters ({cell id: strokes}; [] removes one). Quick: the
 *  font is rebuilt by requestPreview. */
export async function putDrawn(session: string, cells: Record<string, Stroke[]>): Promise<SessionMeta> {
  const res = await patientFetch(
    `/api/sessions/${session}/drawn`,
    { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ cells }) },
    undefined,
  );
  return json<SessionMeta>(res);
}

/** Rebuild the preview font and coverage from everything written so far. */
export async function requestPreview(session: string, progress?: Progress): Promise<SessionMeta> {
  const res = await patientFetch(`/api/sessions/${session}/preview`, { method: "POST" }, progress);
  const job = await json<Job<{ session: SessionMeta }>>(res);
  return (await waitForJob(job, progress)).session;
}

export function fileUrl(session: string, name: string) {
  return `${API_URL}/api/sessions/${session}/files/${encodeURIComponent(name)}`;
}

export const templateUrl = () => `${API_URL}/template.pdf`;
