docker compose up --build -d
docker exec -it ollama ollama pull llama3.2
docker exec -it ollama ollama pull nomic-embed-text
docker exec -it rag_api python ingest.py

Servicio URL💬 Chat web [http://localhost:8000](http://localhost:8000)

🧠 API RAG [http://localhost:8000/docs](http://localhost:8000/docs)

📊 Dashboard [http://localhost:8501](http://localhost:8501)
