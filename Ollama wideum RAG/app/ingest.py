import json, os
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter


BASE_DIR = Path(__file__).resolve().parent
config_path = BASE_DIR / "config" / "rag_config.json"

with open(config_path) as f:
    cfg = json.load(f)

embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://ollama:11434"
)

docs = []
for f_name in os.listdir("./data/docs"):
    if f_name.endswith(".pdf"):
        loader = PyPDFLoader(f"./data/docs/{f_name}")
        docs.extend(loader.load())

splitter = RecursiveCharacterTextSplitter(
    chunk_size=cfg["chunking"]["chunk_size"],
    chunk_overlap=cfg["chunking"]["chunk_overlap"]
)

chunks = splitter.split_documents(docs)

db = Chroma.from_documents(
    chunks,
    embedding=embeddings,
    persist_directory="./data/chroma"
)

db.persist()
print(f"Indexados {len(chunks)} chunks")
