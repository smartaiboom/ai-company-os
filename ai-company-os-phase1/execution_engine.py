"""AI Company OS 작업 실행 엔진 인터페이스와 구현."""

from abc import ABC, abstractmethod
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ExecutionEngine(ABC):
    """모든 작업 실행 엔진이 따라야 하는 공통 인터페이스."""

    @abstractmethod
    def execute(self, project, task, previous_results=None):
        """이전 작업 결과를 참고해 실행 결과 문자열을 반환한다."""
        raise NotImplementedError


class MockExecutionEngine(ExecutionEngine):
    """외부 API를 호출하지 않는 모의 실행 엔진."""

    ROLE_INSTRUCTIONS = {
        "AI 관리자": (
            "목표와 조건을 정리하고, 성공 기준 및 미해결 사항을 명확히 한다."
        ),
        "콘텐츠 제작 담당": (
            "입력 자료와 요구사항을 바탕으로 콘텐츠 초안을 구성한다."
        ),
        "품질 검토 담당": (
            "요구사항 충족 여부를 확인하고, 문제점과 수정안을 정리한다."
        ),
        "시장 조사 담당": (
            "시장 수요, 고객 문제, 경쟁 대안 및 근거를 조사한다."
        ),
        "제품 기획 담당": (
            "조사 결과를 바탕으로 대상 고객, 핵심 기능 및 제품 방향을 정의한다."
        ),
        "개발 담당": (
            "요구사항과 기획을 바탕으로 구현 항목과 검증 방법을 정리한다."
        ),
        "마케팅 담당": (
            "대상 고객, 전달할 가치, 홍보 채널 및 실행 전략을 정리한다."
        ),
        "재무 담당": (
            "예상 비용, 수익 구조, 주요 가정 및 재무 위험을 정리한다."
        ),
    }

    def execute(self, project, task, previous_results=None):
        task_name = task.get("name", "이름 없는 작업")
        role = task.get("role", "미지정")
        goal = project.get("manager_goal") or project.get("goal", "")
        output = task.get("output", "작업 결과물")
        inputs = task.get("inputs", [])
        role_instruction = self.ROLE_INSTRUCTIONS.get(
            role,
            "작업 목표와 입력 자료를 확인하고 지정된 결과물을 작성한다."
        )

        if not goal.strip():
            raise ValueError("프로젝트 목표가 없어 작업을 실행할 수 없습니다.")

        previous_results = previous_results or []

        result_parts = [
            "[모의 실행 결과]",
            f"프로젝트 목표: {goal}",
            f"작업명: {task_name}",
            f"담당 역할: {role}",
            f"역할별 실행 지침: {role_instruction}",
            "필요 입력 자료:",
        ]

        if inputs:
            for item in inputs:
                result_parts.append(f"- {item}")
        else:
            result_parts.append("- 별도 입력 자료가 지정되지 않았습니다.")

        result_parts.append(f"요청 결과물: {output}")

        if role == "AI 관리자":
            if task_name == "최종 보고":
                result_parts.extend([
                    "모의 결과물:",
                    "최종 결과: 검토 및 수정 작업의 결과를 확인했습니다.",
                    "미해결 사항: 실제 검증이 수행되지 않아 추가 검토가 필요합니다.",
                ])
            else:
                result_parts.extend([
                    "모의 결과물:",
                    "프로젝트 목표와 조건을 정리합니다.",
                    "성공 기준과 미해결 사항을 확인합니다.",
                ])
        elif role == "콘텐츠 제작 담당":
            result_parts.extend([
                "모의 결과물:",
                "입력 자료를 바탕으로 초안을 작성합니다.",
                "요구사항과 결과물 형식에 맞춰 내용을 구성합니다.",
            ])
        elif role == "품질 검토 담당":
            result_parts.extend([
                "모의 결과물:",
                "요구사항 충족 여부: 검토 필요",
                "발견된 문제점: 실제 검증 전이므로 아직 확인되지 않음",
                "수정 제안: 요구사항과 결과물을 대조한 뒤 수정 항목을 정리",
                "최종 검토 결과: 추가 검증 필요",
                "미해결 사항: 실제 검증이 수행되지 않아 검토 결과 확정 필요",
            ])
        elif role == "시장 조사 담당":
            result_parts.extend([
                "모의 결과물:",
                "시장 수요, 고객 문제, 경쟁 대안을 조사할 항목으로 정리합니다.",
                "실제 시장 데이터는 아직 조사하지 않았습니다.",
            ])
        elif role == "제품 기획 담당":
            result_parts.extend([
                "모의 결과물:",
                "대상 고객, 핵심 기능, 제품 방향을 정리할 항목으로 구성합니다.",
                "실제 고객 검증은 아직 수행하지 않았습니다.",
            ])
        elif role == "개발 담당":
            result_parts.extend([
                "모의 결과물:",
                "요구사항을 구현 항목과 검증 항목으로 나눕니다.",
                "실제 코드는 아직 작성하지 않았습니다.",
            ])
        elif role == "마케팅 담당":
            result_parts.extend([
                "모의 결과물:",
                "대상 고객, 전달할 가치, 홍보 채널을 정리합니다.",
                "실제 홍보 활동은 아직 수행하지 않았습니다.",
            ])
        elif role == "재무 담당":
            result_parts.extend([
                "모의 결과물:",
                "예상 비용, 수익 구조, 주요 가정과 재무 위험을 정리합니다.",
                "실제 비용 및 수익 데이터는 아직 없습니다.",
            ])
        else:
            result_parts.extend([
                "모의 결과물:",
                f"{output}에 해당하는 내용을 작성할 항목으로 정리합니다.",
            ])

        if previous_results:
            result_parts.append("\n연결된 입력 자료와 실제 결과:")

            for item in previous_results:
                input_name = item.get("input_name", "지정되지 않은 입력 자료")
                previous_name = item.get("task_name", "이름 없는 작업")
                previous_result = item.get("result", "")

                result_parts.append(f"\n입력 자료: {input_name}")
                result_parts.append(f"출처 작업: {previous_name}")

                if input_name == "미해결 사항":
                    unresolved = [
                        line for line in previous_result.splitlines()
                        if "미해결 사항:" in line
                        or "추가 검증 필요" in line
                        or "아직 확인되지 않음" in line
                    ]

                    if unresolved:
                        result_parts.append("관련 내용:")
                        result_parts.extend(unresolved)
                    else:
                        result_parts.append(
                            "관련 내용: 이전 결과에서 별도 미해결 사항을 찾지 못했습니다."
                        )
                else:
                    result_parts.append(f"관련 결과:\n{previous_result}")
        result_parts.extend([
            "",
            "현재는 실행 엔진 검증 단계입니다. 실제 AI 처리는 수행하지 않았습니다.",
        ])

        return "\n".join(result_parts)



class OpenAICompatibleExecutionEngine(ExecutionEngine):
    """OpenAI 호환 Chat Completions API를 사용하는 실제 AI 실행 엔진.

    AI_API_BASE_URL은 /v1 같은 API 기본 경로까지 지정한다.
    AI_API_KEY는 제공자가 키를 요구할 때 설정한다.
    AI_MODEL은 제공자가 지원하는 모델 이름이다.
    """

    def __init__(self, base_url=None, api_key=None, model=None, timeout=None):
        self.base_url = (base_url or os.getenv("AI_API_BASE_URL", "")).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("AI_API_KEY", "")
        self.model = model or os.getenv("AI_MODEL", "")
        self.timeout = timeout or int(os.getenv("AI_API_TIMEOUT", "90"))

        if not self.base_url:
            raise ValueError(
                "실제 AI 엔진을 사용하려면 AI_API_BASE_URL 환경변수를 설정해야 합니다."
            )
        if not self.model:
            raise ValueError(
                "실제 AI 엔진을 사용하려면 AI_MODEL 환경변수를 설정해야 합니다."
            )

    def execute(self, project, task, previous_results=None):
        goal = project.get("manager_goal") or project.get("goal", "")
        task_name = task.get("name", "이름 없는 작업")
        role = task.get("role", "미지정")
        inputs = task.get("inputs", [])
        output = task.get("output", "작업 결과물")
        previous_results = previous_results or []

        if not goal.strip():
            raise ValueError("프로젝트 목표가 없어 작업을 실행할 수 없습니다.")

        system_prompt = (
            "당신은 AI Company OS의 가상회사 직원입니다. "
            "담당 역할과 프로젝트 목표에 맞춰 실제로 유용한 작업 결과를 작성하세요. "
            "근거가 없거나 확인하지 않은 내용은 사실처럼 꾸미지 말고 불확실성을 표시하세요. "
            "이전 작업 결과를 참고하되 오류나 미해결 사항을 그대로 전달하고, "
            "요청 결과물을 명확한 제목과 구조로 작성하세요."
        )
        user_payload = {
            "project_goal": goal,
            "task_name": task_name,
            "assigned_role": role,
            "required_inputs": inputs,
            "requested_output": output,
            "previous_task_results": previous_results,
            "instructions": (
                "위 정보를 바탕으로 이번 작업의 결과물만 작성하세요. "
                "이전 결과가 부족하거나 검증되지 않았다면 그 한계를 명시하세요."
            ),
        }
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
            "temperature": 0.3,
        }).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(
                f"AI API 요청 실패 (HTTP {exc.code}): {detail}"
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"AI API 연결 실패: {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("AI API 응답을 해석할 수 없습니다.") from exc

        try:
            content = response_data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                "AI API 응답에 choices[0].message.content가 없습니다."
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("AI API가 빈 작업 결과를 반환했습니다.")

        return (
            f"[실제 AI 실행 결과]\n"
            f"프로젝트 목표: {goal}\n"
            f"작업명: {task_name}\n"
            f"담당 역할: {role}\n"
            f"사용 모델: {self.model}\n\n"
            f"{content.strip()}\n\n"
            "참고: AI가 생성한 결과이며, 사실 확인이나 외부 검증이 자동으로 "
            "완료되었다는 의미는 아닙니다."
        )


def get_execution_engine():
    """환경변수에 따라 실행 엔진을 선택한다. 기본값은 안전한 모의 실행이다."""
    engine_name = os.getenv("AI_ENGINE", "mock").strip().lower()
    if engine_name == "mock":
        return MockExecutionEngine()
    if engine_name in {"openai_compatible", "openai-compatible"}:
        return OpenAICompatibleExecutionEngine()
    raise ValueError(
        f"지원하지 않는 AI_ENGINE 값입니다: {engine_name}. "
        "mock 또는 openai_compatible을 사용하세요."
    )


def get_execution_engine_name():
    """현재 설정된 실행 엔진 이름을 반환한다."""
    return os.getenv("AI_ENGINE", "mock").strip().lower()


def execute_task(project, task, previous_results=None):
    """설정된 실행 엔진으로 작업을 실행한다."""
    return get_execution_engine().execute(
        project,
        task,
        previous_results=previous_results,
    )


_default_engine = MockExecutionEngine()


def execute_task_mock(project, task, previous_results=None):
    """기존 테스트 및 호출부와의 호환성을 유지하는 모의 실행 함수."""
    return _default_engine.execute(
        project,
        task,
        previous_results=previous_results,
    )
