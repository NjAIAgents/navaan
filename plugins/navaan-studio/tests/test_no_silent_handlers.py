"""NAV-12 (spec 002 FR-035, SC-014, constitution XVII): nothing fails silently.

A Python `except` handler must raise, exit with a message, print, reply with an error, or call the logger (navaan_log: L.exc / L.event / L.ignored);
otherwise it must carry a comment starting `expected:` that says why ignoring the error is right. The same holds for an empty JavaScript `catch` in ui.html and auth.html.
"""
import ast, os, re, unittest

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
LOGNAMES = {"L", "LOG", "log", "logging", "traceback", "logger", "_nl", "_LOG"}   # names the logger is imported under
PROPAGATES = {"print", "warn", "_fail", "die"}


def is_visible_call(n):
    if not isinstance(n, ast.Call): return False
    f = n.func
    while isinstance(f, ast.Attribute):
        if isinstance(f.value, ast.Name) and f.value.id in LOGNAMES: return True
        if f.attr == "exit" and isinstance(f.value, ast.Name) and f.value.id == "sys": return True
        if f.attr in ("_send", "write") and (getattr(f.value, "id", "") in ("self", "stderr") or getattr(f.value, "attr", "") == "stderr"): return True   # a reply to the browser logs itself; stderr is visible
        f = f.value
    return isinstance(f, ast.Name) and f.id in PROPAGATES


def silent_handlers(path):
    with open(path, encoding="utf-8") as fh: src = fh.read()
    lines = src.splitlines(); bad = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.ExceptHandler): continue
        seg = lines[node.lineno - 1: node.end_lineno]
        if any("expected:" in l for l in seg) or (node.lineno >= 2 and "expected:" in lines[node.lineno - 2]): continue
        if not any(isinstance(n, ast.Raise) or is_visible_call(n) for sub in node.body for n in ast.walk(sub)): bad.append(node.lineno)
    return bad


class Silent(unittest.TestCase):
    def test_python_handlers_never_swallow_an_error_silently(self):
        found = {}
        for f in sorted(os.listdir(HERE)):
            if f.endswith(".py"):
                b = silent_handlers(os.path.join(HERE, f))
                if b: found[f] = b
        self.assertEqual(found, {}, "These handlers swallow an error: log it (L.exc, L.ignored) or explain why with a comment `# expected: <reason>`")

    def test_javascript_catch_blocks_are_never_empty(self):
        bad = []
        for n in ("ui.html", "auth.html"):
            with open(os.path.join(HERE, n), encoding="utf-8") as fh: s = fh.read()
            for m in re.finditer(r"catch\s*(\(\s*\w*\s*\))?\s*\{(.*?)\}", s, re.S):
                body = m.group(2)
                if body.strip() == "" or (re.sub(r"/\*.*?\*/", "", body, flags=re.S).strip() == "" and "expected:" not in body):
                    bad.append((n, s[:m.start()].count("\n") + 1))
        self.assertEqual(bad, [], "Empty catch: report it (rep), log it (console.debug) or write /* expected: <reason> */")

    def test_the_checker_itself_catches_a_silent_handler(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "x.py")
            with open(p, "w") as fh: fh.write("def f():\n    try: 1/0\n    except ZeroDivisionError: pass\n    try: 1/0\n    except ZeroDivisionError: pass  # expected: demo\n    try: 1/0\n    except ZeroDivisionError as e: L.ignored(LOG, 'x', e)\n")
            self.assertEqual(silent_handlers(p), [3])


if __name__ == "__main__":
    unittest.main()
