# Round 3 findings: t10 (Claude Code)

Run: `https://www.youtube.com/watch?v=fNk_zzaMoSs` (9:51), fetched fresh, no subagents, no model API code. Output in `runs/round3-t10/`.
**Order disclosure:** I ran from a plan, then wrote the skill file. It records what I did plus two rules I learned mid-run. The written text has not been re-run.

## Measured

- **Wall clock: 138 s**, first fetch to `notes.md` written (`date` stamps). The old pipeline's saved result for this video is 33.3 s.
- Tool time inside that: captions + metadata 8.6 s; stream address 6 s; 23 frames in parallel 5 s; 6 re-grabs 2 s. The remaining ~115 s was me reading, looking and writing.
- **Frames: 29 pulled, 14 used** in 12 images (three became one strip). I looked at 3 contact sheets and 1 full-size frame, not 29 images.
- **How chosen:** I read the 157-line transcript and listed one moment per concept or worked example. The speaker almost never says "look at this", so the choice came from "this idea must have a diagram", not from pointing cues.
- **Second pass:** 3 of 23 first picks landed mid-animation (02:28, 06:24, 06:42), so I re-grabbed. Rule learned: take the end of a passage, not its start.
- Both commands ran inside the sandbox. `yt-dlp` on `PATH` is a stale pyenv copy (`2026.03.17`); I called `/opt/homebrew/bin/yt-dlp` (`2026.10.26`) by path. Two caption tracks arrived (human `en`, automatic `en-orig`); I chose the human one by hand.

## What broke or was weak

- **Coverage hole (measured):** I pulled nothing between 08:08 and 08:48, and after 08:48 only one frame (09:10), which I did not use. The baseline cites frames there (operation recap, data picture, code, next-video preview). Nothing in the transcript told me to look.
- **Traceability (measured):** my notes link sections to timestamps; the baseline cites a caption or frame for every bullet.
- **Small text (assumed):** 640 px tiles were readable here because the type is large. Dense slides or code would need full-size reads, which cost more time.

## Helper versus markdown

| A deterministic helper must do | The markdown can leave to the agent |
|---|---|
| Pick the right `yt-dlp`, pass `--ignore-config`, one call for metadata, captions and stream address | Which moments deserve a picture |
| Choose the caption track; turn it into `[mm:ss] text`; transcribe when there are no captions | Judging a frame as good, early, or mid-transition, and asking again |
| `frames DIR t1 t2 …`: parallel sharp frames plus a contact sheet; hide the signed address and its expiry | Which frames survive, strips, alt text, placement |
| A uniform low-resolution index sheet of the whole video, so the agent sees what it did not ask for (assumed fix for the coverage hole) | Structure, consolidation, wording, the user's prompt |

The inline shell in my draft is about 15 lines and worked first time, so the helper can be small. Its value is removing things I got right by luck: binary choice, track choice, stream format.

## Against `runs/vectors/notes.md`

- **Mine is better at (my judgement of my own work; a reader should decide):** images inline beside the claim, where the baseline lists 22 unlabelled frames at the end; one consolidated summary, tables and a terms list, where the baseline repeats four near-identical "Limits" lines and pads to six bullets per section; the point-versus-vector convention `(−4, 2)` which the baseline omits.
- **Baseline is better at:** speed (about 4× faster); per-claim citations; visual coverage of the last chapter; a fixed 48-frame sample that cannot skip a region by my choice.
- **Same facts (measured by reading both):** every worked example I quote from a frame, other than that point, also appears in the baseline with the same numbers.
- **Assumed:** this video is an easy case (human captions, chapters, slow clean animation, 10 minutes). Nothing here shows the approach holds for an 80-minute talk, automatic captions, or slides the speaker never mentions.
- **Verdict on the hypothesis:** supported for quality on this one video, at roughly 2 minutes instead of 33 s. The agent-as-model works; the transcript alone is not enough to find every visual.
