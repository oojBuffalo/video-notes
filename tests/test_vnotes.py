"""Checks for the logic in vnotes that does not need the network."""
import contextlib
import io
import json
import tempfile
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
        self.assertEqual(vnotes.pick_tracks(info)[0][1], 'u-json3')

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


class FailureTests(unittest.TestCase):
    """What must survive, or be refused, when a step fails."""

    def setUp(self):
        self.out = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))
        self.enterContext(patch.object(vnotes, 'video_info', return_value=VIDEO))

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


if __name__ == '__main__':
    unittest.main()
