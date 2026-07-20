# 로컬 LLM 챗봇 프로젝트 계획서

- 작성일: 2026-07-20
- 대상: 위키독스 "생성형 AI 개발 입문" Chapter 25 실습 기반
- 개발 환경: MacBook Pro (Apple M5, 통합메모리 16GB, arm64)

## 1. 프로젝트 개요

**목적**: 클라우드 API 없이 로컬 하드웨어에서 LLM을 직접 실행하고, 이를 Flask 웹
애플리케이션과 연동해 동작하는 챗봇을 완성한다. Chapter 25 실습 범위를 그대로
따라가는 것을 1차 목표로 하고, 완료 후 확장 여부를 판단한다.

**범위 (v1, Chapter 25 실습 + API 연동 추가 검증)**
- Ollama 설치 및 로컬 모델 실행
- REST API(`/api/generate`, `/api/chat`) 직접 호출 확인
- OpenAI 호환 API(`/v1`)로 기존 SDK 코드 재사용 확인
- Flask 기반 웹 챗봇(대화 이력 유지, HTML 프론트엔드 포함) 구현
- 모델 교체 실험 (llama3.2 vs mistral vs phi3:mini 등 비교)

**범위 밖 (v1에서 제외, 필요시 v2)**
- RAG, 문서 검색 연동
- LangChain 연동
- 배포(외부 공개), 인증/보안
- 대화 이력 영구 저장(DB)

## 2. 하드웨어 기준 모델 추천

M5 / 16GB 통합메모리는 GPU VRAM이 별도로 없고 시스템 메모리를 공유하는
Apple Silicon 구조라, "8GB 이하 VRAM" 등급과 유사하게 보수적으로 잡는 것이 안전하다.

| 우선순위 | 모델 | 명령어 | 비고 |
|---|---|---|---|
| 1차 (기본) | Llama 3.2 3B | `ollama run llama3.2` | 가볍고 빠름, 개발/디버깅용 |
| 2차 (비교용) | Phi-3 Mini | `ollama run phi3:mini` | 소형 대비 추론 품질 우수 |
| 3차 (비교용) | Mistral 7B Q4 | `ollama run mistral` | 16GB에서 실행 가능하나 다른 앱 종료 권장 |
| 한국어 테스트 | Qwen2.5 | `ollama run qwen2.5` | 한국어 응답 품질 확인용 |

7B급(mistral) 실행 시 브라우저·IDE 등 메모리 사용이 큰 앱은 닫고 테스트할 것.
13B 이상은 16GB 환경에서는 v1 범위에서 제외.

**비교 재현성**: `latest` 태그는 시점에 따라 내용이 바뀔 수 있고 모델 크기도
서로 다르므로(예: 기본 태그 기준 Llama 3.2 ~2.0GB, Phi-3 ~2.2GB, Mistral ~4.4GB,
Qwen2.5는 기본 7B·~4.7GB), 비교 시 아래를 함께 기록한다.
- 실제 사용한 모델 태그와 `ollama list`에 표시되는 ID·크기
- 동일 프롬프트와 동일 생성 옵션(temperature 등)
- 최초 로딩(cold) 실행과 워밍업 이후(warm) 실행을 구분
- 모델별 3회 실행
- 응답에 포함된 `total_duration`, `load_duration`, `eval_count`, `eval_duration`으로 토큰/초 계산
- 한국어 정확성·지시 준수·응답 완결성에 대한 간단한 평가표

## 3. 산출물 구조

```
local-llm-chatbot/
├── PLAN.md              # 본 계획서
├── app.py                # Flask 백엔드 (채팅 API, 대화이력)
├── test_ollama_api.py     # 2~3단계: REST/OpenAI 호환 API 호출 점검용 실행 스크립트 (pytest 아님)
├── requirements.txt       # flask, requests, openai (버전 범위 명시)
├── .gitignore             # venv, __pycache__ 등 제외
└── README.md              # 실행 방법, 스크린샷 (완료 후 작성)
```

**개발 환경**
- Python 버전: 로컬 설치 버전 확인 후 명시 (`python3 --version`)
- 가상환경: `python3 -m venv venv && source venv/bin/activate`
- `requirements.txt`는 버전 범위(예: `flask>=3.0,<4`)를 명시해 재현성 확보
- 포트폴리오 목적이므로 `git init` 및 `.gitignore` 초기 커밋에 포함

## 4. 단계별 작업 계획

| 단계 | 작업 | 산출물 | 완료 기준 |
|---|---|---|---|
| 0 | Ollama 설치 확인 | - | `ollama --version` 정상 출력 |
| 1 | 모델 다운로드 | - | `ollama list`에 llama3.2 표시 |
| 2 | REST API 호출 테스트 | `test_ollama_api.py` | 스트리밍/논스트리밍 응답 모두 확인 |
| 3 | OpenAI 호환 API 테스트 | 위 스크립트에 추가 | `/v1/chat/completions`에서 HTTP 200, `choices[0].message.content` 비어있지 않음, 네이티브 API와 동일 모델·프롬프트 처리 확인 |
| 4 | Flask 백엔드 작성 | `app.py` | `/chat` 엔드포인트 curl 테스트 통과(Content-Type 헤더 포함), Ollama 실패 시 대화 이력 불변 확인 |
| 5 | 프론트엔드 연결 | `app.py` 내 템플릿 | 브라우저에서 대화 가능, 2턴 질문으로 문맥 유지 확인, `/reset` 호출 후 이전 문맥 삭제 확인 |
| 6 | 모델 교체 실험 | 결과 메모 (README) | 2절 "비교 재현성" 기준(태그·크기·cold/warm·3회·토큰속도·평가표)에 따라 3개 모델 비교 기록 |
| 7 | 문서화 | `README.md` | 실행법 + 비교 결과 정리 |

## 5. 테스트/검증 방법

- API 직접 테스트:
  ```bash
  curl -X POST http://localhost:11434/api/generate \
    -H "Content-Type: application/json" \
    -d '{"model": "llama3.2", "prompt": "안녕하세요", "stream": false}'
  ```
- Flask 엔드포인트 테스트:
  ```bash
  curl -X POST http://localhost:5000/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "안녕하세요"}'
  ```
- OpenAI 호환 API: Ollama 공식 `/v1/chat/completions` 사용, OpenAI SDK의 `api_key`는 필수 파라미터이나 값 자체는 무시됨을 확인
- 대화 이력 무결성 (v1 완료 기준에 포함):
  - Ollama 호출 성공 후에만 사용자·어시스턴트 메시지를 함께 이력에 확정
  - Ollama 호출 실패 시 대화 이력이 변경되지 않는지 확인
  - 2턴 질문으로 문맥 유지 확인
  - `/reset` 호출 후 이전 문맥이 사라지는지 확인
- 실패/예외 케이스: Ollama 미실행 시 503 응답 반환을 구현하고 테스트 (연결 실패 → 503 변환), 잘못된 JSON, 빈 메시지, 미설치 모델 요청, 타임아웃 케이스도 각각 테스트
- 메모리 관측: `ollama ps`로 로드된 모델과 크기 확인, Activity Monitor로 메모리 압박 여부 체크

## 6. 리스크 및 대응

| 리스크 | 대응 |
|---|---|
| 16GB에서 7B 모델 실행 시 느려짐/스왑 발생 | Q4 양자화 유지, 다른 앱 종료, 3B 모델로 축소 |
| Ollama 서버 미기동 상태로 Flask 요청 실패 | `ollama serve` 상시 실행, 연결 실패를 503으로 변환하는 헬스체크 로직을 구현하고 테스트 |
| 대화 이력이 전역 변수라 다중 사용자 시 섞임 | v1은 단일 사용자 로컬 테스트 전제, 세션 분리는 v2 과제로 명시 |

## 7. v2 확장 로드맵 (포트폴리오/데모 수준으로 올리려면)

챕터 실습(v1)은 "동작 확인" 수준이라, 포트폴리오로 보여주려면 아래 항목이 추가로 필요:

1. **세션/사용자 분리**: 전역 리스트 대신 세션 ID 기반 대화 이력 관리 (Flask session 또는 SQLite)
2. **에러 처리 강화**: 타임아웃, 모델 미존재, 컨텍스트 길이 초과 등 예외 UI 피드백
3. **모델 선택 UI**: 드롭다운으로 llama3.2/mistral/phi3 런타임 전환
4. **응답 스트리밍**: 현재 `stream: False`를 SSE 또는 WebSocket 기반 스트리밍으로 교체 (체감 응답성 개선)
5. **간단한 RAG 데모**: 로컬 문서 업로드 → 임베딩(예: `nomic-embed-text` via Ollama) → 검색 결과를 프롬프트에 포함
6. **배포**: Docker화 + 간단한 README 데모 GIF/스크린샷, 또는 로컬 전용임을 명확히 문서화
7. **성능 비교 대시보드**: 모델별 응답 시간·토큰 속도를 기록해 표/그래프로 정리 (README 또는 별도 페이지)

권장 순서: v1 완료 → 4(스트리밍), 1(세션 분리), 3(모델 선택 UI)까지만 해도
"단순 튜토리얼 재현"과는 차별화된 결과물이 됨. 5(RAG)는 별도 프로젝트로 분리해도 무방.

## 8. 다음 액션

- [ ] Ollama 설치 여부 확인 (`ollama --version`)
- [ ] `ollama pull llama3.2` 실행
- [ ] `test_ollama_api.py` 작성 및 REST API(`/api/generate`, `/api/chat`) 테스트
- [ ] OpenAI 호환 API(`/v1/chat/completions`) 테스트 추가
- [ ] 이후 `app.py` 초안 작성 시작
