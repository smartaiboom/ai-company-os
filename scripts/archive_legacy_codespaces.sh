#!/usr/bin/env bash
# AI Company OS: archive legacy local-only items without deleting their contents.
# Run from any directory: bash scripts/archive_legacy_codespaces.sh
set -euo pipefail

repo="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo" || "$(basename "$repo")" != "ai-company-os" || "$(dirname "$repo")" != "/workspaces" ]]; then
  echo "중단: /workspaces/ai-company-os 저장소에서만 실행할 수 있습니다."
  exit 1
fi
cd "$repo"

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "중단: Git 관리 파일에 커밋되지 않은 변경이 있습니다."
  echo "우선 git status --short 결과를 확인하세요. reset/clean은 하지 마세요."
  exit 1
fi

items=(
  "ai-company-os-phase1"
  "app.py"
  "web_app.py"
  "work_plan.txt"
  "work_history"
  "__pycache__"
)

found=()
for item in "${items[@]}"; do
  if [[ -e "$repo/$item" || -L "$repo/$item" ]]; then
    if git ls-files --error-unmatch -- "$item" >/dev/null 2>&1; then
      echo "중단: $item 은 Git 추적 파일입니다. 기존 자료를 이동하지 않았습니다."
      exit 1
    fi
    found+=("$item")
  fi
done

if (( ${#found[@]} == 0 )); then
  echo "정리할 이전 로컬 파일이 없습니다. 완료."
  exit 0
fi

echo "이전 로컬 항목:"
printf '  %s\n' "${found[@]}"
echo
echo "위 항목은 삭제하지 않고 /workspaces 아래의 별도 보관 폴더로 이동합니다."
echo "예전 app.py 실행 경로 및 편집기 탭은 이동 후 동작하지 않을 수 있습니다."
read -r -p "계속하려면 '정리'를 입력하세요: " approval
if [[ "$approval" != "정리" ]]; then
  echo "취소: 변경된 파일이 없습니다."
  exit 0
fi

archive="$(mktemp -d /workspaces/ai-company-os-local-archive-XXXXXXXX)"
moved=()
for item in "${found[@]}"; do
  mv -- "$repo/$item" "$archive/$item"
  moved+=("$item")
done

{
  echo "AI Company OS 로컬 이전 파일 보관"
  echo "원래 위치: $repo"
  echo "보관 위치: $archive"
  echo "작업 시각(KST): $(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "파일 내용은 수정하거나 삭제하지 않았습니다."
  echo "보관된 항목:"
  printf -- '- %s\n' "${moved[@]}"
  echo "기존 프로젝트 데이터/비밀키를 GitHub에 업로드하지 마세요."
} > "$archive/ARCHIVE_INFO.txt"

echo
echo "정리 완료. 보관 폴더: $archive"
echo "보관된 항목:"
printf '  %s\n' "${moved[@]}"
echo
echo "현재 Git 상태:"
git status --short
echo
echo "주의: 보관 폴더는 GitHub에 올라가지 않습니다. Codespaces를 삭제하기 전에 별도 백업하세요."
