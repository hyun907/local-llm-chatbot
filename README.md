# 로컬 LLM 챗봇 (Ollama + Flask)

클라우드 API 없이 로컬에서 LLM을 실행하고 Flask 웹 챗봇으로 연동한 프로젝트.
위키독스 "생성형 AI 개발 입문" Chapter 25 실습 기반. ([계획서](PLAN.md))

- 개발 환경: MacBook Pro (Apple M5, 통합메모리 16GB), macOS / Ollama 0.32.1 / Python 3.11
- 진행 과정 기록: [실행 기록](docs/EXECUTION_LOG.md) · [학습 기록](docs/LEARNING_LOG.md)

## 실행 방법

```bash
# 1. Ollama 설치 및 서버 기동
brew install ollama
OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve   # 별도 터미널

# 2. 모델 다운로드 (기본 모델: 한국어 품질이 가장 좋았던 qwen2.5)
ollama pull qwen2.5

# 3. Python 환경
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 4. API 점검 (선택)
python test_ollama_api.py

# 5. 챗봇 실행 → 브라우저에서 http://localhost:5001
python app.py
```

> 포트가 5000이 아니라 **5001**인 이유: macOS AirPlay Receiver가 5000 포트를
> 점유하고 있어 충돌을 피했다. `PORT` 환경변수로 변경 가능.

## 구성

| 파일 | 역할 |
|---|---|
| `app.py` | Flask 백엔드 + HTML 프론트엔드 (단일 파일) |
| `test_ollama_api.py` | Ollama REST/OpenAI 호환 API 점검 스크립트 |
| `benchmark_models.py` | 모델 비교 벤치마크 (cold/warm, tok/s) |
| `docs/` | 실행·학습 기록, 벤치마크 결과 |

### API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/` | 챗봇 웹 UI |
| POST | `/chat` | `{"message": "..."}` → `{"reply": "..."}`. 실패 시 400/502/503/504 |
| POST | `/reset` | 대화 이력 초기화 |

대화 이력은 Ollama 호출이 성공한 경우에만 확정되므로, 서버 장애·타임아웃이
발생해도 이전 문맥이 오염되지 않는다. 이력은 **브라우저 세션별로 분리**된다
(세션 ID 쿠키 + 서버 메모리, v2 로드맵 1번 구현 완료).

## 모델 비교 실험 (STEP 6)

`benchmark_models.py`로 동일 프롬프트·동일 옵션(`temperature=0, seed=42`),
모델별 cold 1회 + warm 2회 측정. 응답 전문과 원시값은
[docs/benchmark_results.md](docs/benchmark_results.md) ·
[docs/benchmark_raw.json](docs/benchmark_raw.json) 참고.

| 모델 | 크기 | cold total | warm total | tok/s | 한국어 품질 |
|---|---|---|---|---|---|
| llama3.2 (3B) | 2.0 GB | 3.0s | 2.2s | **51.4** | △ 한자·로마자 혼입 |
| phi3:mini (3.8B) | 2.2 GB | 10.3s | 6.0s | 48.5 | ✕ 비문·사실 오류 다수 |
| mistral (7B) | 4.4 GB | 14.5s | 12.1s | 25.7 | △ 유창하나 환각 심함 |
| qwen2.5 (7B) | 4.7 GB | 5.9s | 4.0s | 25.9 | **◎ 정확·간결** |

**결론**: 한국어 챗봇 용도는 **qwen2.5** 우세 (유일하게 사실 오류·언어 혼입
없음, 간결한 답변 덕에 7B임에도 체감 응답 4초). 이 결과에 따라 챗봇의 **기본
모델을 qwen2.5로 채택**하고, 외국어 혼입을 줄이는 한국어 시스템 프롬프트를
추가했다. 속도 우선·영어 위주라면 환경변수로 교체 가능:

```bash
OLLAMA_MODEL=llama3.2 python app.py
```

상세 평가표와 관찰은 [docs/EXECUTION_LOG.md](docs/EXECUTION_LOG.md),
배운 점 정리는 [docs/LEARNING_LOG.md](docs/LEARNING_LOG.md) 참고.

## 한계 및 다음 단계 (v2)

- ~~대화 이력이 전역 변수 → 다중 사용자 시 섞임~~ → **세션 분리 구현 완료**
  (단, 이력은 메모리에만 있어 서버 재시작 시 소멸 — 영구 저장은 DB 과제)
- `stream: false` 고정 → SSE 스트리밍으로 체감 응답성 개선 여지
- 상세 로드맵은 [PLAN.md 7절](PLAN.md) 참고
