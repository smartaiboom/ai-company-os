"""AI manager planning helpers with a safe deterministic fallback."""

import json
import os
from copy import deepcopy
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_QUESTIONS = [
    "완료 시점이나 기한이 있나요? (없으면 비워둘 수 있습니다)",
    "반드시 포함해야 할 조건이나 피해야 할 사항이 있나요? (없으면 비워둘 수 있습니다)",
    "원하는 결과물 형식이 있나요? (예: 보고서, 표, 코드, 기획안)",
]

DEFAULT_ASSUMPTIONS = [
    "별도 기한이 없으면 작은 단계로 나누어 진행합니다.",
    "사용자가 제공하지 않은 사실은 임의로 확정하지 않고 확인 대상으로 표시합니다.",
]

STARTER_STAGES = [
    {
        "name": "요구사항 정리",
        "role": "AI 관리자",
        "inputs": ["프로젝트 목표", "사용자가 제공한 조건"],
        "output": "목표·조건·성공 기준 정리",
        "risk": "요구사항이 모호할 수 있음",
    },
    {
        "name": "작업 초안 작성",
        "role": "콘텐츠 제작 담당",
        "inputs": ["요구사항 정리 결과"],
        "output": "초안 결과물",
        "risk": "추가 정보가 필요할 수 있음",
    },
    {
        "name": "검토 및 수정",
        "role": "품질 검토 담당",
        "inputs": ["작업 초안", "요구사항 및 성공 기준"],
        "output": "검토 의견 및 수정본",
        "risk": "기준 미충족 시 수정 필요",
    },
    {
        "name": "최종 보고",
        "role": "AI 관리자",
        "inputs": ["최종 결과물", "미해결 사항"],
        "output": "최종 결과 및 미해결 사항",
        "risk": "미해결 사항은 사용자에게 보고",
    },
]

PLANNER_SYSTEM_PROMPT = """당신은 AI Company OS의 관리자입니다.
사용자의 목표를 달성하는 데 필요한 업무를 계획하고, 각 업무에 적절한 AI 직원 역할을 배정합니다.
목표에 따라 필요한 작업 수를 결정하세요. 무조건 4개 작업으로 만들지 마세요.
작업은 실행 가능한 작은 단위여야 하며, 선행 작업의 결과가 후속 작업의 inputs에 연결되도록 하세요.
실제 조사나 실행을 한 것처럼 꾸미지 말고, 계획만 작성하세요.
응답은 JSON 객체 하나만 반환하세요. 설명이나 마크다운 코드 펜스를 추가하지 마세요.
JSON 형식:
{
  "questions": ["사용자에게 확인할 질문"],
  "assumptions": ["계획에 사용한 가정"],
  "stages": [
    {
      "name": "작업 이름",
      "role": "담당 AI 역할",
      "inputs": ["필요한 입력 또는 선행 작업 결과"],
      "output": "완료 시 생성할 결과물",
      "risk": "위험 또는 확인할 사항"
    }
  ]
}
stages는 2개 이상 10개 이하로 작성하세요. 모든 작업에 name, role, inputs, output, risk가 필요합니다.
역할은 목표에 맞게 구체적으로 정하세요. 예: 시장 조사 담당, 제품 기획 담당, 개발 담당, 품질 검토 담당, 마케팅 담당, 재무 담당, AI 관리자.
사용자가 제공하지 않은 사실을 확정하지 말고, 확인할 사항으로 표시하세요."""


def validate_stages(stages):
    """Reject malformed or excessively large plans before user approval."""
    if not isinstance(stages, list) or not 2 <= len(stages) <= 10:
        raise ValueError("AI 관리자 계획의 작업 수는 2개 이상 10개 이하여야 합니다.")

    required_fields = ("name", "role", "inputs", "output", "risk")
    normalized = []
    for index, stage in enumerate(stages, start=1):
        if not isinstance(stage, dict):
            raise ValueError(f"{index}번째 작업 계획 형식이 올바르지 않습니다.")
        item = {}
        for field in required_fields:
            value = stage.get(field)
            if field in ("name", "role", "output", "risk"):
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{index}번째 작업에 {field} 항목이 없습니다.")
                item[field] = value.strip()
            else:
                if not isinstance(value, list) or not all(
                    isinstance(entry, str) and entry.strip() for entry in value
                ):
                    raise ValueError(f"{index}번째 작업의 inputs 형식이 올바르지 않습니다.")
                item[field] = [entry.strip() for entry in value]
        normalized.append(item)
    return normalized


def _request_ai_plan(goal):
    base_url = os.getenv("AI_API_BASE_URL", "").rstrip("/")
    api_key = os.getenv("AI_API_KEY", "")
    model = os.getenv("AI_MODEL", "")
    if not base_url or not model:
        raise ValueError(
            "실제 AI 관리자 계획을 만들려면 AI_API_BASE_URL과 AI_MODEL 설정이 필요합니다."
        )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {"project_goal": goal, "language": "Korean"},
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0.2,
        "max_tokens": 3000,
        "response_format": {"type": "json_object"},
    }
    request = Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=int(os.getenv("AI_API_TIMEOUT", "90"))) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"AI 관리자 API 요청 실패 (HTTP {exc.code}): {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"AI 관리자 API 연결 실패: {exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("AI 관리자 API 응답을 해석할 수 없습니다.") from exc

    try:
        content = response_data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("AI 관리자 응답이 올바른 JSON 계획이 아닙니다.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("AI 관리자 응답은 JSON 객체여야 합니다.")

    stages = validate_stages(parsed.get("stages"))
    questions = parsed.get("questions", [])
    assumptions = parsed.get("assumptions", [])
    if not isinstance(questions, list) or not all(isinstance(x, str) for x in questions):
        raise RuntimeError("AI 관리자 응답의 questions 형식이 올바르지 않습니다.")
    if not isinstance(assumptions, list) or not all(isinstance(x, str) for x in assumptions):
        raise RuntimeError("AI 관리자 응답의 assumptions 형식이 올바르지 않습니다.")
    return stages, questions, assumptions


def build_manager_plan(goal, created_at):
    """Build a plan using the configured engine; mock mode remains API-free."""
    normalized_goal = str(goal or "").strip()
    if not normalized_goal:
        raise ValueError("먼저 프로젝트 목표를 입력해 주세요.")

    engine = os.getenv("AI_ENGINE", "mock").strip().lower()
    if engine in {"openai_compatible", "openai-compatible"}:
        stages, questions, assumptions = _request_ai_plan(normalized_goal)
        cost_note = f"실제 AI 관리자 계획 생성: {os.getenv('AI_MODEL', '설정 모델')} 사용. 승인 전에는 작업이 생성되지 않습니다."
    elif engine == "mock":
        stages = deepcopy(STARTER_STAGES)
        questions = list(DEFAULT_QUESTIONS)
        assumptions = list(DEFAULT_ASSUMPTIONS)
        cost_note = "모의 계획 단계: 외부 AI API 호출 없음, API 비용 0원"
    else:
        raise ValueError(
            f"지원하지 않는 AI_ENGINE 값입니다: {engine}. "
            "mock 또는 openai_compatible을 사용하세요."
        )

    return {
        "goal": normalized_goal,
        "questions": questions,
        "assumptions": assumptions,
        "stages": stages,
        "cost_note": cost_note,
        "status": "pending_approval",
        "created_at": created_at,
    }
