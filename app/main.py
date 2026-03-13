import json
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
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
    print(" WebSocket Conectado")

    try:
        while True:
            try:
                # 1. RECIBIR DATOS DEL CLIENTE
                data = await websocket.receive_text()

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
                print(f"\n Pregunta recibida: {user_query}")

                # 4. --- BUSQUEDA EN VECTOR DB (RAG) ---
                print("🔍 Buscando en la base de datos vectorial...")
                docs = vector_db.similarity_search(user_query, k=5)


                print(f" Se encontraron {len(docs)} fragmentos.")
                contexto = ""

                images_found = []

                for doc in docs:
                    contexto += f"\n{doc.page_content}\n"

                    if "image_urls" in doc.metadata:
                        pagina = doc.metadata.get('page', '?')
                        for url in doc.metadata["image_urls"]:
                            # Evitar duplicados
                            if not any(img["url"] == url for img in images_found):
                                images_found.append({
                                    "url": url,
                                    "page": pagina  # Añadir página
                                })


                for i, d in enumerate(docs):
                    fuente = d.metadata.get('filename', d.metadata.get('source', 'desconocido'))
                    pagina = d.metadata.get('page', '?')
                    print(f"--- Fragmento {i + 1} de {fuente} (pág. {pagina}) ---")
                    print(f"Contenido: {d.page_content[:150]}...")
                    #  Formato más limpio con fuente y página
                    contexto += f"\n[FUENTE: {fuente} - Página {pagina}]\n{d.page_content}\n"

                # 5.  Preparar mensajes para Ollama CON historial
                # Limitamos a los últimos 10 mensajes para no saturar el contexto
                recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history

                messages_for_ollama = [{
                    "role": "system",
                    "content": f"""### ROL
                Eres un asistente experto en maquinas de flexografia y hueco grabado de la empresaComexi. Usa los documentos como fuente principal.

                ### CONTEXTO
                <documentos>
                {contexto}
                </documentos>

                ### INSTRUCCIONES
                1. Responde en el idioma de la pregunta.
                2. Prioriza la información de los <documentos>.
                3. Si encuentras información relacionada, úsala con confianza.
                4. Si NO hay nada relevante, di: "No encuentro detalles específicos en los documentos" y ofrece lo más cercano que veas.
                5. Menciona la fuente cuando sea útil (ej: "Según la documentación...").

                ### PREGUNTA
                """
                }, {"role": "user", "content": user_query}]
                # Añadir la pregunta al final del sistema + historial
                messages_for_ollama.extend(recent_history)

                # 6. Enviar respuesta streaming
                await websocket.send_json({"action": "init_system_response"})

                async with httpx.AsyncClient(timeout=180.0) as client:
                    async with client.stream(
                            "POST",
                            "http://ollama:11434/api/chat",  #  Ajustado para ejecución en host
                            json={
                                "model": "phi3",
                                "messages": messages_for_ollama,  #  Historial + contexto
                                "stream": True,
                                "options": {
                                    "num_gpu": 0,  # 0 = solo CPU ( 1+ si  GPU)
                                    "num_thread": 4,
                                    "temperature": 0.3,  # creatividad numero mas bajo = respuestas más directas y rápidas
                                    "num_ctx": 2048,  # Reduce si tus prompts no son muy largos (ahorra memoria)
                                    "num_predict": 512,  # Límite de tokens de respuesta (evita respuestas infinitas)
                                    "top_p": 0.9,  # Muestreo más eficiente
                                    "repeat_penalty": 1.1  # Evita bucles de repetición
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

                await websocket.send_json({
                    "action": "finish_system_response",
                    "images": images_found  #  ¡Añadir esto!
                })
                print(" Respuesta enviada. Esperando siguiente pregunta...")

            except WebSocketDisconnect:
                print("🔌 Conexión cerrada por el cliente.")
                break  #  Salir del bucle si se desconecta
            except Exception as e:
                print(f" Error en el servidor: {type(e).__name__} - {e}")
                # Intentar notificar al cliente si aún está conectado
                try:
                    await websocket.send_json({"action": "error", "message": str(e)})
                except:
                    pass
                break


    except WebSocketDisconnect:
        print("🔌 Conexión cerrada.")
    except Exception as e:
        print(f" Error en el servidor: {e}")


# Servir estáticos
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/images/{filename}")
async def get_image(filename: str):
    """Sirve imágenes desde static/images"""
    image_path = BASE_DIR / "static" / "images" / filename

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    ext = filename.lower().split(".")[-1]
    content_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp"
    }

    return FileResponse(
        image_path,
        media_type=content_types.get(ext, "image/octet-stream")
    )

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


@app.get("/debug/search")
async def debug_search(q: str = "¿Qué es Remote Eye?"):
    """Verifica qué chunks recupera la búsqueda vectorial"""
    docs = vector_db.similarity_search(q, k=5)

    results = []
    for i, doc in enumerate(docs):
        results.append({
            "chunk": i + 1,
            "source": doc.metadata.get("source", "desconocido"),
            "page": doc.metadata.get("page", "N/A"),
            "score": doc.metadata.get("score", "N/A"),
            "content": doc.page_content[:200] + "..."  # Primeros 200 chars
        })

    return {
        "query": q,
        "chunks_found": len(docs),
        "results": results
    }


# En main.py, después de app.mount("/static", ...):

# Servir imágenes desde el volumen dedicado


# ================= AUTO-ARRANQUE =================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",  # O "main:app" si ejecutas desde la carpeta app/
        host="0.0.0.0",
        port=8000,
        reload=True  # Recarga automática al guardar cambios (desactivar en producción)
    )