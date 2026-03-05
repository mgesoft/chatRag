import json
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# --- Importaciones RAG ---
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()

# --- Configuración de Modelos y DB ---
#  mismo modelo de embeddings que en ingest.py
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
                                                       "content": "Saluda brevemente."}],
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

        # --- DENTRO DEL BUCLE while True del websocket_endpoint ---

        while True:
            try:
                # 1. RECIBIR DATOS DEL CLIENTE
                data = await websocket.receive_text()

                # 2.  Parsear y validar el historial
                try:
                    conversation_history = json.loads(data)
                    # Validar que sea una lista no vacía
                    if not isinstance(conversation_history, list) or len(conversation_history) == 0:
                        raise ValueError("Formato de historial inválido")
                except json.JSONDecodeError:
                    print(f" Error parseando JSON: {data[:100]}")
                    await websocket.send_json({"action": "error", "message": "Formato de mensaje inválido"})
                    continue  # Saltar al siguiente mensaje

                # 3. Extraer la pregunta actual (último mensaje)
                user_query = conversation_history[-1]["content"]
                print(f"\n📩 Pregunta recibida: {user_query}")

                # 4. --- BUSQUEDA EN VECTOR DB (RAG) ---
                print("🔍 Buscando en la base de datos vectorial...")
                docs = vector_db.similarity_search(user_query, k=5)

                if not docs:
                    print(" No se encontró nada relevante en los PDFs.")
                    contexto = "No hay información específica en los documentos."
                else:
                    print(f" Se encontraron {len(docs)} fragmentos.")
                    contexto = ""
                    for i, d in enumerate(docs):
                        print(f"--- Fragmento {i + 1} de {d.metadata.get('source', 'desconocido')} ---")
                        print(f"Contenido: {d.page_content[:150]}...")
                        contexto += f"\n--- FRAGMENTO {i + 1} ---\n{d.page_content}\n"

                # 5.  Preparar mensajes para Ollama CON historial
                # Limitamos a los últimos 10 mensajes para no saturar el contexto
                recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history

                # Construir el array de mensajes para Ollama
                messages_for_ollama = [
                    {
                        "role": "system",
                        "content": f"""Eres un asistente técnico experto en 'Remote Eye'.
        Utiliza el CONTEXTO proporcionado para responder la PREGUNTA de forma detallada.
        Si la respuesta no aparece exactamente igual, intenta explicar lo que entiendas del texto.
        Responde siempre en ESPAÑOL.

        CONTEXTO DOCUMENTAL:
        {contexto}"""
                    }
                ]
                #  Añadir el historial de conversación (user/assistant)
                messages_for_ollama.extend(recent_history)

                # 6. Enviar respuesta streaming
                await websocket.send_json({"action": "init_system_response"})

                async with httpx.AsyncClient(timeout=90.0) as client:
                    async with client.stream(
                            "POST",
                            "http://ollama:11434/api/chat",  #  Ajustado para ejecución en host
                            json={
                                "model": "llama3.2",
                                "messages": messages_for_ollama,  #  Historial + contexto
                                "stream": True,
                                "options": {
                                    "num_gpu": 0,
                                    "num_thread": 4,
                                    "temperature": 0.2,
                                    "num_ctx": 8192  #  Aumentado para historial + contexto RAG
                                }
                            }
                    ) as response:
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            try:
                                chunk = json.loads(line)
                                content = chunk.get("message", {}).get("content", "")
                                if content:
                                    await websocket.send_json({
                                        "action": "append_system_response",
                                        "content": content
                                    })
                            except json.JSONDecodeError:
                                continue

                await websocket.send_json({"action": "finish_system_response"})
                print(" Respuesta enviada. Esperando siguiente pregunta...")

            except WebSocketDisconnect:
                print("🔌 Conexión cerrada por el cliente.")
                break  #  Salir del bucle si se desconecta
            except Exception as e:
                print(f"🔥 Error en el servidor: {type(e).__name__} - {e}")
                # Intentar notificar al cliente si aún está conectado
                try:
                    await websocket.send_json({"action": "error", "message": str(e)})
                except:
                    pass
                break


    except WebSocketDisconnect:
        print("🔌 Conexión cerrada.")
    except Exception as e:
        print(f"🔥 Error en el servidor: {e}")


# Servir estáticos
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/")
async def get_index():
    index_path = BASE_DIR / "static" / "index.html"
    if not index_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="html no encontrado")
    return FileResponse(index_path)

@app.get("/health")
async def health_check():
    try:
        result = vector_db.get(include=[], limit=1)  # Solo verificamos que funcione
        # Si queremos el conteo real, hacemos una llamada sin limit:
        full_result = vector_db.get(include=[])
        count = len(full_result.get("ids", []))
        return {
            "status": "ok",
            "chunks_in_db": count,
            "connection": "chroma: OK",
            "ollama": "http://ollama:11434"
        }
    except Exception as e:
        # Logging adicional para debugging en producción
        import logging
        logging.error(f"Health check failed: {e}")
        return {"status": "error", "detail": str(e)}