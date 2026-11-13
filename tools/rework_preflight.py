"""Read-only cutroom / Gemini preflight. No HTTP, API, secrets, or writes.

Usage:
  PYTHONPATH=core:companies/video python -B tools/rework_preflight.py
  PYTHONPATH=core:companies/video python -B tools/rework_preflight.py --root data/video_representative_workflow/studio
"""
import argparse
from pathlib import Path
import os

from autonomous_company import Store, CompanyError
from representative_rework import ReworkStore, progress_view, execution_settings
from autonomous_gemini35 import MODEL


def inspect(root):
    main = Store(root)
    jobs = ReworkStore(root / "representative_rework")
    paths = sorted(root.glob("company-*.json"))
    print("=== AI 재작업 실행 전 읽기 전용 점검 ===")
    print("데이터 위치:", root)
    print("프로젝트 파일:", len(paths))
    settings = execution_settings()
    print("실행 설정:", "충족" if settings["ready"] else "미충족")
    if settings["missing"]:
        print("부족 설정:", ", ".join(settings["missing"]))
    print("고정 모델:", MODEL)
    print("키 내용/대본 내용/대표 피드백: 출력하지 않음")
    matched = 0
    for path in paths:
        try:
            p = main.load(path.stem)
            flow = p.get("representative", {})
            state = flow.get("rework")
            if not state:
                continue
            matched += 1
            job = jobs.load(state["job"])
            attempts = job.get("real_ai", {}).get("attempts", [])
            reserved = sum(a.get("status") == "reserved" for a in attempts)
            unresolved = sum(a.get("status") not in ("completed", "failed") for a in attempts)
            completed = sum(a.get("status") == "completed" for a in attempts)
            stopped = state.get("status") == "stopped"
            report = progress_view(job, state).get("quality_report")
            decision = state.get("quality_decision")
            history = flow.get("rework_history", [])
            print("---")
            print("프로젝트:", path.stem)
            print("대표 단계:", flow.get("stage"))
            print("재작업:", state.get("status"), "/ 원인:", state.get("error") or "없음")
            print("작업 파일:", job["id"])
            print("호출 기록:", len(attempts), "/ 완료:", completed,
                  "/ 예약:", reserved, "/ 미확정:", unresolved)
            print("과거 기록:", len(history), "/ 대표 품질 보고:", "있음" if report else "없음",
                  "/ 대표 추가 지시:", decision.get("action") if decision else "없음")
            if reserved or unresolved:
                recommendation = "중단: 미확정 호출 기록 확인 필요. 실행 금지"
            elif stopped and (state.get("error") == "rework_goal_not_met" or job.get("reason_code") == "rework_goal_not_met"):
                recommendation = "과거 형식의 품질 실패: 자동 새 작업 생성 대상 아님. 기록 보존 및 별도 복구 설계 필요"
            elif stopped and report and decision and decision.get("action") == "request_revision":
                recommendation = "대표 추가 지시 확인됨: 새 작업 준비 조건 점검 가능. 신규 동의 및 명시 승인 전 API 호출 금지"
            elif stopped and report and not decision:
                recommendation = "대표 판단 대기: 컷룸에서 수정 지시 또는 보류만 기록 가능"
            elif state.get("status") == "pending":
                recommendation = "새 제안 동의 대기: 승인 전 API 호출 금지"
            elif state.get("status") == "approved":
                recommendation = "동의 기록 있음: 실제 실행은 신규 범위·호출 상한 확인 및 별도 사용자 승인 후 판단"
            else:
                recommendation = "실행하지 말고 현재 상태와 기록을 우선 검토"
            print("판정:", recommendation)
        except (CompanyError, KeyError, ValueError, TypeError, OSError) as exc:
            print("---")
            print("프로젝트:", path.stem)
            print("판정: 읽기/무결성 확인 실패, 실행 금지")
            print("오류 종류:", type(exc).__name__)
            print("오류 코드:", getattr(exc, "code", "없음"))
    print("---")
    print("재작업 기록이 있는 프로젝트:", matched)
    print("최종 결과: 본 도구는 조회만 수행하며 동의·실행·복구를 수행하지 않습니다.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path,
                        default=Path("data/video_representative_workflow/studio"))
    args = parser.parse_args()
    inspect(args.root.resolve())


if __name__ == "__main__":
    main()
