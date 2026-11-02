"""Deterministic document format checks. No AI, network or file access."""

import re

REVIEWER_ID = "mock-quality-reviewer-v1"
RULESET_ID = "required-sections-v1"
SECTIONS = ("목표", "결과", "미확인 사항")


def inconclusive_review():
    return {
        "schema_version": 1, "reviewer_id": REVIEWER_ID, "ruleset_id": RULESET_ID,
        "verdict": "inconclusive", "checks": [],
        "feedback": ["형식 검사를 판정할 수 없습니다. 입력·규칙 또는 처리 상태를 확인해 주세요."],
    }


def evaluate_format(result, ruleset_id=RULESET_ID, reviewer_id=REVIEWER_ID):
    if (ruleset_id != RULESET_ID or reviewer_id != REVIEWER_ID
            or not isinstance(result, str) or not result.strip()):
        return inconclusive_review()
    locations = {}
    fence = None
    for number, line in enumerate(result.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is not None:
            continue
        match = re.fullmatch(r"(?:#{1,6}[ \t]+)?(목표|결과|미확인 사항)", stripped)
        if match:
            locations.setdefault(match.group(1), number)
    checks = [
        {"rule_id": f"section-{index}", "expected": section,
         "satisfied": section in locations, "line": locations.get(section)}
        for index, section in enumerate(SECTIONS, 1)
    ]
    missing = [c["expected"] for c in checks if not c["satisfied"]]
    return {
        "schema_version": 1, "reviewer_id": REVIEWER_ID, "ruleset_id": RULESET_ID,
        "verdict": "changes_needed" if missing else "pass", "checks": checks,
        "feedback": [f"'{section}'을 독립된 줄 또는 Markdown 제목으로 추가해 주세요." for section in missing]
        or ["필수 제목 형식 검사를 통과했습니다. 사실성 검증이나 사용자 승인을 뜻하지 않습니다."],
    }


def validate_review(review):
    if (not isinstance(review, dict) or review.get("schema_version") != 1
            or review.get("reviewer_id") != REVIEWER_ID or review.get("ruleset_id") != RULESET_ID
            or review.get("verdict") not in ("pass", "changes_needed", "inconclusive")
            or not isinstance(review.get("feedback"), list) or not 1 <= len(review["feedback"]) <= 3
            or any(not isinstance(f, str) or not f.strip() or len(f) > 500 for f in review["feedback"])):
        raise ValueError("잘못된 형식 검사 판정입니다.")
    checks = review.get("checks")
    if review["verdict"] == "inconclusive":
        if checks != []:
            raise ValueError("판정 불가의 검사 근거가 잘못됐습니다.")
        return
    if not isinstance(checks, list) or len(checks) != len(SECTIONS):
        raise ValueError("형식 검사 근거가 없습니다.")
    for index, (section, check) in enumerate(zip(SECTIONS, checks), 1):
        if (not isinstance(check, dict) or check.get("rule_id") != f"section-{index}"
                or check.get("expected") != section or type(check.get("satisfied")) is not bool
                or (check["satisfied"] and (type(check.get("line")) is not int or check["line"] < 1))
                or (not check["satisfied"] and check.get("line") is not None)):
            raise ValueError("잘못된 형식 검사 근거입니다.")
    if (review["verdict"] == "pass") != all(c["satisfied"] for c in checks):
        raise ValueError("판정과 검사 근거가 일치하지 않습니다.")
