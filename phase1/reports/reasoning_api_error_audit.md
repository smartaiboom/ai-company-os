# 개발 업무 HTTP 400: reasoning 필수 오류 점검

점검일: 2026-10-29  
대상 오류: `Reasoning is mandatory for this endpoint and cannot be disabled.`  
범위: 실행 엔진 요청 구성, 설정 로딩, reasoning 제어값, 제공자 요청 형식 대조

## 요약

코드와 현재 프로세스 환경 설정에서 직접 확인한 가장 강한 원인은 **요청 payload가 reasoning을 명시적으로 비활성화하면서 OpenRouter가 선택한 endpoint/모델 경로가 reasoning을 필수로 요구하는 충돌**이다. 요청은 `execution_engine.py:282-285`에서 `reasoning: {enabled: false, exclude: true}`와 `chat_template_kwargs: {enable_thinking: false}`를 모두 넣는다. 사용자가 제공한 서버 오류는 reasoning 비활성화를 거부한다.

현재 `AI_MODEL=openrouter/free`는 특정 모델 ID가 아니라 OpenRouter가 무료 모델 중 하나를 라우팅하는 선택자이므로, 이 설정만으로 오류를 발생시킨 정확한 하위 모델·제공자·라우트는 알 수 없다. 따라서 위 원인 설명은 코드와 오류 문구가 일치하는 **강한 추정**이며, 실제 요청의 라우팅 메타데이터나 해당 실패 요청 기록을 확인한 결론은 아니다.

## 현재 설정 확인

비밀값을 출력하지 않고 현재 프로세스의 세 환경변수만 확인했다. `AI_API_BASE_URL`은 사용자 정보·쿼리 문자열을 출력하지 않도록 정규화했다.

| 변수 | 현재 확인값 | 코드 동작 |
|---|---|---|
| `AI_ENGINE` | `openai_compatible` | `execution_engine.py:392-398`에서 실제 OpenAI 호환 엔진을 선택 |
| `AI_API_BASE_URL` | `https://openrouter.ai/api/v1` | `execution_engine.py:204`에서 환경변수로 읽고 끝의 `/`를 제거 |
| `AI_MODEL` | `openrouter/free` | `execution_engine.py:206`에서 읽고 `:209`에서 실제 API 요청 전에 이 값만 허용하는 보호 검사를 수행 |

코드 검색에서 `.env` 파일 로더는 발견되지 않았으며, 이 설정들은 `os.getenv()`로 읽힌다. `.env` 파일 내용이나 API 키는 열람하거나 출력하지 않았다. `AI_API_KEY`는 실제 값 확인 없이 요청 코드가 존재하는지만 확인했다.

## 요청 구성과 reasoning 비활성화 여부

`execution_engine.py:195-214`는 OpenAI 호환 Chat Completions 실행기를 정의한다. 모델 보호 검사를 통과하고 base URL이 있으면 `execution_engine.py:271-286`에서 JSON 본문을 만든다. 본문에는 `model`, system/user `messages`, `temperature: 0.3`, `max_tokens: 4096` 외에 다음 제어가 있다.

- `reasoning: {"enabled": false, "exclude": true}` — reasoning 기능을 끄도록 명시한다.
- `chat_template_kwargs: {"enable_thinking": false}` — 모델별 템플릿에서 thinking을 끄도록 명시한다.

이후 `execution_engine.py:292-297`은 `{AI_API_BASE_URL}/chat/completions`에 JSON POST 요청을 만든다. `AI_API_KEY`가 설정되어 있다면 Bearer 헤더를 넣지만 키 값은 본 보고서에 기록하지 않았다. HTTP 오류 응답은 `execution_engine.py:302-306`에서 응답 본문 일부를 포함한 오류로 다시 던진다. 따라서 제시된 오류 문구는 서버가 반환한 응답 내용으로 앱의 HTTPError 처리와 부합한다.

## OpenRouter 형식과 코드의 차이

OpenRouter 공식 Chat Completions 문서는 `POST /api/v1/chat/completions`와 `model`·`messages` 형식을 설명하며, `reasoning`을 reasoning 모델의 설정 객체로 문서화한다. 이 엔드포인트의 일반 요청 형식과 현재 코드의 endpoint·주요 본문 형식은 일치한다. [OpenRouter Chat Completions API 문서](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion)

OpenRouter 공식 무료 모델 안내는 `openrouter/free`가 매 요청마다 사용 가능한 무료 모델 중 하나를 선택한다고 설명한다. 따라서 하위 모델에 따라 reasoning 요구사항과 지원 파라미터가 달라질 수 있고, 현재 프로젝트 설정만으로 어떤 모델이 문제 응답을 냈는지 특정할 수 없다. [OpenRouter Free Models 안내](https://openrouter.ai/collections/free-models/), [openrouter/free 라우터 설명](https://openrouter.ai/openrouter/free/apps)

코드와 오류의 구체적인 차이는 표준 endpoint 경로보다는 **reasoning 제어값**이다. 코드가 비활성화를 명시하지만 응답 endpoint는 비활성화를 허용하지 않고 reasoning을 필수로 요구한다. OpenRouter 문서상 `reasoning`은 선택적 설정 파라미터이며 일반 API 문서가 모든 라우팅 대상 모델의 개별 요구 조건을 보장하지 않는다. 무료 라우터가 어떤 하위 모델을 골랐는지, 그 모델 제공자가 어떤 별도 필수 필드를 적용했는지는 실패 응답 문구만으로 확인되지 않는다.

## 확인된 사실과 추정

**확인된 사실**

- 현재 프로세스 환경은 `AI_ENGINE=openai_compatible`, `AI_API_BASE_URL=https://openrouter.ai/api/v1`, `AI_MODEL=openrouter/free`다.
- 요청 코드는 reasoning을 비활성화하는 두 파라미터를 payload에 명시한다.
- OpenRouter Chat Completions URL로 JSON POST를 보내며, HTTP 오류 응답 본문을 애플리케이션 오류에 포함한다.
- 현재 모델 값은 OpenRouter 무료 라우터 ID이며 특정 하위 모델 ID가 아니다.
- 오류 문구 자체는 사용자가 제공한 것이며, 이번 점검에서 API를 호출해 재현하지 않았다.

**추정 또는 미확인**

- 가장 가능성 높은 원인은 선택된 모델/제공자 endpoint의 reasoning 필수 조건과 `enabled: false` 설정의 충돌이다. 오류 문구와 payload가 직접 맞물리지만 실제 라우팅 결과가 없어 확정은 아니다.
- `chat_template_kwargs.enable_thinking=false`가 해당 라우팅 대상에서 별도 문제를 일으켰는지는 확인할 수 없다. 다만 보고된 문구는 reasoning 비활성화 거부를 직접 가리킨다.
- 이 실패 요청의 실제 하위 모델, 제공자, endpoint, 선택된 라우트 및 서버가 `exclude`·`chat_template_kwargs`를 어떻게 처리했는지는 확인되지 않았다.
- 공식 일반 요청 문서에 없는 `chat_template_kwargs`가 현재 라우터 경로에서 허용·전달되는지 정적 코드나 문서만으로 검증할 수 없다.

## 테스트 및 작업 기록

실행한 명령:

```text
python -m unittest tests.test_execution_engine
```

결과: **12개 테스트 통과 (OK)**. 테스트는 설정 누락·무료 모델 검사와 모의 실행기 등을 확인한다. 기존 테스트에는 실제 HTTP payload에 reasoning 필드가 포함되는지, 해당 400 응답을 재현하는 검사는 없다. 따라서 테스트 결과는 오류 원인 재현이나 외부 제공자 호환성 검증을 의미하지 않는다.

- 코드, `.env`, API 키, 프로젝트 데이터 및 기존 작업 결과: 변경 없음.
- 생성한 보고서: `reports/reasoning_api_error_audit.md`.
- 외부 AI API 호출: 없음.
- 비밀값: 열람·기록하지 않음.
