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

## STEP 4~5. Flask 백엔드 + 프론트엔드

- `app.py` 작성: `/`(HTML 프론트), `/chat`, `/reset` 3개 엔드포인트.
  대화 이력은 전역 리스트(v1 단일 사용자 전제), **Ollama 호출 성공 후에만**
  user/assistant 메시지를 함께 이력에 확정하는 구조.
- **포트 변경**: macOS의 AirPlay Receiver(ControlCenter)가 5000 포트를 점유하고
  있어(`lsof -iTCP:5000` 확인) 기본 포트를 **5001**로 변경. PLAN의 curl 예시와
  다른 부분.

### curl 검증 결과 (PLAN 5절 기준 전부 수행)

| # | 케이스 | 기대 | 결과 |
|---|---|---|---|
| 1 | `GET /` | HTML 200 | ✅ `text/html; charset=utf-8` |
| 2 | 1턴: "제 이름은 승현입니다" | 200 + 응답 | ✅ history_length 2 |
| 3 | 2턴: "제 이름이 뭐라고 했죠?" | 문맥 유지 | ✅ "승현" 응답, history_length 4 |
| 4 | `POST /reset` | 이력 삭제 | ✅ history_length 0 |
| 5 | reset 후 이름 질문 | 문맥 상실 | ✅ 이름 모름 (일반 자기소개 응답) |
| 6 | 잘못된 JSON | 400 | ✅ `{"error": "...JSON이 아닙니다"}` |
| 7 | 빈 메시지 (`""`, `"   "`) | 400 | ✅ |
| 8 | 미설치 모델 요청 | 502 | ✅ `model 'no-such-model' not found` |
| 9 | 타임아웃 (OLLAMA_TIMEOUT=0.3s 인스턴스) | 504 | ✅ |
| 10 | Ollama 서버 중단 후 요청 | 503 | ✅ 안내 메시지 포함 |
| 11 | **이력 무결성**: 6~10 실패 후 이력 길이 | 불변 | ✅ 실패 전 2 → 실패들 → 성공 후 4 (실패분 미반영) |
| 12 | Ollama 재기동 후 복구 | 200 | ✅ `ollama ps`: llama3.2 100% GPU, 2.3GB 로드 |

**완료 기준 충족**: `/chat` curl 테스트(Content-Type 포함) ✅, 실패 시 이력
불변 ✅, 2턴 문맥 유지 ✅, `/reset` 후 문맥 삭제 ✅, 연결 실패 → 503 변환 ✅

## STEP 6. 모델 교체 실험

- 비교 대상: llama3.2(3B), phi3:mini(3.8B), mistral(7B) + 한국어 참고용 qwen2.5(7B)
- `benchmark_models.py`로 PLAN 2절 기준 수행: 동일 프롬프트("수도 + 명소 3곳,
  한국어로만"), `temperature=0, seed=42`, 모델별 **cold 1회 + warm 2회**,
  각 실행 전후 `ollama stop`으로 언로드. 원시값은
  [benchmark_raw.json](benchmark_raw.json), 표는
  [benchmark_results.md](benchmark_results.md).

### 속도 측정 결과

| 모델 | ID | 크기 | cold total | cold load | warm total 평균 | tok/s (warm) |
|---|---|---|---|---|---|---|
| llama3.2 (3B) | a80c4f17acd5 | 2.0 GB | 3.0s | 0.9s | 2.2s | **51.4** |
| phi3:mini (3.8B) | 4f2222927938 | 2.2 GB | 10.3s | 1.3s | 6.0s | 48.5 |
| mistral (7B) | 6577803aa9a0 | 4.4 GB | 14.5s | 2.2s | 12.1s | 25.7 |
| qwen2.5 (7B) | 845dbda0ea48 | 4.7 GB | 5.9s | 1.9s | 4.0s | 25.9 |

- warm 3회 간 tok/s 편차는 ±0.4 이내로 재현성 양호.
- 3B급(51 tok/s)과 7B급(26 tok/s)이 정확히 2배 차이 — 통합메모리 대역폭에
  묶이는 구조를 그대로 반영.

### 한국어 품질 평가표 (cold 응답 기준, 응답 전문은 benchmark_results.md)

| 모델 | 한국어 정확성 | 지시 준수 | 응답 완결성 | 사실 정확성 | 총평 |
|---|---|---|---|---|---|
| llama3.2 | △ "왕宫", "인cheon" 한자·로마자 혼입 | ○ 3곳 제시 | ○ | △ 인천대성당을 서울 명소로 제시 | 빠르지만 코드 스위칭 잦음 |
| phi3:mini | ✕ 문장 비문 다수, " endregion" 토큰 누출 | ✕ 2곳만 제시 | ✕ 논리 붕괴 | ✕ 부산·세종·대전을 수도로 나열 | 한국어 사용 불가 수준 |
| mistral | ○ 대체로 유창 | ○ 3곳 제시 | ○ | ✕ 명동을 "성당역", 인천공항을 천안 소재 명소로 서술 | 유창하나 환각 심함 |
| qwen2.5 | **◎ 혼입 없음** | **◎** | **◎** | **◎ 경복궁·남산타워·청계천 모두 타당** | **한국어 서비스 최적** |

**결론**: 한국어 챗봇 용도로는 **qwen2.5**가 명확한 승자. 속도는 7B라 26 tok/s
지만 답이 간결해 체감 응답 시간(warm 4.0s)은 mistral(12.1s)의 1/3.
영어 위주·속도 우선이면 llama3.2. 챗봇 기본 모델은
`OLLAMA_MODEL=qwen2.5 python app.py`로 교체 가능.

**완료 기준 충족**: 태그·ID·크기 기록 ✅, 동일 프롬프트·옵션 ✅, cold/warm 구분 ✅,
모델별 3회 ✅, 토큰 속도 계산 ✅, 평가표 작성 ✅

## STEP 7. 문서화

- `README.md` 작성: 실행법, 구성, 엔드포인트, 비교 결과 요약, v2 로드맵 링크
- 최종 커밋·푸시로 마무리
