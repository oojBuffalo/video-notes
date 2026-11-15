---
name: video-notes
description: Notes from a video URL. The host agent is the model. A helper only fetches captions and frames.
---

# Video notes

You write the notes. Do not call a notes API. Quality beats the clock. Sixty seconds is a goal, not a gate.

## Inputs

A video URL, an optional focus prompt, and an output directory. Create the directory. Do not reuse another run's frames or notes.

## Fetch

Use `yt-dlp --ignore-config`. Never inherit the user's yt-dlp config.

1. Dump metadata (`-J --skip-download`). Record title and duration.
2. If an English caption track exists, download it (`--skip-download --write-subs --sub-langs en`). Prefer a timed track (json3 or vtt).
3. If no captions exist, download audio only and transcribe it with a local transcriber. A longer run is expected. Do not invent a transcript.

Read the timed text before choosing any picture.

## Choose frames

Pick a timestamp only where the words depend on a picture: a drawn object, an equation, a chart, a "this arrow", a before/after. Skip talking heads and repeated beats of the same drawing.

Keep one frame per distinct visual claim. About six to twelve is enough for a short lesson. Do not sample a fixed grid.

## Pull frames

Resolve a video-only URL at or below 1080p:

```sh
yt-dlp --ignore-config -g -f "bv*[height<=1080][vcodec^=avc1]/bv*[height<=1080]/b" URL
```

For each timestamp, save `frame-MMSS.jpg` in the output directory:

```sh
ffmpeg -y -ss MM:SS -i VIDEO_URL -frames:v 1 -q:v 2 frame-MMSS.jpg
```

Seek before the input. If ffmpeg fails on the direct URL, retry that frame with an HLS URL (`-f bv*[height<=1080]/b`). If the still is blank, a transition, or the wrong beat, move one or two seconds and pull once more. Then stop. Look at every kept image before writing about it.

## Write

Write `notes.md` in the output directory.

- Lead with the title, duration, and one short overview in your own words.
- Order claims by time. Put each supporting image directly under the sentence it supports, as `![what is visible](frame-MMSS.jpg)`.
- State only what the transcript says or what is visible in a frame you pulled. If you did not read a formula, say so.
- A custom prompt changes emphasis. It does not waive the rules above.

## Stop

Leave the helper's files (info json, captions, frames) beside the notes. Do not delete a failed fetch to hide it.
