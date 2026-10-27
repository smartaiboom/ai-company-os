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

if __name__ == "__main__":
    unittest.main()
