"""Ollama 기반 로컬 LLM 챗봇 — Flask 백엔드 + 단일 페이지 프론트엔드 (STEP 4~5).

실행:
    python app.py                      # http://localhost:5001
환경변수:
    OLLAMA_HOST     (기본 http://localhost:11434)
    OLLAMA_MODEL    (기본 llama3.2)
    OLLAMA_TIMEOUT  (기본 120초)
    PORT            (기본 5001 — macOS AirPlay가 5000을 점유)

대화 이력은 브라우저 세션(쿠키의 세션 ID)별로 분리해 서버 메모리에 관리한다.
Ollama 호출이 성공했을 때만 user/assistant 메시지를 함께 이력에 확정하므로,
호출 실패 시 이력은 변하지 않는다.
"""

import json
import os
import secrets
import uuid

import requests
from flask import Flask, Response, jsonify, render_template_string, request, session

import rag

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
# 2차 모델 비교(사후 개선 5) 결과 한국어 품질 1위였던 exaone3.5(한국어 특화)를 기본값으로 사용
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "exaone3.5")
TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "120"))

# 소형 모델의 외국어 혼입·어색한 어미를 줄이기 위한 시스템 프롬프트.
# 이력에는 저장하지 않고 매 요청 맨 앞에 붙인다.
SYSTEM_PROMPT = (
    "당신은 친절한 한국어 챗봇입니다. 항상 자연스럽고 문법에 맞는 한국어로만 "
    "답하세요. 영어 단어, 한자, 다른 언어를 섞지 마세요. 답은 간결하게 하세요."
)

# Ollama 기본값(0.8)에서는 저확률 코드 토큰(":numel" 등)이 간헐적으로 누출됨.
# 0.4로 낮춰 누출을 억제하되 답변 다양성은 유지한다.
TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.4"))

# RAG 인덱스: data/*.txt를 임베딩해 둔다. 실패해도 챗봇은 RAG 없이 동작.
try:
    rag_index = rag.RagIndex.build()
    print(f"[RAG] 청크 {len(rag_index.chunks)}개 인덱싱 완료 (모델: {rag.EMBED_MODEL})")
except Exception as e:  # noqa: BLE001 - 기동 실패 사유가 무엇이든 챗봇은 살린다
    rag_index = None
    print(f"[RAG] 비활성화: {e}")

app = Flask(__name__)
# 세션 쿠키 서명용 키. 미지정 시 프로세스마다 새로 생성되므로
# 재시작하면 기존 쿠키가 무효화된다(로컬 용도로는 충분).
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

# 세션 ID → 대화 이력. 쿠키에는 ID만 두고 이력 본문은 서버 메모리에 유지
# (쿠키 4KB 제한 회피). 프로세스 재시작 시 소멸 — 영구 저장은 v2 로드맵의 DB 과제.
histories: dict[str, list[dict]] = {}


def session_history() -> list[dict]:
    """현재 브라우저 세션의 대화 이력을 반환한다. 최초 방문이면 ID를 발급한다."""
    sid = session.get("sid")
    if sid is None:
        sid = uuid.uuid4().hex
        session["sid"] = sid
    return histories.setdefault(sid, [])

# raw 문자열이어야 함: JS의 "\n\n"(SSE 이벤트 구분자)을 파이썬이
# 실제 줄바꿈으로 바꿔버리면 JS 문법 오류로 프론트 전체가 죽는다.
PAGE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>로컬 LLM 챗봇</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, sans-serif; max-width: 720px;
         margin: 0 auto; padding: 1rem; display: flex; flex-direction: column;
         height: 100vh; }
  h1 { font-size: 1.1rem; display: flex; justify-content: space-between;
       align-items: center; }
  h1 small { font-weight: normal; opacity: .6; }
  #log { flex: 1; overflow-y: auto; border: 1px solid #8884;
         border-radius: 8px; padding: 1rem; }
  .msg { margin: .5rem 0; padding: .5rem .8rem; border-radius: 10px;
         white-space: pre-wrap; word-break: break-word; max-width: 85%; }
  .user { background: #2563eb; color: #fff; margin-left: auto; width: fit-content; }
  .assistant { background: #8882; width: fit-content; }
  .error { color: #dc2626; font-size: .85rem; }
  .sources { font-size: .72rem; opacity: .55; margin: -.3rem 0 .5rem .2rem; }
  form { display: flex; gap: .5rem; margin-top: .8rem; }
  input[type=text] { flex: 1; padding: .6rem; border: 1px solid #8886;
                     border-radius: 8px; font-size: 1rem; }
  button { padding: .6rem 1rem; border: 0; border-radius: 8px;
           background: #2563eb; color: #fff; cursor: pointer; }
  button:disabled { opacity: .5; }
  #reset { background: #8885; color: inherit; }
</style>
</head>
<body>
<h1>로컬 LLM 챗봇 <small>{{ model }} · Ollama</small></h1>
<div id="log"></div>
<form id="f">
  <input type="text" id="m" placeholder="메시지를 입력하세요" autocomplete="off" autofocus>
  <button type="submit" id="send">전송</button>
  <button type="button" id="reset">초기화</button>
</form>
<script>
const log = document.getElementById("log");
const form = document.getElementById("f");
const input = document.getElementById("m");
const send = document.getElementById("send");

function add(cls, text) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  add("user", message);
  input.value = "";
  send.disabled = true;
  const pending = add("assistant", "…");
  try {
    const r = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    if (!r.ok) {
      // 검증 실패·연결 불가 등은 스트림이 아닌 JSON 오류로 온다
      const data = await r.json();
      pending.className = "msg error";
      pending.textContent = "오류 (" + r.status + "): " + (data.error || "알 수 없는 오류");
      return;
    }
    // SSE 스트림 수신: "data: {...}\n\n" 단위로 잘라 델타를 이어 붙인다
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    let started = false;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const line = buf.slice(0, idx).trim();
        buf = buf.slice(idx + 2);
        if (!line.startsWith("data:")) continue;
        const evt = JSON.parse(line.slice(5));
        if (evt.delta) {
          if (!started) { pending.textContent = ""; started = true; }
          pending.textContent += evt.delta;
          log.scrollTop = log.scrollHeight;
        } else if (evt.done && evt.sources && evt.sources.length) {
          const src = document.createElement("div");
          src.className = "sources";
          src.textContent = "📄 참고 자료: " + evt.sources.join(", ");
          log.appendChild(src);
          log.scrollTop = log.scrollHeight;
        } else if (evt.error) {
          pending.className = "msg error";
          pending.textContent = evt.error;
        }
      }
    }
  } catch (err) {
    pending.className = "msg error";
    pending.textContent = "요청 실패: " + err;
  } finally {
    send.disabled = false;
    input.focus();
  }
});

document.getElementById("reset").addEventListener("click", async () => {
  await fetch("/reset", { method: "POST" });
  log.innerHTML = "";
  input.focus();
});
</script>
</body>
</html>"""


@app.get("/")
def index():
    return render_template_string(PAGE, model=DEFAULT_MODEL)


@app.post("/chat")
def chat():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(error="요청 본문이 올바른 JSON이 아닙니다."), 400
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify(error="message 필드가 비어 있습니다."), 400
    model = data.get("model") or DEFAULT_MODEL
    # 세션 접근은 요청 컨텍스트 안에서만 가능하므로, 스트리밍 제너레이터에는
    # 이력 리스트의 참조를 미리 잡아 넘긴다.
    chat_history = session_history()

    # RAG: 질문과 유사한 문서 청크가 있으면 시스템 프롬프트에 근거로 주입
    system_prompt = SYSTEM_PROMPT
    sources = []
    if rag_index is not None:
        try:
            hits = rag_index.search(message)
        except requests.exceptions.RequestException:
            hits = []  # 임베딩 실패 시 RAG 없이 진행
        if hits:
            context = "\n\n".join(chunk for _, chunk in hits)
            sources = [
                chunk.split("]")[0].lstrip("[") for _, chunk in hits if chunk.startswith("[")
            ]
            system_prompt += (
                "\n\n아래 참고 자료가 질문과 관련될 수 있습니다. 관련된 내용은 "
                "반드시 자료에 근거해 정확하게 답하고, 자료와 무관한 질문이면 "
                "자료를 무시하세요.\n\n" + context
            )

    # 이력을 복사한 요청 페이로드를 만들고, 완주 이전에는 세션 이력을 건드리지 않는다
    messages = (
        [{"role": "system", "content": system_prompt}]
        + chat_history
        + [{"role": "user", "content": message}]
    )
    try:
        r = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {"temperature": TEMPERATURE},
            },
            stream=True,
            timeout=TIMEOUT,
        )
    except requests.exceptions.ConnectTimeout:
        return jsonify(error="Ollama 서버 연결이 시간 초과되었습니다."), 503
    except requests.exceptions.ReadTimeout:
        return jsonify(error=f"Ollama 응답이 {TIMEOUT:.0f}초 안에 시작되지 않았습니다."), 504
    except requests.exceptions.ConnectionError:
        return jsonify(
            error="Ollama 서버에 연결할 수 없습니다. `ollama serve` 실행 여부를 확인하세요."
        ), 503

    if r.status_code != 200:
        try:
            detail = r.json().get("error", r.text)
        except ValueError:
            detail = r.text
        return jsonify(error=f"Ollama 오류: {detail}"), 502

    def sse(payload: dict) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def stream():
        parts = []
        try:
            for line in r.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("error"):
                    yield sse({"error": f"Ollama 오류: {chunk['error']}"})
                    return
                delta = chunk.get("message", {}).get("content", "")
                if delta:
                    parts.append(delta)
                    yield sse({"delta": delta})
                if chunk.get("done"):
                    break
            else:
                yield sse({"error": "Ollama 스트림이 완료 신호 없이 끊겼습니다."})
                return
        except requests.exceptions.RequestException:
            yield sse({"error": "Ollama 스트림 수신 중 연결이 끊겼습니다."})
            return
        reply = "".join(parts)
        if not reply.strip():
            yield sse({"error": "Ollama가 빈 응답을 반환했습니다."})
            return
        # 스트림이 done까지 완주한 경우에만 user/assistant 메시지를 함께 이력에 반영
        chat_history.append({"role": "user", "content": message})
        chat_history.append({"role": "assistant", "content": reply})
        yield sse(
            {
                "done": True,
                "model": model,
                "history_length": len(chat_history),
                "sources": sources,
            }
        )

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/reset")
def reset():
    session_history().clear()
    return jsonify(ok=True, history_length=0)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="127.0.0.1", port=port, debug=False)
