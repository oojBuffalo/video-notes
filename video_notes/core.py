"""The fixed work for the skill: fetch the words and index sheets, pull frames, save notes."""
import configparser
import functools
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

EVERY = 10  # seconds between index tiles
COLS, ROWS = 6, 5  # six 10 s tiles make each index row one minute
SPAN = COLS * ROWS * EVERY  # seconds of video on one index sheet
MODEL_DIRS = ['/usr/local/share/whisper/models']
FIT = 'scale={0}:{1}:force_original_aspect_ratio=decrease,pad={0}:{1}:(ow-iw)/2:(oh-ih)/2'
SKILL = Path(__file__).resolve().parents[1] / 'skill' / 'SKILL.md'
CONFIG = Path.home() / '.config' / 'vnotes' / 'config'
OUTPUT_DEFAULTS = {'directory': '.', 'folder_template': 'notes-%(id)s', 'notes_template': 'notes.md'}
NAME_FIELDS = ('id', 'title', 'channel', 'uploader', 'upload_date')


class Fail(Exception):
    """An error to show the user as one plain line."""


def output_config():
    config = configparser.ConfigParser(interpolation=None)
    config['output'] = OUTPUT_DEFAULTS
    try:
        with CONFIG.open(encoding='utf-8') as stream:
            config.read_file(stream)
    except FileNotFoundError:
        return OUTPUT_DEFAULTS
    except (configparser.Error, UnicodeError, OSError) as error:
        raise Fail(f'Could not read {CONFIG}: {error}') from None
    settings = config['output']
    unknown = (set(config.sections()) - {'output'}) | (set(settings) - OUTPUT_DEFAULTS.keys())
    if unknown:
        raise Fail(f'Unknown setting in {CONFIG}: {", ".join(sorted(unknown))}')
    if not settings['directory']:
        raise Fail(f'{CONFIG}: directory is empty.')
    return settings


def output_name(settings, key, info):
    """Render one filename component, keeping separators in video metadata out of paths."""
    def substitute(match):
        if match[0] == '%%':
            return '%'
        field = match[1]
        if field not in NAME_FIELDS:
            raise Fail(f'{CONFIG}: {key} accepts %(field)s for {", ".join(NAME_FIELDS)}, or %% for a percent sign.')
        value = str(info.get(field) or 'NA')
        return re.sub(r'[/\\:*?"<>|\x00-\x1f\x7f]', '_', value).strip(' .') or 'NA'

    name = re.sub(r'%%|%\((\w+)\)s|%', substitute, settings[key])
    if not name.strip(' .') or re.search(r'[/\\\x00-\x1f\x7f]', name) or len(name.encode('utf-8')) > 255:
        raise Fail(f'{CONFIG}: {key} must produce a single filename of at most 255 bytes.')
    return name


def stamp(seconds):
    """Formats seconds as a transcript time.

    Args:
        seconds: Offset from the start of the video.

    Returns:
        `mm:ss` under an hour, `h:mm:ss` from one hour on.
    """
    seconds = int(seconds)
    hours, minutes, rest = seconds // 3600, seconds % 3600 // 60, seconds % 60
    return f'{hours}:{minutes:02}:{rest:02}' if hours else f'{minutes:02}:{rest:02}'


def parse_time(text):
    """Reads a time the agent typed.

    Args:
        text: Seconds, `mm:ss` or `h:mm:ss`, with or without square brackets.

    Returns:
        The time in whole seconds.

    Raises:
        Fail: If the text is not a time.
    """
    parts = text.strip('[]').split(':')
    if len(parts) > 3 or not all(part.isdigit() for part in parts):
        raise Fail(f'Not a time: {text!r}. Use seconds, mm:ss or h:mm:ss.')
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return seconds


def caption_lines(data):
    """Turns a json3 caption file into transcript lines.

    Args:
        data: Parsed json3 captions.

    Returns:
        One `[mm:ss] text` string per caption that has text.
    """
    lines = []
    for event in data.get('events', []):
        text = ''.join(seg.get('utf8', '') for seg in event.get('segs', []))
        text = html.unescape(' '.join(text.split()))
        if text:
            lines.append(f"[{stamp(event['tStartMs'] / 1000)}] {text}")
    return lines


def whisper_lines(data):
    """Turns whisper-cli JSON output into transcript lines.

    Args:
        data: Parsed `whisper-cli -oj` output.

    Returns:
        One `[mm:ss] text` string per segment that has text.
    """
    return [f"[{stamp(seg['offsets']['from'] / 1000)}] {seg['text'].strip()}"
            for seg in data.get('transcription', []) if seg['text'].strip()]


def pick_tracks(info):
    """Orders the caption tracks worth trying, best first.

    Human captions in the video's language come first, then the automatic
    track of the spoken words (`-orig`), then other automatic tracks in that
    language.

    Args:
        info: yt-dlp's info for the video.

    Returns:
        A list of `(label, language code)` pairs for tracks that offer json3.
    """
    # ponytail: only the video's own language (English when unknown) is tried;
    # anything else falls through to transcription. Add a --lang flag if needed.
    base = (info.get('language') or 'en').split('-')[0]
    found = []
    for kind, tracks in (('human', info.get('subtitles') or {}),
                         ('automatic', info.get('automatic_captions') or {})):
        langs = [lang for lang in tracks if lang.split('-')[0] == base]
        if kind == 'human':
            langs.sort(key=lambda lang: (lang != base, lang))
        else:
            langs.sort(key=lambda lang: (not lang.endswith('-orig'), lang))
        for lang in langs:
            if any(f.get('ext') == 'json3' for f in tracks[lang]):
                found.append((f'{lang} ({kind})', lang))
    return found


def pick_streams(formats, height):
    """Chooses the video streams to read frames from.

    Args:
        formats: yt-dlp's format list for the video.
        height: Tallest picture wanted, in pixels.

    Returns:
        Stream URLs to try in order: the best direct stream, then the best HLS
        stream. Empty when the video has no picture.
    """
    def best(protocols):
        video = [f for f in formats if f.get('url') and f.get('protocol') in protocols
                 and f.get('vcodec') not in (None, 'none')]
        fits = [f for f in video if (f.get('height') or 0) <= height]
        if fits:
            # avc1 decodes everywhere, so it wins a tie on height
            return max(fits, key=lambda f: (f.get('height') or 0, f['vcodec'].startswith('avc1')))['url']
        return min(video, key=lambda f: f.get('height') or 0)['url'] if video else None

    return [url for url in (best(('https', 'http')), best(('m3u8_native', 'm3u8'))) if url]


def run(command, timeout):
    """Runs a command without letting stream addresses reach the output.

    Args:
        command: Program and arguments.
        timeout: Seconds to wait before giving up.

    Returns:
        `(ok, stdout, error text)`. The error text has every URL removed.
    """
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, '', f'timed out after {timeout} s'
    return done.returncode == 0, done.stdout, scrub(done.stderr)


def scrub(text):
    """Removes addresses and anything shaped like an API key from text that will be shown.

    Args:
        text: An error message from a program or a server.

    Returns:
        The text with every URL and every `sk-...` key replaced.
    """
    return re.sub(r'\bsk-[\w*.-]+', '<key>', re.sub(r'https?://\S+', '<url>', text)).strip()


@functools.lru_cache
def newest_ytdlp():
    """Finds the newest yt-dlp on PATH; an old copy often fails on current sites.

    Returns:
        Path of the yt-dlp with the highest version.

    Raises:
        Fail: If there is no yt-dlp on PATH.
    """
    found = {}
    for folder in os.get_exec_path():
        path = os.path.join(folder, 'yt-dlp')
        if os.path.isfile(path) and os.access(path, os.X_OK):
            version = tuple(int(n) for n in re.findall(r'\d+', run([path, '--version'], 30)[1]))
            found.setdefault(version, path)
    if not found:
        raise Fail('yt-dlp is not installed or not on PATH.')
    return found[max(found)]


def ytdlp(*args, timeout=180):
    """Runs the newest yt-dlp, ignoring the user's yt-dlp config.

    Args:
        *args: Arguments after the fixed safe ones.
        timeout: Seconds to wait.

    Returns:
        `(ok, stdout, error text)` as from `run`.
    """
    return run([newest_ytdlp(), '--ignore-config', '--no-warnings', '--no-playlist', *args], timeout)


def video_info(url):
    """Asks yt-dlp for everything it knows about a video.

    Args:
        url: The video page.

    Returns:
        yt-dlp's info dictionary.

    Raises:
        Fail: If yt-dlp cannot read the page.
    """
    ok, out, error = ytdlp('-J', '--', url)
    if not ok:
        raise Fail(f'yt-dlp could not read {url}: {error[-300:]}')
    return json.loads(out)


def transcribe(url, language):
    """Downloads the audio and transcribes it with whisper-cli.

    Args:
        url: The video page.
        language: Spoken language code, or `auto`.

    Returns:
        Transcript lines.

    Raises:
        Fail: If whisper-cli or its model file is missing, or a step fails.
    """
    cli = shutil.which('whisper-cli')
    if not cli:
        raise Fail('No usable captions, and whisper-cli is not installed, so the audio cannot be transcribed.')
    model = os.environ.get('VNOTES_WHISPER_MODEL') or next(
        (str(path) for folder in MODEL_DIRS for path in sorted(Path(folder).glob('ggml-*.bin'))), '')
    if not os.path.isfile(model):
        raise Fail('No usable captions, and no whisper model file. Set VNOTES_WHISPER_MODEL to a '
                   f'ggml-*.bin file (looked in {", ".join(MODEL_DIRS)}).')
    with tempfile.TemporaryDirectory() as tmp:
        ok, _, error = ytdlp('-f', 'ba/b', '-x', '--audio-format', 'wav', '--postprocessor-args',
                             'ffmpeg:-ar 16000 -ac 1', '-o', f'{tmp}/audio.%(ext)s', '--', url, timeout=3600)
        if not ok:
            raise Fail(f'Could not download the audio: {error[-300:]}')
        whisper = [cli, '-m', model, '-f', f'{tmp}/audio.wav', '-l', language, '-oj', '-of', f'{tmp}/out']
        ok, _, error = run(whisper, 4 * 3600)
        if not ok:  # a sandbox can block the GPU; the CPU is slower but works
            print('whisper-cli failed on the GPU. Trying again on the CPU, which is slower.', file=sys.stderr)
            ok, _, error = run([*whisper, '-ng'], 12 * 3600)
        if not ok:
            raise Fail(f'whisper-cli failed: {error[-300:]}')
        return whisper_lines(json.loads(Path(tmp, 'out.json').read_text()))


def sheet_starts(length):
    """Lists where each index sheet starts.

    Args:
        length: Length of the video in seconds.

    Returns:
        One start time in seconds per sheet: `ceil(length / SPAN)` of them, so
        the last partial stretch of the video gets a sheet too.
    """
    return list(range(0, math.ceil(length), SPAN))


def index_sheets(info, out):
    """Writes low-resolution contact sheets covering the whole timeline.

    Args:
        info: yt-dlp's info for the video.
        out: The notes folder.

    Returns:
        Sheet paths in time order. Empty when the video has no picture.

    Raises:
        Fail: If the video has a picture but no stream could be read.
    """
    if not pick_streams(info.get('formats') or [], 240):
        return []
    folder, build = out / 'index', out / 'index.part'  # the old index stays until a new one is complete
    grid = f'fps=1/{EVERY},{FIT.format(320, 180)},tile={COLS}x{ROWS}:padding=4:color=white'
    with tempfile.TemporaryDirectory() as tmp:
        # yt-dlp downloads a small copy first. Reading the remote stream with ffmpeg is throttled:
        # one five-minute sheet of an 82-minute video took 150 s that way, and 0.2 s from a local file.
        Path(tmp, 'info.json').write_text(json.dumps(info))
        ok, _, error = ytdlp('--load-info-json', f'{tmp}/info.json', '-f',
                             'bv*[height<=240][vcodec^=avc1]/bv*[height<=240]/wv*/w',
                             '-o', f'{tmp}/video.%(ext)s', timeout=3600)
        videos = [path for path in Path(tmp).glob('video.*') if path.suffix != '.part']
        if not ok or not videos:
            raise Fail(f'Could not download the low-resolution video for the index: {error[-300:]}')
        try:  # the file's own length decides the sheets; the site's figure is a rounded fallback
            length = float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                '-of', 'csv=p=0', str(videos[0])], 120)[1])
        except ValueError:
            length = info.get('duration')
        if not length:
            raise Fail('Could not find out how long the video is, so the index cannot be built.')
        shutil.rmtree(build, ignore_errors=True)
        build.mkdir()

        def sheet(start):
            target = build / f'index-{start // 60:03}m.jpg'
            ok, _, error = run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-ss', str(start), '-t', str(SPAN),
                                '-i', str(videos[0]), '-vf', grid, '-frames:v', '1', '-update', '1', '-q:v', '4',
                                '-y', str(target)], 600)
            good = ok and target.exists() and target.stat().st_size
            return (target.name, '') if good else (None, error or 'no picture came back')

        with ThreadPoolExecutor(8) as pool:
            results = list(pool.map(sheet, sheet_starts(length)))
    failed = [error for name, error in results if not name]
    # ponytail: a last sheet with less than one frame of video comes back empty and fails the index
    if failed or len(results) != math.ceil(length / SPAN):
        shutil.rmtree(build, ignore_errors=True)
        raise Fail(f'Could not build {len(failed)} of {math.ceil(length / SPAN)} index sheets: '
                   f'{(failed or ["wrong sheet count"])[0][-300:]}')
    shutil.rmtree(folder, ignore_errors=True)
    build.rename(folder)
    return [folder / name for name, _ in results]


def fetch(url, out=None, force_transcribe=False):
    """Writes meta.json, transcript.txt and the index sheets for a video.

    Args:
        url: The video page.
        out: Exact folder to write into. When omitted, use the configured directory and folder template.
        force_transcribe: Transcribe the audio even when captions exist.

    Returns:
        The folder written.

    Raises:
        Fail: If the video, its words or its index cannot be fetched.
    """
    settings = output_config()
    info = video_info(url)
    notes_file = output_name(settings, 'notes_template', info)
    if not notes_file.lower().endswith('.md') or notes_file.casefold() in {'draft.md', 'plan.md', 'notes.rejected.md'}:
        raise Fail(f'{CONFIG}: notes_template must name a Markdown (.md) file other than draft.md, plan.md or notes.rejected.md.')
    if out is None:
        out = Path(settings['directory']).expanduser() / output_name(settings, 'folder_template', info)
        if out.is_symlink():
            raise Fail(f'The configured video folder {out} is a symlink. Choose a different folder.')
        if out.is_dir() and any(out.iterdir()):
            try:
                previous = json.loads((out / 'meta.json').read_text())
            except (OSError, ValueError):
                previous = {}
            if not isinstance(previous, dict) or previous.get('id') != info['id']:
                raise Fail(f'{out} already contains other files. Choose a unique folder_template, e.g. notes-%(id)s.')
    else:
        out = Path(out).expanduser()
    if (out / notes_file).is_symlink():
        raise Fail(f'The notes path {out / notes_file} is a symlink. Choose a different notes filename.')
    out.mkdir(parents=True, exist_ok=True)
    lines, source, problem = [], None, ''
    tracks = [] if force_transcribe else pick_tracks(info)
    with tempfile.TemporaryDirectory() as tmp:
        # yt-dlp downloads the captions: a plain HTTP read of a long track gets cut off
        Path(tmp, 'info.json').write_text(json.dumps(info))
        for source, lang in tracks:
            problem = ytdlp('--load-info-json', f'{tmp}/info.json', '--skip-download', '--write-subs',
                            '--write-auto-subs', '--sub-langs', lang, '--sub-format', 'json3', '-o', f'{tmp}/cap')[2]
            try:
                lines = caption_lines(json.loads(Path(tmp, f'cap.{lang}.json3').read_text()))
            except (OSError, ValueError):
                continue
            if lines:
                break
    if not lines:
        if tracks:
            print(f'Captions exist ({tracks[0][0]}) but could not be downloaded: {problem[-200:]}', file=sys.stderr)
        print('Transcribing the audio. This takes longer than reading captions.', file=sys.stderr)
        lines = transcribe(url, (info.get('language') or 'auto').split('-')[0])
        source = 'whisper-cli transcription'
        if not lines:
            raise Fail('The audio was transcribed but no speech was found, so there are no words to make notes from.')
    meta = {key: info.get(key) for key in
            ('id', 'title', 'uploader', 'duration', 'upload_date', 'chapters', 'description')}
    meta.update(url=info.get('webpage_url') or url, words=source, notes_file=notes_file)
    (out / 'meta.json').write_text(json.dumps(meta, indent=1, ensure_ascii=False) + '\n')
    (out / 'transcript.txt').write_text('\n'.join(lines) + '\n')
    print(f'{out}/meta.json')
    print(f'Notes path: {out / notes_file}')
    print(f'{out}/transcript.txt  {len(lines)} lines from {source}')
    sheets = index_sheets(info, out)
    if not sheets:
        print('No picture in this video, so no index sheets.')
        return out
    print(f'{len(sheets)} index sheets: one tile every {EVERY} s, {COLS} tiles per row, so each row is one minute.')
    for n, sheet in enumerate(sheets):
        print(f'{sheet}  starts {stamp(n * SPAN)}')
    return out


def frames(out, times, url=None):
    """Writes full-size frames at the given times, plus contact sheets.

    Args:
        out: A folder that `fetch` has filled.
        times: Times as typed: seconds, `mm:ss` or `h:mm:ss`.
        url: The video page. Defaults to the one recorded in meta.json.

    Returns:
        Process exit code: 0 when every frame arrived, 1 otherwise.

    Raises:
        Fail: If the folder was not fetched, a time is malformed, or the video
            has no picture.
    """
    out = Path(out)
    try:
        meta = json.loads((out / 'meta.json').read_text())
        url = url or meta['url']
    except (OSError, ValueError, KeyError):
        raise Fail(f'{out}/meta.json is missing or unreadable. Run `vnotes fetch URL {out}` first.') from None
    seconds = sorted({parse_time(text) for text in times})
    length = meta.get('duration')
    if length and seconds[-1] >= length:  # ffmpeg would return the last frame for these
        raise Fail(f'{stamp(seconds[-1])} is past the end of the video ({stamp(length)}).')
    # ponytail: the signed stream address is resolved again on every call (about
    # 6 s) and never written to disk. Cache it if that wait starts to matter.
    streams = pick_streams(video_info(url).get('formats') or [], 1080)
    if not streams:
        raise Fail('This video has no picture to take frames from.')
    folder = out / 'frames'
    folder.mkdir(exist_ok=True)

    def grab(second):
        path = folder / f"{stamp(second).replace(':', '-')}.jpg"
        part = path.with_suffix('.part.jpg')  # an existing frame is replaced only by a good new one
        errors = []
        for stream in streams * 3:  # stream reads drop at random; a retry usually works
            ok, _, error = run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-ss', str(second), '-i', stream,
                                '-frames:v', '1', '-update', '1', '-q:v', '2', '-y', str(part)], 90)
            if ok and part.exists() and part.stat().st_size:
                os.replace(part, path)
                return path, ''
            errors.append(error.splitlines()[-1] if error else 'no picture came back')
        part.unlink(missing_ok=True)
        return None, '; '.join(dict.fromkeys(errors))

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(grab, seconds))
    got = [(second, path) for second, (path, _) in zip(seconds, results) if path]
    missed = [f'{stamp(second)} ({error})' for second, (path, error) in zip(seconds, results) if not path]
    first = len(list(folder.glob('sheet-*.jpg'))) + 1
    with tempfile.TemporaryDirectory() as tmp:
        for n, (_, path) in enumerate(got):
            os.symlink(path.resolve(), f'{tmp}/{n:04}.jpg')
        ok, _, error = run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-start_number', '0',
                            '-i', f'{tmp}/%04d.jpg', '-vf', f'{FIT.format(640, 360)},tile=4x3:padding=6:color=white',
                            '-q:v', '3', '-start_number', str(first), str(folder / 'sheet-%02d.jpg')], 300)
    if got and not ok:
        print(f'Could not build a contact sheet ({error[-200:]}); the frames are still there.')
    for n in range(0, len(got) if ok else 0, 12):
        print(f'{folder}/sheet-{first + n // 12:02}.jpg  tiles in time order, left to right, top to bottom:')
        for row in range(n, min(n + 12, len(got)), 4):
            print('  ' + '  '.join(stamp(second) for second, _ in got[row:row + 4]))
    if got:
        print(f'Full-size frames are in {folder}/, named by time, for example {got[0][1].name}.')
    for line in missed:
        print(f'Could not get {line}')
    return 1 if missed else 0


def local_images(text):
    """Lists the local file that each Markdown image in the text points at.

    Args:
        text: Markdown.

    Returns:
        The complete destination of every image, inline or reference-style,
        leaving out destinations with a URL scheme such as `https:`.
    """
    # ponytail: alt text with a `]` inside it, and a destination with a `)` inside it, are not parsed.
    # Use a Markdown parser if notes ever need those.
    place = r'(?:<([^<>\n]*)>|([^\s<)][^\s)]*))'  # `<a path with spaces>` or a path without spaces
    found = [angled or plain for angled, plain in re.findall(r'!\[[^\]]*\]\(\s*' + place, text)]
    defined = {label.strip().lower(): angled or plain
               for label, angled, plain in re.findall(r'^ {0,3}\[([^\]\n]+)\]:\s*' + place, text, re.M)}
    for alt, label in re.findall(r'!\[([^\]]*)\](?:\[([^\]]*)\])?(?!\()', text):  # ![alt][label], ![alt][], ![alt]
        found.append(defined.get((label or alt).strip().lower()))
    return [target for target in found if target and not re.match(r'[a-z][a-z0-9+.-]*:', target, re.I)]


def save_notes(out, text, filename='notes.md'):
    """Saves the notes, unless they link to images that are not files inside the notes folder.

    Args:
        out: The notes folder.
        text: The complete notes.
        filename: The notes filename selected during fetch.

    Returns:
        The image links that point at no file, or at one outside the folder.
        Empty when the notes were saved.
    """
    root = out.resolve()  # a link must not reach outside the folder, even to a file that exists
    missing = sorted({target for target in local_images(text)
                      if not ((root / target).resolve().is_relative_to(root) and (root / target).is_file())})
    if not missing:
        part = out / 'notes.md.part'
        part.write_text(text + '\n')
        os.replace(part, out / filename)
        print(out / filename)
    return missing
