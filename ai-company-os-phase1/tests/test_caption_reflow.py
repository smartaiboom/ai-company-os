"""Offline layout-only recovery: original wording retained, strict bounds unchanged."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from autonomous_company import CompanyError,digest
from local_artifacts import prepare_video,validate_video,TOOLS,VIDEO_TOOL


def spec(text):
    return {'tool':VIDEO_TOOL,'width':1280,'height':720,'audio':False,
            'scenes':[{'text':text,'seconds':6}]}


class CaptionReflowTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket.connect','socket.create_connection','socket.getaddrinfo'):
            p=patch(name,side_effect=AssertionError('network forbidden'));p.start();self.addCleanup(p.stop)

    def test_long_korean_words_preserved_offsets_and_idempotence(self):
        source=spec('좋은 질문을 작성하려면 원하는 목표와 구체적인 상황을 함께 설명해 주세요.')
        before=deepcopy(source);rendered,trace=prepare_video(source)
        self.assertEqual(before,source);validate_video(rendered)
        self.assertTrue(trace['changes']);self.assertEqual(digest(source),trace['source_input_hash'])
        chars=list(source['scenes'][0]['text'])
        for offset in trace['changes'][0]['space_to_newline_offsets']:
            self.assertEqual(' ',chars[offset]);chars[offset]='\n'
        self.assertEqual(''.join(chars),rendered['scenes'][0]['text'])
        again,second=prepare_video(rendered)
        self.assertEqual(rendered,again);self.assertEqual([],second['changes'])

    def test_28_boundary_existing_newlines_multiple_scenes(self):
        value=spec('가'*28+' '+'나'*10);value['scenes']*=3
        result,trace=prepare_video(value)
        self.assertEqual(3,len(trace['changes']))
        self.assertEqual('가'*28+'\n'+'나'*10,result['scenes'][0]['text'])
        for text in ('가'*28,'가'*14+'\n'+'나'*20,'가\n나\n다\n라'):
            rendered,trace=prepare_video(spec(text));self.assertEqual(text,rendered['scenes'][0]['text'])
            self.assertFalse(trace['changes'])

    def test_unbreakable_4_line_and_120_char_limits(self):
        for value,code in [('가'*29,'caption_overflow'),('가\n나\n다\n라\n마','caption_overflow'),
                           (('가'*22+' ')*4+'나'*28,'caption_overflow'), # exactly 120 chars
                           ('가'*121,'invalid_text'),('가\t나','invalid_caption')]:
            with self.subTest(size=len(value)),self.assertRaises(CompanyError) as failure:
                prepare_video(spec(value))
            self.assertEqual(code,failure.exception.code)
        with self.assertRaises(CompanyError):validate_video(spec('가'*28+' '+'나'))

    def test_tool_contract_and_duration_guards(self):
        notice=str(TOOLS[VIDEO_TOOL])
        for rule in ('28','4 lines','120 chars','0.5..30','1..16','120s'):
            self.assertIn(rule,notice)
        for value,code in [(dict(spec('짧은 문장'),scenes=[]),'invalid_scenes'),
                           (dict(spec('짧은 문장'),scenes=[{'text':'안내','seconds':31}]),'invalid_duration'),
                           (dict(spec('짧은 문장'),scenes=[{'text':'안내','seconds':30}]*5),'video_too_long')]:
            with self.assertRaises(CompanyError) as failure:prepare_video(value)
            self.assertEqual(code,failure.exception.code)
