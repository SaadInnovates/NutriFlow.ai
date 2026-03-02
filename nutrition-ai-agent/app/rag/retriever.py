from functools import lru_cache

from app.config import get_settings
from app.rag.vectorstore import get_vectorstore


@lru_cache
def get_retriever():
	settings = get_settings()
	vectorstore = get_vectorstore()
	return vectorstore.as_retriever(search_kwargs={"k": settings.retrieval_k})
