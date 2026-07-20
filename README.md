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

# 2. 모델 다운로드 (기본 모델: 한국어 특화 exaone3.5, RAG 임베딩: bge-m3)
ollama pull exaone3.5
ollama pull bge-m3

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
| `rag.py` | RAG 검색 모듈 (bge-m3 임베딩 + 코사인 유사도) |
| `data/` | RAG 지식 문서 (서울 명소) — txt를 추가하면 자동 인덱싱 |
| `docs/` | 실행·학습 기록, 벤치마크 결과 |

### API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/` | 챗봇 웹 UI |
| POST | `/chat` | `{"message": "..."}` → **SSE 스트림** (`data: {"delta": ...}` 이벤트, 완료 시 `{"done": true}`). 검증·연결 실패 시 JSON 400/502/503/504 |
| POST | `/reset` | 대화 이력 초기화 |

대화 이력은 Ollama 호출이 성공한 경우에만 확정되므로, 서버 장애·타임아웃이
발생해도 이전 문맥이 오염되지 않는다. 이력은 **브라우저 세션별로 분리**된다
(세션 ID 쿠키 + 서버 메모리, v2 로드맵 1번 구현 완료).

### RAG (검색 증강 생성)

`data/*.txt`의 문서를 bge-m3로 임베딩해두고, 질문과 유사도 0.5 이상인 상위
청크를 시스템 프롬프트에 근거로 주입한다. 근거가 쓰인 답변에는 UI에
"📄 참고 자료" 표시가 붙는다. 적용 전후 비교:

| 질문 | RAG 없음 (환각) | RAG 적용 |
|---|---|---|
| 경복궁은 어느 구에? | "용산구" ✕ | **"종로구, 1395년 창건"** ✓ |
| 서울 최고층 건물은? | (모델 지식에 의존) | **"롯데월드타워, 약 555m"** ✓ |
| 파이썬이 뭐야? | - | 자료 무관 → RAG 미개입, 일반 답변 |

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
| qwen2.5 (7B) | 4.7 GB | 5.9s | 4.0s | 25.9 | ○ 정확·간결, 간헐적 영어 누출 |
| exaone3.5 (7.8B) | 4.8 GB | 6.6s | 4.2s | 25.1 | **◎ 한국어 특화, 혼입·오류 없음** |
| qwen3:8b (think off) | 5.2 GB | 4.3s | 1.6s | 23.6 | △ 지시 준수 약함 |

**결론**: 1차 비교(상위 4종)에서는 qwen2.5가 우세했으나, 실사용에서 간헐적
영어 누출·사실 오류가 관찰되어 2차 비교를 진행했고, 한국어 특화 모델인
**exaone3.5를 기본 모델로 최종 채택**했다 (혼입·사실 오류 없음, 지시 준수
최상, 속도 동급). 외국어 혼입을 줄이는 한국어 시스템 프롬프트도 함께 사용한다.
속도 우선·영어 위주라면 환경변수로 교체 가능:

```bash
OLLAMA_MODEL=llama3.2 python app.py
```

상세 평가표와 관찰은 [docs/EXECUTION_LOG.md](docs/EXECUTION_LOG.md),
배운 점 정리는 [docs/LEARNING_LOG.md](docs/LEARNING_LOG.md) 참고.

## 한계 및 다음 단계 (v2)

- ~~대화 이력이 전역 변수 → 다중 사용자 시 섞임~~ → **세션 분리 구현 완료**
  (단, 이력은 메모리에만 있어 서버 재시작 시 소멸 — 영구 저장은 DB 과제)
- ~~`stream: false` 고정~~ → **SSE 스트리밍 구현 완료** (첫 글자 표시 ~3초 → 0.25초)
- ~~사실 오류(환각)~~ → **RAG 구현 완료** (단, 준비된 문서 범위 안에서만 유효)
- 남은 작업의 우선순위·예상 규모는 [docs/NEXT_STEPS.md](docs/NEXT_STEPS.md)에 정리
  (1순위: 모델 선택 UI → README 스크린샷 → pytest 자동화)
