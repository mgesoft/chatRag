import json
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity
from langchain_community.embeddings import OllamaEmbeddings

BASE_DIR = Path(__file__).resolve().parent
config_path = BASE_DIR  /"config" / "rag_config.json"

with open(config_path) as f:
    cfg = json.load(f)

embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://ollama:11434"
)

def evaluate_answer(question, context, answer):
    q = embeddings.embed_query(question)
    c = embeddings.embed_query(context)
    similarity = cosine_similarity([q], [c])[0][0]

    return {
        "context_similarity": round(similarity, 3),
        "answer_length": len(answer),
        "passes_similarity": similarity >= cfg["evaluation"]["context_relevance_threshold"],
        "passes_length": len(answer) >= cfg["evaluation"]["answer_length_min"],
        "pass": (
            similarity >= cfg["evaluation"]["context_relevance_threshold"]
            and len(answer) >= cfg["evaluation"]["answer_length_min"]
        )
    }
