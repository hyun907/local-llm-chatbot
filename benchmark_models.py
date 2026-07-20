"""모델 비교 벤치마크 (STEP 6).

PLAN.md 2절 "비교 재현성" 기준을 따른다:
  - 동일 프롬프트, 동일 옵션(temperature=0, seed=42)
  - 모델별 cold 1회(로드 직후) + warm 2회 = 3회 실행
  - total_duration / load_duration / eval_count / eval_duration 기록, tok/s 계산
  - `ollama list`의 태그·ID·크기 함께 기록

실행:
    python benchmark_models.py                  # 기본 모델 목록 전체
    python benchmark_models.py exaone3.5 ...    # 지정 모델만 측정, 기존 결과에 병합
출력:
    docs/benchmark_raw.json      # 원시 측정값 (재실행 시 모델 단위로 병합)
    docs/benchmark_results.md    # 마크다운 표 (README에 인용)
"""

import json
import subprocess
import sys
from pathlib import Path

import requests

OLLAMA_HOST = "http://localhost:11434"
MODELS = ["llama3.2", "phi3:mini", "mistral", "qwen2.5"]
PROMPT = (
    "대한민국의 수도는 어디인가요? 그 도시의 대표 명소 3곳을 각각 한 문장으로 "
    "소개해주세요. 반드시 한국어로만 답하세요."
)
OPTIONS = {"temperature": 0, "seed": 42}
RUNS = 3  # cold 1회 + warm 2회

DOCS = Path(__file__).parent / "docs"


def model_info() -> dict[str, dict]:
    """`ollama list` 기준 태그별 ID·크기."""
    out = subprocess.run(["ollama", "list"], capture_output=True, text=True).stdout
    info = {}
    for line in out.strip().splitlines()[1:]:
        parts = line.split()
        info[parts[0]] = {"id": parts[1], "size": f"{parts[2]} {parts[3]}"}
    return info


def unload(model: str) -> None:
    """cold 측정을 위해 모델을 메모리에서 내린다."""
    subprocess.run(["ollama", "stop", model], capture_output=True)


def run_once(model: str) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "stream": False,
        "options": OPTIONS,
    }
    if model.startswith("qwen3"):
        # qwen3는 기본으로 사고 과정을 생성한다. 챗봇 응답 비교의 공정성을 위해
        # (사고 토큰이 eval_count·지연에 섞이지 않도록) 끈다.
        payload["think"] = False
    r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=600)
    r.raise_for_status()
    body = r.json()
    return {
        "total_s": body["total_duration"] / 1e9,
        "load_s": body.get("load_duration", 0) / 1e9,
        "eval_count": body["eval_count"],
        "eval_s": body["eval_duration"] / 1e9,
        "tok_per_s": body["eval_count"] / body["eval_duration"] * 1e9,
        "response": body["message"]["content"],
    }


def main() -> None:
    info = model_info()
    models = sys.argv[1:] or MODELS
    raw_path = DOCS / "benchmark_raw.json"
    # 지정 모델만 다시 잴 때는 기존 결과를 유지한 채 해당 모델만 갱신
    results = json.loads(raw_path.read_text()) if raw_path.exists() else {}
    for model in models:
        tag = model if model in info else f"{model}:latest"
        print(f"\n=== {model} ({info.get(tag, {}).get('size', '?')}) ===")
        unload(model)
        runs = []
        for i in range(RUNS):
            kind = "cold" if i == 0 else "warm"
            r = run_once(model)
            r["kind"] = kind
            runs.append(r)
            print(
                f"  [{kind}] total {r['total_s']:.1f}s, load {r['load_s']:.1f}s, "
                f"{r['eval_count']} tok, {r['tok_per_s']:.1f} tok/s"
            )
        unload(model)  # 다음 모델을 위해 메모리 반환
        results[model] = {"info": info.get(tag, {}), "runs": runs}

    DOCS.joinpath("benchmark_raw.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2)
    )

    # 마크다운 표 생성
    lines = [
        "# 모델 비교 벤치마크 결과 (자동 생성)",
        "",
        f"- 프롬프트: {PROMPT}",
        f"- 옵션: `{OPTIONS}`, 모델별 cold 1회 + warm 2회",
        "",
        "| 모델 | ID | 크기 | cold total(s) | cold load(s) | warm total(s) 평균 | tok/s 평균(warm) |",
        "|---|---|---|---|---|---|---|",
    ]
    for model, data in results.items():
        cold = data["runs"][0]
        warms = data["runs"][1:]
        warm_total = sum(r["total_s"] for r in warms) / len(warms)
        warm_tps = sum(r["tok_per_s"] for r in warms) / len(warms)
        i = data["info"]
        lines.append(
            f"| {model} | {i.get('id', '?')} | {i.get('size', '?')} "
            f"| {cold['total_s']:.1f} | {cold['load_s']:.1f} "
            f"| {warm_total:.1f} | {warm_tps:.1f} |"
        )
    lines += ["", "## 모델별 첫 실행(cold) 응답 전문", ""]
    for model, data in results.items():
        lines += [f"### {model}", "", "```", data["runs"][0]["response"], "```", ""]
    DOCS.joinpath("benchmark_results.md").write_text("\n".join(lines))
    print("\ndocs/benchmark_raw.json, docs/benchmark_results.md 저장 완료")


if __name__ == "__main__":
    main()
