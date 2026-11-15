# Video notes, round 2: recommendation from t10 (Claude Code)

## Decision

Make **direct native video input the main path**: one streaming Gemini API call that takes the public YouTube URL, static processing, plus the prompt.
Keep **portable frames + captions** as the fallback for everything that path cannot do.
Still a small companion CLI; still not the yt-dlp fork, a plugin, or an agent skill.

I cannot say this meets 60 seconds. No model latency was measured in this round, and Google's docs give no latency guarantee.

## What I revise from round 1

| Round 1 position | Now |
|---|---|
| Defer visuals to v2 | Wrong for this requirement. Visuals are in v1. |
| LLM as a stdin command string (`claude -p`, etc.) | Dropped. It cannot carry video or images. |
| Agent picks frames after reading the transcript | Dropped from the fast path. It is several model round trips. Google's docs say the same of their own agentic mode: it "can take longer". Keep it only as a slow, thorough mode. |
| Local captions fetch as the first step | Off the critical path. See the failed measurement below. |
| Companion CLI; atomic output; exit checks; size guard | Unchanged. |

## Evidence

**Measured on this machine (one video, one attempt per binary):**

- `yt-dlp` captions + metadata fetch, no download, for one 19-minute YouTube video did not finish with either installed binary: pyenv `2026.03.17` ran past 120 s, Homebrew `2026.10.26` ran past 90 s. Neither wrote a file.
- Cause not diagnosed. I piped output through `tail`, so I have no error text, and another pane was running `yt-dlp` at the same time. Do not generalize from this; it shows only that local acquisition is not something we can currently assume takes seconds here.
- `yt-dlp` on `PATH` resolves to the older pyenv copy, not the Homebrew one.

**Not measured:** any model latency, time to first token, frame extraction time, whisper speed, and whether any API key is set (that check never ran).

**From Google's video-understanding docs** (`ai.google.dev/gemini-api/docs/video-understanding`, which redirects to `aistudio.google.com/docs/video-understanding`; I read it through a summarizing fetch, so check exact numbers before relying on them):

- Public YouTube URLs are accepted as a video part. Private and unlisted videos are not. The feature is in preview; "pricing and rate limits are likely to change".
- Free tier: 8 hours of YouTube video per day. Paid tier: no length-based limit.
- Static processing is the default: 1 frame per second, with configurable `fps` and `start_offset` / `end_offset` clipping.
- 66 tokens per frame at low media resolution, 258 otherwise; audio 32 tokens per second. About 100 tokens per second of video at default (low) resolution, about 300 at high.
- With a 1M-token context: up to 3 hours at default (low) resolution, 1 hour at high.
- Agentic navigation is opt-in and can raise time to first token and total time.

I did not check whether any other provider accepts a video URL or video file. Treat the direct path as Google-only until someone verifies otherwise.

## The three options

| | Direct video URL | Portable frames + captions | Pre-indexing |
|---|---|---|---|
| Cold URL to notes | One API call; no local fetch | Fetch captions, get frames, then one call | Not applicable: the slow work is moved earlier, so it does not meet the cold-URL requirement |
| Visual coverage | Every second sampled at 1 fps | Only the frames you pick; a budget of N frames thins out on long videos | Same as portable |
| Diagram readability | Unknown. Default is the low setting (66 tokens per frame); high costs three times the tokens and caps at 1 hour | You control resolution; full-size frames possible | Same as portable |
| Provider choice | Google only (as far as verified) | Any model that accepts images | Any |
| Sources | Public YouTube only | Anything `yt-dlp` handles, including private or local files | Same as portable |
| Re-run with a new prompt | Full call again | Model call only; inputs are cached locally | Model call only |
| Code | About 20 lines | Several times that, plus frame selection | Portable plus a queue |
| Speed risk | Provider latency, unmeasured | Local acquisition, which failed to complete here twice | None at request time |

Pre-indexing is worth having only if you feed it from a queue such as a watch-later list. It is an optimization of the portable path, not an answer to the stated requirement.

**Existing agent harness** (Claude Code, Codex, Hermes with a skill): not for the fast path. It adds harness start-up and one model turn per tool call (fetch, extract, read each image). Unmeasured, but structurally multi-turn. It suits a thorough mode where time does not matter.

## Minimal fast architecture

`vnotes URL [PROMPT]`:

1. One streaming request: YouTube URL as the video part, static processing, prompt asking for timestamped notes that describe each diagram.
2. Stream to the terminal and to `notes.md.tmp`; rename to `notes.md` only on a clean finish with non-empty output.
3. Flags for model, `fps` and media resolution. No `yt-dlp`, no `ffmpeg`, no cache.

**Cold versus partial:** streaming means the first text arrives at time to first token, well before the notes are complete. Report both numbers separately once measured. Complete-notes time is bounded below by output speed: for example, 2,000 tokens at 100 tokens per second is 20 s of generation alone (arithmetic, not a measurement).

**Arbitrary durations:** one call covers up to 1 hour at high resolution or 3 hours at low, per the docs. Beyond that, split into segments with the offsets, run them in parallel, and concatenate in order with no merge pass. Whether parallel segments hold wall-clock time flat is a guess; rate limits apply.

## Where the goal is infeasible or unproven

- **Any promise of 60 s.** The provider guarantees nothing and the feature is in preview.
- **Long videos.** Input grows linearly (about 1M tokens for 1 hour at high resolution). I expect complete notes in 60 s to fail well before the 1-hour mark; that is a guess.
- **Private, unlisted or non-YouTube sources.** The direct path does not take them; the portable path does, with no speed promise.
- **Videos without captions on the portable path.** Transcription time is added and was not measured.
- **Slow or reasoning-heavy models and very long notes.** Output speed alone can use the budget.
- **"Chosen LLM" together with "under 60 s with visuals".** These pull apart. Fast with visuals currently means Gemini by default; other models come through the portable path.

## The one test to run before building

Time a single streaming call on a 20-minute diagram-heavy video, at low and at high media resolution. Record time to first token and total time, and check whether one diagram's labels appear correctly in the notes. That settles both open questions: latency and readability.
