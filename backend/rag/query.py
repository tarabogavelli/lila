import os
from dotenv import load_dotenv

import chromadb
from llama_index.core import VectorStoreIndex, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding

load_dotenv()

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_store")

_query_engine = None


def get_query_engine():
    global _query_engine
    if _query_engine is not None:
        return _query_engine

    Settings.embed_model = OpenAIEmbedding(
        model="text-embedding-3-small",
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    chroma_collection = chroma_client.get_or_create_collection("lila_library")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    index = VectorStoreIndex.from_vector_store(vector_store)

    _query_engine = index.as_query_engine(
        similarity_top_k=5,
        response_mode="compact",
    )

    return _query_engine


async def query_literary_knowledge(question: str) -> str:
    """
    Run RAG query over How Fiction Works and Frantumaglia.
    Returns synthesized answer with chapter-level source attribution.
    """
    engine = get_query_engine()
    response = engine.query(question)

    sources = []
    for node in response.source_nodes:
        meta = node.metadata
        title = meta.get("title", "Unknown")
        ch_num = meta.get("chapter_number", "?")
        ch_title = meta.get("chapter_title", "")
        source_str = f"{title}, Chapter {ch_num}"
        if ch_title:
            source_str += f" ('{ch_title}')"
        if source_str not in sources:
            sources.append(source_str)

    attribution = " and ".join(sources) if sources else "my reading"
    return f"{response.response}\n\n[Sources: {attribution}]"
