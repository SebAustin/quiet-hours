# Demo video pipeline

Reproducible, no camera or microphone needed:

1. `npm i && npx playwright install chromium` in this folder.
2. `node record.mjs` — drives the live dashboard through the three-day demo and writes `out/raw.webm` + `out/markers.json`.
3. Edit `narration.json` if the run differed, then `python tts.py Matthew` — Amazon Polly generative voice, one MP3 per scene.
4. `python assemble.py` — slides + footage segments fitted to each narration line, concatenated, loudness-normalized → `out/quiet-hours-demo.mp4`.

Slides are HTML in `slides/`, rendered with headless Chrome. Outputs in `out/` are not committed.
