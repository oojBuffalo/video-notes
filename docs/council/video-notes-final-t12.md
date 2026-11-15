# Decision: one command, Gemini static URL as the engine

Advisor t12. Wraps up rounds 1–2 and the addendum. No new research. Benchmarks that were not run are marked missing.

## Decision

Ship a companion command, not a change to yt-dlp and not an agent skill.

```text
vnotes URL [--prompt file] [--out notes.md]
```

Default engine: one Gemini call on a **public YouTube URL**, processing **static**, agentic **off**. The prompt asks for timestamped notes whose diagram claims come from the frames, plus the user’s prompt appended under that rule.

That is the whole architecture. yt-dlp is not on this path. Forking it, or a postprocessor plugin, still does not fit: the work is a model call with a token budget, and the local fork is a clean tracking checkout of upstream (`412e7f0a4`). A Claude Code, Codex, or Hermes skill may later invoke `vnotes`. It is not the pipeline.

## Why this engine

Google’s video-understanding docs say static mode is the one for a broad whole-video request and for latency-sensitive queries. Agentic mode adds navigation round trips and can take longer on that kind of prompt. Custom fps and clipping exist only in static mode. A public YouTube URL is an accepted input (preview; private and unlisted excluded).

Visuals are in the call. Default sampling is 1 fps. Low (default) resolution is about 100 tokens per second of video; high, the setting they point at for dense text, is about 300. A 1M context is about 3 hours at low and about 1 hour at high. Those are their published token rates, not times.

The other designs lost on evidence we already have:

- Speech-only, visuals later (round 1). Wrong product. Diagrams have to inform the notes.
- Download, transcribe, then write. No full-file transcription speed was measured. Caption fetch was fast; transcribing a lecture was never shown to fit a one-minute budget.
- Storyboard as the pictures. Measured on `fNk_zzaMoSs` (591 s): best board is 159×90 at 0.2 fps, fetched in 2.9 s. Layout is visible. Matrices are not. That cannot be the source of an equation.
- A local pipeline of captions plus a handful of sharp frames as the default. Its three-second fetch was real, and its sharp-frame fetch was never timed. Ranking it first used a missing Gemini number as if it were a loss. The docs already name the latency-sensitive mode. Measure that mode.

## What 60 seconds means

It is a budget, not a result. No end-to-end time was measured for any model call. The docs publish no sub-60-second guarantee. Do not claim one for any duration, resolution, or output length.

Two measured times do constrain the command:

- `yt-dlp -J` with `~/.config/yt-dlp/config.txt` took **117 s** and pulled 4,041 comments. The notes command must not inherit that config.
- The same metadata dump with `--ignore-config` took **2.5 s**. English captions took **3.0 s** (15 KB). The storyboard took **2.9 s**. Useful only for the fallback.

Cold URL to finished notes and “run the prompt again on files already saved” are different. Only a model call was ever a candidate for the second. It was not timed. Streaming a first paragraph is not a finished note. Reprinting a saved note is not a pipeline.

Duration is still unset. Token count grows with seconds × fps × resolution, and output length grows with how long the model writes. Until duration is set, do not pick fps, do not clip, and do not promise coverage. Lower fps or a clip keeps a long video inside a token window by not looking at all of it. The note has to say so.

## Alternatives, in order

1. **Baseline, build this.** Static YouTube URL. When a duration bound exists, run two calls on one URL and one prompt before changing anything else: default resolution at 1 fps, and high resolution at 1 fps. Record wall clock, time to first token, input tokens, output tokens. Score a few pre-chosen on-screen facts as correct, wrong, or omitted. That pair was not run. Missing on purpose.
2. **Same engine, smaller look.** Static only, lower `fps` or a `start_offset`/`end_offset` window. Use it when the duration bound makes 1 fps at high resolution overflow the context window or when call 2 of the pair is too slow for the budget. The notes cover the sampled window, not the whole video.
3. **Fallback if the pair fails the formula check or the clock.** Ignore the user yt-dlp config. Take the caption file. Use the storyboard only to choose timestamps. Fetch a few higher-resolution frames. One image-and-text call, any vision model, output capped. If a frame does not arrive, the note says that diagram was not read. This path was not built and the frame fetch was not timed. OpenAI’s vision docs, as checked earlier, take images, not a YouTube URL, so this is the path that is actually provider-swappable. The default is not.

Refuse rather than invent a third system for: no captions and no Gemini video call, private or unlisted URLs on the default engine, or a user-selected slow model that spends the whole minute decoding. Say which input was missing.

## Missing on purpose

No Gemini call, no p50/p95, no transcription real-time factor, no high-resolution frame download, no second video, no chosen fps. The 3 s and 117 s figures are one run each on one public 10-minute video.
