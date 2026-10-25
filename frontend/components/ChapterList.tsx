"use client";

import { Icon } from "@/components/Icons";
import { TopBar } from "@/components/TopBar";
import { CHAPTERS, type ChapterId } from "@/lib/chapters";
import { useLang } from "@/lib/i18n";

// Every chapter, to jump to any of them (English, for example).
export function ChapterList(props: {
  lists: Record<ChapterId, string[]>;
  done: (id: string) => boolean;
  progress: { drawn: number; total: number }; // every chapter
  current: ChapterId | null;
  onChapter: (c: ChapterId) => void;
  onBack: () => void;
  onPaper: () => void;
  onFont: () => void;
}) {
  const { t, num } = useLang();
  return (
    <div className="screen list-screen">
      <TopBar onFont={props.onFont}>
        <button type="button" className="link-button" onClick={props.onBack}>
          <Icon name="back" size={18} /> {t("ফিরে যান", "Back")}
        </button>
      </TopBar>
      <h2>{t("অধ্যায়", "Chapters")}</h2>
      <p className="list-progress">
        {t("মোট আঁকা", "Drawn in all")}{" "}
        <span className="mono">
          {num(props.progress.drawn)}/{num(props.progress.total)}
        </span>
      </p>
      <ol className="chapter-list">
        {CHAPTERS.map((c) => {
          const ids = props.lists[c.id];
          const n = ids.filter(props.done).length;
          return (
            <li key={c.id}>
              <button type="button" className={`chapter-row${c.id === props.current ? " current" : ""}`} onClick={() => props.onChapter(c.id)}>
                <span>
                  {t(c.name[0], c.name[1])}
                  {c.optional && <span className="tag">{t("ঐচ্ছিক", "optional")}</span>}
                </span>
                <span className="mono">
                  {num(n)}/{num(ids.length)}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
      <p>
        <button type="button" className="link-button" onClick={props.onPaper}>
          {t("কাগজে লিখে ছবি দিতে চান?", "Rather write on paper and send photos?")}
        </button>
      </p>
    </div>
  );
}
