"use client";

import { Download } from "@/components/Download";
import { Icon } from "@/components/Icons";
import { Specimen } from "@/components/Specimen";
import { TopBar } from "@/components/TopBar";
import { TryIt } from "@/components/TryIt";
import type { SessionMeta } from "@/lib/api";
import { pct } from "@/lib/bn";
import type { ChapterId } from "@/lib/chapters";
import { useLang } from "@/lib/i18n";
import type { LayoutCell } from "@/lib/layout";

// The font so far: type in it, see every letter (tap one to redraw it),
// download it.
export function FontScreen(props: {
  session: string | null;
  meta: SessionMeta | null;
  lists: Record<ChapterId, string[]>;
  cells: Map<string, LayoutCell>;
  userFont: string | null;
  building: boolean;
  onBack: () => void;
  onRedraw: (id: string) => void;
}) {
  const { t, num } = useLang();
  const words = props.meta?.font ? (props.meta.word_coverage ?? 0) : null;
  return (
    <div className="screen font-screen">
      <TopBar>
        <button type="button" className="link-button" onClick={props.onBack}>
          <Icon name="back" size={18} /> {t("ফিরে যান", "Back")}
        </button>
      </TopBar>
      <h2>{t("আমার ফন্ট", "My font")}</h2>
      <p aria-live="polite">
        {props.building
          ? t("ফন্ট বানাচ্ছি…", "making your font…")
          : words !== null
            ? t(`বাংলা শব্দের ${num(pct(words))}% এখন আপনার ফন্টে লেখা যায়।`, `${pct(words)}% of Bangla words can now be written in your font.`)
            : null}
      </p>
      <TryIt userFont={props.userFont} />
      <Specimen lists={props.lists} cells={props.cells} meta={props.meta} userFont={props.userFont} onRedraw={props.onRedraw} />
      <Download session={props.session} ready={Boolean(props.meta?.font)} />
      <footer className="footer" lang="en">
        Built on Noto Sans Bengali (SIL Open Font License 1.1). Conjunct and word frequencies from Bangla Wikipedia (CC BY-SA 4.0).
      </footer>
    </div>
  );
}
