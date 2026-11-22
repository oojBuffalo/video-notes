"""Checks for the logic in vnotes that does not need the network."""
import contextlib
import http.server
import io
import json
import math
import tempfile
import threading
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from unittest.mock import patch

loader = SourceFileLoader('vnotes', str(Path(__file__).resolve().parents[1] / 'vnotes'))
vnotes = module_from_spec(spec_from_loader('vnotes', loader))
loader.exec_module(vnotes)


def track(*exts):
    """Builds a caption track entry with one URL per format."""
    return [{'ext': ext, 'url': f'u-{ext}'} for ext in exts]


class TimeTests(unittest.TestCase):
    def test_stamp_switches_format_at_one_hour(self):
        self.assertEqual(vnotes.stamp(82.9), '01:22')
        self.assertEqual(vnotes.stamp(3599), '59:59')
        self.assertEqual(vnotes.stamp(3682), '1:01:22')

    def test_parse_time_reads_every_form_the_transcript_uses(self):
        self.assertEqual(vnotes.parse_time('82'), 82)
        self.assertEqual(vnotes.parse_time('1:22'), 82)
        self.assertEqual(vnotes.parse_time('[01:22]'), 82)
        self.assertEqual(vnotes.parse_time('1:01:22'), 3682)
        for bad in ('', '1:2:3:4', '1.5', 'abc', '-3'):
            with self.assertRaises(vnotes.Fail):
                vnotes.parse_time(bad)

    def test_stamp_and_parse_time_round_trip(self):
        for seconds in (0, 59, 60, 3599, 3600, 4902):
            self.assertEqual(vnotes.parse_time(vnotes.stamp(seconds)), seconds)


class IndexTests(unittest.TestCase):
    def test_sheet_count_is_the_length_over_five_minutes_rounded_up(self):
        self.assertEqual(vnotes.sheet_starts(591), [0, 300])
        self.assertEqual(vnotes.sheet_starts(600), [0, 300])
        self.assertEqual(vnotes.sheet_starts(600.4), [0, 300, 600])
        self.assertEqual(vnotes.sheet_starts(3), [0])
        for length in (1, 299, 300, 301, 4902, 10800.5):
            self.assertEqual(len(vnotes.sheet_starts(length)), math.ceil(length / 300))
        self.assertEqual(vnotes.sheet_starts(4902)[-1], 4800)  # the final 102 s get their own sheet


class CaptionTests(unittest.TestCase):
    def test_caption_lines_join_words_and_skip_empty_events(self):
        data = {'events': [
            {'tStartMs': 1230, 'segs': [{'utf8': 'A &amp;'}, {'utf8': ' B\nC'}]},
            {'tStartMs': 2000, 'segs': [{'utf8': '\n'}]},
            {'tStartMs': 3000},
            {'tStartMs': 3_725_000, 'segs': [{'utf8': 'late'}]},
        ]}
        self.assertEqual(vnotes.caption_lines(data), ['[00:01] A & B C', '[1:02:05] late'])

    def test_whisper_lines_use_segment_offsets(self):
        data = {'transcription': [{'offsets': {'from': 61_000, 'to': 63_000}, 'text': ' Hello.'},
                                  {'offsets': {'from': 63_000, 'to': 64_000}, 'text': '  '}]}
        self.assertEqual(vnotes.whisper_lines(data), ['[01:01] Hello.'])

    def test_human_captions_beat_automatic_and_spoken_words_beat_translation(self):
        info = {'language': 'en-US',
                'subtitles': {'en-GB': track('json3'), 'en': track('vtt', 'json3'), 'fr': track('json3')},
                'automatic_captions': {'ar-orig': track('json3'), 'en': track('json3'),
                                       'en-orig': track('json3')}}
        self.assertEqual([label for label, _ in vnotes.pick_tracks(info)],
                         ['en (human)', 'en-GB (human)', 'en-orig (automatic)', 'en (automatic)'])
        self.assertEqual(vnotes.pick_tracks(info)[0][1], 'en')

    def test_tracks_without_json3_or_in_another_language_are_skipped(self):
        info = {'subtitles': {'en': track('vtt'), 'de': track('json3')}, 'automatic_captions': None}
        self.assertEqual(vnotes.pick_tracks(info), [])


class StreamTests(unittest.TestCase):
    formats = [
        {'url': 'audio', 'protocol': 'https', 'vcodec': 'none'},
        {'url': 'd240', 'protocol': 'https', 'vcodec': 'avc1.4', 'height': 240},
        {'url': 'd1080vp9', 'protocol': 'https', 'vcodec': 'vp9', 'height': 1080},
        {'url': 'd1080avc', 'protocol': 'https', 'vcodec': 'avc1.6', 'height': 1080},
        {'url': 'd2160', 'protocol': 'https', 'vcodec': 'vp9', 'height': 2160},
        {'url': 'h720', 'protocol': 'm3u8_native', 'vcodec': 'avc1.4', 'height': 720},
        {'url': 'h1080', 'protocol': 'm3u8_native', 'vcodec': 'vp09.0', 'height': 1080},
    ]

    def test_direct_stream_comes_before_hls_and_respects_the_height(self):
        self.assertEqual(vnotes.pick_streams(self.formats, 1080), ['d1080avc', 'h1080'])
        self.assertEqual(vnotes.pick_streams(self.formats, 240), ['d240', 'h720'])

    def test_no_picture_means_no_streams(self):
        self.assertEqual(vnotes.pick_streams(self.formats[:1], 1080), [])


VIDEO = {'id': 'x', 'duration': 100,
         'formats': [{'url': 's', 'protocol': 'https', 'vcodec': 'avc1.6', 'height': 1080}]}


class OutputConfigTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.config = self.root / '.config/vnotes/config'
        self.config.parent.mkdir(parents=True)
        self.enterContext(patch.object(vnotes, 'CONFIG', self.config))
        self.enterContext(patch.dict(vnotes.os.environ, HOME=str(self.root)))
        self.enterContext(contextlib.chdir(self.root))
        self.log = self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.errors = self.enterContext(contextlib.redirect_stderr(io.StringIO()))
        self.info = {'id': 'x', 'title': '../A/B'}
        self.enterContext(patch.object(vnotes, 'video_info', return_value=self.info))
        self.enterContext(patch.object(vnotes, 'transcribe', return_value=['[00:00] Hello']))
        self.enterContext(patch.object(vnotes.shutil, 'which', return_value='/fake/tool'))

    def cli(self, *args):
        with patch.object(vnotes.sys, 'argv', ['vnotes', *args]):
            return vnotes.main()

    def test_missing_config_preserves_layout(self):
        self.assertEqual(self.cli('fetch', 'url'), 0)
        self.assertEqual(json.loads(Path('notes-x/meta.json').read_text())['notes_file'], 'notes.md')

    def test_skill_fetch_headless_and_direct_use_the_same_paths(self):
        self.config.write_text('[output]\ndirectory = ~/Study Notes\nfolder_template = %(id)s - %(title)s\n'
                               'notes_template = %(upload_date)s %(title)s 100%%.md\n')
        folder = self.root / 'Study Notes/x - _A_B'
        filename = 'NA _A_B 100%.md'
        self.assertEqual(self.cli('fetch', 'url'), 0)
        self.assertIn(f'Notes path: {folder / filename}', self.log.getvalue())
        self.assertEqual(json.loads((folder / 'meta.json').read_text())['notes_file'], filename)
        with patch.object(vnotes, 'ask', return_value='# Headless'):
            self.assertEqual(self.cli('notes', 'url'), 0)
        self.assertEqual((folder / filename).read_text(), '# Headless\n')
        with patch.object(vnotes, 'connect'), patch.object(vnotes, 'send', side_effect=['outline', 'draft', '# Direct']):
            self.assertEqual(self.cli('direct', 'url', '--via', 'openai', '--out', 'custom folder'), 0)
        self.assertTrue((Path('custom folder') / filename).read_text().startswith('# Direct\n'))
        self.assertEqual(self.cli('fetch', 'url', 'exact'), 0)
        self.assertTrue(Path('exact/meta.json').is_file())

    def test_bad_config_reports_the_file_and_writes_nothing(self):
        for contents in ('[output', '[output]\noutput_dir = typo', '[output]\nfolder_template = ..',
                         '[output]\nfolder_template = ../%(id)s', '[output]\nnotes_template = DRAFT.md',
                         '[output]\nnotes_template = %(typo)s.md'):
            with self.subTest(contents=contents):
                self.config.write_text(contents)
                self.assertEqual(self.cli('fetch', 'url'), 1)
                self.assertIn(str(self.config), self.errors.getvalue())
                self.assertFalse(Path('notes-x').exists())

    def test_matching_titles_do_not_overwrite_another_video(self):
        self.config.write_text('[output]\nfolder_template = %(title)s')
        self.assertEqual(self.cli('fetch', 'first'), 0)
        self.info['id'] = 'second'
        self.assertEqual(self.cli('fetch', 'second'), 1)
        self.assertEqual(json.loads(Path('_A_B/meta.json').read_text())['id'], 'x')


class FailureTests(unittest.TestCase):
    """What must survive, or be refused, when a step fails."""

    def setUp(self):
        self.out = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))
        self.enterContext(patch.object(vnotes, 'video_info', return_value=VIDEO))
        self.enterContext(patch.object(vnotes, 'CONFIG', self.out / 'missing-config'))

    def test_failed_frame_refresh_keeps_the_frame_the_notes_use(self):
        (self.out / 'meta.json').write_text(json.dumps({'url': 'u', 'duration': 100}))
        (self.out / 'frames').mkdir()
        (self.out / 'frames' / '00-10.jpg').write_bytes(b'old')
        with patch.object(vnotes, 'run', return_value=(False, '', 'boom')):
            self.assertEqual(vnotes.frames(self.out, ['10']), 1)
        self.assertEqual((self.out / 'frames' / '00-10.jpg').read_bytes(), b'old')

    def test_failed_index_rebuild_keeps_the_old_index(self):
        (self.out / 'index').mkdir()
        (self.out / 'index' / 'index-000m.jpg').write_bytes(b'old')
        with patch.object(vnotes, 'run', return_value=(False, '', 'boom')), self.assertRaises(vnotes.Fail):
            vnotes.index_sheets(VIDEO, self.out)
        self.assertEqual([path.name for path in self.out.rglob('*.jpg')], ['index-000m.jpg'])

    def test_empty_transcription_is_refused(self):
        with patch.object(vnotes, 'transcribe', return_value=[]), self.assertRaisesRegex(vnotes.Fail, 'no speech'):
            vnotes.fetch('u', self.out)
        self.assertFalse((self.out / 'transcript.txt').exists())


class LinkTests(unittest.TestCase):
    def test_every_local_image_target_is_checked_and_web_images_are_not(self):
        out = Path(self.enterContext(tempfile.TemporaryDirectory()), 'notes')
        out.mkdir()
        for name in ('here.jpg', 'with space.jpg', '../outside.jpg'):
            (out / name).write_bytes(b'jpg')
        beyond = str((out / '../outside.jpg').resolve())  # exists, but not inside the notes folder
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        text = ('![a](here.jpg) ![b](here.jpg "a title") ![s](<with space.jpg>) ![r][Ok] ![ok] '
                '![web](https://x.test/far.png) [a plain link](other.jpg) ![not an image]\n'
                '![c](gone.png) ![d](titled.jpg "a title") ![e](<frames/missing image.jpg>) ![f](frames/missing.svg) '
                f'![g](here.jpg.backup) ![h][ref] ![logo][] ![up](../outside.jpg) ![abs]({beyond})\n\n'
                '[ok]: here.jpg\n[ref]: defined.webp "a title"\n[Logo]: <logo file.png>\n')
        self.assertEqual(vnotes.save_notes(out, text), sorted([
            '../outside.jpg', beyond, 'defined.webp', 'frames/missing image.jpg', 'frames/missing.svg', 'gone.png', 'here.jpg.backup',
            'logo file.png', 'titled.jpg']))
        self.assertFalse((out / 'notes.md').exists())
        self.assertEqual(vnotes.save_notes(out, text.splitlines()[0]), [])
        self.assertTrue((out / 'notes.md').exists())


class HeadlessTests(unittest.TestCase):
    """The headless loop: frames are served first, and broken notes are never saved."""

    def setUp(self):
        self.out = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        (self.out / 'meta.json').write_text('{}')
        (self.out / 'transcript.txt').write_text('[00:10] words\n')
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(patch.object(vnotes.shutil, 'which', return_value='/bin/agent'))
        self.enterContext(patch.object(vnotes, 'fetch', return_value=self.out))

    def pull(self, out, times, url):
        """Stands in for `frames`: records the request and writes the frame."""
        self.asked = (times, url)
        (out / 'frames').mkdir(exist_ok=True)
        (out / 'frames' / '00-10.jpg').write_bytes(b'jpg')

    def test_a_frame_request_is_served_before_notes_are_saved(self):
        replies = ['FRAMES: 10\nthe diagram at 0:10 matters', '# Notes\n\n![a diagram](frames/00-10.jpg)']
        with patch.object(vnotes, 'ask', side_effect=replies) as ask, patch.object(vnotes, 'frames', self.pull):
            vnotes.notes('trusted-url', None, 'claude', None)
        self.assertEqual(self.asked, (['10'], 'trusted-url'))
        self.assertIn('the diagram at 0:10 matters', ask.call_args_list[1].args[1])
        self.assertEqual((self.out / 'notes.md').read_text(), replies[1] + '\n')

    def test_notes_linking_to_missing_images_are_not_saved(self):
        with patch.object(vnotes, 'ask', return_value='![gone](frames/09-99.jpg)') as ask, \
                self.assertRaises(vnotes.Fail):
            vnotes.notes('u', None, 'codex', None)
        self.assertFalse((self.out / 'notes.md').exists())
        self.assertIn('frames/09-99.jpg', ask.call_args_list[1].args[1])


class RequestTests(unittest.TestCase):
    """The three request shapes carry the same instruction, text and picture."""

    def setUp(self):
        self.image = Path(self.enterContext(tempfile.TemporaryDirectory()), 'a.jpg')
        self.image.write_bytes(b'jpg')  # base64: anBn

    def test_responses_body_for_the_chatgpt_login(self):
        body = vnotes.responses_body('m', 'rules', ['look', self.image])
        self.assertEqual((body['model'], body['stream'], body['store']), ('m', True, False))
        self.assertEqual(body['input'][0], {'type': 'message', 'role': 'developer',
                                            'content': [{'type': 'input_text', 'text': 'rules'}]})
        self.assertEqual(body['input'][1]['content'], [
            {'type': 'input_text', 'text': 'look'},
            {'type': 'input_image', 'image_url': 'data:image/jpeg;base64,anBn'}])
        self.assertNotIn('tools', body)

    def test_chat_body_for_openai_compatible_servers(self):
        body = vnotes.chat_body('m', 'rules', ['look', self.image])
        self.assertEqual(body['messages'][0], {'role': 'system', 'content': 'rules'})
        self.assertEqual(body['messages'][1]['content'], [
            {'type': 'text', 'text': 'look'},
            {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,anBn'}}])
        self.assertNotIn('tools', body)

    def test_messages_body_for_anthropic(self):
        body = vnotes.messages_body('m', 'rules', ['look', self.image])
        self.assertEqual((body['system'], body['stream']), ('rules', True))
        self.assertEqual(body['messages'], [{'role': 'user', 'content': [
            {'type': 'text', 'text': 'look'},
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': 'anBn'}}]}])
        self.assertNotIn('tools', body)

    def test_reply_text_reads_all_three_streams(self):
        streams = [
            [b'event: x\n', b'data: {"type":"response.output_text.delta","delta":"Hel"}\n',
             b'data: {"type":"response.output_text.delta","delta":"lo"}\n', b'data: {"type":"response.completed"}\n'],
            [b': keep-alive\n', b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n',
             b'data: {"choices":[{"delta":{"content":"lo"},"finish_reason":"stop"}]}\n', b'data: [DONE]\n'],
            [b'data: {"type":"content_block_delta","delta":{"type":"thinking_delta","thinking":"hm"}}\n',
             b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}\n',
             b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n'],
        ]
        for stream in streams:
            self.assertEqual(vnotes.reply_text(stream), 'Hello')

    def test_a_cut_off_refused_or_failed_reply_is_an_error(self):
        for line in (b'data: {"choices":[{"delta":{"content":"Hel"},"finish_reason":"length"}]}\n',
                     b'data: {"type":"message_delta","delta":{"stop_reason":"refusal"}}\n',
                     b'data: {"type":"response.failed","response":{"error":{"message":"boom"}}}\n',
                     b'data: {"type":"response.completed"}\n'):
            with self.assertRaises(vnotes.Fail):
                vnotes.reply_text([b'data: {"type":"response.output_text.delta","delta":""}\n', line])

    def test_a_stream_without_its_end_mark_is_a_dropped_connection(self):
        for line in (b'data: {"type":"response.output_text.delta","delta":"Hel"}\n',
                     b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n',
                     b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hel"}}\n'):
            with self.assertRaises(ConnectionError):
                vnotes.reply_text([line])


GOOD = (b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Red"}}\n\n'
        b'data: {"type":"message_stop"}\n\n')


class FakeServer(http.server.BaseHTTPRequestHandler):
    """Stands in for Anthropic: answers each request with the next `(status, body)` in `script`."""

    script, seen = [], []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['content-length'])))
        self.seen.append((self.headers, body))  # header names compare without case
        status, reply = self.script.pop(0)
        self.send_response(status)
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, *args):
        pass


class SendTests(unittest.TestCase):
    def setUp(self):
        try:
            server = http.server.HTTPServer(('127.0.0.1', 0), FakeServer)
        except PermissionError:
            self.skipTest('this sandbox does not allow listening on a local port')
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        FakeServer.seen = []
        self.enterContext(patch.dict(vnotes.URLS, anthropic=f'http://127.0.0.1:{server.server_port}/v1/messages'))
        self.enterContext(patch.dict(vnotes.os.environ, ANTHROPIC_API_KEY='hunter2-token'))
        self.enterContext(patch.object(vnotes.time, 'sleep'))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def send(self, *script):
        FakeServer.script = list(script)
        return vnotes.send('anthropic', 'claude-opus-5-5', 'rules', ['look'])

    def test_send_signs_the_request_retries_when_busy_and_returns_the_reply(self):
        self.assertEqual(self.send((529, b'{"error":{"message":"busy"}}'), (200, GOOD)), 'Red')
        headers, body = FakeServer.seen[1]
        self.assertEqual((headers['x-api-key'], headers['anthropic-version']), ('hunter2-token', '2026-10-21'))
        self.assertEqual((body['system'], body['messages'][0]['content'][0]['text']), ('rules', 'look'))
        self.assertEqual(len(FakeServer.seen), 2)

    def test_a_refused_request_fails_once_without_showing_the_key_or_an_address(self):
        with self.assertRaises(vnotes.Fail) as caught:
            self.send((404, b'no such model at https://x.test/y; you sent hunter2-token and sk-ant-other'))
        self.assertIn('404', str(caught.exception))
        for secret in ('hunter2', 'sk-ant', 'x.test'):
            self.assertNotIn(secret, str(caught.exception))
        self.assertEqual(len(FakeServer.seen), 1)

    def test_an_error_inside_the_stream_does_not_show_the_key_either(self):
        for kind, tries in (('invalid_request_error', 1), ('overloaded_error', 4)):
            FakeServer.seen = []
            echo = (200, b'data: {"type":"error","error":{"type":"%s","message":"bad key hunter2-token"}}\n\n'
                    % kind.encode())
            with self.assertRaises(vnotes.Fail) as caught:
                self.send(*[echo] * tries)
            self.assertIn(kind, str(caught.exception))
            self.assertNotIn('hunter2', str(caught.exception))
            self.assertEqual(len(FakeServer.seen), tries)

    def test_a_passing_fault_or_a_cut_off_stream_is_tried_again(self):
        overloaded = b'data: {"type":"error","error":{"type":"overloaded_error","message":"busy"}}\n\n'
        self.assertEqual(self.send((200, overloaded), (200, GOOD.split(b'\n\n')[0] + b'\n\n'), (200, GOOD)), 'Red')
        self.assertEqual(len(FakeServer.seen), 3)


class DirectTests(unittest.TestCase):
    def test_frame_lines_read_times_and_ignore_everything_else(self):
        plan = ('OUTLINE\n1. Intro | not a frame\n| 12 | a table row |\n\nFRAMES\n'
                '01:22 | the loop diagram\n- `0:45 | title formula`\n[1:01:22] | late chart\n01:22 | a repeat\n')
        self.assertEqual(vnotes.frame_lines(plan),
                         [(45, 'title formula'), (82, 'the loop diagram'), (3682, 'late chart')])

    def test_missing_credentials_stop_the_run_before_the_fetch(self):
        with patch.dict(vnotes.os.environ, clear=True), patch.object(vnotes, 'fetch') as fetch:
            for via, model in (('openai', None), ('openrouter', None), ('anthropic', None), ('endpoint', 'm')):
                with self.assertRaises(vnotes.Fail):
                    vnotes.direct('u', None, via, model, None)
            with patch.object(vnotes, 'CODEX_AUTH', Path('/nonexistent/auth.json')), self.assertRaises(vnotes.Fail):
                vnotes.direct('u', None, 'chatgpt', None, None)
        fetch.assert_not_called()

    def run_direct(self, replies):
        """Runs `direct` on a fetched folder with a fake model and a fake frame puller."""
        out = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        (out / 'meta.json').write_text('{"duration": 100, "url": "u", "words": "en (human)"}')
        (out / 'transcript.txt').write_text('[00:10] words\n')
        (out / 'index').mkdir()
        (out / 'index' / 'index-000m.jpg').write_bytes(b'jpg')
        calls, replies = [], iter(replies)

        def send(via, model, system, parts):
            calls.append(parts)
            return next(replies)

        def pull(folder, times, url):
            calls.append((times, url))
            (folder / 'frames').mkdir()
            (folder / 'frames' / '00-10.jpg').write_bytes(b'jpg')
            print('Could not get 00:50 (boom)')

        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        with patch.object(vnotes, 'fetch', return_value=out), patch.object(vnotes, 'send', send), \
                patch.object(vnotes, 'frames', pull), patch.dict(vnotes.os.environ, OPENAI_API_KEY='k'):
            try:
                vnotes.direct('trusted-url', 'focus on x', 'openai', None, None)
            except vnotes.Fail as error:
                calls.append(error)
        return out, calls

    def test_steps_run_in_order_plan_frames_write_check_save(self):
        out, (plan, pulled, write, check) = self.run_direct([
            'OUTLINE\n1. Intro\nFRAMES\n00:10 | the diagram\n00:50 | a chart\n02:00 | past the end\n',
            '# Draft with no image', '# Notes\n\n![d](frames/00-10.jpg)'])
        self.assertEqual(plan[1:], ['Index sheet index-000m.jpg, starting at 00:00:', out / 'index' / 'index-000m.jpg'])
        self.assertIn('focus on x', plan[0])
        self.assertEqual(pulled, (['10', '50'], 'trusted-url'))
        self.assertEqual(write[1:], ['frames/00-10.jpg at 00:10. Planned to show: the diagram',
                                     out / 'frames' / '00-10.jpg'])
        self.assertIn('Could not get 00:50', write[0])
        self.assertIn('# Draft with no image', check[0])
        self.assertEqual(check[1:], write[1:])  # every pulled frame goes to the check, linked or not
        self.assertEqual((out / 'notes.md').read_text(), (
            '# Notes\n\n![d](frames/00-10.jpg)\n\n---\n\nWords: en (human). Index sheets sent to the model: 1. '
            'Frames pulled and sent: 1. Written by gpt-6.2-sol via openai with `vnotes direct`.\n'))

    def test_checked_notes_with_a_broken_image_link_are_not_saved(self):
        out, calls = self.run_direct(['FRAMES\n00:10 | the diagram\n', '# Draft', '![gone](frames/09-99.jpg)'])
        self.assertIn('frames/09-99.jpg', str(calls[-1]))
        self.assertFalse((out / 'notes.md').exists())


if __name__ == '__main__':
    unittest.main()
