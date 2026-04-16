import os
from dotenv import load_dotenv

import chromadb
from llama_index.core import VectorStoreIndex, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding

load_dotenv()

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_store")

_query_engine = None
_index = None
_course_query_engine = None
_course_index = None


def _get_index():
    global _index
    if _index is not None:
        return _index

    Settings.embed_model = OpenAIEmbedding(
        model="text-embedding-3-small",
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    chroma_collection = chroma_client.get_or_create_collection("lila_library")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    _index = VectorStoreIndex.from_vector_store(vector_store)
    return _index


def get_query_engine():
    global _query_engine
    if _query_engine is not None:
        return _query_engine

    index = _get_index()
    _query_engine = index.as_query_engine(
        similarity_top_k=5,
        response_mode="compact",
    )

    return _query_engine


def _get_course_index():
    global _course_index
    if _course_index is not None:
        return _course_index

    Settings.embed_model = OpenAIEmbedding(
        model="text-embedding-3-small",
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    chroma_collection = chroma_client.get_or_create_collection("bildungsroman_notes")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    _course_index = VectorStoreIndex.from_vector_store(vector_store)
    return _course_index


def get_course_query_engine():
    global _course_query_engine
    if _course_query_engine is not None:
        return _course_query_engine

    index = _get_course_index()
    _course_query_engine = index.as_query_engine(
        similarity_top_k=5,
        response_mode="compact",
    )

    return _course_query_engine


def reset_query_engine():
    global _query_engine, _index, _course_query_engine, _course_index
    _query_engine = None
    _index = None
    _course_query_engine = None
    _course_index = None


async def retrieve_relevant_chunks(question: str, top_k: int = 3) -> list[str]:
    index = _get_index()
    retriever = index.as_retriever(similarity_top_k=top_k)
    nodes = await retriever.aretrieve(question)
    chunks = []
    for node in nodes:
        meta = node.metadata
        title = meta.get("title", "Unknown")
        ch_num = meta.get("chapter_number", "?")
        ch_title = meta.get("chapter_title", "")
        source = f"{title}, Chapter {ch_num}"
        if ch_title:
            source += f" ('{ch_title}')"
        chunks.append(f"[{source}]\n{node.text}")
    return chunks


async def query_literary_knowledge(question: str) -> str:
    engine = get_query_engine()
    response = await engine.aquery(question)

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


async def retrieve_course_chunks(question: str, top_k: int = 3) -> list[str]:
    index = _get_course_index()
    retriever = index.as_retriever(similarity_top_k=top_k)
    nodes = await retriever.aretrieve(question)
    chunks = []
    for node in nodes:
        meta = node.metadata
        ch_num = meta.get("chapter_number", "?")
        ch_title = meta.get("chapter_title", "")
        source = f"Course Notes, Section {ch_num}"
        if ch_title:
            source += f" ('{ch_title}')"
        chunks.append(f"[{source}]\n{node.text}")
    return chunks


async def query_course_notes(question: str) -> str:
    engine = get_course_query_engine()
    response = await engine.aquery(question)

    sources = []
    for node in response.source_nodes:
        meta = node.metadata
        ch_num = meta.get("chapter_number", "?")
        ch_title = meta.get("chapter_title", "")
        source_str = f"Course Notes, Section {ch_num}"
        if ch_title:
            source_str += f" ('{ch_title}')"
        if source_str not in sources:
            sources.append(source_str)

    attribution = " and ".join(sources) if sources else "course notes"
    return f"{response.response}\n\n[Sources: {attribution}]"
