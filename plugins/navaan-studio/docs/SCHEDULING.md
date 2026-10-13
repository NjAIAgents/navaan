# Scheduled publishing and best time

Pick a time and the pipeline publishes then, from approvals you already gave. Scheduling never approves anything.

- Portal: song page, card "Publishing schedule", or Analytics page, "Best time to publish", click a slot, or press Implement on a timing recommendation.
- Terminal: `navaan.py schedule <slug> --at "2026-10-16 18:30"` (local time of this computer), `schedules`, `schedule-clear <slug>`, `schedule-run [--loop]`.
- Two times: Instagram Reel at the chosen time, YouTube video and Short go public 15 minutes earlier (the Reel links to the public video).
  Steps held until their time: `go_public` and `publish_instagram`. Everything before them runs as usual.
- Gates `go_public`, `instagram_caption`, `publish_instagram` must be approved. If one is missing at the time, the step waits and runs on the next check after you approve, up to 12 hours late, then the slot is marked missed.
- The portal checks every minute while it runs (a restart is needed once to load this feature). Without the portal use `schedule-run --loop` or cron. This computer must be on and online: both platforms are published through their APIs from here.
- A failed step is retried up to 3 times, 10 minutes apart.

## Best time

`besttime.py` (also the Analytics page card) combines, all in UTC and shown in your local time: hours your followers are online (weight 0.5), how your own Reels did by hour and weekday (0.3, needs 8 posts), when peers' strongest posts went out (0.2, needs 10 strong posts). Slots are the next 7 days, posted one hour before the followers' peak, at most two a day.

## Implement a recommendation

Open recommendations have an Implement button. Timing opens the schedule picker. Hashtags refreshes `hashtags.json`. Anything else is saved as a standing rule in `standing_rules.json` (next to the songs folder), which the caption, YouTube text and shot list skills apply to every new item. Reopen or dismiss the recommendation to remove its rule.
