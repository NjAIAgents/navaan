"""navaan_log.py  one structured log stream for the whole app.

Author: Navjyot Nishant
Created: 2026-10-15
Last updated: 2026-10-15
Description: JSON-lines logging for the web server, the pipeline and the browser, with ids in context, secret scrubbing and a log per run.

Why: NAV-12, spec 002 FR-034 and FR-035, constitution XVII (nothing fails silently).
Standard library only. Every record is one JSON object per line:
  ts (UTC), level, service, component, event, plus the ids in context (request_id, job_id, item, step, user) and any fields passed in.
Errors carry error.type, error.message and error.stack. Secrets, tokens, passwords, email addresses and query strings are masked before anything is written.

Where it goes
  stdout            for the container (Docker json-file now; a shipper such as Grafana Alloy or Promtail tails it later, no code change)
  <LOGDIR>/app.jsonl   rotated at midnight UTC, kept 14 days
  <LOGDIR>/runs/<job_id>.jsonl   the whole pipeline run in order, one file per run (spec FR-034), pruned after 30 days
LOGDIR is NAVAAN_LOG_DIR, else ~/.local/share/navaan/logs. Level is NAVAAN_LOG_LEVEL (default INFO).
Loki labels to use later: service, env, level, component. Keep the ids in the record body, not in labels (cardinality).

Use
  import navaan_log as L; log = L.get("publish")
  L.event(log, "info", "upload_started", file=name)
  try: ...
  except Exception: L.exc(log, "upload_failed", file=name)          # logs once, with the stack
  with L.ctx(item=slug, step=sid): ...                              # ids ride along on every record inside
A handler that deliberately ignores an error still logs it at debug:  L.ignored(log, "why", exc)
A non-fatal failure that should be seen (warning with the stack, debug if only a file is missing):  L.soft(log, "event")
"""
import os, re, sys, json, time, uuid, logging, datetime, threading, contextvars, traceback
from logging.handlers import TimedRotatingFileHandler

SERVICE = "navaan-studio"
_CTX = contextvars.ContextVar("navaan_log_ctx", default={})
_LOCK = threading.Lock()
_STATE = {"ready": False, "dir": None}

# ---- context -------------------------------------------------------------------------------------------------------------------
class ctx:
    """with L.ctx(item=slug, step=sid): every record written inside carries these ids. Nesting adds to the outer context."""
    def __init__(self, **kw): self.kw = {k: v for k, v in kw.items() if v not in (None, "")}
    def __enter__(self): self.tok = _CTX.set({**_CTX.get(), **self.kw}); return self
    def __exit__(self, *a): _CTX.reset(self.tok)

def bind(**kw):
    """Add ids to the context of the current thread until the enclosing `with L.ctx(...)` ends (used where the step is only known midway)."""
    _CTX.set({**_CTX.get(), **{k: v for k, v in kw.items() if v not in (None, "")}})

def current(key=None, default=None):
    c = _CTX.get()
    return c if key is None else c.get(key, default)

def new_request_id(incoming=None):
    """Use the proxy's X-Request-Id when it looks sane, else make one. The id goes back to the browser so a report can be traced."""
    if incoming and re.fullmatch(r"[A-Za-z0-9_-]{8,64}", incoming): return incoming
    return uuid.uuid4().hex[:16]

def new_job_id(item=""):
    return (re.sub(r"[^A-Za-z0-9_-]", "", item)[:40] or "job") + "-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:4]

# ---- scrubbing -----------------------------------------------------------------------------------------------------------------
_SECRET_KEY = re.compile(r"(pass(word|wd)?|secret|token|authorization|cookie|api[_-]?key|credential|signature|otp|recovery|private[_-]?key)", re.I)
_RULES = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"), "[email]"),
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"), r"\1 [redacted]"),
    (re.compile(r"(?i)([A-Za-z0-9_-]*(?:password|passwd|pwd|secret|token|api[_-]?key|authorization|cookie|signature)[A-Za-z0-9_-]*)(\"?\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;&}]+)"), r"\1\2[redacted]"),
    (re.compile(r"\bya29\.[A-Za-z0-9._-]+"), "[redacted]"),
    (re.compile(r"\bsk[-_][A-Za-z0-9_-]{16,}"), "[redacted]"),
    (re.compile(r"\bEAA[A-Za-z0-9]{20,}"), "[redacted]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"), "[redacted]"),
    (re.compile(r"\bhvs\.[A-Za-z0-9_-]{16,}"), "[redacted]"),
    (re.compile(r"\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]*"), "[redacted]"),   # JWT
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[redacted]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "[redacted]"),
    (re.compile(r"\b1//[\w-]{20,}"), "[redacted]"),   # Google refresh token
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "[redacted]"),
    (re.compile(r"\bbot\d{6,}:[\w-]{30,}"), "bot[redacted]"),   # Telegram bot URL
    (re.compile(r"(?<=[\w/])\?[^\s\"'<>]*"), "?[redacted]"),   # query strings: the whole run
]

def scrub_text(s, limit=4000):
    for rx, rep in _RULES: s = rx.sub(rep, s)
    return s if len(s) <= limit else s[:limit] + f"...[{len(s) - limit} more characters]"

def scrub(v, depth=0):
    if depth > 6: return "[deep]"
    if isinstance(v, str): return scrub_text(v)
    if isinstance(v, dict): return {str(k): ("[redacted]" if _SECRET_KEY.search(str(k)) else scrub(x, depth + 1)) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)): return [scrub(x, depth + 1) for x in list(v)[:200]]
    if isinstance(v, (int, float, bool)) or v is None: return v
    return scrub_text(str(v))

# ---- format and sinks ----------------------------------------------------------------------------------------------------------
def _record_dict(r):
    d = {"ts": datetime.datetime.fromtimestamp(r.created, datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
         "level": r.levelname.lower(), "service": SERVICE, "component": r.name.split(".", 1)[-1] if "." in r.name else r.name, "event": scrub_text(str(r.getMessage()), 500)}
    d.update(scrub(_CTX.get()))
    d.update(scrub(getattr(r, "fields", {}) or {}))
    if r.exc_info and r.exc_info[0]:
        et, ev, tb = r.exc_info
        d["error"] = {"type": et.__name__, "message": scrub_text(str(ev), 1000), "stack": scrub_text("".join(traceback.format_exception(et, ev, tb)), 6000)}
    d["thread"] = r.threadName
    return d

class JsonFormatter(logging.Formatter):
    def format(self, r): return json.dumps(_record_dict(r), ensure_ascii=False, default=str)

class _RunFile(logging.Handler):
    """One file per pipeline run, so a whole run reads in order. Only records that carry a job_id go here."""
    def emit(self, r):
        jid = _CTX.get().get("job_id") or (getattr(r, "fields", {}) or {}).get("job_id")
        d = _STATE.get("dir")
        if not jid or not d: return
        try:
            p = os.path.join(d, "runs"); os.makedirs(p, exist_ok=True)
            with _LOCK, open(os.path.join(p, re.sub(r"[^A-Za-z0-9_.-]", "", str(jid)) + ".jsonl"), "a", encoding="utf-8") as f: f.write(self.format(r) + "\n")
        except OSError:  # expected: disk full or a read-only volume must never take the app down; the other sinks still have the record
            pass

class _Dedupe(logging.Filter):
    """The same warning or error (same logger, event and error) is written once a minute; the next one that gets through says how many were held back."""
    def __init__(self, window=60): super().__init__(); self.window = window; self.seen = {}; self.lock = threading.Lock()
    def filter(self, r):
        if r.levelno < logging.WARNING: return True
        ei = r.exc_info[1] if r.exc_info and r.exc_info[1] is not None else None
        if r.getMessage().startswith("auth_"): return True   # every failed sign-in is an audit record, from every address
        c = _CTX.get(); f = getattr(r, "fields", {}) or {}
        key = (r.name, r.getMessage(), type(ei).__name__ if ei is not None else "", str(ei)[:200] if ei is not None else "", c.get("item"), c.get("step"), c.get("ip"), f.get("item"), f.get("step"))
        now = time.time()
        with self.lock:
            last, held = self.seen.get(key, (0, 0))
            if now - last < self.window: self.seen[key] = (last, held + 1); return False
            if held: r.fields = {**(getattr(r, "fields", {}) or {}), "suppressed": held}
            self.seen[key] = (now, 0)
            if len(self.seen) > 2000: self.seen.clear()
        return True


def logdir(): return os.environ.get("NAVAAN_LOG_DIR") or os.path.join(os.path.expanduser("~"), ".local", "share", "navaan", "logs")

def setup(stdout=True, service=None):
    """Idempotent. The server and the worker call it with stdout=True. The command line calls it with stdout=False so its own output stays readable."""
    global SERVICE
    if service: SERVICE = service
    root = logging.getLogger("navaan")
    want_stdout = stdout or os.environ.get("NAVAAN_LOG_STDOUT") == "1"
    if _STATE["ready"]:
        if want_stdout and not _STATE.get("stdout"):  # the CLI set up file-only first, then `serve` asked for stdout
            sh = logging.StreamHandler(sys.stdout); sh.setFormatter(JsonFormatter()); sh.addFilter(_Dedupe()); root.addHandler(sh); _STATE["stdout"] = True
        return root
    root.setLevel(getattr(logging, os.environ.get("NAVAAN_LOG_LEVEL", "INFO").upper(), logging.INFO)); root.propagate = False
    fmt = JsonFormatter()
    d = logdir()
    try:
        os.makedirs(d, exist_ok=True); _STATE["dir"] = d
        fh = TimedRotatingFileHandler(os.path.join(d, "app.jsonl"), when="midnight", backupCount=14, utc=True, encoding="utf-8"); fh.setFormatter(fmt); fh.addFilter(_Dedupe()); root.addHandler(fh)
        rh = _RunFile(); rh.setFormatter(fmt); root.addHandler(rh)
        _prune(os.path.join(d, "runs"), 30)
    except OSError as e:  # expected: no writable log folder (read-only image, test sandbox); stdout still works
        sys.stderr.write(f"navaan_log: no log file in {d}: {e}\n")
    if want_stdout:
        sh = logging.StreamHandler(sys.stdout); sh.setFormatter(fmt); sh.addFilter(_Dedupe()); root.addHandler(sh); _STATE["stdout"] = True
    _STATE["ready"] = True
    return root

def _prune(p, days):
    if not os.path.isdir(p): return
    cut = time.time() - days * 86400
    for n in os.listdir(p):
        f = os.path.join(p, n)
        try:
            if os.path.isfile(f) and os.path.getmtime(f) < cut: os.remove(f)
        except OSError:  # expected: another process removed it first
            pass

def reset_for_tests():
    root = logging.getLogger("navaan")
    for h in list(root.handlers): root.removeHandler(h); h.close()
    _STATE.update(ready=False, dir=None, stdout=False)

# ---- the API the rest of the app uses ------------------------------------------------------------------------------------------
def get(component):
    return logging.getLogger("navaan." + component)

_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING, "warn": logging.WARNING, "error": logging.ERROR}

def event(logger, level, name, **fields):
    logger.log(_LEVELS.get(level, logging.INFO), name, extra={"fields": fields})

def exc(logger, name, **fields):
    """Call inside an except block. Logs the active exception once, with its stack."""
    logger.error(name, exc_info=True, extra={"fields": fields})

def soft(logger, name, **fields):
    """Call inside an except block for a failure that is not fatal. Logs a warning with the stack, and only a debug record when the cause is just a missing file."""
    e = sys.exc_info()[1]
    logger.log(logging.DEBUG if isinstance(e, (FileNotFoundError, NotADirectoryError)) else logging.WARNING, name, exc_info=True, extra={"fields": fields})

def ignored(logger, why, e=None, **fields):
    """For a handler that deliberately ignores an error: say why, and keep a debug record."""
    logger.debug("ignored: " + why, exc_info=(type(e), e, e.__traceback__) if e is not None else None, extra={"fields": fields})
