"""Ollama API 호출 점검 스크립트 (STEP 2~3).

pytest가 아니라 직접 실행하는 점검용 스크립트다.

    python test_ollama_api.py

검증 항목:
  1. /api/generate  논스트리밍 — 단발 프롬프트 응답
  2. /api/generate  스트리밍   — 청크 단위 수신
  3. /api/chat      논스트리밍 — messages 형식 응답
  4. /v1/chat/completions      — OpenAI SDK로 동일 모델·프롬프트 처리
"""

import json
import sys

import requests
from openai import OpenAI

OLLAMA_HOST = "http://localhost:11434"
MODEL = "llama3.2"
PROMPT = "안녕하세요. 한 문장으로 자기소개를 해주세요."


def check(name: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def test_generate_non_streaming() -> bool:
    """1. /api/generate 논스트리밍"""
    r = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": MODEL, "prompt": PROMPT, "stream": False},
        timeout=120,
    )
    body = r.json()
    ok = r.status_code == 200 and bool(body.get("response", "").strip())
    tokens_per_sec = (
        body["eval_count"] / body["eval_duration"] * 1e9
        if body.get("eval_duration")
        else 0
    )
    print(f"  응답: {body.get('response', '')[:80]}...")
    return check(
        "/api/generate (non-streaming)",
        ok,
        f"eval {body.get('eval_count')} tokens, {tokens_per_sec:.1f} tok/s",
    )


def test_generate_streaming() -> bool:
    """2. /api/generate 스트리밍 — 한 줄에 JSON 객체 하나씩(NDJSON) 도착"""
    r = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": MODEL, "prompt": PROMPT, "stream": True},
        stream=True,
        timeout=120,
    )
    chunks = []
    for line in r.iter_lines():
        if not line:
            continue
        piece = json.loads(line)
        chunks.append(piece.get("response", ""))
        if piece.get("done"):
            break
    text = "".join(chunks)
    print(f"  청크 수: {len(chunks)}, 조립된 응답: {text[:80]}...")
    return check(
        "/api/generate (streaming)",
        r.status_code == 200 and len(chunks) > 1 and bool(text.strip()),
        f"{len(chunks)} chunks",
    )


def test_chat_non_streaming() -> bool:
    """3. /api/chat — role/content 메시지 배열 형식"""
    r = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": PROMPT}],
            "stream": False,
        },
        timeout=120,
    )
    body = r.json()
    content = body.get("message", {}).get("content", "")
    print(f"  응답: {content[:80]}...")
    return check(
        "/api/chat (non-streaming)",
        r.status_code == 200 and bool(content.strip()),
    )


def test_openai_compatible() -> bool:
    """4. /v1/chat/completions — OpenAI SDK 재사용.

    api_key는 SDK에서 필수 파라미터지만 Ollama는 값을 무시한다.
    """
    client = OpenAI(base_url=f"{OLLAMA_HOST}/v1", api_key="ollama")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": PROMPT}],
    )
    content = resp.choices[0].message.content or ""
    print(f"  응답: {content[:80]}...")
    return check(
        "/v1/chat/completions (OpenAI SDK)",
        bool(content.strip()),
        f"model={resp.model}, finish_reason={resp.choices[0].finish_reason}",
    )


def main() -> int:
    # 서버 헬스체크: 미기동이면 바로 안내하고 종료
    try:
        requests.get(OLLAMA_HOST, timeout=3)
    except requests.exceptions.ConnectionError:
        print(f"Ollama 서버에 연결할 수 없습니다: {OLLAMA_HOST}")
        print("먼저 `ollama serve`를 실행하세요.")
        return 1

    results = [
        test_generate_non_streaming(),
        test_generate_streaming(),
        test_chat_non_streaming(),
        test_openai_compatible(),
    ]
    print(f"\n{sum(results)}/{len(results)} 테스트 통과")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
