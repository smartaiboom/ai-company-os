"""Fictional M4 consent for tests only; never enables production or a real transport."""

from ai_safety import goal_hash


def approved_project(project):
    return {
        **project, "id": project.get("id", "unit-real-ai"),
        "real_ai": {
            "enabled": True, "limit": 7, "attempts": [],
            "consent": {"approved": True, "approved_at": "2026-11-02T00:00:00+09:00",
                        "goal_hash": goal_hash(project.get("manager_goal") or project.get("goal", "")),
                        "data_scope": "goal_task_inputs_predecessors_feedback"},
        },
    }
