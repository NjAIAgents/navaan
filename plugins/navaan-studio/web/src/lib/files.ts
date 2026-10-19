import { token } from "./api";

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

export const MAX_VIDEO_BYTES = 2048 * 1024 * 1024;   // the server refuses more (reel.max_upload_mb)

/** Send the footage of a reel as the raw request body (no base64, so a large phone video fits); onProgress gets bytes sent and the total. The server shrinks it afterwards. */
export function uploadVideo(slug: string, f: File, onProgress: (done: number, total: number) => void): Promise<void> {
  return new Promise((res, rej) => {
    const x = new XMLHttpRequest();
    x.open("POST", `/api/reel/upload?slug=${encodeURIComponent(slug)}&name=${encodeURIComponent(f.name)}`);
    x.setRequestHeader("X-Navaan-Token", token());
    x.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded, e.total); };
    x.onload = () => {
      if (x.status === 200) return res();
      let m = `The upload failed (${x.status}).`;
      try { m = (JSON.parse(x.responseText) as { error?: string }).error ?? m; } catch { /* not JSON: a proxy's error page */ }
      rej(new Error(m));
    };
    x.onerror = () => rej(new Error("The upload was interrupted. Check the connection and try again."));
    x.send(f);
  });
}
