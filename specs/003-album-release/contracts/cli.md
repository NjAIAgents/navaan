# CLI contract: Album release (`navaan.py`)

The release commands are the same functions the studio routes call, so the owner can release from the terminal too. Each one prints what it did and leaves a history line. Nothing ever bypasses readiness.

```text
navaan.py album-status <album>                      readiness and per-song state (no change)
navaan.py album-release <album> --yes               release now (lists the songs first; --yes is the confirm)
navaan.py album-release <album> --at "2026-12-01 18:00" --yes   schedule, local time
navaan.py album-cancel <album>                      scheduled or missed -> draft
navaan.py album-announce <album> on|off             coming-soon page on or off
```

Exit codes:

| Code | Meaning |
|---|---|
| 0 | done |
| 2 | bad argument |
| 4 | not ready (each song's reason printed) |
| 9 | the state does not allow it (e.g. cancel on a published album) |

`publish_youtube.py go-public <slug> --only full|short --yes`: flips only that kind of item. With no `--only` it flips both, as today (kept for aha and inspiration).
