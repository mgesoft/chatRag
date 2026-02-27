import os
import json
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# --- Importaciones RAG ---
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

app = FastAPI()

# --- Configuración de Modelos y DB ---
# Usamos el mismo modelo de embeddings que en ingest.py
embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://ollama:11434"
)

# Cargamos la base de datos que ya tiene los 13 chunks
vector_db = Chroma(
    persist_directory="./data/chroma",
    embedding_function=embeddings
)


@app.websocket("/init")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🚀 WebSocket Conectado")

    try:
        # 1. SALUDO INICIAL
        await websocket.send_json({"action": "init_system_response"})
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", "http://ollama:11434/api/chat",
                                     json={
                                         "model": "llama3.2",
                                         "messages": [{"role": "user",
                                                       "content": "Saluda brevemente y di que estás listo para analizar los documentos de Remote Eye."}],
                                         "stream": True,
                                         "options": {"num_gpu": 0, "num_thread": 4}
                                     }) as response:
                async for line in response.aiter_lines():
                    if not line: continue
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        await websocket.send_json({"action": "append_system_response", "content": content})
        await websocket.send_json({"action": "finish_system_response"})

        # 2. BUCLE DE PREGUNTAS (RAG REAL)
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            user_query = payload[-1]["content"]

            print(f"\n📩 Pregunta recibida: {user_query}")

            # --- BUSQUEDA EN TUS PDFS ---
            print("🔍 Buscando en la base de datos vectorial...")
            # Aumentamos a k=5 para capturar más información
            docs = vector_db.similarity_search(user_query, k=5)

            if not docs:
                print("❌ No se encontró nada relevante en los PDFs.")
                contexto = "No hay información específica en los documentos."
            else:
                print(f"✅ Se encontraron {len(docs)} fragmentos.")
                # Esto imprimirá en tu terminal lo que el sistema "lee"
                contexto = ""
                for i, d in enumerate(docs):
                    print(f"--- Fragmento {i + 1} de {d.metadata.get('source', 'desconocido')} ---")
                    print(f"Contenido: {d.page_content[:150]}...")
                    contexto += f"\n--- FRAGMENTO {i + 1} ---\n{d.page_content}\n"

            # Prompt optimizado para que no sea tan tímido
            prompt_final = f"""Eres un asistente técnico experto en 'Remote Eye'.
Utiliza el CONTEXTO proporcionado para responder la PREGUNTA de forma detallada.
Si la respuesta no aparece exactamente igual, intenta explicar lo que entiendas del texto.

CONTEXTO:
{contexto}

PREGUNTA: {user_query}

RESPUESTA EN ESPAÑOL:"""

            await websocket.send_json({"action": "init_system_response"})

            # --- RESPUESTA DE LLAMA 3.2 ---
            async with httpx.AsyncClient(timeout=90.0) as client:
                async with client.stream("POST", "http://ollama:11434/api/chat",
                                         json={
                                             "model": "llama3.2",
                                             "messages": [{"role": "user", "content": prompt_final}],
                                             "stream": True,
                                             "options": {
                                                 "num_gpu": 0,
                                                 "num_thread": 4,
                                                 "temperature": 0.2,  # Un poco más de creatividad
                                                 "num_ctx": 4096  # Suficiente espacio para el contexto
                                             }
                                         }) as response:
                    async for line in response.aiter_lines():
                        if not line: continue
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            await websocket.send_json({"action": "append_system_response", "content": content})

            await websocket.send_json({"action": "finish_system_response"})
            print("✅ Respuesta enviada. Esperando siguiente pregunta...")

    except WebSocketDisconnect:
        print("🔌 Conexión cerrada.")
    except Exception as e:
        print(f"🔥 Error en el servidor: {e}")


# Servir estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def get_index():
    return FileResponse("static/index.html")