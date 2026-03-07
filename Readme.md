docker compose up --build -d
docker exec -it ollama ollama pull deepseek-r1:1.5b
docker exec -it ollama ollama pull nomic-embed-text
docker exec -it rag_api python ingest.py

Servicio URL💬 Chat web [http://localhost:8000](http://localhost:8000)

🧠 API RAG [http://localhost:8000/docs](http://localhost:8000/docs)

 Dashboard [http://localhost:8501](http://localhost:8501)

# Instalacion sin dockers

## Instalar Ollama en local 

Instalar Ollama : https://ollama.com/

Subir modelo (actual: llama 3.1). Si se cambia el modelo hay que cambiar el código.

````ollama pull llama3.1````

Subir modelo embed:

````ollama pull nomic-embed-text````






