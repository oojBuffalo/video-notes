# Video notes: companion CLI, not a yt-dlp fork

Advisor: t12 (read-only). Repo inspected: `/Users/ooj/Fun/code/yt-dlp` at `412e7f0a4`, branch `master` tracking `origin/master`, clean. It is a sync fork. Last commit is an upstream dependency bump. Do not put product code there.

## Recommendation

Build a small companion command, `vnotes <url>`. Shell out to the stock `yt-dlp` binary. Do not fork yt-dlp, do not add a postprocessor plugin, and do not implement the pipeline as a Claude Code / Codex / Hermes skill.

The hard URL/site problem is already solved. The new problem is text: pick a transcript, cache it, run a grounded prompt, write notes. That product has its own dependencies, secrets, cache, and failure modes. It should own a 200-line CLI, not an extractor codebase that must track upstream weekly.

## Why not the other layers

**Fork.** Upstream will not take Whisper, API keys, or a notes prompt. A local patch means every YouTube breakage is a merge, or you stop merging and downloads rot. This checkout has no local notes work to preserve. Keep updating `yt-dlp` with `-U` or by pulling master. Call it.

**Plugin.** Plugins are only `extractor` or `postprocessor` (`README` Plugins; `yt_dlp/plugins.py`). A postprocessor runs after a successful download, inside the yt-dlp process, once per file. Every plugin is imported even when unused, with no code checks. The plugin API has no compatibility promise. `--use-postprocessor NAME[:ARGS]` cannot cleanly carry a multiline prompt, a model name, a cache policy, or "do not download if subtitles exist." Whisper or an LLM SDK inside that process is a dependency and crash domain yt-dlp does not want. A wrapper command would still be required for the UX you asked for. The plugin adds a seam and buys nothing.

`yt-dlp` already has the hooks a companion needs: `-x` / `--extract-audio`, `--write-subs`, `--write-auto-subs`, `--skip-download`, `--dump-single-json`, chapters, and an exec postprocessor. Use those from outside.

**Agent skill.** A skill re-decides the pipeline every run: whether to download, which flags, whether to keep the transcript, how to chunk. That burns tokens, skips cache, and is not runnable without an agent. Write the skill later, in about ten lines: "run `vnotes`, then talk about the file." The skill is a client. It is not the implementation. Same answer for Claude Code, Codex, and Hermes.

## Smallest useful version

One command:

```text
vnotes URL [--prompt file.md] [--model name] [--out notes.md]
```

Behavior:

1. `yt-dlp --dump-single-json` for id, title, chapters, subtitle URLs. Do not import the Python package. A pinned subprocess invocation survives upstream refactors better than a private import.
2. Text source, in order: manual subtitles, then auto-captions, then a local transcriber (`whisper.cpp` or whatever binary is on `PATH`). Download audio only when both subtitle sources are missing or unusable. Normalize everything to `{start, end, text}` and write `transcript.json`.
3. Cache by extractor plus video id: `info.json`, `transcript.json`, notes. LLM failure must not delete the transcript. A second run with a new prompt must not re-download.
4. Default prompt is the contract: timestamped outline, claims, definitions, action items, and quotes only when they appear in the transcript. The user's prompt is appended. It does not replace that contract unless they pass something like `--prompt-only`.
5. If the transcript fits, one model call. If it does not, split on chapters from the info JSON, then one consolidate call. That consolidate step is the "refined notes" feature. Print the notes path. Non-zero exit on failure.

Out of v1: vision, diarization, embeddings, a plugin registry, a TUI, a database.

## Visuals

Leave them out of v1. Speech is the notes. Frames are a different product.

A slide talk, a whiteboard, and a screencast need frames. A podcast or talking-head does not, and a vision pass on B-roll makes the notes worse: the model describes the room.

When you add them, make `--visual` opt-in and a second pass:

- Download a small video rendition only after the transcript exists.
- Sample a hard cap (about 20 frames) at scene changes. Drop near-duplicates.
- Attach each frame to the transcript segment at that timestamp.
- Ask the model only for those segments: what is on screen that the speech does not already say (slide title, code, chart, diagram). Merge short "On screen" bullets.
- Do not send the whole video, a fixed 1 fps strip, or storyboard thumbnails. Thumbnails are cheap and mostly useless for notes.

Heuristic later, still not the default: offer `--visual` when subtitle text is sparse relative to duration, or when the user says slides. Do not auto-enable it.

## Assumptions worth dropping

- "Transcribe the audio" is often wasted work. Many URLs already have a better transcript than Whisper. Subs first.
- "One simple command" is a UX constraint, not a reason to live inside yt-dlp. The command may shell out.
- "Detailed notes" from one free-form prompt will be fluent and wrong on a long video. Timestamps and a quote rule are the product. The custom prompt is an overlay.
- Model choice matters less than keeping `transcript.json`, so the prompt can be re-run without touching the network.
- "Possibly visuals" should not shape v1. It roughly doubles download size, adds ffmpeg scene logic, and adds a vision model. Ship speech notes. Add a flag when a real video needs the screen.
- An agent feels like the fastest way to get a first note. It is the expensive, unreproducible version of this same pipeline.
