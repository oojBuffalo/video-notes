---
name: video-notes
description: Turn a video URL into detailed study notes with the key diagrams placed inline. Use when the user gives a video URL and asks for notes, a summary or a study guide.
---

# Video notes

You are the model. Read the transcript, decide which moments need a picture, look at those frames yourself, then write the notes. Do not call a model API. Do not start subagents.

Input: a video URL, and optionally what the user cares about. Output: one new folder holding `notes.md` and the images it embeds. Work inside that folder.

## 1. Fetch the text (about 10 s)

```sh
yt-dlp --ignore-config --no-warnings --skip-download \
  --write-subs --write-auto-subs --sub-langs 'en,en-orig' --sub-format json3 \
  --print-to-file '%(.{id,title,uploader,duration,upload_date,chapters,description})j' meta.json \
  -o cap -- "$URL"
python3 - > transcript.txt <<'EOF'
import json
for e in json.load(open('cap.en.json3'))['events']:
    t = ''.join(s.get('utf8', '') for s in e.get('segs', [])).replace('\n', ' ').strip()
    s = e['tStartMs'] // 1000
    if t: print(f'[{s//60:02d}:{s%60:02d}] {t}')
EOF
```

Use `cap.en.json3` (human captions) when it exists; otherwise `cap.en-orig.json3` (automatic).
No captions at all: download the audio, transcribe it, and tell the user the run will take longer.

## 2. Choose the moments

Read `meta.json` and the whole transcript. List the seconds you want to see:

- Any passage where the speaker shows, draws, writes, points ("here", "this one"), or works an example with numbers.
- At least one per chapter, and one for any stretch over a minute that has none. The speaker does not announce every diagram.
- Take the **end** of the passage, just before the next topic starts. Animations and slide builds are complete there.
- Budget two to three candidates per minute, up to about 40. Ask for them all in one batch.

## 3. Pull frames and look (about 15 s per batch)

```sh
mkdir -p cand
yt-dlp --ignore-config --no-warnings -f 'bv*[height<=1080][vcodec^=avc1]/bv*[height<=1080]' \
  -g -- "$URL" > .stream_url
printf '%s\n' 28 82 96 | xargs -P 8 -I{} sh -c \
  'ffmpeg -nostdin -loglevel error -ss {} -i "$(cat .stream_url)" -frames:v 1 -q:v 3 -y cand/$(printf %04d {}).jpg'
ffmpeg -nostdin -loglevel error -pattern_type glob -i 'cand/[0-9]*.jpg' \
  -vf 'scale=640:360,tile=4x3:padding=6:color=white' -q:v 4 -y cand/sheet_%d.jpg
```

- Look at the contact sheets, not each frame. Tiles are in time order, left to right, top to bottom.
- A tile that is mid-transition, or not yet showing what was described: ask again a few seconds later or earlier.
- Open a frame at full size only when you must quote small text from it.
- Stop after two rounds. A missing picture is better than a slow run.

## 4. Write `notes.md`

- Open with a short summary a reader could stop at.
- Follow the video's chapters, or your own sections if it has none. Give each a timestamp link (`&t=123s`).
- Put each image directly after the sentences it supports, with alt text that says what it shows. No gallery at the end.
- Keep an image only if it adds what the text cannot. Combine near-identical frames into one strip.
- Quote numbers from a frame only if you read them yourself. Say when a fact comes from the frame and not the narration.
- Do not describe visuals you did not look at.
- Consolidate: one statement per idea, tables for comparisons, a short list of terms at the end.
- Last line: which caption track you used and how many frames.

Copy kept frames into the folder at 1280 px wide, named `mm-ss-topic.jpg`:

```sh
ffmpeg -nostdin -loglevel error -i cand/0096.jpg -vf scale=1280:-2 -q:v 3 -y 01-36-topic.jpg
```

## 5. Finish

- Delete `.stream_url`. It is a signed address and it expires.
- Check that every image link in `notes.md` points at a file that exists.
- Tell the user the path, the frame count, and anything you could not see or read.
