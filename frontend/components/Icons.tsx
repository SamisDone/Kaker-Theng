// Line icons for the small drawing buttons: ink, square ends, like a ruled
// pen line. Each button that uses one has its own label for screen readers.

const PATHS = {
  back: "M19 12H5M11 6l-6 6 6 6",
  skip: "M3 12h13M10 6l6 6-6 6M20 5v14",
  clear: "M6 6l12 12M18 6L6 18",
  undo: "M9 14L4 9l5-5M4 9h10.5a5.5 5.5 0 0 1 0 11H11",
  down: "M7 10l5 5 5-5",
} as const;

export function Icon({ name, size = 22 }: { name: keyof typeof PATHS; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={PATHS[name]} fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="square" strokeLinejoin="miter" />
    </svg>
  );
}
