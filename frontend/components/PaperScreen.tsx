"use client";

import { FragmentExamples } from "@/components/FragmentExamples";
import { Icon } from "@/components/Icons";
import { TopBar } from "@/components/TopBar";
import { type SlotState, UploadSlot } from "@/components/UploadSlot";
import { type PageInfo, templateUrl } from "@/lib/api";
import type { Fonts } from "@/lib/chapters";
import { useLang } from "@/lib/i18n";
import type { Layout } from "@/lib/layout";

export type PaperStep = "print" | "write" | 1 | 2 | 3;

// The template's pages for each font: English is page 1, Bangla pages 2 and 3.
export const PAPER_PAGES: Record<Fonts, (1 | 2 | 3)[]> = { both: [1, 2, 3], bn: [2, 3], en: [1] };

// Paper, one step per screen: print, write, then one photo per page of the
// chosen font.
export function PaperScreen(props: {
  step: PaperStep;
  fonts: Fonts;
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
  const { step, layout, fonts } = props;
  const pages = PAPER_PAGES[fonts];
  const stage = step === "print" ? 0 : step === "write" ? 1 : 2;
  // The static copy loads instantly; the backend's copy is the fallback.
  const pdf = layout ? `/kt/${layout.template_pdfs?.[fonts] ?? layout.template_pdf}` : templateUrl(fonts);
  const after = (n: number) => pages[pages.indexOf(n as 1 | 2 | 3) + 1] ?? null;
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
          <p>
            {
              {
                both: t("তিনটে A4 পাতা।", "Three A4 pages."),
                bn: t("বাংলার দুটো A4 পাতা।", "The two Bangla A4 pages."),
                en: t("ইংরেজির একটা A4 পাতা।", "The one English A4 page."),
              }[fonts]
            }{" "}
            {t("১০০% মাপে ছাপুন, রঙিন বা সাদাকালো দুটোই চলবে।", "Print at 100% (actual size), in colour or black and white.")}
          </p>
          <p>
            <a className="button big primary" href={pdf} target="_blank" rel="noopener">
              {t("টেমপ্লেট (PDF)", "Template (PDF)")}
            </a>
          </p>
          <div className="thumbs">
            {pages.map((n) => {
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
          {fonts !== "en" && (
            <p>
              {fonts === "both"
                ? t("পাতা ১ আর ২ দিলেই ফন্ট চলবে। পাতা ৩ ঐচ্ছিক: যুক্তাক্ষর আরও ভালো হয়।", "Pages 1 and 2 make a working font. Page 3 is optional: it makes conjuncts better.")
                : t("পাতা ২ দিলেই ফন্ট চলবে। পাতা ৩ ঐচ্ছিক: যুক্তাক্ষর আরও ভালো হয়।", "Page 2 makes a working font. Page 3 is optional: it makes conjuncts better.")}
            </p>
          )}
          {layout && fonts !== "en" && <FragmentExamples fragments={layout.fragments} headline={layout.headline} />}
          <p className="card-buttons">
            <button type="button" className="button big primary" onClick={() => props.onStep(pages[0])}>
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
            {after(step) ? (
              <button type="button" className={`button big${props.pages[String(step)] ? " primary" : ""}`} onClick={() => props.onStep(after(step)!)}>
                {props.pages[String(step)] ? t(`পাতা ${num(after(step)!)} →`, `Page ${after(step)} →`) : t(`এটা বাদ, পাতা ${num(after(step)!)} →`, `Skip to page ${after(step)} →`)}
              </button>
            ) : (
              <button type="button" className={`button big${props.pages[String(step)] ? " primary" : ""}`} onClick={props.onFont}>
                {props.pages[String(step)] ? t("আমার ফন্ট →", "My font →") : t("বাদ দিন, আমার ফন্ট →", "Skip, see my font →")}
              </button>
            )}
          </p>
        </>
      )}
    </div>
  );
}
