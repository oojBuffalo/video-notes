import unittest
from unittest.mock import patch
import io
import urllib.error
from vnotes import transcript, validate, request_json, main, codex_schema, group_chapters

class GroundingTests(unittest.TestCase):
    def test_short_chapters_group_without_losing_coverage(self):
        chapters = [{'title':str(i), 'start_time':i*40, 'end_time':(i+1)*40} for i in range(29)]
        groups = group_chapters(chapters, 1160)
        self.assertLessEqual(len(groups), 6)
        self.assertEqual([c for g in groups for c in g['subchapters']], chapters)
        self.assertEqual(groups[0]['start_time'], 0)
        self.assertEqual(groups[-1]['end_time'], 1160)
        self.assertTrue(all(a['end_time'] == b['start_time'] for a,b in zip(groups,groups[1:])))
        self.assertEqual(group_chapters(chapters[:4], 160), chapters[:4])

    def test_missing_key_fails_before_creating_output(self):
        with patch.dict('os.environ', {}, clear=True), patch('sys.argv', ['vnotes', 'https://example.test', '--engine', 'gemini', '--out', 'unused']), patch('pathlib.Path.mkdir') as mkdir, patch('sys.stderr', io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                main()
            self.assertEqual(error.exception.code, 2)
            mkdir.assert_not_called()

    def test_codex_schema_preserves_citation_constraints(self):
        schema = {'type':'OBJECT', 'properties':{'evidence':{'type':'ARRAY', 'maxItems':4,
            'items':{'type':'STRING', 'enum':['F001']}}}, 'required':['evidence']}
        result = codex_schema(schema)
        self.assertFalse(result['additionalProperties'])
        self.assertEqual(result['properties']['evidence'], {'type':'array', 'maxItems':4,
            'items':{'type':'string','enum':['F001']}})

    def test_caption_segments_preserve_timing(self):
        self.assertEqual(transcript({'events':[{'tStartMs':1230,'segs':[{'utf8':'A &amp; B'}]}]}),
                         [{'id':'T0000','seconds':1.23,'text':'A & B'}])

    def test_reject_fabricated_reference(self):
        with self.assertRaisesRegex(ValueError, 'Unknown evidence'):
            validate({'sections':[{'points':[{'text':'claim','evidence':['F999'],'visual':True}]}]}, {}, [])

    def test_reject_visual_without_image(self):
        with self.assertRaisesRegex(ValueError, 'without a supplied frame'):
            validate({'sections':[{'points':[{'text':'claim','evidence':['T0000'],'visual':True}]}]}, {'T0000':{}}, [])

    def test_transient_failure_retried_within_budget(self):
        error = urllib.error.HTTPError('https://example.test', 503, 'busy', {}, io.BytesIO(b'{}'))
        with patch('vnotes.urllib.request.urlopen', side_effect=[error, io.BytesIO(b'{"ok":true}')]) as call, patch('vnotes.time.sleep'):
            self.assertEqual(request_json(None, lambda:30), ({'ok':True}, 1))
            self.assertEqual(call.call_count, 2)

    def test_no_retry_when_deadline_near(self):
        error = urllib.error.HTTPError('https://example.test', 503, 'busy', {}, io.BytesIO(b'{}'))
        with patch('vnotes.urllib.request.urlopen', side_effect=error) as call:
            with self.assertRaises(urllib.error.HTTPError):
                request_json(None, lambda:5)
            self.assertEqual(call.call_count, 1)

    def test_daily_quota_not_retried(self):
        body = b'{"error":{"details":[{"retryDelay":"19808s"}]}}'
        error = urllib.error.HTTPError('https://example.test', 429, 'quota', {}, io.BytesIO(body))
        with patch('vnotes.urllib.request.urlopen', side_effect=error) as call, patch('vnotes.time.sleep') as sleep:
            with self.assertRaises(urllib.error.HTTPError):
                request_json(None, lambda:40)
            self.assertEqual(call.call_count, 1)
            sleep.assert_not_called()

if __name__ == '__main__':
    unittest.main()
