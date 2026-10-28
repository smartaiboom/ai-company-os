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
            "당신은 한국어로 업무 결과물을 작성하는 가상회사 직원입니다. "
            "지금부터 설명이나 생각 과정이 아니라 완성된 결과물만 출력하세요. "
            "첫 줄은 결과물 제목으로 시작하세요. "
            "지시사항이나 입력 내용을 복사, 번역, 요약, 재진술하지 마세요. "
            "'The user wants', 'I need to', 'Let me', 'I will' 같은 자기 설명이나 작업 계획을 절대 출력하지 마세요. "
            "최종 결과물은 자연스럽고 쉬운 한국어로 작성하세요. 영어 단어·문장·약어는 원칙적으로 쓰지 말고, 제품명이나 꼭 필요한 고유명사에만 사용하며 처음 나올 때 한국어 뜻을 설명하세요. P0/P1/P2 대신 필수·다음 단계·후속 단계라고 쓰고, API·UI·ROI 같은 약어도 쉬운 한국어로 바꾸세요. "
            "제공된 자료가 AI 생성 보고서라면 독립적인 증거로 취급하지 말고 미검증 주장으로 표시하세요. "
            "출처가 없는 수치와 사실을 만들지 말고, 실제 조사나 설문을 수행했다고 주장하지 마세요. "
            "확인된 근거, 출처가 필요한 주장, 가정·추정, 미확인 사항을 구분하세요."
        )
        user_payload = {
            "프로젝트 목표": goal,
            "작업명": task_name,
            "담당 역할": role,
            "필요 입력 자료": inputs,
            "요청 결과물": output,
            "이전 작업 결과": previous_results,
        }
        user_content = (
            "아래 업무 정보를 참고해 실제 결과물을 작성하세요. "
            "정보를 되풀이하지 말고 결과물 내용부터 시작하세요. "
            "응답은 한국어로 작성하세요.\n"
            + json.dumps(user_payload, ensure_ascii=False)
            + "\n"
            "제품 기획 담당 업무라면 일반적인 자동화 SaaS를 크게 설계하지 말고, "
            "현재 개발 중인 AI Company OS 자체의 다음 실행 가능한 단계에 맞춘 기획서를 작성하세요. "
            "이 프로젝트의 목적은 사용자가 큰 목표를 입력하면 AI 관리자가 업무를 나누고, "
            "AI 직원들이 순서대로 작업하며, 이전 작업 결과를 다음 작업에 전달하고, "
            "검토·수정 후 결과물을 만드는 가상 회사 시스템을 구현하는 것입니다. "
            "현재 구현된 기능을 모르면 이미 구현되었다고 단정하지 말고, 확인이 필요한 사항으로 표시하세요. "
            "기획서에는 다음을 반드시 포함하세요: "
            "목표 고객과 구체적인 사용자 문제, 핵심 가치 제안, "
            "핵심 기능 3~5개와 기능별 사용자 문제·우선순위(필수·다음 단계·후속 단계)·검증 가능한 합격 기준을 담은 표, "
            "각 기능의 구현 범위, MVP에서 제외할 기능과 제외 이유, "
            "측정 가능한 전체 성공 기준, 미해결 사항 및 다음 행동. "
            "성공 기준은 가능한 한 관찰·측정 가능한 형태로 작성하고, 수치가 근거 없이 정해진 경우 '초기 가설'로 표시하세요. "
            "기능 우선순위는 '필수', '다음 단계', '후속 단계'로 구분하고 이유를 설명하세요. "
            "첫 버전에는 외부 이메일·슬랙 연동, 구독 결제, 복잡한 드래그앤드롭 빌더 등 "
            "현재 핵심 흐름 검증에 필요하지 않은 대규모 기능을 넣지 마세요. "
            "시장 조사 자료의 수치나 주장은 출처가 실제로 확인되지 않았다면 '선행 AI 보고서의 미검증 주장'으로 표시하세요. "
            "실제 설문이나 경쟁 제품 조사를 하지 않았다면 조사 결과를 만들지 말고 검증할 가설로 적으세요. "
            "첫 줄은 '제품 기획서' 같은 실제 결과물 제목으로 시작하고, 지시사항이나 작업 계획은 출력하지 마세요."
        )
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            "temperature": 0.3,
            "max_tokens": 4096,
            "chat_template_kwargs": {"enable_thinking": False},
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
            choice = response_data["choices"][0]
            message = choice["message"]
            content = message.get("content")
            # Some routed models place their generated text in a reasoning field
            # or return an empty content field. Check common compatible fields.
            if not content:
                content = (
                    message.get("reasoning_content")
                    or message.get("reasoning")
                    or message.get("output_text")
                )
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                "AI API 응답에 choices[0].message가 없습니다."
            ) from exc

        if isinstance(content, list):
            content = "\\n".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            )
        if not isinstance(content, str) or not content.strip():
            fields = ", ".join(sorted(message.keys())) if isinstance(message, dict) else "(message 없음)"
            finish_reason = choice.get("finish_reason", "알 수 없음") if isinstance(choice, dict) else "알 수 없음"
            raise RuntimeError(
                "AI API가 작업 결과 내용을 반환하지 않았습니다. "
                f"finish_reason={finish_reason}, message_fields={fields}. "
                "모델 응답에 내용이 없으므로 설정된 AI_MODEL의 호환성을 확인해야 합니다."
            )
        # Reject leaked planning notes instead of showing them as a finished deliverable.
        internal_note_markers = (
            "the user wants", "i need to", "let's draft", "let's write",
            "let's compose", "make sure", "structure:", "need to ensure",
            "i should write", "we need to", "let's compose carefully",
        )
        lowered_content = content.strip().lower()
        if any(marker in lowered_content for marker in internal_note_markers):
            raise RuntimeError(
                "AI가 완성된 결과물 대신 작업 계획이나 작성 메모를 반환했습니다. "
                "해당 결과는 저장·사용하지 말고 같은 작업을 다시 실행해 주세요."
            )

        normalized_content = content.strip().lower()
        if normalized_content in {"user safety: safe", "safe", "user safety: unsafe"}:
            raise RuntimeError(
                "AI API가 업무 결과 대신 안전성 판정 문구만 반환했습니다. "
                "AI_MODEL을 다른 지원 모델로 변경한 뒤 다시 실행해 주세요."
            )

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
