# Video notes

Turn a video URL into study notes with the video's diagrams, slides and code placed beside the text they support.

![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)

The product is an agent skill: [`skill/SKILL.md`](skill/SKILL.md).
An agent you already pay for (Claude Code, Codex) reads the transcript, looks at the video's pictures itself and writes the notes.
A small helper, `vnotes`, does the fixed work around it. There is no model API code here and no API key to set.

[Setup](#setup) · [Usage](#usage) · [How it works](#how-it-works) · [Commands](#commands) · [Limits](#limits) · [Development](#development)

## Setup

You need Python 3, `yt-dlp` and `ffmpeg` on `PATH`. No Python packages are installed.

Put the helper on `PATH`, from the root of this repository:

```sh
ln -s "$PWD/vnotes" ~/.local/bin/vnotes
```

That is enough for `vnotes notes`. To use the skill inside your own agent sessions as well, link the `skill/` folder into the agent's skills folder under the name `video-notes`:

```sh
ln -s "$PWD/skill" ~/.claude/skills/video-notes    # Claude Code
ln -s "$PWD/skill" ~/.codex/skills/video-notes     # Codex
```

Each agent reads `SKILL.md` from that folder. Start a new session afterwards, then ask for notes on a video URL.

A video without captions is transcribed from its audio. That needs `whisper-cli` (whisper.cpp) and a `ggml-*.bin` model file, found in `/usr/local/share/whisper/models` or named by `VNOTES_WHISPER_MODEL`.
If the GPU is unavailable (for example inside a command sandbox), transcription is retried on the CPU, which took about three minutes for a ten-minute video here.

## Usage

One command, using the login of an agent CLI you already have:

```sh
vnotes notes 'https://www.youtube.com/watch?v=tUPPVhBBcoM' \
  --prompt 'Focus on the architecture diagrams.' \
  --agent claude \
  --out runs/my-video
```

`--prompt`, `--agent` (`claude` or `codex`, default `claude`) and `--out` (default `notes-<video id>`) are optional.
Open `runs/my-video/notes.md` when it finishes. The transcript, index sheets and frames stay beside it.

Or, inside an agent session that has the skill, ask for notes on a URL.

## How it works

1. `vnotes fetch` writes the transcript and **index sheets**: low-resolution contact sheets of the whole timeline, one tile every 10 seconds.
2. The agent reads the transcript and looks at every index sheet. Speakers do not announce most of what they show, so the index is how unmentioned slides and diagrams get found.
3. The agent asks `vnotes frames` for sharp 1080p frames at the moments it chose and checks them. For any picture the first call missed, it makes one more call that brackets it with several times between the neighbouring index tiles, and keeps the best.
4. The agent writes `notes.md` with each image directly after the text it supports.

Quality comes first: there is no time limit and no cap on frames. A longer video gets more index sheets, not a thinner look.

### What the headless agent is allowed to do

A transcript and the text on a slide are written by strangers, and the agent reads both. So `vnotes notes` runs the agent read-only and does the rest itself:

- The agent's reply is either `FRAMES: 1:22 3:54 …` or the finished notes. `vnotes` pulls the frames from the URL you gave on the command line, and `vnotes` writes `notes.md`.
- Notes that link to an image that does not exist are not saved.
- Each frame request starts the agent again as a fresh session, so a headless run reads the material two or three times.

What was checked by asking each agent to try, on this machine (`claude` 2.1.325, `codex-cli` 0.169.0):

| | `claude` | `codex` |
|---|---|---|
| Launch | only the `Read` tool, `--restricted`, `--safe-mode`, `--strict-mcp-config`, no saved session | `-s read-only`, `--ignore-user-config`, `--ephemeral`, web search off, 16 features off including `shell_tool` |
| Run a shell command | no tool for it | no tool for it |
| Write a file | no tool for it | rejected by the read-only sandbox |
| Fetch a URL or search | no tool for it | no tool for it |
| Read outside the notes folder | blocked | cannot read text files at all; it views images |

What this does **not** guarantee:

- The feature list switched off for `codex` matches version 0.169.0. A newer version can add tools that the list does not name. It still listed tools for patching files, starting sub-agents and listing MCP resources, and no switch was found that removes them. When tried, patching was rejected by the sandbox, a sub-agent had the same limits as its parent, and the MCP resource list was empty.
- Admin-managed `claude` settings still apply.
- The agent can still be misled. A hostile transcript cannot make it run or send anything, but it can make the notes wrong, or put a misleading link in them. Read the notes as you would read the video.
- The transcript and frames are sent to the model provider.

Inside your own interactive session the skill runs `vnotes frames` directly, under whatever permissions that session has. None of the above applies there.

## Commands

| Command | Writes |
|---|---|
| `vnotes fetch URL DIR` | `meta.json`, `transcript.txt` (`[mm:ss] text` lines), `index/index-NNNm.jpg` |
| `vnotes fetch --transcribe URL DIR` | the same, with the audio transcribed even when captions exist |
| `vnotes frames DIR TIME...` | `frames/MM-SS.jpg` at 1080p and `frames/sheet-NN.jpg` contact sheets; times are seconds, `mm:ss` or `h:mm:ss` |
| `vnotes notes URL [--prompt TEXT] [--agent claude\|codex] [--out DIR]` | everything above, then `notes.md` from the agent's reply |

What the helper takes care of, so the agent does not have to get it right by luck:

- uses the newest `yt-dlp` on `PATH` and ignores your `yt-dlp` config
- prefers human captions in the video's language, then automatic captions of the spoken words
- downloads captions with `yt-dlp`, and says so when captions exist but cannot be fetched and the audio is transcribed instead
- reads frames from the direct stream and falls back to HLS; retries reads that drop
- keeps signed stream addresses out of its output and out of the notes folder
- downloads a small 240p copy to build the index, because reading a long remote stream with `ffmpeg` is throttled
- rejects times past the end of the video
- replaces an existing frame or index only when the new one is complete
- refuses an empty transcription instead of writing an empty transcript

## Limits

- Captions are tried only in the video's own language (English when the site does not say). Anything else is transcribed.
- Index tiles are 10 seconds apart, so a picture on screen for less than that can be missed.
- Index tiles carry no printed time. The agent works it out from the layout: each row is one minute.
- The notes are only as careful as the agent that writes them. The skill tells it to quote small text only from a frame opened at full size.
- Tested on YouTube only.

## Project layout

```
skill/SKILL.md   the skill: what the agent does, step by step
vnotes           the helper: one standard-library Python script
tests/           checks for caption parsing, track choice, stream choice, time formats
docs/            validation.md (what was measured) and council/ (the reports behind it)
runs/            generated notes (ignored by git)
```

## Development

What has been measured, and what is still unproven, is in [docs/validation.md](docs/validation.md).

```sh
python3 -m unittest discover -s tests -v
```

<!-- TODO: license -->
