# Visuals: your own pictures (default) or Flow

Every music item starts with a choice, shown in the portal as a card on the song page (gate `visuals_mode`):

1. My pictures, one cover picture: the picture is held for the whole song. Needs 1 picture.
2. My pictures, video: needs at least 4 pictures. Optional camera style and scene prompts override the director's defaults.
3. Google Flow clips: the older path, spends credits (`credits` gate), unchanged.

Own pictures live in `songs/<slug>/images/` and the choice in `songs/<slug>/visuals.json`
(`mode`, `layout`, `images`, `camera`, `scene`). From a terminal: `visuals_cfg.py <slug> --mode own --layout video`.

## Steps for "my pictures, video"

- `shots`: the `director-shots` skill reads the lyrics and the pictures and writes `shots.json` (one shot per lyric section, long sections split, each with picture, camera move, focus, scene note and times). Times come from `caption_cues.json` when present, otherwise they are estimated from line counts, so check them.
- Gate `shots` (human only): read and edit the list in the portal (picture, camera move, times, note), then Save and approve. The approval is tied to the file hash, so a later edit needs a new approval.
- `video`: `shots_render.py` renders locally with Remotion (`Shots` composition, cross fades, slow camera moves, fade out), 1920x1080 at 24 fps, plus `cover_16x9.png`, `cover_1x1.png`, `thumb_16x9.jpg`, then `tag_mp3.py`. Allow about 10 minutes for a 4 minute song. No credits.
- Camera moves: push_in, pull_out, pan_left, pan_right, tilt_up, tilt_down, drift, hold.

The static layout skips `shots` and renders with ffmpeg. Songs that already have clips or a rendered video are treated as Flow songs and are not asked.
Shorts and Reels are cut afterwards as before (YouTube Studio Clips, `clip_reel.py` with `bg_image`).
