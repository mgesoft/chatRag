import os

from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import PyPDF2

# Configuración
PDF_DIR = Path("./docs")
CHROMA_DIR = Path("./data/chroma")
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# Embeddings
embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
)


def extract_text_by_page(pdf_path):
    """Extrae texto de un PDF página por página"""
    pages_data = []

    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)

        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()

            if text and len(text.strip()) > 100:
                pages_data.append({
                    "page_num": page_num + 1,
                    "text": text.strip(),
                    "source": str(pdf_path)
                })

    return pages_data


def create_chunks_with_metadata(pages_data, chunk_size=500, chunk_overlap=50):
    """Crea chunks manteniendo metadata"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""]
    )

    documents = []

    for page_info in pages_data:
        chunks = splitter.split_text(page_info["text"])

        for i, chunk in enumerate(chunks):
            if len(chunk.strip()) < 20:
                continue

            doc = Document(
                page_content=chunk,
                metadata={
                    "source": page_info["source"],
                    "filename": Path(page_info["source"]).name,
                    "page": page_info["page_num"],
                    "chunk_index": i
                }
            )
            documents.append(doc)

    return documents


def ingest_pdfs():
    """Función principal"""
    print("🚀 Iniciando ingestión de PDFs...")

    pdf_files = list(PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"❌ No se encontraron PDFs en {PDF_DIR}")
        return

    print(f"📁 Encontrados {len(pdf_files)} PDFs")

    all_documents = []

    for pdf_path in pdf_files:
        print(f"\n📄 Procesando: {pdf_path.name}")
        pages_data = extract_text_by_page(pdf_path)
        print(f"    {len(pages_data)} páginas con texto")

        docs = create_chunks_with_metadata(pages_data)
        print(f"    {len(docs)} chunks creados")

        all_documents.extend(docs)

    if not all_documents:
        print("❌ No se pudo extraer ningún chunk")
        return

    print(f"\n💾 Guardando {len(all_documents)} chunks en ChromaDB...")

    #  Sin variable innecesaria
    Chroma.from_documents(
        documents=all_documents,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR)
    )

    print(f" Ingestión completada!")

    #  Opcional: Verificación rápida
    print(f"\n📊 Ubicación: {CHROMA_DIR}")
    print(f"📊 Total chunks: {len(all_documents)}")


if __name__ == "__main__":
    ingest_pdfs()