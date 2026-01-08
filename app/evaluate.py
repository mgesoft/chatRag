import json
from pathlib import Path
# El módulo sklearn se instala como scikit-learn
from sklearn.metrics.pairwise import cosine_similarity
# Cambio de import para evitar avisos de deprecación
from langchain_ollama import OllamaEmbeddings

BASE_DIR = Path(__file__).resolve().parent
# Ajustamos a la carpeta config donde está tu json
config_path = BASE_DIR / "data" / "rag-config.json"

with open(config_path) as f:
    cfg = json.load(f)

embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://ollama:11434"
)


def evaluate_answer(question, context, answer):
    # Generar vectores
    q = embeddings.embed_query(question)
    c = embeddings.embed_query(context)

    # Calcular similitud
    similarity = float(cosine_similarity([q], [c])[0][0])

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