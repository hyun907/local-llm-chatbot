# 학습 기록 (LEARNING_LOG)

실행 절차는 [EXECUTION_LOG.md](EXECUTION_LOG.md)에, 각 STEP에서 배운 개념은 여기에 정리한다.

---

## STEP 0. Ollama와 Apple Silicon 메모리 구조

- **Ollama**: 로컬에서 LLM을 실행하는 런타임. 내부적으로 llama.cpp 기반이며,
  모델 다운로드(레지스트리) + 실행(추론 서버) + REST API 제공을 한 번에 해준다.
  기본 포트는 `11434`.
- **Apple Silicon 통합메모리(Unified Memory)**: CPU와 GPU가 하나의 메모리 풀을
  공유한다. "GPU VRAM 16GB"가 아니라 OS·앱·모델이 16GB를 나눠 쓰는 구조라,
  모델 크기 선택 시 dGPU VRAM 8GB급으로 보수적으로 잡아야 스왑을 피할 수 있다.
- **서버 기동 옵션** (Homebrew caveat 권장값):
  - `OLLAMA_FLASH_ATTENTION=1`: 어텐션 연산의 메모리 효율 개선.
  - `OLLAMA_KV_CACHE_TYPE=q8_0`: KV 캐시(대화 컨텍스트 저장 공간)를 8bit로
    양자화해 메모리 절약. 긴 컨텍스트일수록 효과가 큼.

## STEP 1. 모델 태그와 양자화

- `ollama pull llama3.2`의 기본(latest) 태그는 **3B 파라미터, Q4_K_M 양자화**
  버전으로 2.0GB. 원본 FP16 3B는 약 6GB인데 4bit 양자화로 1/3 수준이 된 것.
- **양자화(Quantization)**: 가중치를 16bit → 4bit 등으로 낮춰 메모리·속도를
  얻고 약간의 품질을 내주는 트레이드오프. Q4_K_M은 "4bit + 중요 레이어는
  더 높은 정밀도"를 쓰는 혼합 방식.
- `latest` 태그는 시점에 따라 가리키는 내용이 바뀔 수 있으므로, 재현성이
  필요하면 `ollama list`의 **ID(digest)** 를 함께 기록해야 한다.
  (이번 실행: `llama3.2:latest` = `a80c4f17acd5`)

<a id="step-2-3"></a>
## STEP 2~3. Ollama의 세 가지 API

| API | 용도 | 요청 형식 |
|---|---|---|
| `/api/generate` | 단발 텍스트 완성 | `prompt` 문자열 하나 |
| `/api/chat` | 대화형 (멀티턴) | `messages: [{role, content}, ...]` 배열 |
| `/v1/chat/completions` | OpenAI 호환 | OpenAI SDK 그대로 사용 가능 |

- **스트리밍 방식**: `stream: true`면 응답이 NDJSON(한 줄에 JSON 하나)으로
  토큰 단위 도착한다. 각 청크의 `response`를 이어 붙이고 `done: true`에서
  종료. OpenAI의 SSE(`data: ...`) 형식과 다르다는 점에 주의.
- **성능 메트릭**: 논스트리밍 응답 마지막에 `eval_count`(생성 토큰 수)와
  `eval_duration`(나노초)이 붙는다. 토큰 속도 = `eval_count / eval_duration × 1e9`.
  이번 측정: 51.3 tok/s (llama3.2 3B, M5).
- **OpenAI 호환 레이어**: `base_url`만 `http://localhost:11434/v1`로 바꾸면
  기존 OpenAI SDK 코드가 그대로 동작한다. `api_key`는 SDK에서 필수라 아무
  값이나 넣어야 하지만 Ollama는 검증하지 않는다. → 기존 OpenAI 기반 코드를
  로컬 LLM으로 갈아끼울 때 코드 수정이 거의 없다는 게 핵심 이점.
- **작은 모델의 한국어 한계**: llama3.2 3B는 한국어 질문에 베트남어·중국어가
  섞인 답("Tôi là...", "我的")을 내는 **코드 스위칭** 현상을 보였다. 다국어
  학습 데이터에서 한국어 비중이 작은 소형 모델의 전형적 한계. 한국어 중심
  서비스라면 qwen2.5 등 한국어 비중이 높은 모델이 필요함을 시사한다.
