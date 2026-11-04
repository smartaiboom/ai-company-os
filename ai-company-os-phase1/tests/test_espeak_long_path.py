"""Real local audio regression with synthetic text and a deep app-owned directory."""
import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import local_artifacts as media


class EspeakLongPathTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket.connect','socket.create_connection','socket.getaddrinfo'):
            p=patch(name,side_effect=AssertionError('network forbidden'));p.start();self.addCleanup(p.stop)

    def test_real_deep_directory_audio_render_and_decode(self):
        original=media.run_command;calls=[]
        def run(args,timeout=180,*,stage,cwd=None):
            if stage=='espeak_audio':
                self.assertIsNotNone(cwd);self.assertGreater(len(str(cwd)),199)
                self.assertEqual('0.txt',args[args.index('-f')+1])
                self.assertEqual('0.wav',args[args.index('-w')+1])
                self.assertTrue((Path(cwd)/'0.txt').is_file());calls.append(stage)
            return original(args,timeout,stage=stage,cwd=cwd)
        with tempfile.TemporaryDirectory() as root:
            deep=Path(root)/('a'*100)/('b'*100);deep.mkdir(parents=True)
            spec={'tool':'caption_video_v1','width':320,'height':240,'audio':True,
                  'scenes':[{'text':'합성 안내입니다.','seconds':3}]}
            with patch.object(media,'run_command',side_effect=run):result=media.render_video(spec,deep)
            self.assertTrue(result['decoded']);self.assertTrue(result['audio'])
            self.assertTrue((deep/'video.mp4').is_file());self.assertEqual(['espeak_audio'],calls)

    def test_cwd_forwarding_keeps_safe_failure_diagnostics(self):
        private='private-directory-and-stderr'
        with patch.object(media.subprocess,'run',side_effect=subprocess.CalledProcessError(1,[private],stderr=private)) as run:
            with self.assertRaises(media.LocalToolError) as error:
                media.run_command(['espeak-ng','-f','0.txt','-w','0.wav'],stage='espeak_audio',cwd=private)
            self.assertEqual({'stage':'espeak_audio','category':'exit_nonzero','exit_code':1},error.exception.diagnostics)
            self.assertNotIn(private,str(error.exception))
            self.assertEqual(private,run.call_args.kwargs['cwd'])
