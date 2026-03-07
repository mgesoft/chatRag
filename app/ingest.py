"""
 Procesa PDFs extrayendo texto e imágenes para RAG
"""
import os
import json
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import fitz  # PyMuPDF - pip install PyMuPDF
import re
import unicodedata

BASE_DIR = Path(__file__).resolve().parent  # Raíz del proyecto
PDF_DIR = BASE_DIR / "docs"
CHROMA_DIR = BASE_DIR / "data" / "chroma"
IMAGES_DIR = BASE_DIR / "static" / "images"

# Crear directorios si no existen
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Embeddings - APUNTANDO A OLLAMA LOCAL
embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://localhost:11434"  # ← localhost, no http://ollama:11434
)



def remove_accents(texto):
    # NFD descompone caracteres, Mn filtra las marcas de acento (Combining Diacritical Marks)
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                   if unicodedata.category(c) != 'Mn')

def extract_images_from_pdf(pdf_path: Path) -> list[dict]:
    images_meta = []
    pdf_name = pdf_path.stem

    # ✅ SANITIZAR NOMBRE (quitar acentos y caracteres especiales)
    safe_pdf_name = pdf_name.lower()
    safe_pdf_name = re.sub(r'[^\w\-]', '_', safe_pdf_name)  # Solo letras, números, guiones
    safe_pdf_name = re.sub(r'_+', '_', safe_pdf_name)  # Evitar múltiples guiones seguidos
    safe_pdf_name = remove_accents(safe_pdf_name)

    doc = fitz.Document(str(pdf_path))

    for page_num, page in enumerate(doc):
        image_list = page.get_images(full=True)

        if image_list:
            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)

                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    # ✅ Nombre sanitizado
                    img_filename = f"{safe_pdf_name}_p{page_num + 1}_img{img_index + 1}.{image_ext}"
                    img_path =IMAGES_DIR / img_filename

                    with open(img_path, "wb") as f:
                        f.write(image_bytes)

                    images_meta.append({
                        "page": page_num + 1,
                        "url": f"/static/images/{img_filename}",
                        "filename": img_filename
                    })
                except Exception as e:
                    print(f"⚠️ Error: {e}")
                    continue
                else:
                    # Fallback: snapshot de página
                    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))
                    img_filename = f"{safe_pdf_name}_p{page_num + 1}_page.jpg"
                    img_path = IMAGES_DIR / img_filename
                    pix.save(str(img_path))

                    images_meta.append({
                        "page": page_num + 1,
                        "url": f"/images/{img_filename}",  # ✅ CORRECT!
                        "filename": img_filename,
                        "type": "page_snapshot"
                    })

    doc.close()
    print(f"📸 {pdf_path.name}: {len(images_meta)} imágenes generadas")
    return images_meta
# ================= EXTRACCIÓN DE TEXTO POR PÁGINA =================
def extract_text_by_page(pdf_path: Path) -> list[dict]:
    """
    Extrae texto de un PDF página por página.
    Retorna: [{page_num: int, text: str, source: str, filename: str}, ...]
    """
    pages_data = []

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        print(f"Error abriendo {pdf_path.name}: {e}")
        return []

    for page_num, page in enumerate(doc):
        text = page.get_text("text").strip()

        # Filtrar páginas vacías o con muy poco contenido
        if len(text) < 100:
            continue

        pages_data.append({
            "page_num": page_num + 1,
            "text": text,
            "source": str(pdf_path),
            "filename": pdf_path.name
        })

    doc.close()
    print(f"📝 {pdf_path.name}: {len(pages_data)} páginas con texto válido")
    return pages_data


# ================= CREACIÓN DE CHUNKS CON METADATA =================
def create_chunks_with_metadata(
        pages_data: list[dict],
        images_meta: list[dict],
        chunk_size: int = 500,
        chunk_overlap: int = 50
) -> list[Document]:



    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    documents = []
    seen_contents = set()  # Evitar duplicados exactos

    for page_info in pages_data:  #  Corregido: era 'pages_'
        # Obtener imágenes de esta página específica
        page_images = [
            img for img in images_meta
            if img["page"] == page_info["page_num"]
        ]

        # Dividir texto de esta página
        chunks = splitter.split_text(page_info["text"])

        for i, chunk in enumerate(chunks):
            chunk_clean = chunk.strip()

            if len(chunk_clean) < 20 or chunk_clean in seen_contents:
                print(f" Saltando chunk duplicado: {chunk_clean[:50]}...")
                continue
            seen_contents.add(chunk_clean)


            #  Construir metadata base (solo tipos simples)
            metadata = {
                "source": page_info["source"],
                "filename": page_info["filename"],
                "page": page_info["page_num"],
                "chunk_index": i,
                "total_chunks_page": len(chunks)
            }

            #  Solo añadir image_urls si hay imágenes (lista de strings, NO lista de dicts)
            if page_images:
                metadata["image_urls"] = [img["url"] for img in page_images]
                metadata["image_pages"] = ", ".join(str(img["page"]) for img in page_images)

            doc = Document(
                page_content=chunk_clean,
                metadata=metadata
            )
            documents.append(doc)

    print(f" Creados {len(documents)} chunks únicos")
    return documents


# ================= FUNCIÓN PRINCIPAL DE INGESTIÓN =================
def ingest_pdfs():
    """Procesa todos los PDFs y guarda en ChromaDB"""
    print(" Iniciando ingestión de PDFs con imágenes...")
    print(f" PDFs: {PDF_DIR.absolute()}")
    print(f" ChromaDB: {CHROMA_DIR.absolute()}")
    print(f"  Imágenes: {IMAGES_DIR.absolute()}")

    # Buscar PDFs
    pdf_files = list(PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No se encontraron PDFs en {PDF_DIR}")
        return

    print(f" Encontrados {len(pdf_files)} PDFs: {[f.name for f in pdf_files]}")

    all_documents = []
    total_images = 0

    for pdf_path in pdf_files:
        print(f"\n{'=' * 60}")
        print(f"📄 Procesando: {pdf_path.name}")
        print(f"{'=' * 60}")

        # 1. Extraer imágenes
        images_meta = extract_images_from_pdf(pdf_path)
        total_images += len(images_meta)

        # 2. Extraer texto por página
        pages_data = extract_text_by_page(pdf_path)
        if not pages_data:
            print(f"⚠️ Sin texto extraíble en {pdf_path.name}, saltando...")
            continue

        # 3. Crear chunks con metadata de imágenes
        docs = create_chunks_with_metadata(pages_data, images_meta)
        print(f" {pdf_path.name}: {len(docs)} chunks, {len(images_meta)} imágenes")

        all_documents.extend(docs)

    if not all_documents:
        print("No se pudo crear ningún chunk válido")
        return

    # 4. Guardar en ChromaDB
    print(f"\n Guardando {len(all_documents)} chunks en ChromaDB...")

    Chroma.from_documents(
        documents=all_documents,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR)
    )

    # 5. Reporte final
    unique_pages = len(set(d.metadata["page"] for d in all_documents))
    unique_sources = len(set(d.metadata["filename"] for d in all_documents))

    print(f"\n{'=' * 60}")
    print(f" INGESTIÓN COMPLETADA")
    print(f"{'=' * 60}")
    print(f" Total chunks: {len(all_documents)}")
    print(f" Páginas procesadas: {unique_pages}")
    print(f" Documentos fuente: {unique_sources}")
    print(f"  Total imágenes: {total_images}")
    print(f" Imágenes guardadas en: {IMAGES_DIR}")
    print(f" Base vectorial en: {CHROMA_DIR}")

    # Guardar reporte JSON
    report = {
        "timestamp": str(Path(CHROMA_DIR).stat().st_mtime),
        "total_chunks": len(all_documents),
        "total_images": total_images,
        "unique_pages": unique_pages,
        "unique_sources": unique_sources,
        "sample_chunks": [
            {
                "filename": d.metadata["filename"],
                "page": d.metadata["page"],
                "preview": d.page_content[:150],
                "image_urls": d.metadata.get("image_urls", [])
            }
            for d in all_documents[:5]
        ]
    }

    report_path = CHROMA_DIR.parent / "ingest_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f" Reporte guardado: {report_path}")


# ================= EJECUCIÓN =================
if __name__ == "__main__":
    ingest_pdfs()