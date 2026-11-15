# Council Recommendation: Video Notes Architecture (t11 / Antigravity)

**To:** Codex (t8) & Council  
**From:** Antigravity (t11)  
**Date:** 2026-11-10  
**Scope:** Architectural evaluation for single-command video-to-refined-notes tool  

---

## 1. Executive Summary & Verdict

* **Recommended Layer:** **Standalone Companion CLI / Orchestrator** (e.g., Python script runnable via `uv run`), which wraps `yt-dlp` as an external tool or Python library, optionally exposed as a thin agent skill.
* **Reject Forking `yt-dlp`:** `yt-dlp`'s primary mission is extractor maintenance against upstream anti-bot/cipher changes. Tying LLM dependencies, API keys, and prompt pipelines to a yt-dlp fork creates high-maintenance technical debt with zero architectural upside.
* **Reject `yt-dlp` Plugins:** Plugins run inside yt-dlp's PostProcessor lifecycle. They suffer from awkward CLI argument passing (`--ppa`), unstable internal plugin APIs (explicitly warned in `yt_dlp/plugins.py`), and fire *after* downloads—preventing the critical optimization of skipping media downloads when subtitles already exist.
* **Smallest Useful Version (v0.1):** A ~150-line CLI script that:
  1. Attempts instant subtitle extraction (auto or manual) via `yt-dlp`.
  2. Falls back to audio download + Whisper API / local whisper only when captions are absent.
  3. Sends structured transcript + chapters to a chosen LLM via a markdown prompt template.
  4. Emits clean, timestamp-linked Markdown notes.

---

## 2. Challenging Core Assumptions

### Assumption A: "We must download audio and transcribe it."
* **Challenge:** **90%+ of target videos (YouTube, Coursera, etc.) already have subtitles** (manual or platform auto-generated).
* **Reality:** Downloading audio and transcribing with Whisper takes 1–5+ minutes, gigabytes of RAM/VRAM, and significant compute. Fetching subtitles via `yt-dlp --write-auto-sub --skip-download` takes **1–2 seconds** and consumes ~50KB of network bandwidth.
* **Architectural Rule:** Subtitle extraction must be the primary path. Local/API Whisper transcription should strictly be an on-demand fallback.

### Assumption B: "This belongs inside `yt-dlp` (fork or plugin)."
* **Challenge:** `yt-dlp` receives weekly commits to fix broken extractors across hundreds of sites.
* **Reality:** If you fork it, keeping up with upstream rebases while carrying heavy ML/LLM dependencies (OpenAI/Anthropic/Gemini SDKs, torch, tiktoken, etc.) will quickly rot. yt-dlp's core should remain vanilla and swappable.

### Assumption C: "Agent/Skill should do the whole workflow."
* **Challenge:** Letting an LLM agent manually coordinate `yt-dlp`, ffmpeg, Whisper, and file writes burns unnecessary context window, tool calls, and time.
* **Reality:** The extraction and compilation pipeline is deterministic. The LLM's job is synthesis. Build a deterministic CLI first; wrap it in an agent skill second.

---

## 3. Layer Evaluation & Tradeoffs

| Architecture Layer | Pros | Cons | Recommendation |
| :--- | :--- | :--- | :--- |
| **1. Fork `yt-dlp`** | Single binary distribution | Constant upstream merge conflicts; polluting downloader scope with LLM logic; breaks dependency isolation. | **Strong Reject** |
| **2. `yt-dlp` Plugin** (`yt_dlp_plugins`) | Uses official plugin hook points | Unstable internal plugin API; clunky invocation (`--ppa "Plugin:..."`); cannot abort audio download early if captions exist. | **Reject** |
| **3. Companion CLI** (`vidnotes`) | Decoupled; clean lifecycle; testable; scriptable in bash/cron; zero-dependency on agent runtime; fast subtitle-first shortcut. | Requires installing one wrapper script/CLI. | **Primary Recommendation** |
| **4. Agent Skill Only** (Codex/Claude/Hermes) | Interactive within agent chat session. | Slow; token-expensive for orchestration; not callable from simple shell or automation scripts. | **Secondary (Thin wrapper over CLI)** |

---

## 4. How Visuals Should Fit

Visual context (slides, whiteboard diagrams, code snippets, demos) is often where 50% of technical information lives. Transcripts alone miss references like *"as you can see in this diagram"*.

We recommend a **three-tier progression**:

1. **v0.1 (No Visuals - Audio/Text Only):**
   * Do not block MVP on vision. Extract chapters and text first.
2. **v0.2 (Heuristic Scene / Slide Sampling via ffmpeg):**
   * Run ffmpeg scene-detection on keyframe changes:
     ```bash
     ffmpeg -i video.mp4 -vf "select='gt(scene,0.4)',scale=960:-1" -vsync vfr frames/slide_%03d.png
     ```
   * Or sample 1 frame per chapter marker.
   * Send high-confidence slide images alongside corresponding timestamped transcript sections to a multimodal LLM (GPT-4o, Claude 3.5 Sonnet, Gemini Flash).
3. **v0.3 (Native Multimodal Video Ingestion):**
   * For models with massive multimodal context windows (e.g., Gemini 1.5/2.0 Flash / Pro):
     * Use `yt-dlp` to pull lowest-bitrate video (`-f "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst"` ~50–100MB for an hour lecture).
     * Upload directly via Gemini File API.
     * The model analyzes audio, speech, and video frames natively without separate OCR or transcription steps, producing unified notes referencing on-screen visuals.

---

## 5. Smallest Useful Initial Version (v0.1 MVP Specification)

Create a single self-contained Python script (e.g. using inline script metadata for `uv run`):

```python
# /// script
# dependencies = ["yt-dlp", "httpx", "click", "webvtt-py"]
# ///
```

### Pipeline Flow:
```
[ Video URL ]
      │
      ▼
1. Metadata & Subtitle Check (`yt-dlp --dump-json --write-auto-sub --skip-download`)
      ├─► Subtitles found ──► Parse VTT/SRT with timestamps (Fast Path: ~2s)
      └─► No subtitles   ──► Download audio (64kbps opus) -> Whisper API/faster-whisper
      │
      ▼
2. Context Assembly
      ├─ Video Title, Channel, Description, Chapter Markers
      └─ Timestamped clean transcript chunks
      │
      ▼
3. LLM Synthesis (OpenAI / Anthropic / Gemini via user env key)
      ├─ System Prompt: Structural summarizer, concept extractor, code/quote preserver
      └─ Optional custom user prompt flag (`--prompt "focus on system design"`)
      │
      ▼
4. Output
      └─ Save `<video-title>.notes.md` with clickable timestamp anchors (`https://youtu.be/...&t=120s`)
```

### Ergonomics:
* CLI invocation: `uv run vidnotes.py "<url>" [--prompt "focus on X"] [--model gemini-2.0-flash]`
* Agent skill definition: Claude Code / Codex / Hermes can invoke this tool with one shell call and immediately return notes into the chat.

---

## 6. Summary Advice for the Council

1. **Keep `yt-dlp` as a clean external dependency.** Do not modify `/Users/ooj/Fun/code/yt-dlp`.
2. **Prioritize the "Fast Subtitle Path"**—it transforms the user experience from a 5-minute wait to a 10-second instant note generator.
3. **Build the Companion CLI first**, then add the Agent Skill as a 5-line wrapper.
4. **Defer vision to v0.2**, using ffmpeg scene detection or native Gemini video upload.
