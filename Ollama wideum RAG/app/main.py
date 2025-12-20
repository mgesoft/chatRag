from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import json, os, requests, numpy as np, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from pydantic import BaseModel
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import PyPDFLoader
from rank_bm25 import BM25Okapi
from evaluate import evaluate_answer


BASE_DIR = Path(__file__).resolve().parent
config_path = BASE_DIR / "config" / "rag_config.json"

# --- Config ---
with open(config_path) as f:
    cfg = json.load(f)

app = FastAPI(title="RAG PDFs Técnicos")

# --- JWT ---
SECRET_KEY = "supersecretkey123"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
fake_user = {"username": "admin", "password": pwd_context.hash("1234")}

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None

async def get_current_user(token: str = Depends(oauth2_scheme)):
    username = verify_token(token)
    if username is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return username

# --- Login ---
@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = fake_user
    if form_data.username != user["username"] or not pwd_context.verify(form_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    access_token = create_access_token({"sub": user["username"]}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": access_token, "token_type": "bearer"}

# --- Serve chat web ---
app.mount("/static", os.path.join("static"), name="static")

@app.get("/")
def chat_ui(user: str = Depends(get_current_user)):
    return FileResponse("static/index.html")

# --- RAG setup ---
embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url="http://ollama:11434")
vector_db = Chroma(persist_directory="./data/chroma", embedding_function=embeddings)

docs, texts = [], []
for f_name in os.listdir("./data/docs"):
    if f_name.endswith(".pdf"):
        loader = PyPDFLoader(f"./data/docs/{f_name}")
        for d in loader.load():
            docs.append(d)
            texts.append(d.page_content.lower())

bm25 = BM25Okapi([t.split() for t in texts])

HISTORY_DIR = "./data/chats"
os.makedirs(HISTORY_DIR, exist_ok=True)
LOG_PATH = "./data/evaluations.jsonl"

def load_history(username):
    path = os.path.join(HISTORY_DIR, f"{username}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []

def save_history(username, history):
    path = os.path.join(HISTORY_DIR, f"{username}.json")
    with open(path, "w") as f:
        json.dump(history, f, indent=2)

class Question(BaseModel):
    question: str
    model: str = "llama2"

@app.post("/rag")
def rag(q: Question, user: str = Depends(get_current_user)):
    # Historial
    history = load_history(user)

    # Hybrid Retrieval
    bm_scores = bm25.get_scores(q.question.lower().split())
    bm_idx = np.argsort(bm_scores)[-cfg["retrieval"]["bm25_k"]:][::-1]
    bm_docs = [docs[i] for i in bm_idx]
    vec_docs = vector_db.similarity_search(q.question, k=cfg["retrieval"]["vector_k"])
    merged = {d.page_content: d for d in bm_docs + vec_docs}
    final_docs = list(merged.values())[:cfg["retrieval"]["final_k"]]

    context = "\n\n".join(f"[{i+1}] {d.page_content}" for i, d in enumerate(final_docs))
    sources = [f"PDF:{d.metadata.get('source','unknown')} Page:{d.metadata.get('page','?')}" for d in final_docs]

    # Prompt con memoria
    recent_hist = history[-cfg["memory"]["recent_interactions"]:]
    chat_context = "\n".join([f"Usuario: {m['user']}\nAI: {m['ai']}" for m in recent_hist])
    prompt = f"""
Historial reciente:
{chat_context}

Contexto con referencias:
{context}

Pregunta:
{q.question}

Responde mencionando referencias si es posible.
"""

    res = requests.post(
        "http://ollama:11434/api/chat",
        json={"model": q.model, "messages":[{"role":"user","content":prompt}], "stream": False},
        timeout=180
    ).json()

    answer = res["message"]["content"]
    evaluation = evaluate_answer(q.question, context, answer)

    # Guardar historial usuario
    history.append({"timestamp": datetime.utcnow().isoformat(),
                    "user": q.question, "ai": answer,
                    "sources": sources, **evaluation})
    save_history(user, history)

    # Log global evaluaciones
    record = {"timestamp": datetime.utcnow().isoformat(), "username": user,
              "question": q.question, "answer": answer, **evaluation}
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record)+"\n")

    return {"answer": answer, "evaluation": evaluation, "sources": sources, "history_len": len(history)}
