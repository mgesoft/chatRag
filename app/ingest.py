import os
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma


def start_ingestion():
    # Obtiene la ruta de la carpeta donde está este script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    docs_path = os.path.join(base_dir, "docs")

    print(f"📂 Buscando en ruta absoluta: {docs_path}")

    if not os.path.exists(docs_path) or not os.listdir(docs_path):
        print(f"❌ ERROR: No hay archivos en {docs_path}")
        print(f"Contenido actual de {base_dir}: {os.listdir(base_dir)}")
        return

    print(f"📄 Cargando documentos desde {docs_path}...")
    loader = DirectoryLoader(docs_path, glob="./*.pdf", loader_cls=PyPDFLoader)
    raw_documents = loader.load()

    if not raw_documents:
        print("❌ ERROR: No se pudo extraer texto de los PDFs. ¿Están vacíos o son solo imágenes?")
        return

    print(f"✅ Cargados {len(raw_documents)} páginas de documentos.")

    # 2. Dividir en trozos (Chunks)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    docs = text_splitter.split_documents(raw_documents)
    print(f"✂️ Dividido en {len(docs)} fragmentos.")

    # 3. Crear Embeddings y Guardar
    print("🧠 Generando embeddings (esto puede tardar)...")
    embeddings = OllamaEmbeddings(
        model="nomic-embed-text",
        base_url="http://ollama:11434"
    )

    persist_directory = "./data/chroma"

    # Crear la base de datos
    db = Chroma.from_documents(
        docs,
        embeddings,
        persist_directory=persist_directory
    )

    print(f"🎉 ÉXITO: Base de datos guardada en {persist_directory}")


if __name__ == "__main__":
    start_ingestion()