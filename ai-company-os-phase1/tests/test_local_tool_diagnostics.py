"""Offline subprocess failure categories: no command, stderr or paths retained."""
import json
import subprocess
import unittest
from unittest.mock import patch
from local_artifacts import run_command,LocalToolError,COMMAND_STAGES
from autonomous_company import CompanyError


class LocalToolDiagnosticTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket.connect','socket.create_connection','socket.getaddrinfo'):
            p=patch(name,side_effect=AssertionError('network forbidden'));p.start();self.addCleanup(p.stop)

    def test_all_stages_and_failures_redact_command_and_stderr(self):
        private='private-key-and-project-path'
        cases=[(FileNotFoundError(private),'executable_missing',None),
               (PermissionError(private),'os_error',None),
               (subprocess.CalledProcessError(1,[private],output=private,stderr=private),'exit_nonzero',1),
               (subprocess.CalledProcessError(-9,[private],stderr=private),'exit_nonzero',-9),
               (subprocess.TimeoutExpired([private],180,output=private,stderr=private),'timeout',None)]
        for stage in COMMAND_STAGES:
            for error,category,code in cases:
                with self.subTest(stage=stage,category=category),patch('local_artifacts.subprocess.run',side_effect=error):
                    with self.assertRaises(LocalToolError) as raised:run_command([private],stage=stage)
                    self.assertEqual('local_tool_failed',raised.exception.code)
                    self.assertEqual({'stage':stage,'category':category,'exit_code':code},raised.exception.diagnostics)
                    self.assertNotIn(private,str(raised.exception));self.assertNotIn(private,json.dumps(raised.exception.diagnostics))

    def test_success_and_unknown_stage_blocked(self):
        with patch('local_artifacts.subprocess.run',return_value=subprocess.CompletedProcess([],0,b'safe-output',b'')) as run:
            self.assertEqual(b'safe-output',run_command(['synthetic'],stage='ffprobe_final'))
            run.assert_called_once_with(['synthetic'],check=True,capture_output=True,timeout=180)
        with patch('local_artifacts.subprocess.run') as run:
            with self.assertRaises(CompanyError):run_command(['synthetic'],stage='private-path')
            run.assert_not_called()
