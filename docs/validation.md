# Validation

What was measured for the skill-first tool, and what was not.
Every number here comes from a run on one machine on 2026-11-14, except section 6, which is from 2026-11-17. Nothing here is a guarantee of speed or quality.
The reports behind each number are in [`council/`](council/).

The earlier prototype (a fixed pipeline that called model APIs) was removed. Its saved times were 33.3 s, 38.0 s and 49.2 s for the three videos below; they are quoted only as the baseline.

## Test videos

| Short name | Video | Length | Words came from |
|---|---|---|---|
| Vectors | `fNk_zzaMoSs` (3Blue1Brown animation) | 9:51 | human English captions |
| Warp | `tUPPVhBBcoM` (conference slide talk) | 20:36 | automatic English captions |
| Paper Club | `-XL2gClQ2gg` (several talks with slides) | 81:42 | automatic English captions |

All three are on YouTube.

## 1. Does the agent-as-model approach work? (round 3)

Four agents each wrote a skill draft and followed it by hand on Vectors, with no model API code and no index sheets yet.

| Agent | Time to notes | Frames pulled | Images in notes |
|---|---:|---:|---:|
| t8 (Codex) | 104 s | 10 | 7 |
| t10 (Claude Code) | 138 s | 29 | 12 |
| t11 | 205 s | 16 | not stated |
| t12 | 218 s | 15 | 11 |
| Old pipeline | 33.3 s | 48 (fixed) | 22, in an appendix |

- All four placed images beside the text they support. The coordinator judged all four sets of notes better than the baseline. No blind reader scored them.
- All four found the same gap: frames chosen from the transcript miss pictures the speaker never mentions. The index sheets exist because of this.
- Frames chosen from a sentence often landed mid-animation (t10: 3 of 23; t12: 4 of 15 dropped).

## 2. Acceptance runs of the built tool

Each agent followed `skill/SKILL.md` using `vnotes fetch` and `vnotes frames`.

| | t10 on Warp | t12 on Warp | t11 on Paper Club |
|---|---:|---:|---:|
| Index sheets viewed | 5 of 5 | 5 of 5 | 16 (one missing, see section 4) |
| Frames pulled | 25 | 44 | 49 |
| Images in notes | 7 | 27 | 33 |
| Frames opened at full size | 7 | 26 | 14 |
| Total time | not cleanly timed | 584 s | 2,785 s |
| of which `fetch` | 11.8 s | 6.95 s | 2,352 s (before the fix in section 4) |

t10's run was interleaved with debugging the helper, so it has no clean total.

**Did the index find pictures the transcript does not announce?** Yes, in all three runs.

- Warp (t10, t12): the formula `Factory efficiency = Software shipped / (token cost + human cost)`, the inner and outer loop diagram with its `SKILL.md` names, the word "[Optional]" on human code review, the 932,409-lines callout, the Same.dev clone example.
- Paper Club (t11): a tissue heatmap, a four-domain design comparison, a mouse-brain fluorescence image, and exact figures on several slides.

**What went wrong in these runs, and what changed.**

| Found by | Problem | Change |
|---|---|---|
| t12 | With one nudge allowed, two slides seen on the index never got a still | Step 3 now makes one more call that brackets each missed picture. Tried by hand on those two slides: caught at 7:25 and 11:45 |
| t11 | `fetch` took 39 minutes on the 82-minute video and left out the last sheet | Section 4 |
| t10 | Section links taken from the chapter list were about 20 s late | The skill now says to take them from the transcript |
| t10 | 10 of 25 frames failed on the first pull | Reads are retried. Three further pulls of 25 frames all succeeded |

## 3. Headless runs (`vnotes notes`)

Run on Vectors with the final, read-only launch.

| Agent | Time | Turns | Images in notes | Broken image links |
|---|---:|---:|---:|---:|
| `claude` 2.1.325 | 95 s | 2 | 14 | 0 |
| `codex-cli` 0.169.0 | 169 s | 3 | 8 | 0 |

Two earlier launch designs also produced notes (124 s and 181 s) but let the agent run commands, and were replaced after review.

**What the headless agent can do**, checked by asking each one to try:

| | `claude` | `codex` |
|---|---|---|
| Run a shell command | no tool | no tool |
| Write a file | no tool | rejected by the read-only sandbox |
| Fetch a URL or search | no tool | no tool |
| Read outside the notes folder | blocked | cannot read text files; it views images |
| Start a sub-agent | no tool | yes, and the sub-agent had the same limits |

No live test used a hostile transcript.

## 4. `fetch` timing, before and after

Measured on Paper Club (4,902 s).

| Version | Time | Index sheets | Captions |
|---|---:|---:|---|
| One `ffmpeg` reading the remote stream start to end (t11) | 2,352 s | 16 of 17, tail missing | fetched |
| One seeked `ffmpeg` per sheet on the remote stream (t10) | 236 s | 17 of 17 | fetched |
| yt-dlp downloads a 240p copy, sheets cut locally (t10) | 14.6 s | 17 of 17 | 2,299 lines |
| The same, measured independently (t1r) | 14.1 s | 17 of 17 | 2,299 lines |

- The remote stream is throttled to about playback speed (t11 measured about 12 KiB/s). With one seeked read per sheet, seven sheets still took 110 to 225 s each and the other ten took about 4 s.
- yt-dlp downloaded the 19.5 MB copy in 3.4 s, and cutting 17 sheets from it took 2.2 s.
- On Warp, `fetch` took 11.8 s before and 13.6 s after.
- The sheet count is now exactly the file's length divided by five minutes, rounded up, and `fetch` fails if it differs.

**Captions.** On Paper Club a plain HTTP download of the caption track was cut off after 1.2 MB, and the second track returned HTTP 429. `fetch` then transcribed the audio without saying why. Captions now go through yt-dlp's downloader, which fetched the full track (4,598 caption events), and `fetch` reports it when captions exist but cannot be fetched.

**Transcription.** Forced on Vectors: 176 s end to end, 135 lines, on the CPU. The command sandbox blocked the GPU, so the GPU path did not complete.

## 5. Review and tests

- t8 reviewed the code and reported four findings; three were reproduced with mocks. All four are fixed.
- 30 unit tests pass: time formats, caption parsing, track choice, stream choice, sheet count, keeping a frame or index when a refresh fails, refusing an empty transcription, serving a frame request before saving notes, and not saving notes that link to missing images. For `vnotes direct`: the three request bodies, reading the three reply streams, a cut-off or refused reply, a stream that ends without its end mark, the frame-line parser, missing credentials, the step order with a fake model, and the image-link check (titles, reference-style links, other image types). Against a local fake server: a retry when busy, a refusal, an error inside the stream that echoes the key, and a retry after a passing fault or a cut-off stream.
- The tests do not touch the network or a real agent. The four fake-server tests are skipped where a local port cannot be opened.

## 6. `vnotes direct`: request shapes

No full run of `vnotes direct` is recorded here yet. What was tried is one small request per provider through `send()`: the question "What colour is this image?" with one 64 by 64 red JPEG.

| `--via` | Model | Result |
|---|---|---|
| `chatgpt` | `gpt-6.2-sol` | replied "Red" in 4.5 s |
| `openrouter` | `nvidia/nemotron-3.5-super-vl:free` | replied "Red" in 10.3 s |
| `openrouter` | `openai/gpt-6.2-sol` (the default) | refused, 403: the key in this environment has reached its spending limit |
| `openrouter` | `google/gemma-4-31b-it:free` | 429 from the upstream provider on all four tries (waits of 5, 20 and 60 s) |
| `openai` | `gpt-6.2-sol` | refused, 401: the key in this environment is not valid |
| `anthropic` | `claude-opus-5-5` | local fake server only: no key is set |

- **How the ChatGPT request was worked out.** The installed codex 0.169.0 was run against a local recorder. That showed its headers (`Authorization`, `chatgpt-account-id`, `originator`, `User-Agent`) on its side calls. It did not show the model request, because codex will not send that over plain HTTP, so the body fields were read from the codex source at tag `rust-v0.169.0`. A body with only `model`, `stream`, `store: false`, `reasoning` and `input` (one developer message, one user message) was accepted with the two credential headers and `User-Agent: vnotes`. No `originator` header is sent.
- **Model ids.**
  - `chatgpt`: the backend's own model list for this account puts `gpt-6.2-sol` first, with text and image input.
  - `openrouter`: `openai/gpt-6.2-sol` is in OpenRouter's public model list.
  - `openai`: the model list could not be read (401). The id is the one the other two lists use.
  - `anthropic`: the id comes from Anthropic's published model table, not from a live list.
- **After the review fixes** the `chatgpt` and free `openrouter` requests were repeated and both replied "Red" (5.3 s and 3.7 s), so both send the end mark that `vnotes` now requires.
- **Sizes, worked out offline.** With a saved run of the Warp video, the plan request is 1.6 MB (5 index sheets) and the write request is 9.9 MB (40 frames). Neither was sent.

## Still unproven

- **`vnotes direct` end to end.** No full run was made, so nothing is known yet about its time, its notes, or whether each provider accepts a 10 MB request.
- **`vnotes direct` with `openai`, `anthropic` and `endpoint`.** No request to any of them succeeded or was possible. The Chat Completions shape they share with `openrouter` did work there.
- **`vnotes direct` with the default OpenRouter model.** Only a free model answered.

- **HLS fallback.** It worked in 1 of 4 attempts. The direct stream carried every successful run.
- **Transcription on the GPU.** Never completed here. A long video without captions has not been run at all.
- **Sites other than YouTube.** Not tried.
- **Languages other than English.** Not tried. Captions are only attempted in the video's own language.
- **Headless runs on a long video.** Only the 10-minute video was run headless.
- **The bracketing rule in a full run.** The helper call was tried by hand on two slides; no agent has yet followed the new step 3 end to end.
- **Installing the skill by linking.** Both skills folders exist on this machine and hold other skills laid out the same way, but the links in the README were not made and a linked `video-notes` skill was not loaded.
- **Videos longer than 82 minutes.**
- **Quality.** Each agent judged its own notes. No one outside the project has compared them, and no notes were checked claim by claim.
- **Cost.** Token use was not measured.
