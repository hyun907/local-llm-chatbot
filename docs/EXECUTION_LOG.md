# 실행 기록 (EXECUTION_LOG)

- 프로젝트: 로컬 LLM 챗봇 (PLAN.md 기반, 위키독스 "생성형 AI 개발 입문" Ch.25)
- 환경: MacBook Pro (Apple M5, 16GB 통합메모리, arm64), macOS (Darwin 25.5.0)
- 실행일: 2026-07-20

각 STEP은 PLAN.md 4절 "단계별 작업 계획"의 단계 번호와 일치한다.
개념 정리는 [LEARNING_LOG.md](LEARNING_LOG.md) 참고.

---

## STEP 0. Ollama 설치 및 환경 확인

| 항목 | 결과 |
|---|---|
| Ollama | 미설치 상태 → `brew install ollama`로 설치, **v0.32.1** |
| Python | **3.11.15** (`python3 --version`) |
| Homebrew | 6.0.10 |

- 서버 기동: `OLLAMA_FLASH_ATTENTION="1" OLLAMA_KV_CACHE_TYPE="q8_0" ollama serve` (백그라운드)
  - Homebrew caveat이 권장한 환경변수 그대로 사용. Flash Attention + KV 캐시 q8_0 양자화는
    16GB 통합메모리 환경에서 메모리 사용량을 줄여준다.
- 기동 확인: `curl http://localhost:11434/` → `Ollama is running` ✅

**완료 기준 충족**: `ollama --version` 정상 출력 ✅

## STEP 1. 모델 다운로드

- `ollama pull llama3.2` 실행 (기본 태그 = 3B, Q4_K_M 양자화)
- `ollama list` 결과: `llama3.2:latest` / ID `a80c4f17acd5` / **2.0 GB** ✅

**완료 기준 충족**: `ollama list`에 llama3.2 표시 ✅

## STEP 2~3. REST API + OpenAI 호환 API 테스트

- 가상환경: `python3 -m venv venv` 후 `requirements.txt` 설치
  - 설치된 버전: Flask 3.1.3, requests 2.34.2, openai 2.46.0
- `test_ollama_api.py` 작성 후 실행 → **4/4 통과**

| # | 테스트 | 결과 | 비고 |
|---|---|---|---|
| 1 | `/api/generate` 논스트리밍 | PASS | eval 40 tokens, **51.3 tok/s** |
| 2 | `/api/generate` 스트리밍 | PASS | NDJSON 49청크 수신 후 조립 |
| 3 | `/api/chat` 논스트리밍 | PASS | `message.content` 비어있지 않음 |
| 4 | `/v1/chat/completions` (OpenAI SDK) | PASS | `api_key="ollama"` 더미 값으로 동작, `finish_reason=stop` |

**관찰**: llama3.2(3B)의 한국어 응답에 베트남어("Tôi là...")·중국어("我的")가
섞여 나오는 코드 스위칭 문제 확인. STEP 6 모델 비교에서 한국어 정확성 항목으로
정량 비교 예정. → [LEARNING_LOG.md](LEARNING_LOG.md#step-2-3) 참고

**완료 기준 충족**: 스트리밍/논스트리밍 모두 확인 ✅, `/v1/chat/completions`
HTTP 200 + `choices[0].message.content` 비어있지 않음 + 네이티브 API와 동일
모델·프롬프트 처리 ✅
