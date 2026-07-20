"""Ollama 기반 로컬 LLM 챗봇 — Flask 백엔드 + 단일 페이지 프론트엔드 (STEP 4~5).

실행:
    python app.py                      # http://localhost:5001
환경변수:
    OLLAMA_HOST     (기본 http://localhost:11434)
    OLLAMA_MODEL    (기본 llama3.2)
    OLLAMA_TIMEOUT  (기본 120초)
    PORT            (기본 5001 — macOS AirPlay가 5000을 점유)

대화 이력은 전역 리스트 하나로 관리한다(v1: 단일 사용자 로컬 전제).
Ollama 호출이 성공했을 때만 user/assistant 메시지를 함께 이력에 확정하므로,
호출 실패 시 이력은 변하지 않는다.
"""

import os

import requests
from flask import Flask, jsonify, render_template_string, request

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
# 모델 비교 실험(STEP 6) 결과 한국어 품질이 가장 좋았던 qwen2.5를 기본값으로 사용
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5")
TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "120"))

# 소형 모델의 외국어 혼입·어색한 어미를 줄이기 위한 시스템 프롬프트.
# 이력에는 저장하지 않고 매 요청 맨 앞에 붙인다.
SYSTEM_PROMPT = (
    "당신은 친절한 한국어 챗봇입니다. 항상 자연스럽고 문법에 맞는 한국어로만 "
    "답하세요. 영어 단어, 한자, 다른 언어를 섞지 마세요. 답은 간결하게 하세요."
)

app = Flask(__name__)

# v1: 단일 사용자 전제의 전역 대화 이력 (세션 분리는 v2 과제)
chat_history: list[dict] = []

PAGE = """<!doctype html>
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
    const data = await r.json();
    if (r.ok) {
      pending.textContent = data.reply;
    } else {
      pending.className = "msg error";
      pending.textContent = "오류 (" + r.status + "): " + (data.error || "알 수 없는 오류");
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

    # 이력을 복사한 요청 페이로드를 만들고, 성공 이전에는 전역 이력을 건드리지 않는다
    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + chat_history
        + [{"role": "user", "content": message}]
    )
    try:
        r = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
            timeout=TIMEOUT,
        )
    except requests.exceptions.ConnectTimeout:
        return jsonify(error="Ollama 서버 연결이 시간 초과되었습니다."), 503
    except requests.exceptions.ReadTimeout:
        return jsonify(error=f"Ollama 응답이 {TIMEOUT:.0f}초 안에 오지 않았습니다."), 504
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

    reply = r.json().get("message", {}).get("content", "")
    if not reply.strip():
        return jsonify(error="Ollama가 빈 응답을 반환했습니다."), 502

    # 성공이 확정된 뒤에만 user/assistant 메시지를 함께 이력에 반영
    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": reply})
    return jsonify(reply=reply, model=model, history_length=len(chat_history))


@app.post("/reset")
def reset():
    chat_history.clear()
    return jsonify(ok=True, history_length=0)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="127.0.0.1", port=port, debug=False)
