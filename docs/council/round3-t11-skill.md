# Video Notes Agent Skill

Generate structured, diagram-grounded notes from a video URL using the host agent as the multimodal synthesizer.

## Workflow

1. **Acquire Metadata & Captions**
   Run `yt-dlp --ignore-config --dump-json "<URL>"` to get title, duration, and chapters.
   Download English captions via `yt-dlp --ignore-config --write-auto-sub --sub-lang en --skip-download --sub-format json3 -o "transcript" "<URL>"`.
   If captions are missing, fall back to downloading audio (`yt-dlp -f ba`) and transcribing with Whisper.

2. **Analyze Transcript for Visual Moments**
   Scan the timestamped transcript. Identify moments where understanding requires visual context:
   - Deictic references ("as you see here", "this graph", "notice how this moves", "look at this diagram").
   - Mathematical formulas, code snippets, or system architecture diagrams being introduced or derived.
   - Distinct slide transitions or demonstrations.
   Note the exact timestamps ($T$) where each visual is stable and clearly displayed.

3. **Extract Targeted Keyframes**
   Do not dump uniform frames. For each identified timestamp, fetch direct stream URLs:
   `STREAM_URL=$(yt-dlp --ignore-config -f "bestvideo[height<=1080][ext=mp4]/bestvideo[height<=1080]" -g "<URL>")`
   Extract a single sharp frame using ffmpeg:
   `ffmpeg -ss <TIMESTAMP> -i "$STREAM_URL" -frames:v 1 -q:v 2 "<OUT_DIR>/frame_<TIMESTAMP>.jpg"`

4. **Inspect & Curate Frames**
   Inspect each captured image. Discard frames that are blurred by transitions or uninformative (e.g. talking head without slides). Retain only high-value visual artifacts: diagrams, plots, tables, and equations.

5. **Synthesize Inline Visual Notes**
   Write markdown notes (`notes.md`) structured by topic/chapter:
   - Integrate each selected image directly **inline** next to the specific explanation it supports: `![Diagram Description](./frame_<TIMESTAMP>.jpg)`.
   - Transcribe on-screen formulas, axis labels, and code accurately from the image.
   - Explain what the visual demonstrates in direct correlation with the speaker's arguments.
   - Provide clickable timestamp links back to the source video: `[MM:SS](<URL>&t=<SECONDS>)`.
