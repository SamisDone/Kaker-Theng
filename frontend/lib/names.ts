// Plain names for the parts of Bangla that are written next to a letter.
// The faint ghost on the canvas shows where they go.

const NAMES: Record<string, [string, string]> = {
  "া": ["আ-কার", "a-kar"],
  "ি": ["ই-কার", "i-kar"],
  "ী": ["ঈ-কার", "dirgho i-kar"],
  "ু": ["উ-কার", "u-kar"],
  "ূ": ["ঊ-কার", "dirgho u-kar"],
  "ৃ": ["ঋ-কার", "ri-kar"],
  "ে": ["এ-কার", "e-kar"],
  "ৈ": ["ঐ-কার", "oi-kar"],
  "ৗ": ["ঔ-কারের ডান অংশ", "right half of ou-kar"],
  "্": ["হসন্ত", "hasanta"],
  "ং": ["অনুস্বার", "anusvara"],
  "ঃ": ["বিসর্গ", "bisarga"],
  "ঁ": ["চন্দ্রবিন্দু", "chandrabindu"],
  "়": ["নিচের বিন্দু", "the dot below"],
  "্র": ["র-ফলা", "ra-phala"],
  "্য": ["য-ফলা", "ya-phala"],
  "র্": ["রেফ", "reph"],
};

/** What a cell with a ghost letter asks for, as [Bangla, English] names. */
export function signName(text: string, ghost: string): [string, string] | null {
  return NAMES[text.replace(ghost, "")] ?? null;
}
