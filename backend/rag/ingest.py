"""
Run once: python -m rag.ingest
Persists ChromaDB to backend/rag/chroma_store/
"""

import os
from dotenv import load_dotenv

import chromadb
from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding

from rag.chapter_extractor import extract_chapters

load_dotenv()

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_store")
DATA_PATH = os.path.join(os.path.dirname(__file__), "../data")

PDF_CONFIGS = [
    (
        "conversations_with_friends.pdf",
        "conversations_with_friends",
        "Conversations with Friends",
        "Sally Rooney",
    ),
    ("heart_the_lover.pdf", "heart_the_lover", "Heart, the Lover", "Lily King"),
]


def ingest():
    Settings.embed_model = OpenAIEmbedding(
        model="text-embedding-3-small",
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    documents = []

    for filename, source_key, display_title, author in PDF_CONFIGS:
        pdf_path = os.path.join(DATA_PATH, filename)
        if not os.path.exists(pdf_path):
            print(f"WARNING: {pdf_path} not found, skipping")
            continue

        chapters = extract_chapters(pdf_path, source_key)
        print(f"\n{display_title}: found {len(chapters)} chapters")

        for ch in chapters:
            print(
                f"  Chapter {ch.number}: '{ch.title}' "
                f"(pages {ch.start_page}-{ch.end_page}, {len(ch.text)} chars)"
            )

            doc = Document(
                text=ch.text,
                metadata={
                    "source": source_key,
                    "title": display_title,
                    "author": author,
                    "chapter_number": ch.number,
                    "chapter_title": ch.title,
                    "start_page": ch.start_page,
                    "end_page": ch.end_page,
                },
                metadata_separator="\n",
                metadata_template="{key}: {value}",
                text_template="Source: {metadata_str}\n\n{content}",
            )
            documents.append(doc)

    if not documents:
        print("\nNo PDFs found. Place PDFs in backend/data/ and re-run.")
        return None

    print(f"\nTotal documents (chapters): {len(documents)}")

    splitter = SentenceSplitter(
        chunk_size=768,
        chunk_overlap=128,
    )
    nodes = splitter.get_nodes_from_documents(documents)
    print(f"Total nodes (chunks): {len(nodes)}")

    sample = nodes[0] if nodes else None
    if sample:
        print(f"Sample node metadata: {sample.metadata}")

    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    try:
        chroma_client.delete_collection("lila_library")
    except Exception:
        pass
    chroma_collection = chroma_client.get_or_create_collection("lila_library")

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    index = VectorStoreIndex(
        nodes,
        storage_context=storage_context,
        show_progress=True,
    )

    print(f"\nIngestion complete. ChromaDB persisted to {CHROMA_PATH}")
    return index


COURSE_PDF = "bildungsroman_notes.pdf"
COURSE_COLLECTION = "bildungsroman_notes"


def ingest_course_notes():
    Settings.embed_model = OpenAIEmbedding(
        model="text-embedding-3-small",
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    pdf_path = os.path.join(DATA_PATH, COURSE_PDF)
    if not os.path.exists(pdf_path):
        print(f"\nWARNING: {pdf_path} not found, skipping course notes ingestion")
        return None

    chapters = extract_chapters(pdf_path, "bildungsroman_notes")
    print(f"\nBildungsroman Course Notes: found {len(chapters)} sections")

    documents = []
    for ch in chapters:
        print(
            f"  Section {ch.number}: '{ch.title}' "
            f"(pages {ch.start_page}-{ch.end_page}, {len(ch.text)} chars)"
        )
        book_title = ch.title.split(" — ")[0] if " — " in ch.title else ch.title
        doc = Document(
            text=ch.text,
            metadata={
                "source": "bildungsroman_notes",
                "title": "Bildungsroman Course Notes",
                "author": "Lecture Notes",
                "book_title": book_title,
                "chapter_number": ch.number,
                "chapter_title": ch.title,
                "start_page": ch.start_page,
                "end_page": ch.end_page,
            },
            metadata_separator="\n",
            metadata_template="{key}: {value}",
            text_template="Source: {metadata_str}\n\n{content}",
        )
        documents.append(doc)

    splitter = SentenceSplitter(chunk_size=4096, chunk_overlap=0)
    nodes = splitter.get_nodes_from_documents(documents)
    print(f"Course notes chunks: {len(nodes)}")

    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    try:
        chroma_client.delete_collection(COURSE_COLLECTION)
    except Exception:
        pass
    chroma_collection = chroma_client.get_or_create_collection(COURSE_COLLECTION)

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    index = VectorStoreIndex(nodes, storage_context=storage_context, show_progress=True)

    print(f"Course notes ingestion complete ({COURSE_COLLECTION} collection)")
    return index


if __name__ == "__main__":
    ingest()
    ingest_course_notes()
