"use client";

import { FragmentExamples } from "@/components/FragmentExamples";
import { Icon } from "@/components/Icons";
import { TopBar } from "@/components/TopBar";
import { type SlotState, UploadSlot } from "@/components/UploadSlot";
import { type PageInfo, templateUrl } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { Layout } from "@/lib/layout";

export type PaperStep = "print" | "write" | 1 | 2 | 3;

// Paper, one step per screen: print, write, then one photo per page.
export function PaperScreen(props: {
  step: PaperStep;
  layout: Layout | null;
  session: string | null;
  pages: Record<string, PageInfo>;
  slots: Record<number, SlotState>;
  notes: Record<number, { bn: string; en: string } | null>;
  onPhoto: (page: number, file: File) => void;
  onStep: (step: PaperStep) => void;
  onBack: () => void;
  onFont: () => void;
}) {
  const { t, num } = useLang();
  const { step, layout } = props;
  const stage = step === "print" ? 0 : step === "write" ? 1 : 2;
  // The static copy loads instantly; the backend's copy is the fallback.
  const pdf = layout ? `/kt/${layout.template_pdf}` : templateUrl();
  const STEPS: [string, string][] = [
    ["ছাপুন", "Print"],
    ["লিখুন", "Write"],
    ["ছবি তুলুন", "Photograph"],
  ];

  return (
    <div className="screen paper-screen">
      <TopBar onFont={props.onFont}>
        <button type="button" className="link-button" onClick={props.onBack}>
          <Icon name="back" size={18} /> {t("ফিরে যান", "Back")}
        </button>
      </TopBar>
      <ol className="steps">
        {STEPS.map(([bn, en], i) => (
          <li key={en} aria-current={i === stage ? "step" : undefined} className={i < stage ? "past" : undefined}>
            <span className="mono">{num(i + 1)}</span> {t(bn, en)}
          </li>
        ))}
      </ol>

      {step === "print" && (
        <>
          <h2>{t("টেমপ্লেট ছাপুন", "Print the template")}</h2>
          <p>{t("তিনটে A4 পাতা। ১০০% মাপে ছাপুন, রঙিন বা সাদাকালো দুটোই চলবে।", "Three A4 pages. Print at 100% (actual size), in colour or black and white.")}</p>
          <p>
            <a className="button big primary" href={pdf} target="_blank" rel="noopener">
              {t("টেমপ্লেট (PDF)", "Template (PDF)")}
            </a>
          </p>
          <div className="thumbs">
            {[1, 2, 3].map((n) => {
              const page = layout?.pages[n];
              return (
                <figure key={n}>
                  <a href={pdf} target="_blank" rel="noopener">
                    <img src={`/kt/template-p${n}.png`} width={128} height={181} alt={t(`টেমপ্লেটের পাতা ${num(n)}`, `Template page ${n}`)} />
                  </a>
                  <figcaption>
                    {num(n)} · {t(page?.title_bn ?? "", page?.title_en ?? "")}
                  </figcaption>
                </figure>
              );
            })}
          </div>
          <p className="card-buttons">
            <button type="button" className="button big primary" onClick={() => props.onStep("write")}>
              {t("ছাপা হয়েছে →", "Printed →")}
            </button>
          </p>
        </>
      )}

      {step === "write" && (
        <>
          <h2>{t("ঘরে ঘরে লিখুন", "Fill in the boxes")}</h2>
          <p>{t("গাঢ় কলমে, প্রতিটা ঘরের ভেতরে। চার কোণের কালো চৌকোয় কিছু লিখবেন না।", "Use a dark pen and stay inside each box. Leave the four black corner squares clear.")}</p>
          <p>{t("পাতা ১ আর ২ দিলেই ফন্ট চলবে। পাতা ৩ ঐচ্ছিক: যুক্তাক্ষর আরও ভালো হয়।", "Pages 1 and 2 make a working font. Page 3 is optional: it makes conjuncts better.")}</p>
          {layout && <FragmentExamples fragments={layout.fragments} headline={layout.headline} />}
          <p className="card-buttons">
            <button type="button" className="button big primary" onClick={() => props.onStep(1)}>
              {t("লেখা হয়েছে →", "Done writing →")}
            </button>
          </p>
        </>
      )}

      {typeof step === "number" && (
        <>
          <h2>
            {t(`পাতা ${num(step)}`, `Page ${step}`)}
            {layout && <span className="h2-sub">{t(layout.pages[step].title_bn, layout.pages[step].title_en)}</span>}
          </h2>
          <p>{t("পুরো পাতা আর চার কোণের কালো চৌকো ছবিতে রাখুন। ছবি এক ঘণ্টা পর মুছে যায়।", "Keep the whole page and its four black corner squares in the photo. Photos are deleted after an hour.")}</p>
          <UploadSlot
            page={step}
            session={props.session}
            info={props.pages[String(step)]}
            state={props.slots[step]}
            note={props.notes[step] ?? null}
            onPhoto={(f) => props.onPhoto(step, f)}
          />
          <p className="card-buttons">
            {step < 3 ? (
              <button type="button" className={`button big${props.pages[String(step)] ? " primary" : ""}`} onClick={() => props.onStep((step + 1) as PaperStep)}>
                {props.pages[String(step)] ? t(`পাতা ${num(step + 1)} →`, `Page ${step + 1} →`) : t(`এটা বাদ, পাতা ${num(step + 1)} →`, `Skip to page ${step + 1} →`)}
              </button>
            ) : (
              <button type="button" className={`button big${props.pages["3"] ? " primary" : ""}`} onClick={props.onFont}>
                {props.pages["3"] ? t("আমার ফন্ট →", "My font →") : t("বাদ দিন, আমার ফন্ট →", "Skip, see my font →")}
              </button>
            )}
          </p>
        </>
      )}
    </div>
  );
}
