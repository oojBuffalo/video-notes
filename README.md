# Video notes

Generate explanatory notes from a video's English captions and 48 sampled 1080p frames. Notes include timestamp links and the images supporting visual claims.

## Run

Requires Python 3, `yt-dlp`, `ffmpeg`, and an authenticated `codex` CLI.

```sh
./vnotes.py 'https://www.youtube.com/watch?v=tUPPVhBBcoM' \
  --out runs/my-video \
  --prompt 'Explain the diagrams and important caveats.'
```

The prompt is optional. The output directory must be new. Open `runs/my-video/notes.md` when the command finishes. The directory also contains sources, model responses, and timing data for inspection. Failed runs return a nonzero exit status.

Codex uses your existing login and its default model. Set `--model` to choose another model. It runs in ephemeral, read-only mode without user configuration, instructed to use the supplied sources without tools. Captions and images are sent to the model provider.

For Gemini, use `--engine gemini` with `GOOGLE_API_KEY` configured. `--model` and `--review-model` select its draft and review models; both default to `gemini-3.5-flash-lite`.

## Saved results

| Video | End-to-end time | Notes |
|---|---:|---|
| YC Paper Club, 81:42 | 49.2 s | [Read](runs/yc-paper-club/notes.md) |
| Vectors, 9:51 | 33.3 s | [Read](runs/vectors/notes.md) |
| Warp factory engineering, 20:36 | 38.0 s | [Read](runs/warp-factory/notes.md) |

These local results are ignored by Git. See [validation](docs/validation.md) for checks and limitations.

## Development

```sh
python3 -m unittest discover -s tests -v
```

```text
vnotes.py          command and pipeline
tests/            regression tests
docs/             validation record
runs/             generated output (ignored)
.local/           archived experiments (ignored)
```

The previous experiment workspace is preserved in `.local/benchmark-history.tar.gz`; every archived file was hash-checked before removing the loose originals. The runnable implementation is `vnotes.py`; scripts inside saved runs are historical snapshots.

## Limits

English captions and an accessible 1080p H264 stream are required; HLS is tried when direct streams fail. There is no speech-transcription fallback. Adjacent short chapters are grouped into at most six sections.

The 60-second budget covers acquisition, synthesis, validation, and writing notes. Provider delays can cause failure, and cleanup may finish after the deadline. Forty-eight sampled frames can miss brief diagrams. Valid source IDs do not guarantee factual correctness.
