// What happened to the visitor's own font on this page (fetched from the
// server, loaded into the browser), for the save report. The last few
// lines only.

export const fontLog: string[] = [];

export function logFont(line: string) {
  fontLog.push(`${new Date().toISOString().slice(11, 19)} ${line}`);
  if (fontLog.length > 8) fontLog.shift();
}
