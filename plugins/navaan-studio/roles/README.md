# Picture roles

The picture plan is written by three separate roles. Each is one prompt file here and each runs on the OpenAI chat model (Settings, Who writes the picture plan). Edit a file to change how that role works. Placeholders look like <<title>> and are filled in by scripts/prompt_pack.py.

- look.md: art director. The look of the film (style line, palette, overall camera style).
- story.md: story director. The emotion, the people and one scene per picture, following the whole lyrics in order.
- camera.md: camera operator. One camera move and focus point per picture.

The motion of things inside a picture (flame, steam, leaves) is a separate step, the motion-regions skill.
