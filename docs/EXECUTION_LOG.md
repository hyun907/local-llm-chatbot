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
- 완료 기준: `ollama list`에 llama3.2 표시

(진행 중 — 완료 후 결과 추가)
