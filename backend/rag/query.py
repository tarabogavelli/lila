import os
import re
from dotenv import load_dotenv

import chromadb
from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.vector_stores import (
    MetadataFilter,
    MetadataFilters,
    FilterOperator,
    FilterCondition,
)
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.postprocessor.cohere_rerank import CohereRerank

load_dotenv()

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_store")

SIMILARITY_TOP_K = 15
RERANK_TOP_N = 5

LITERARY_BOOK_KEYWORDS = {
    "conversations with friends": "conversations_with_friends",
    "sally rooney": "conversations_with_friends",
    "heart the lover": "heart_the_lover",
    "lily king": "heart_the_lover",
}

COURSE_BOOK_KEYWORDS = {
    "woman warrior": "The Woman Warrior",
    "hong kingston": "The Woman Warrior",
    "never let me go": "Never Let Me Go",
    "ishiguro": "Never Let Me Go",
    "sula": "Sula",
    "toni morrison": "Sula",
    "go tell it on the mountain": "Go Tell it on the Mountain",
    "baldwin": "Go Tell it on the Mountain",
    "metamorphosis": "The Metamorphosis",
    "kafka": "The Metamorphosis",
    "jane eyre": "Jane Eyre",
    "bronte": "Jane Eyre",
    "pere goriot": "Père Goriot",
    "balzac": "Père Goriot",
}

_CHAPTER_RE = re.compile(r"chapter\s+(\d+)", re.IGNORECASE)

_index = None
_course_index = None
_reranker = None


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


def _get_reranker():
    global _reranker
    if _reranker is not None:
        return _reranker

    _reranker = CohereRerank(
        api_key=os.getenv("COHERE_API_KEY"),
        top_n=RERANK_TOP_N,
        model="rerank-english-v3.0",
    )
    return _reranker


def reset_query_engine():
    global _index, _course_index, _reranker
    _index = None
    _course_index = None
    _reranker = None


def _build_filters(question: str, collection: str) -> MetadataFilters | None:
    lower = question.lower()
    filters = []

    if collection == "lila_library":
        for keyword, source_val in LITERARY_BOOK_KEYWORDS.items():
            if keyword in lower:
                filters.append(
                    MetadataFilter(
                        key="source", operator=FilterOperator.EQ, value=source_val
                    )
                )
                break

        ch_match = _CHAPTER_RE.search(lower)
        if ch_match:
            ch_num = int(ch_match.group(1))
            filters.append(
                MetadataFilter(
                    key="chapter_number", operator=FilterOperator.EQ, value=ch_num
                )
            )

    elif collection == "bildungsroman_notes":
        for keyword, book_title in COURSE_BOOK_KEYWORDS.items():
            if keyword in lower:
                filters.append(
                    MetadataFilter(
                        key="book_title",
                        operator=FilterOperator.EQ,
                        value=book_title,
                    )
                )
                break
    else:
        return None

    if not filters:
        return None

    return MetadataFilters(filters=filters, condition=FilterCondition.AND)


def _format_chunks(nodes) -> str:
    if not nodes:
        return "No relevant passages found."

    chunks = []
    for node in nodes:
        meta = node.metadata
        title = meta.get("title", "Unknown")
        ch_title = meta.get("chapter_title", "")
        ch_num = meta.get("chapter_number", "?")
        source = f"{title}, Chapter {ch_num}"
        if ch_title:
            source += f" ('{ch_title}')"
        chunks.append(f"[{source}]\n{node.text}")

    return "\n\n---\n\n".join(chunks)


async def query_literary_knowledge(question: str) -> str:
    index = _get_index()
    filters = _build_filters(question, "lila_library")
    retriever = index.as_retriever(similarity_top_k=SIMILARITY_TOP_K, filters=filters)
    nodes = await retriever.aretrieve(question)

    reranker = _get_reranker()
    reranked = reranker.postprocess_nodes(nodes, query_str=question)

    return _format_chunks(reranked)


async def query_course_notes(question: str) -> str:
    index = _get_course_index()
    filters = _build_filters(question, "bildungsroman_notes")
    retriever = index.as_retriever(similarity_top_k=SIMILARITY_TOP_K, filters=filters)
    nodes = await retriever.aretrieve(question)

    reranker = _get_reranker()
    reranked = reranker.postprocess_nodes(nodes, query_str=question)

    return _format_chunks(reranked)
