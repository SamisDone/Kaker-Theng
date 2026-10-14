// Shrink a phone photo before upload: long side ~2500 px, JPEG 0.85. Keeps
// uploads quick on mobile data and the small server's memory low.

const LONG_SIDE = 2500;
const QUALITY = 0.85;

export async function shrinkPhoto(file: File): Promise<Blob> {
  // Respect the camera's EXIF orientation.
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  const scale = Math.min(1, LONG_SIDE / Math.max(bitmap.width, bitmap.height));
  const w = Math.round(bitmap.width * scale);
  const h = Math.round(bitmap.height * scale);
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("no canvas");
  ctx.drawImage(bitmap, 0, 0, w, h);
  bitmap.close();
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", QUALITY));
  if (!blob) throw new Error("could not encode photo");
  return blob;
}
