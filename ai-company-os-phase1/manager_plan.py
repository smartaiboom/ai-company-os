"""Manager planning helpers.

This module currently provides a deterministic starter plan. It is deliberately
separate from the web handler so a goal-driven AI planner can replace it later.
"""
from copy import deepcopy


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


def build_manager_plan(goal, created_at):
    """Build a starter plan without calling an external AI service.

    The starter stages remain a temporary fallback; the planner is isolated so
    later work can generate a variable number of stages based on the goal.
    """
    normalized_goal = str(goal or "").strip()
    if not normalized_goal:
        raise ValueError("먼저 프로젝트 목표를 입력해 주세요.")

    return {
        "goal": normalized_goal,
        "questions": list(DEFAULT_QUESTIONS),
        "assumptions": list(DEFAULT_ASSUMPTIONS),
        "stages": deepcopy(STARTER_STAGES),
        "cost_note": "모의 계획 단계: 외부 AI API 호출 없음, API 비용 0원",
        "status": "pending_approval",
        "created_at": created_at,
    }
