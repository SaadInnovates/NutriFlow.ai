from pathlib import Path
import hashlib
import json
import warnings

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.config import get_settings


_VECTORSTORE = None


def _cache_dir(data_dir: Path) -> Path:
	cache_root = data_dir.parent / ".faiss_cache"
	cache_root.mkdir(parents=True, exist_ok=True)
	return cache_root


def _corpus_signature(data_dir: Path, settings) -> str:
	entries: list[str] = []
	if data_dir.exists():
		for path in sorted(data_dir.glob("**/*")):
			if not path.is_file() or path.suffix.lower() not in {".txt", ".md", ".pdf"}:
				continue
			stat = path.stat()
			rel = path.relative_to(data_dir).as_posix()
			entries.append(f"{rel}:{stat.st_size}:{stat.st_mtime_ns}")
	else:
		entries.append("missing_data_dir")

	payload = {
		"embedding_model": settings.embedding_model,
		"chunk_size": settings.chunk_size,
		"chunk_overlap": settings.chunk_overlap,
		"entries": entries,
	}
	serialized = json.dumps(payload, sort_keys=True)
	return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _cache_paths(settings) -> tuple[Path, Path, str]:
	cache_dir = _cache_dir(settings.data_dir)
	signature = _corpus_signature(settings.data_dir, settings)
	index_dir = cache_dir / "faiss_index"
	signature_file = cache_dir / "signature.json"
	return index_dir, signature_file, signature


def _load_cached_vectorstore(embeddings: HuggingFaceEmbeddings, index_dir: Path, signature_file: Path, signature: str):
	if not index_dir.exists() or not signature_file.exists():
		return None
	try:
		stored = json.loads(signature_file.read_text(encoding="utf-8"))
		if stored.get("signature") != signature:
			return None
		return FAISS.load_local(str(index_dir), embeddings, allow_dangerous_deserialization=True)
	except Exception:
		return None


def _save_cached_vectorstore(vectorstore: FAISS, index_dir: Path, signature_file: Path, signature: str) -> None:
	vectorstore.save_local(str(index_dir))
	signature_file.write_text(json.dumps({"signature": signature}, indent=2), encoding="utf-8")


def _read_pdf_text(path: Path) -> str:
	reader = PdfReader(str(path))
	return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def _read_documents_from_dir(data_dir: Path) -> list[Document]:
	documents: list[Document] = []
	if not data_dir.exists():
		return documents

	for path in data_dir.glob("**/*"):
		if not path.is_file() or path.suffix.lower() not in {".txt", ".md", ".pdf"}:
			continue
		if path.suffix.lower() == ".pdf":
			text = _read_pdf_text(path)
		else:
			text = path.read_text(encoding="utf-8", errors="ignore").strip()
		if text:
			documents.append(Document(page_content=text, metadata={"source": str(path)}))
	return documents


def _default_knowledge() -> list[Document]:
	fallback = """
General nutrition guidance:
- Prioritize minimally processed whole foods and balanced meals.
- Include lean proteins, high-fiber carbohydrates, and healthy fats at most meals.
- For fat loss, use a moderate calorie deficit and high satiety foods.
- For muscle gain, maintain a small calorie surplus with sufficient protein intake.
- Typical protein target range is 1.2-2.2 g/kg/day depending on goals and training.
- Keep hydration adequate and sodium/potassium balance aligned with activity level.
- People with diabetes, kidney disease, hypertension, or food allergies need tailored plans.
""".strip()
	return [Document(page_content=fallback, metadata={"source": "default_knowledge"})]


def get_vectorstore() -> FAISS:
	global _VECTORSTORE
	if _VECTORSTORE is not None:
		return _VECTORSTORE

	settings = get_settings()
	documents = _read_documents_from_dir(settings.data_dir)
	if not documents:
		documents = _default_knowledge()

	splitter = RecursiveCharacterTextSplitter(
		chunk_size=settings.chunk_size,
		chunk_overlap=settings.chunk_overlap,
	)
	chunks = splitter.split_documents(documents)

	with warnings.catch_warnings():
		warnings.filterwarnings("ignore", message=".*HuggingFaceEmbeddings.*deprecated.*")
		warnings.filterwarnings("ignore", message=".*Core Pydantic V1 functionality isn't compatible with Python 3.14.*")
		embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
	index_dir, signature_file, signature = _cache_paths(settings)
	cached = _load_cached_vectorstore(embeddings, index_dir, signature_file, signature)
	if cached is not None:
		_VECTORSTORE = cached
		return _VECTORSTORE

	_VECTORSTORE = FAISS.from_documents(chunks, embeddings)
	_save_cached_vectorstore(_VECTORSTORE, index_dir, signature_file, signature)
	return _VECTORSTORE
