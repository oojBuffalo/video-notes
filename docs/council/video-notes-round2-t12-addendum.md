# Addendum: static YouTube URL is the baseline

Advisor t12. This corrects the route ranking in `/tmp/video-notes-round2-t12.md`. It does not add a latency measurement.

## Revision

Direct Gemini processing of a public YouTube URL, with processing set to **static**, is the baseline to measure. The local caption-and-frame pipeline is the fallback if that baseline fails a named test, not the thing to build first.

Round 2 ranked the frame pipeline first because its fetch was timed (~3 s) and the Gemini call was not. That was the wrong use of a missing number. Both routes still have an unmeasured model call. The official docs say static mode is the latency-sensitive choice for a broad, whole-video request, and that agentic navigation adds round trips and can take longer. The baseline should follow that, and then be timed. Agentic stays off for this product.

No duration was claimed, and none is claimed here. The user has not fixed duration. Nothing in the docs is a sub-60-second guarantee. 60 seconds remains a budget for a later benchmark, not a property of static mode.

## What the current docs support

From the video-understanding page (fetched earlier this session from `ai.google.dev`, which redirects to `aistudio.google.com/docs/video-understanding`):

- A public YouTube URL is a video input. Private and unlisted videos are excluded. The feature is preview.
- Default processing is static at **1 FPS**. Custom `fps`, and `start_offset` / `end_offset`, exist only in static mode. The documented custom-fps example is `0.5`.
- Static is the mode they recommend for broad summaries of the whole recording and for latency-sensitive queries. Agentic is for long video and narrow questions, and it can raise time-to-first-token on broad queries.
- Tokens, at 1 FPS: about **100 per second** of video at low (default) resolution, about **300 per second** at high. High is the setting they point at for dense text and small detail. A 1M window is about 3 hours at low and about 1 hour at high.
- They publish no end-to-end seconds.

Default static is therefore two choices at once: 1 FPS, and low resolution. Low resolution is the latency setting and the wrong setting for reading formulas. The baseline has to split those, or a fast result will be mistaken for a diagram result.

## Baseline to run once duration is known

One public YouTube URL. Same notes prompt. Same model. Two calls, both `processing.type = "static"`, agentic off:

1. Default resolution, `fps` 1.
2. High `media_resolution`, `fps` 1.

Log wall clock, time-to-first-token, input tokens, output tokens, and finish reason. Score the same pre-chosen on-screen facts (a formula or an axis label) as correct, wrong, or omitted.

`fps` and clipping wait on duration. Token count scales with `fps` times seconds times resolution. Lowering `fps` or clipping a window is how a long video stays inside a token budget. It is also how the notes stop covering the whole video. Do not pick a number until the duration bound exists. Do not describe a clipped or downsampled run as a complete viewing.

## What this does not decide

- It does not say static finishes in 60 seconds for any length, any resolution, or any output size.
- It does not make Gemini a stand-in for every LLM. This baseline is a Gemini call. Other providers still need images or a file, which is the other architecture.
- It does not retire the storyboard finding. A 159×90 board still cannot carry equations. That only matters again if the high-resolution static run misses the clock or fails the formula check. Then the fallback is a few sharp frames plus the caption file, with unread diagrams marked unread.
- It does not change the layer. This is one command that calls the API. It is still not a yt-dlp fork, a postprocessor, or an agent skill. The command must not inherit the user yt-dlp config, because that config already spent 117 seconds fetching comments on a metadata dump.
