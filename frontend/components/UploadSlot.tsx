"use client";

import { useId } from "react";
import { fileUrl, type PageInfo, templateUrl } from "@/lib/api";
import { bnNum, cornerBn } from "@/lib/bn";

export type SlotState =
  | { kind: "idle" }
  | { kind: "busy"; step: "shrinking" | "sending" | "queued" | "reading" | "waking"; ahead?: number }
  | { kind: "error"; bn: string; en: string; code?: string };

const STEP: Record<string, [string, string]> = {
  shrinking: ["ছবি ছোট করছি…", "resizing the photo…"],
  sending: ["ছবি পাঠাচ্ছি…", "sending the photo…"],
  reading: ["হাতের লেখা পড়ছি…", "reading your handwriting…"],
  waking: ["কাক ঘুম থেকে উঠছে…", "waking up the crow…"],
};

function statusText(s: Extract<SlotState, { kind: "busy" }>): [string, string] {
  if (s.step === "queued") {
    const n = s.ahead ?? 1;
    return [`আপনার আগে ${bnNum(n)} জন আছে`, `${n} ${n === 1 ? "person" : "people"} ahead of you`];
  }
  return STEP[s.step];
}

export function UploadSlot(props: {
  page: number;
  titleBn: string;
  titleEn: string;
  optional: boolean;
  session: string | null;
  info: PageInfo | undefined;
  state: SlotState;
  note: { bn: string; en: string } | null;
  onPhoto: (file: File) => void;
  children?: React.ReactNode;
}) {
  const id = useId();
  const { page, info, state } = props;
  const busy = state.kind === "busy";
  const bad = info?.cells.filter((c) => c.status !== "ok") ?? [];
  const missing = bad.filter((c) => c.status === "missing");
  const outside = bad.filter((c) => c.status === "touches_edge");
  const total = info?.cells.length ?? 0;

  return (
    <div className="slot">
      <div className="slot-title">
        <h3 lang="bn">
          পাতা {bnNum(page)} · {props.titleBn}
        </h3>
        <span className="en-sub" lang="en">
          page {page} · {props.titleEn}
        </span>
        {props.optional && <span className="tag">ঐচ্ছিক · optional</span>}
      </div>

      <label className="drop" htmlFor={id}>
        <span lang="bn">{info ? "আবার ছবি দিন" : "পাতার ছবি দিন"}</span>
        <span className="en-sub" lang="en">
          {info ? "replace with a new photo" : "add page photo"}
        </span>
        <input
          id={id}
          type="file"
          accept="image/*"
          capture="environment"
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) props.onPhoto(file);
          }}
        />
      </label>

      <div className="status" aria-live="polite">
        {busy && (
          <p>
            {statusText(state)[0]}
            <span className="en-sub" lang="en">
              {statusText(state)[1]}
            </span>
          </p>
        )}
      </div>

      {state.kind === "error" && (
        <p className="margin-note" role="alert">
          {state.bn}
          <span className="en-sub en" lang="en">
            {state.en}
          </span>
          {state.code === "old_template" && (
            <a href={templateUrl()} target="_blank" rel="noopener">
              নতুন টেমপ্লেট · current template
            </a>
          )}
        </p>
      )}
      {props.note && (
        <p className="margin-note">
          {props.note.bn}
          <span className="en-sub en" lang="en">
            {props.note.en}
          </span>
        </p>
      )}

      {info && props.session && (
        <div className="result">
          <img
            src={fileUrl(props.session, info.thumbnail)}
            alt={
              bad.length
                ? `পাতা ${bnNum(page)}-এর সোজা করা ছবি, লাল দাগ দেওয়া ${bnNum(bad.length)}টা ঘর পড়া যায়নি। Straightened photo of page ${page}; ${bad.length} cells circled in red couldn't be read.`
                : `পাতা ${bnNum(page)}-এর সোজা করা ছবি, সব ঘর পড়া গেছে। Straightened photo of page ${page}; every cell was read.`
            }
          />
          <div>
            <p>
              {bnNum(total)}টার মধ্যে {bnNum(total - missing.length)}টা ঘর পড়া গেছে।
              <span className="en-sub" lang="en">
                {total - missing.length} of {total} cells read.
              </span>
            </p>
            {info.missing_corners.length > 0 && (
              <p className="margin-note">
                {info.missing_corners.map(cornerBn).join(", ")} কোণের চৌকো দেখা যায়নি, তবু পড়া গেছে।
                <span className="en-sub en" lang="en">
                  Couldn't see the {info.missing_corners.join(", ")} corner, but the page was still read.
                </span>
              </p>
            )}
            {missing.length > 0 && (
              <p className="margin-note">
                খালি: {missing.map((c) => c.text).join("  ")}
                <span className="en-sub en" lang="en">
                  Empty, so these won&apos;t be in the font. Fill them in and photograph the page again.
                </span>
              </p>
            )}
            {outside.length > 0 && (
              <p className="margin-note">
                ঘরের বাইরে গেছে: {outside.map((c) => c.text).join("  ")}
                <span className="en-sub en" lang="en">
                  These ran out of their box and may be cut off.
                </span>
              </p>
            )}
          </div>
        </div>
      )}
      {props.children}
    </div>
  );
}
