import os
import json
import asyncio
import httpx
import numpy as np
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# --- Librerías RAG ---
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from rank_bm25 import BM25Okapi

# Importación de tu script local (asegúrate de que evaluate.py esté en la carpeta)
try:
    from evaluate import evaluate_answer
except ImportError:
    def evaluate_answer(q, c, a):
        return {"score": 0, "reason": "Evaluator not found"}

# --- Configuración de Rutas ---
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "rag-config.json"
DOCS_DIR = BASE_DIR / "docs"
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = DATA_DIR / "chroma"

app = FastAPI()

# --- Carga de Configuración ---
if not CONFIG_PATH.exists():
    CONFIG_PATH = BASE_DIR / "data" / "rag-config.json"

try:
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
except Exception:
    cfg = {"retrieval": {"bm25_k": 3, "vector_k": 3, "final_k": 5}}

# --- Inicialización RAG ---
# Se inicializa al arrancar la API
embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://ollama:11434"
)

vector_db = Chroma(
    persist_directory=str(CHROMA_DIR),
    embedding_function=embeddings
)

docs_list = []
texts_content = []

print("Cargando documentos para búsqueda léxica...")
if DOCS_DIR.exists():
    for f_name in os.listdir(DOCS_DIR):
        if f_name.endswith(".pdf"):
            try:
                loader = PyPDFLoader(str(DOCS_DIR / f_name))
                for d in loader.load():
                    docs_list.append(d)
                    texts_content.append(d.page_content.lower())
            except Exception as e:
                print(f"Error cargando {f_name}: {e}")

bm25 = BM25Okapi([t.split() for t in texts_content]) if texts_content else None
print(f"BM25 inicializado con {len(docs_list)} páginas.")


# --- Lógica de WebSocket ---

@app.websocket("/init")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Cliente conectado vía WebSocket")
    # --- NUEVO: Saludo inicial ---
    saludo = "¡Hola! Soy tu asistente técnico Wideum. ¿En qué puedo ayudarte hoy con tus documentos?"

    await websocket.send_json({"action": "init_system_response"})
    # Enviamos el saludo
    await websocket.send_json({
        "action": "append_system_response",
        "content": saludo
    })
    await websocket.send_json({"action": "finish_system_response"})
    # ----------------------------
    try:
        while True:
            # Recibir el historial enviado por el JS
            raw_data = await websocket.receive_text()
            chat_history = json.loads(raw_data)

            # La última entrada es el mensaje actual del usuario
            user_query = chat_history[-1]["content"]
            print(f"Procesando pregunta: {user_query}")

            # 1. Recuperación RAG (Híbrida)
            context_text = ""
            if bm25:
                # Búsqueda BM25
                bm_scores = bm25.get_scores(user_query.lower().split())
                bm_idx = np.argsort(bm_scores)[-cfg["retrieval"]["bm25_k"]:][::-1]
                bm_docs = [docs_list[i] for i in bm_idx]

                # Búsqueda Vectorial
                vec_docs = vector_db.similarity_search(user_query, k=cfg["retrieval"]["vector_k"])

                # Unificar
                merged = {d.page_content: d for d in bm_docs + vec_docs}
                final_docs = list(merged.values())[:cfg["retrieval"]["final_k"]]
                context_text = "\n\n".join([d.page_content for d in final_docs])

            # 2. Notificar al JS que la respuesta del sistema comienza
            await websocket.send_json({"action": "init_system_response"})

            # 3. Petición Streaming a Ollama con httpx
            prompt = f"""
            Instrucción: Responde de forma breve y concisa (máximo 3 frases). 
            Si la respuesta no está en el contexto, di simplemente que no lo sabes.
            No repitas la pregunta ni saludes.

            Contexto:
            {context_text}

            Pregunta: {user_query}
            """

            full_answer = ""
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                        "POST",
                        "http://ollama:11434/api/chat",
                        json={
                            "model": "llama3.2",
                            "messages": [
                                # Añadimos un mensaje de sistema para reforzar la brevedad
                                {"role": "system",
                                 "content": "Eres un asistente técnico que responde con brevedad extrema."},
                                {"role": "user", "content": prompt}
                            ],
                            "stream": True,
                            "options": {
                                "num_predict": 120,  # Respuesta corta para no saturar
                                "temperature": 0.1,  # Respuesta precisa
                                "num_gpu": 1,  # Fuerza el uso de la GPU
                                "num_thread": 4  # Hilos de apoyo de CPU
                            }
                        }
                ) as response:
                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        chunk = json.loads(line)
                        if "message" in chunk:
                            content = chunk["message"].get("content", "")
                            full_answer += content

                            # Enviamos el pedazo de texto al JS
                            await websocket.send_json({
                                "action": "append_system_response",
                                "content": content
                            })

                        if chunk.get("done"):
                            break

            # 4. Finalizar la respuesta
            await websocket.send_json({"action": "finish_system_response"})
            print("Respuesta completada y enviada.")

    except WebSocketDisconnect:
        print("El cliente cerró la conexión.")
    except Exception as e:
        print(f"Error en el socket: {e}")
        await websocket.close()


# --- Archivos Estáticos y UI ---

# Montar la carpeta static para CSS/JS/Imágenes
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# Ruta principal: Sirve el index.html
@app.get("/")
async def get_index():
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Archivo static/index.html no encontrado"}