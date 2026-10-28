"use client";

import { Icon } from "@/components/Icons";
import { TopBar } from "@/components/TopBar";
import type { Chapter, ChapterId, Script } from "@/lib/chapters";
import { useLang } from "@/lib/i18n";

// Every chapter of the chosen font, to jump to any of them; and, for one
// language, a way to add the other.
export function ChapterList(props: {
  chapters: Chapter[];
  other: Script | null; // the language not chosen (yet); null with both
  onAdd: (script: Script) => void;
  lists: Record<ChapterId, string[]>;
  done: (id: string) => boolean;
  progress: { drawn: number; total: number }; // every chapter shown
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
        {props.chapters.map((c) => {
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
      {props.other && (
        <p>
          <button type="button" className="button" onClick={() => props.onAdd(props.other!)}>
            {props.other === "en" ? t("ইংরেজিও আঁকুন", "Add English") : t("বাংলাও আঁকুন", "Add Bangla")}
          </button>
        </p>
      )}
      <p>
        <button type="button" className="link-button" onClick={props.onPaper}>
          {t("কাগজে লিখে ছবি দিতে চান?", "Rather write on paper and send photos?")}
        </button>
      </p>
    </div>
  );
}
