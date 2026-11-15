# Conclusion: direct static YouTube call, no latency promise

Advisor t12. Evidence already collected only. No model call was made. One-run timings are that run, not a rule about every video or every machine.

## Decision

Cold path: a companion command sends a **public YouTube URL** to Gemini with **static** processing and agentic mode off. Visuals are in that call because the provider samples frames. Official docs confirm the URL input. They do not guarantee a finish time. Do not claim under 60 seconds.

Do not fork yt-dlp. Do not implement this as a postprocessor or as a Claude Code, Codex, or Hermes skill. The skill may call the command later.

Pre-indexing does not meet the cold-URL requirement. It is out of the default path.

## Three architectures

**Direct video.** One Gemini request, public YouTube URL, `processing` static. Default sample rate is 1 fps. Custom fps and clipping exist only in static mode. Low resolution is about 100 tokens per second of video; high, the setting aimed at dense text, is about 300. A 1M window is about 3 hours at low and about 1 hour at high. Those are published token rates. Agentic navigation is documented to add round trips and can take longer; docs point latency-sensitive, whole-video requests at static. Preview feature. Private and unlisted URLs are excluded. No end-to-end seconds are published, and none were measured here.

**Portable frames plus captions.** Fetch a caption track and images, then call any vision model. On this machine, one public video (`fNk_zzaMoSs`, 591 s), `yt-dlp --ignore-config`: English captions **3.0 s**, 15 KB; best storyboard **2.9 s**, 98 KB, frames **159×90** at **0.2 fps**. I looked at one sheet. Layout was visible. The matrices were not readable. A higher-resolution frame download was not done. Full-file transcription speed was not measured. This path is the one that can switch providers. It was not shown to produce equation-level notes, and it was not timed through a model.

**Pre-indexing.** Transcript, frames, or a finished note already stored before the user pastes the URL. A second prompt can be one model call, or a reprint. That is a different clock. It does not answer a cold URL. It is not the architecture.

## Acquisition, this run only

| What | Result | Scope |
| --- | --- | --- |
| `yt-dlp -J` with this user's config (`--write-comments` and the rest of `~/.config/yt-dlp/config.txt`) | **117 s**, JSON included 4,041 comments | This config, this video. Not a claim that metadata is always slow. |
| Same dump, `--ignore-config` | **2.5 s** | This video, one run. |
| Captions and storyboard above | About **3 s** each | Same. |
| Gemini static call, any resolution or fps | Not run | Latency unknown. |
| Sharp frame at a timestamp | Not fetched | Unknown. |
| Speech-to-text of the whole file | Not run | Unknown. |

A notes command that inherits this yt-dlp config spent the minute on comments in this run. The direct-video path does not invoke yt-dlp, so that failure does not apply to it. It also does not prove the Gemini call is fast.

## 60 seconds

Budget only. Cold URL to finished notes was not timed. Docs give no guarantee. Duration is unset, so fps and clipping stay unset: both reduce tokens by looking at less of the video. Cached or pre-indexed output is not evidence for the cold path.

## If the baseline is not usable

Measure the baseline before replacing it: same URL, same prompt, static, agentic off, default resolution at 1 fps and high resolution at 1 fps. Record wall clock, tokens, and whether a pre-chosen on-screen fact is correct, wrong, or omitted. That pair was not run.

Use portable frames plus captions only if that pair cannot be used (URL not public YouTube, or the formula check fails, or the call is past the budget). Captions from an ignore-config fetch, storyboard only to pick times, a few sharp frames, output capped, unread diagrams marked unread. That fallback was not built. If those frames are not acquired, say so. Do not fill them in from the 159×90 sheet.

Round 1 (speech first, visuals later) is withdrawn. Diagrams stay in the default call. The local frame pipeline is the alternative, not the default.
