// The logo: ক drawn as a crow's leg standing on a line, a red dot at its
// foot. The same strokes as public/mark.svg, for the inline mark (start
// screen, top bar) and the share card's canvas.

export const MARK_VIEWBOX = [300, 500, 780, 920] as const; // x, y, width, height
export const MARK_STROKE = 22; // at full size; heavier when small (markStroke)
export const MARK_DOT = { cx: 684, cy: 1240, r: 24 };
export const MARK_PATHS = [
  "M362 652 L945 566",
  "M652 622 C655 760 660 930 664 1078",
  "M644 628 L368 846 L648 1062",
  "M652 626 C720 610 790 630 797 700 C803 770 760 822 712 826 C676 829 672 780 684 752 C700 718 760 712 784 760 C796 784 790 808 780 820",
  "M664 1080 L546 1218",
  "M664 1080 L830 1194",
  "M664 1080 L683 1226",
  "M386 1352 C440 1300 560 1296 700 1296 C840 1296 930 1262 1016 1206",
];

/** Stroke width in mark units for a mark `height` px tall: the drawn
 *  weight, but never thinner on screen than `minPx` (a hairline at 20 px
 *  would vanish). The dot grows with the stroke. */
export function markStroke(height: number, minPx = 1.4): { stroke: number; dot: number } {
  const stroke = Math.max(MARK_STROKE, (minPx * MARK_VIEWBOX[3]) / height);
  return { stroke, dot: (MARK_DOT.r * stroke) / MARK_STROKE };
}
