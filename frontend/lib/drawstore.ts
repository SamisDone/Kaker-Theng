// Drawn letters kept in this browser, so closing the tab loses nothing. The
// server keeps a copy for an hour; this one is what we send again when the
// server has forgotten us. Storage can be missing or full (private mode):
// every access is wrapped, and drawing still works without it.

import type { Stroke } from "@/lib/strokes";

const KEY = "kaker-theng-drawn-v1";

export type Saved = {
  fingerprint: string; // the template layout these cell ids belong to
  cells: Record<string, Stroke[]>;
  at: string | null; // the cell on screen
  draft?: { id: string; strokes: Stroke[] } | null; // its strokes before "next"
};

export function loadDrawn(fingerprint: string): Saved {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const saved = JSON.parse(raw) as Saved;
      if (saved.fingerprint === fingerprint && saved.cells) return saved;
    }
  } catch {
    // unreadable or blocked: start empty
  }
  return { fingerprint, cells: {}, at: null };
}

export function saveDrawn(saved: Saved): boolean {
  try {
    localStorage.setItem(KEY, JSON.stringify(saved));
    return true;
  } catch {
    return false;
  }
}
