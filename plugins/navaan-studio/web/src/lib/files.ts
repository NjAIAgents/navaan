export const MAX_AUDIO_BYTES = 22 * 1024 * 1024;   // the server refuses more (suno_import.MAX_UPLOAD)

/** The file as base64 (the part after "data:...;base64,"), the form the upload routes take. */
export function fileB64(f: File): Promise<string> {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(String(r.result).split(",", 2)[1] ?? "");
    r.onerror = () => rej(new Error("The file could not be read."));
    r.readAsDataURL(f);
  });
}
