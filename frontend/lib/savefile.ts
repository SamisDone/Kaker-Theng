// Hand a file to the visitor: the phone's share sheet where the browser can
// share files (save to photos, send on WhatsApp...), a download otherwise.

export type Saved = "shared" | "downloaded" | "cancelled";

export async function saveFile(blob: Blob, name: string, title: string): Promise<Saved> {
  const file = new File([blob], name, { type: blob.type });
  if (navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title });
      return "shared";
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return "cancelled";
      // Share failed for another reason: fall back to a download.
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return "downloaded";
}
