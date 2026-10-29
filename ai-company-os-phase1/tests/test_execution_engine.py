import unittest

from execution_engine import execute_task_mock


class ExecutionEngineTests(unittest.TestCase):
    def test_execute_task_mock_returns_result(self):
        project = {
            "goal": "초보자를 위한 AI 제품 개발"
        }
        task = {
            "name": "시장 조사",
            "output": "시장 조사 보고서"
        }

        result = execute_task_mock(project, task)

        self.assertIn("초보자를 위한 AI 제품 개발", result)
        self.assertIn("시장 조사", result)
        self.assertIn("시장 조사 보고서", result)
        self.assertIn("실제 AI 처리는 수행하지 않았습니다.", result)

    def test_execute_task_mock_rejects_empty_goal(self):
        project = {"goal": ""}
        task = {"name": "시장 조사", "output": "보고서"}

        with self.assertRaises(ValueError):
            execute_task_mock(project, task)

    def test_execute_task_mock_accepts_previous_results(self):
        project = {"goal": "초보자를 위한 AI 제품 개발"}
        task = {
            "name": "제품 기획",
            "output": "제품 기획서"
        }
        previous_results = [
            {
                "task_name": "시장 조사",
                "result": "초보 사용자는 쉬운 자동화 도구를 원한다."
            }
        ]

        result = execute_task_mock(
            project,
            task,
            previous_results=previous_results
        )

        self.assertIn("시장 조사", result)
        self.assertIn(
            "초보 사용자는 쉬운 자동화 도구를 원한다.",
            result
        )

    def test_execute_task_mock_shows_linked_input_name(self):
        project = {
            "goal": "유튜브에 올릴 영상 제작"
        }
        task = {
            "name": "작업 초안 작성",
            "inputs": ["요구사항 정리 결과"],
            "output": "초안 결과물"
        }
        previous_results = [
            {
                "input_name": "요구사항 정리 결과",
                "task_name": "요구사항 정리",
                "result": "목표와 성공 기준이 정리되었습니다."
            }
        ]

        result = execute_task_mock(
            project,
            task,
            previous_results=previous_results
        )

        self.assertIn("연결된 입력 자료와 실제 결과", result)
        self.assertIn("입력 자료: 요구사항 정리 결과", result)
        self.assertIn("출처 작업: 요구사항 정리", result)
        self.assertIn("목표와 성공 기준이 정리되었습니다.", result)

    def test_execute_task_mock_uses_role_instruction(self):
        project = {"goal": "유튜브에 올릴 영상 제작"}
        task = {
            "name": "검토 및 수정",
            "role": "품질 검토 담당",
            "inputs": ["작업 초안", "요구사항 및 성공 기준"],
            "output": "검토 의견 및 수정본",
        }

        result = execute_task_mock(project, task)

        self.assertIn("담당 역할: 품질 검토 담당", result)
        self.assertIn(
            "요구사항 충족 여부를 확인하고, 문제점과 수정안을 정리한다.",
            result,
        )
    def test_execute_task_mock_generates_quality_review_result(self):
        project = {"goal": "제품 초안 검토"}
        task = {
            "name": "검토 및 수정",
            "role": "품질 검토 담당",
            "inputs": ["작업 초안", "요구사항 및 성공 기준"],
            "output": "검토 의견 및 수정본",
        }

        result = execute_task_mock(project, task)

        self.assertIn("모의 결과물:", result)
        self.assertIn("요구사항 충족 여부: 검토 필요", result)
        self.assertIn("발견된 문제점:", result)
        self.assertIn("수정 제안:", result)
        self.assertIn("최종 검토 결과: 추가 검증 필요", result)

    def test_final_report_includes_linked_input_results(self):
        project = {"goal": "테스트용 프로젝트"}
        task = {
            "name": "최종 보고",
            "role": "AI 관리자",
            "inputs": ["최종 결과물", "미해결 사항"],
            "output": "최종 결과 및 미해결 사항",
        }
        previous_results = [
            {
                "input_name": "최종 결과물",
                "task_name": "검토 및 수정",
                "result": "최종 검토 결과: 추가 검증 필요",
            },
            {
                "input_name": "미해결 사항",
                "task_name": "검토 및 수정",
                "result": "미해결 사항: 실제 검증이 수행되지 않아 검토 결과 확정 필요",
            },
        ]

        result = execute_task_mock(
            project,
            task,
            previous_results=previous_results,
        )

        self.assertIn("연결된 입력 자료와 실제 결과", result)
        self.assertIn("입력 자료: 최종 결과물", result)
        self.assertIn("출처 작업: 검토 및 수정", result)
        self.assertIn("최종 검토 결과: 추가 검증 필요", result)
        self.assertIn("입력 자료: 미해결 사항", result)
        self.assertIn("미해결 사항: 실제 검증이 수행되지 않아 검토 결과 확정 필요", result)


    def test_get_execution_engine_defaults_to_mock(self):
        from unittest.mock import patch
        from execution_engine import MockExecutionEngine, get_execution_engine

        with patch.dict("os.environ", {}, clear=True):
            self.assertIsInstance(get_execution_engine(), MockExecutionEngine)

    def test_openai_compatible_engine_requires_configuration(self):
        from unittest.mock import patch
        from execution_engine import OpenAICompatibleExecutionEngine

        with patch.dict("os.environ", {"AI_MODEL": "openrouter/free"}, clear=True):
            with self.assertRaisesRegex(ValueError, "AI_API_BASE_URL"):
                OpenAICompatibleExecutionEngine()

    def test_openai_compatible_request_does_not_disable_reasoning(self):
        import json
        import os
        from unittest.mock import patch
        from execution_engine import execute_task

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self):
                return b'{"choices":[{"message":{"content":"ordinary result includes safe"}}]}'

        env = {
            "AI_ENGINE": "openai_compatible",
            "AI_API_BASE_URL": "https://example.invalid/v1",
            "AI_MODEL": "openrouter/free",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("execution_engine.urlopen", return_value=FakeResponse()) as mocked_urlopen:
                result = execute_task({"goal": "테스트 목표"}, {"name": "테스트 업무"})

        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertIn("ordinary result includes safe", result)
        self.assertEqual(payload["model"], "openrouter/free")
        self.assertNotIn("reasoning", payload)
        self.assertNotIn("chat_template_kwargs", payload)

    def test_safety_verdict_only_response_is_rejected_without_model_change_advice(self):
        import os
        from unittest.mock import patch
        from execution_engine import execute_task

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self):
                return b'{"choices":[{"finish_reason":"stop","message":{"role":"assistant","content":"User Safety: Safe"}}]}'

        env = {
            "AI_ENGINE": "openai_compatible",
            "AI_API_BASE_URL": "https://example.invalid/v1",
            "AI_MODEL": "openrouter/free",
            "AI_API_KEY": "AUTH_SENTINEL",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("execution_engine.urlopen", return_value=FakeResponse()):
                with self.assertLogs("execution_engine", level="WARNING") as diagnostics:
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "응답 내용과 라우팅된 모델의 동작을 확인",
                    ) as error:
                        execute_task(
                            {"goal": "PRIVATE_PROMPT_SENTINEL"},
                            {
                                "name": "테스트 업무",
                                "inputs": ["PRIVATE_INPUT_SENTINEL"],
                            },
                            previous_results=[{
                                "task_name": "선행 작업",
                                "result": "PRIVATE_RESULT_SENTINEL",
                            }],
                        )

        self.assertIn("업무 결과 대신 안전성 판정 문구만 반환했습니다", str(error.exception))
        self.assertNotIn("AI_MODEL을 다른 지원 모델로 변경", str(error.exception))
        log_message = " ".join(diagnostics.output)
        self.assertIn("finish_reason=stop", log_message)
        self.assertIn("message_fields=('content', 'role')", log_message)
        self.assertIn("content_length=17", log_message)
        self.assertIn("content_empty=False", log_message)
        self.assertIn("safety_verdict=safe", log_message)
        self.assertNotIn("User Safety: Safe", log_message)
        self.assertNotIn("PRIVATE_PROMPT_SENTINEL", log_message)
        self.assertNotIn("PRIVATE_INPUT_SENTINEL", log_message)
        self.assertNotIn("PRIVATE_RESULT_SENTINEL", log_message)
        self.assertNotIn("AUTH_SENTINEL", log_message)

    def test_empty_ai_response_logs_only_safe_diagnostic_metadata(self):
        import os
        from unittest.mock import patch
        from execution_engine import execute_task

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self):
                return b'{"choices":[{"finish_reason":"content_filter","message":{"role":"assistant","content":""}}]}'

        env = {
            "AI_ENGINE": "openai_compatible",
            "AI_API_BASE_URL": "https://example.invalid/v1",
            "AI_MODEL": "openrouter/free",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("execution_engine.urlopen", return_value=FakeResponse()):
                with self.assertLogs("execution_engine", level="WARNING") as diagnostics:
                    with self.assertRaisesRegex(RuntimeError, "응답 진단 로그"):
                        execute_task({"goal": "PRIVATE_PROMPT_SENTINEL"}, {"name": "테스트 업무"})

        log_message = " ".join(diagnostics.output)
        self.assertIn("finish_reason=content_filter", log_message)
        self.assertIn("message_fields=('content', 'role')", log_message)
        self.assertIn("content_length=0", log_message)
        self.assertIn("content_empty=True", log_message)
        self.assertNotIn("PRIVATE_PROMPT_SENTINEL", log_message)

    def test_length_finish_reason_is_rejected_and_logs_token_limits(self):
        import json
        import os
        from unittest.mock import patch
        from execution_engine import MAX_RESPONSE_TOKENS, execute_task

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self):
                return (
                    b'{"choices":[{"finish_reason":"length","message":'
                    b'{"role":"assistant","content":"PARTIAL_RESPONSE_SENTINEL"}}],'
                    b'"usage":{"prompt_tokens":120,"completion_tokens":4096,'
                    b'"total_tokens":4216}}'
                )

        env = {
            "AI_ENGINE": "openai_compatible",
            "AI_API_BASE_URL": "https://example.invalid/v1",
            "AI_MODEL": "openrouter/free",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("execution_engine.urlopen", return_value=FakeResponse()) as mocked_urlopen:
                with self.assertLogs("execution_engine", level="WARNING") as diagnostics:
                    with self.assertRaisesRegex(RuntimeError, "응답이 중간에 끊겼습니다"):
                        execute_task({"goal": "테스트 목표"}, {"name": "테스트 업무"})

        request = mocked_urlopen.call_args.args[0]
        request_payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request_payload["max_tokens"], MAX_RESPONSE_TOKENS)
        self.assertEqual(MAX_RESPONSE_TOKENS, 4096)
        log_message = " ".join(diagnostics.output)
        self.assertIn("finish_reason=length", log_message)
        self.assertIn("request_max_tokens=4096", log_message)
        self.assertIn("prompt_tokens=120", log_message)
        self.assertIn("completion_tokens=4096", log_message)
        self.assertIn("total_tokens=4216", log_message)
        self.assertNotIn("PARTIAL_RESPONSE_SENTINEL", log_message)

    def test_non_free_model_is_rejected_before_api_request(self):
        from unittest.mock import patch
        from execution_engine import execute_task

        env = {
            "AI_ENGINE": "openai_compatible",
            "AI_API_BASE_URL": "https://example.invalid/v1",
            "AI_MODEL": "some-provider/some-model",
        }
        with patch.dict("os.environ", env, clear=True):
            with patch("execution_engine.urlopen") as mocked_urlopen:
                with self.assertRaisesRegex(ValueError, "openrouter/free"):
                    execute_task({"goal": "test"}, {"name": "test"})
                mocked_urlopen.assert_not_called()

    def test_missing_model_is_rejected_before_api_request(self):
        from unittest.mock import patch
        from execution_engine import execute_task

        env = {
            "AI_ENGINE": "openai_compatible",
            "AI_API_BASE_URL": "https://example.invalid/v1",
        }
        with patch.dict("os.environ", env, clear=True):
            with patch("execution_engine.urlopen") as mocked_urlopen:
                with self.assertRaisesRegex(ValueError, "openrouter/free"):
                    execute_task({"goal": "test"}, {"name": "test"})
                mocked_urlopen.assert_not_called()

    def test_get_execution_engine_rejects_unknown_engine(self):
        from unittest.mock import patch
        from execution_engine import get_execution_engine

        with patch.dict("os.environ", {"AI_ENGINE": "unknown"}, clear=True):
            with self.assertRaisesRegex(ValueError, "지원하지 않는 AI_ENGINE"):
                get_execution_engine()

if __name__ == "__main__":
    unittest.main()
