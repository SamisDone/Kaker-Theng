const DIGITS = "০১২৩৪৫৬৭৮৯";

export function bnNum(n: number | string): string {
  return String(n).replace(/[0-9]/g, (d) => DIGITS[Number(d)]);
}

export function pct(x: number): number {
  return Math.round(x * 100);
}

const CORNER_BN: Record<string, string> = {
  "top-left": "উপরে বাঁয়ের",
  "top-right": "উপরে ডানের",
  "bottom-right": "নিচে ডানের",
  "bottom-left": "নিচে বাঁয়ের",
};

export function cornerBn(c: string) {
  return CORNER_BN[c] ?? c;
}
