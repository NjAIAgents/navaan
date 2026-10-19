// Anonymous visit counts of the public site (NAV-33): a page view, a play with the seconds listened, a click on the account pitch.
// No cookie and nothing stored in the browser: the server counts unique visitors with a hash it forgets every day.
// Where the visit came from is read once, when the site is opened: our own ?src= tag on a link, else the referring site.
const landing = (() => { try { return { src: new URLSearchParams(window.location.search).get("src") ?? "", ref: document.referrer }; } catch { return { src: "", ref: "" }; } })();   // expected: no window in a test runner
let counting = false;

/** On for listeners only: the studio (the owner) is never counted. */
export const setCounting = (on: boolean) => { counting = on; };

export function hit(kind: "view" | "play" | "pitch", slug?: string | null, seconds = 0, closing = false) {
  if (!counting) return;
  const body = JSON.stringify({ kind, ...(slug ? { slug } : {}), ...(seconds ? { seconds: Math.round(seconds) } : {}), ...(landing.src ? { src: landing.src } : {}), ...(landing.ref ? { ref: landing.ref } : {}) });
  // keepalive only while the page is closing (the last play): otherwise a plain request, which the browser can see finish
  fetch("/api/site/hit", { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: closing, credentials: "same-origin" }).then((r) => r.text()).catch(() => undefined);   // the answer is read so the request finishes (an unread body keeps it open)   // expected: a lost count never bothers the listener
}
