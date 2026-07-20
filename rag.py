"""간단한 RAG(검색 증강 생성) 모듈.

data/*.txt를 빈 줄 기준 청크로 나누고, Ollama의 nomic-embed-text로 임베딩해
메모리에 보관한다. 질문이 오면 코사인 유사도 상위 청크를 돌려준다.
데모 규모(수십 청크)라 벡터 DB 없이 순수 파이썬으로 충분하다.

단독 실행으로 검색 품질을 확인할 수 있다:
    python rag.py "경복궁은 어디에 있어?"
"""

import math
import os
import sys
from pathlib import Path

import requests

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
# bge-m3: 다국어(한국어 포함) 검색 성능이 nomic-embed-text보다 우수했고,
# 무관한 질의를 임계값 아래로 잘 걸러냄 (EXECUTION_LOG 사후 개선 6 참고)
EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "bge-m3")
DATA_DIR = Path(__file__).parent / "data"


def _embed(texts: list[str]) -> list[list[float]]:
    r = requests.post(
        f"{OLLAMA_HOST}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["embeddings"]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


class RagIndex:
    def __init__(self, chunks: list[str], vectors: list[list[float]]):
        self.chunks = chunks
        self.vectors = vectors

    @classmethod
    def build(cls, data_dir: Path = DATA_DIR) -> "RagIndex":
        chunks = []
        for path in sorted(data_dir.glob("*.txt")):
            for block in path.read_text().split("\n\n"):
                block = block.strip()
                if block:
                    chunks.append(block)
        if not chunks:
            raise ValueError(f"{data_dir}에 문서(.txt)가 없습니다.")
        # nomic-embed-text는 용도 접두사(search_document/search_query)를 붙여야
        # 검색 성능이 제대로 나온다 (모델 카드 요구사항). bge-m3 등은 불필요.
        prefix = "search_document: " if "nomic" in EMBED_MODEL else ""
        return cls(chunks, _embed([prefix + c for c in chunks]))

    def search(
        self, query: str, k: int = 3, min_score: float = 0.5
    ) -> list[tuple[float, str]]:
        """유사도 상위 k개 청크를 (점수, 본문) 목록으로 반환. min_score 미만은 제외."""
        prefix = "search_query: " if "nomic" in EMBED_MODEL else ""
        qv = _embed([prefix + query])[0]
        scored = sorted(
            ((_cosine(qv, v), c) for v, c in zip(self.vectors, self.chunks)),
            reverse=True,
        )
        return [(s, c) for s, c in scored[:k] if s >= min_score]


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "경복궁은 어디에 있어?"
    index = RagIndex.build()
    print(f"청크 {len(index.chunks)}개 인덱싱 완료. 질의: {query}\n")
    for score, chunk in index.search(query):
        print(f"[{score:.3f}] {chunk[:80]}...")
