// The drawing goes chapter by chapter, Bangla first. Inside a chapter the
// letters keep the backend's drawing order (most used first,
// backend/app/draworder.py). The vowel signs come after the 15 most used
// consonants, not after all of them: with them the font writes about 42%
// of Bangla words after 41 letters, where all consonants first gave 8% after
// 44 (backend/scripts/words_curve.py).

import type { Layout, LayoutCell } from "@/lib/layout";

export type ChapterId = "vowels" | "consonants" | "signs" | "more-consonants" | "phala" | "conjuncts" | "digits" | "english";

/** Which font the visitor makes: Bangla, English, or both in one (the default). */
export type Fonts = "bn" | "en" | "both";
export type Script = "bn" | "en";

const FIRST_CONSONANTS = 15;

export type Chapter = {
  id: ChapterId;
  name: [string, string]; // Bangla, English
  optional?: boolean;
  about: (n: string) => [string, string]; // n: how many letters, in the screen's digits
  sample: string; // a line to show in the user's font once the chapter is done
};

export const CHAPTERS: Chapter[] = [
  {
    id: "vowels",
    name: ["স্বরবর্ণ", "Vowels"],
    about: (n) => [
      `${n}টা স্বরবর্ণ; যেগুলো বেশি ব্যবহার হয়, সেগুলো আগে। ধূসর অক্ষরটা মাপ আর জায়গা দেখায়; তার ওপর নিজের মতো করে লিখুন।`,
      `${n} vowels, the most used first. The grey letter shows the size and the place: write over it in your own hand.`,
    ],
    sample: "অ আ ই ঈ উ ঊ ঋ এ ঐ ও ঔ",
  },
  {
    id: "consonants",
    name: ["ব্যঞ্জনবর্ণ", "Consonants"],
    about: (n) => [
      `সবচেয়ে বেশি লাগে এমন ${n}টা ব্যঞ্জনবর্ণ। মাত্রা থাকলে সেটা ওপরের রেখায় টানুন; অক্ষর বসবে নিচের রেখায়।`,
      `The ${n} most used consonants. Where a letter has a মাত্রা, draw it on the top line; the letter sits on the bottom line.`,
    ],
    sample: "ঘর বন পথ জল কলম নগর",
  },
  {
    id: "signs",
    name: ["কার-চিহ্ন", "Vowel signs"],
    about: () => [
      "কার আর অন্য চিহ্ন: এগুলো আঁকলে আপনার ফন্টে অনেক শব্দ লেখা যাবে। ধূসর ক-টা আঁকবেন না: শুধু চিহ্নটা লিখুন, দাগ-কাটা ঘরের ভেতরে।",
      "Vowel signs and other marks: with these your font writes many words. Don't draw the grey ক: write only the sign, inside the dashed box.",
    ],
    sample: "আমি বাংলায় লিখি।",
  },
  {
    id: "more-consonants",
    name: ["আরও ব্যঞ্জনবর্ণ", "More consonants"],
    about: (n) => [
      `বাকি ${n}টা ব্যঞ্জনবর্ণ। আগের মতো: মাত্রা ওপরের রেখায়, অক্ষর নিচের রেখায়।`,
      `The other ${n} consonants. As before: the মাত্রা on the top line, the letter on the bottom line.`,
    ],
    sample: "ঘর বন পথ জল কলম নগর",
  },
  {
    id: "phala",
    name: ["ফলা ও রেফ", "Phala and reph"],
    about: () => ["র-ফলা, য-ফলা আর রেফ। আগের মতো: শুধু চিহ্নটা, দাগ-কাটা ঘরে।", "Ra-phala, ya-phala and reph. As before: only the sign, in the dashed box."],
    sample: "প্রতিদিন সূর্য ওঠে।",
  },
  {
    id: "conjuncts",
    name: ["যুক্তাক্ষর", "Conjuncts"],
    optional: true,
    about: (n) => [
      `ঐচ্ছিক, ${n}টা ঘর। এগুলো ছাড়াও ফন্ট চলে; আঁকলে যুক্তাক্ষর আপনার হাতের মতো হয়। কিছু ঘরে শুধু একটা অংশ, দাগ-কাটা ঘরে।`,
      `Optional, ${n} boxes. Your font works without them; drawing them makes conjuncts look like your hand. Some ask for one part only, in the dashed box.`,
    ],
    sample: "বিদ্যালয়ের সামনে বৃষ্টি পড়ছে।",
  },
  {
    id: "digits",
    name: ["সংখ্যা", "Digits"],
    about: () => ["বাংলা সংখ্যা, ০ থেকে ৯।", "The Bangla digits, ০ to ৯."],
    sample: "২১ ফেব্রুয়ারি ১৯৫২",
  },
  {
    id: "english",
    name: ["English", "English"],
    about: (n) => [
      `ইংরেজির ${n}টা ঘর: আগে ছোট হাতের অক্ষর, ডট-রেখা পর্যন্ত; তারপর বড় হাতের, সংখ্যা আর চিহ্ন, ওপরের রেখা পর্যন্ত।`,
      `${n} boxes: lowercase first, up to the dotted line; then capitals, digits and punctuation, up to the top line.`,
    ],
    sample: "The quick brown fox jumps over the lazy dog.",
  },
];

// A Bangla-only font still needs the comma, question mark and quotes Bangla
// text uses (it has none of its own). They are English cells; for a Bangla
// font they are drawn at the end of the digits chapter.
export const BANGLA_TEXT_MARKS = [",", "?", "!", "'", '"'];

const BANGLA_DIGITS_AND_MARKS: Chapter = {
  ...CHAPTERS.find((c) => c.id === "digits")!,
  name: ["সংখ্যা ও চিহ্ন", "Digits and marks"],
  about: () => [
    "বাংলা সংখ্যা, ০ থেকে ৯; তারপর বাংলা লেখায় লাগে এমন কয়েকটা চিহ্ন: কমা, প্রশ্নবোধক, বিস্ময়বোধক আর উদ্ধৃতি।",
    "The Bangla digits, ০ to ৯; then a few marks Bangla text uses: comma, question mark, exclamation mark and quotes.",
  ],
};

/** The language a chapter's letters are. */
export const scriptOf = (id: ChapterId): Script => (id === "english" ? "en" : "bn");

/** The chapters of this font, in order. */
export function chaptersFor(fonts: Fonts): Chapter[] {
  if (fonts === "en") return CHAPTERS.filter((c) => c.id === "english");
  if (fonts === "bn") return CHAPTERS.filter((c) => c.id !== "english").map((c) => (c.id === "digits" ? BANGLA_DIGITS_AND_MARKS : c));
  return CHAPTERS;
}

export const chapterById = (id: ChapterId, fonts: Fonts = "both") => chaptersFor(fonts).find((c) => c.id === id) ?? CHAPTERS.find((c) => c.id === id)!;

/** The languages of a choice. */
export const scriptsOf = (fonts: Fonts): Script[] => (fonts === "both" ? ["bn", "en"] : [fonts]);

function chapterOf(cell: LayoutCell): ChapterId {
  if (cell.kind === "latin") return "english";
  if (cell.id.startsWith("p3-")) return "conjuncts";
  switch (cell.group) {
    case "vowel":
      return "vowels";
    case "consonant":
      return "consonants";
    case "digit":
      return "digits";
    case "phala":
      return "phala";
    case "other": // ৎ is a letter; কং and কঃ are signs on a ghost ক
      return cell.ghost ? "signs" : "consonants";
    case "tall": // tall boxes: signs, reph, and the digits ৮ ৯
      if (!cell.ghost) return "digits";
      return cell.text.startsWith("র্") ? "phala" : "signs";
    default: // "sign", "nukta"
      return "signs";
  }
}

/** Cell ids per chapter, most useful first. For a Bangla-only font the
 *  digits chapter ends with the marks Bangla text uses (BANGLA_TEXT_MARKS). */
export function chapterLists(layout: Layout, cells: Map<string, LayoutCell>, fonts: Fonts = "both"): Record<ChapterId, string[]> {
  const out = Object.fromEntries(CHAPTERS.map((c) => [c.id, [] as string[]])) as Record<ChapterId, string[]>;
  for (const id of layout.draw_order) out[chapterOf(cells.get(id)!)].push(id);
  out["more-consonants"] = out.consonants.slice(FIRST_CONSONANTS);
  out.consonants = out.consonants.slice(0, FIRST_CONSONANTS);
  if (fonts === "bn") {
    const marks = BANGLA_TEXT_MARKS.map((m) => out.english.find((id) => cells.get(id)!.text === m)).filter((id): id is string => Boolean(id));
    out.digits = [...out.digits, ...marks];
  }
  return out;
}

/** The chapter a cell is drawn in, among these chapters (all, by default). */
export function chapterIn(lists: Record<ChapterId, string[]>, id: string, chapters: Chapter[] = CHAPTERS): ChapterId {
  return chapters.find((c) => lists[c.id].includes(id))?.id ?? chapters[0].id;
}

/** The languages these written cells have letters of: an English comma or
 *  quotes drawn for Bangla text don't count as English (fontbuild.has_script). */
export function scriptsWritten(ids: Iterable<string>, cells: Map<string, LayoutCell>): Script[] {
  let bn = false;
  let en = false;
  for (const id of ids) {
    const cell = cells.get(id);
    if (!cell) continue;
    if (cell.kind !== "latin") bn = true;
    else if (!BANGLA_TEXT_MARKS.includes(cell.text)) en = true;
  }
  return [...(bn ? (["bn"] as const) : []), ...(en ? (["en"] as const) : [])];
}
