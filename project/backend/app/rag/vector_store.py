import math
import re
from collections import Counter
from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings

from app.core.config import EMBEDDING_PROVIDER, VECTOR_DB_DIR
from app.rag.document_loader import document_loader, DocumentChunk
from app.rag.gemini_service import gemini_service

BASE_COLLECTION = "hust_documents"
DEFAULT_PROVIDER = "default"
GEMINI_PROVIDER = "gemini"


def tokenize(text: str) -> List[str]:
    """Tách âm tiết/từ (giữ dấu tiếng Việt) để chấm điểm từ khóa BM25."""
    return re.findall(r"\w+", text.lower())


def bm25_rank(query: str, docs: List[str], k1: float = 1.5, b: float = 0.75) -> List[int]:
    """Trả về chỉ số tài liệu có điểm BM25 > 0, sắp xếp giảm dần.

    Bổ sung cho tìm kiếm vector: câu hỏi tiếng Việt có từ khóa đặc thù
    ("cảnh cáo", "đồ án", "học bổng") được bắt chính xác kể cả khi embedding yếu.
    """
    query_terms = set(tokenize(query))
    if not query_terms or not docs:
        return []
    tokenized = [tokenize(d) for d in docs]
    avg_len = sum(len(t) for t in tokenized) / len(tokenized) or 1.0
    doc_freq = Counter(term for tokens in tokenized for term in set(tokens))
    n = len(docs)
    scores = []
    for idx, tokens in enumerate(tokenized):
        tf = Counter(tokens)
        score = 0.0
        for term in query_terms:
            if term not in tf:
                continue
            idf = math.log(1 + (n - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            freq = tf[term]
            score += idf * freq * (k1 + 1) / (freq + k1 * (1 - b + b * len(tokens) / avg_len))
        if score > 0:
            scores.append((score, idx))
    scores.sort(reverse=True)
    return [idx for _, idx in scores]

class VectorStoreManager:
    def __init__(self, persist_dir: Path = VECTOR_DB_DIR):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client: Optional[chromadb.PersistentClient] = None
        self.collection = None
        self.provider = DEFAULT_PROVIDER
        self.collection_name = BASE_COLLECTION
        self._gemini_failed = False
        self._init_client()

    def _desired_provider(self) -> str:
        if EMBEDDING_PROVIDER == DEFAULT_PROVIDER or self._gemini_failed:
            return DEFAULT_PROVIDER
        return GEMINI_PROVIDER if gemini_service.is_configured() else DEFAULT_PROVIDER

    def _init_client(self):
        """Kết nối collection ứng với bộ embedding đang dùng.

        Mỗi bộ embedding có số chiều vector khác nhau nên dùng collection riêng:
        ``hust_documents`` (mặc định của Chroma) và ``hust_documents_gemini``.
        """
        self.provider = self._desired_provider()
        self.collection_name = (
            BASE_COLLECTION if self.provider == DEFAULT_PROVIDER else f"{BASE_COLLECTION}_{self.provider}"
        )
        try:
            if self.client is None:
                self.client = chromadb.PersistentClient(
                    path=str(self.persist_dir),
                    settings=Settings(anonymized_telemetry=False)
                )
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "description": "Kho tri thức quy chế đào tạo và sổ tay sinh viên HUST",
                    "embedding_provider": self.provider,
                }
            )
            print(f"[VectorStoreManager] Đã kết nối ChromaDB tại {self.persist_dir} ({self.collection_name}). Tổng chunks hiện có: {self.collection.count()}")
        except Exception as e:
            print(f"[VectorStoreManager] Lỗi khởi tạo ChromaDB: {e}")

    def _ensure_provider(self):
        """Đổi collection khi API key được thêm/xóa lúc runtime."""
        if self.collection is None or self.provider != self._desired_provider():
            self._init_client()

    def _disable_gemini(self, error: Exception):
        print(f"[VectorStoreManager] Gemini embedding lỗi, chuyển về embedding mặc định: {error}")
        self._gemini_failed = True
        self._init_client()

    def _embed(self, texts: List[str], task_type: str) -> Optional[List[List[float]]]:
        """None nghĩa là để Chroma tự embed bằng mô hình mặc định."""
        if self.provider != GEMINI_PROVIDER:
            return None
        return gemini_service.embed_texts(texts, task_type)

    def sync_documents(self, force: bool = False) -> Dict[str, Any]:
        """
        Đồng bộ tài liệu từ data/documents vào ChromaDB Vector Store.
        Tự động nạp các chunks mới hoặc cập nhật khi có thay đổi.
        """
        self._ensure_provider()

        current_count = self.collection.count() if self.collection else 0

        chunks = document_loader.load_all_chunks()
        if not chunks:
            return {"status": "empty", "message": "Không tìm thấy tài liệu nào trong data/documents/", "count": 0}

        if force and self.client:
            try:
                self.client.delete_collection(self.collection_name)
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={
                        "description": "Kho tri thức đề cương môn học và quy chế đào tạo tín chỉ HUST",
                        "embedding_provider": self.provider,
                    }
                )
                print("[VectorStoreManager] Đã làm mới collection cho kho tri thức môn học.")
            except Exception as e:
                print(f"[VectorStoreManager] Lỗi reset collection: {e}")
        elif current_count > 0:
            print(f"[VectorStoreManager] Collection đã có {current_count} chunks. Tiến hành cập nhật/upsert...")

        documents = []
        metadatas = []
        ids = []

        for c in chunks:
            meta = c.metadata
            chunk_id = f"{meta['source']}_chunk_{meta['chunk_index']}"
            documents.append(c.text)
            # ChromaDB metadata chỉ chấp nhận str, int, float, bool
            clean_meta = {
                "source": str(meta.get("source", "")),
                "file_name": str(meta.get("file_name", "")),
                "title": str(meta.get("title", "")),
                "chunk_index": int(meta.get("chunk_index", 0)),
                "total_chunks": int(meta.get("total_chunks", 1)),
                "file_type": str(meta.get("file_type", "md")),
                "file_hash": str(meta.get("file_hash", ""))
            }
            metadatas.append(clean_meta)
            ids.append(chunk_id)

        # Batch upsert vào ChromaDB (mỗi batch tối đa 200 chunks)
        try:
            embeddings = self._embed(documents, "RETRIEVAL_DOCUMENT")
        except Exception as e:
            self._disable_gemini(e)
            return self.sync_documents(force=force)

        batch_size = 100
        for i in range(0, len(ids), batch_size):
            end = i + batch_size
            batch = {
                "ids": ids[i:end],
                "documents": documents[i:end],
                "metadatas": metadatas[i:end],
            }
            if embeddings is not None:
                batch["embeddings"] = embeddings[i:end]
            self.collection.upsert(**batch)

        new_total = self.collection.count()
        print(f"[VectorStoreManager] Đồng bộ thành công {len(ids)} chunks vào ChromaDB. Tổng hiện có: {new_total}")

        return {
            "status": "success",
            "synced_chunks": len(ids),
            "total_chunks": new_total,
            "embedding_provider": self.provider,
            "sources": list(set([m["source"] for m in metadatas]))
        }

    def similarity_search(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        """
        Tìm kiếm lai (Hybrid Retrieval): Kết hợp Semantic Search (Vector) 
        và Exact Code / Article Token Matching để đảm bảo chính xác 100% khi tra cứu
        mã học phần (ET4340, ET3290...), điều khoản quy chế (Điều 3, Điều 9...), hoặc thuật ngữ.
        """
        self._ensure_provider()
        try:
            if not self.collection or self.collection.count() == 0:
                self.sync_documents()
        except Exception:
            self._init_client()
            if not self.collection or self.collection.count() == 0:
                self.sync_documents()

        if not self.collection:
            return []

        query_upper = query.upper()
        # 1. Trích xuất mã học phần (vd: ET4340, ET 4230 -> ET4230)
        norm_query = re.sub(r'\b([A-Z]{2,3})\s+(\d{4}[A-Z]?)\b', r'\1\2', query_upper)
        course_codes = re.findall(r'\b([A-Z]{2,3}\d{4}[A-Z]?)\b', norm_query)

        # 2. Trích xuất điều khoản (vd: Điều 3, Điều 9)
        article_matches = re.findall(r'\b(ĐIỀU\s+\d+)\b', norm_query)

        # 3. Vector Semantic Search
        actual_k = min(k * 2, self.collection.count())
        semantic_chunks = []
        try:
            try:
                query_embeddings = self._embed([query], "RETRIEVAL_QUERY")
            except Exception as e:
                # Collection Gemini không truy vấn được bằng vector mặc định
                # (khác số chiều) nên chuyển hẳn sang collection mặc định.
                self._disable_gemini(e)
                if self.collection.count() == 0:
                    self.sync_documents()
                query_embeddings = None
            if query_embeddings is not None:
                results = self.collection.query(query_embeddings=query_embeddings, n_results=actual_k)
            else:
                results = self.collection.query(query_texts=[query], n_results=actual_k)
            if results and "documents" in results and results["documents"]:
                docs = results["documents"][0]
                metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
                dists = results["distances"][0] if "distances" in results and results["distances"] else [1.0] * len(docs)
                for doc, meta, dist in zip(docs, metas, dists):
                    semantic_chunks.append({
                        "text": doc,
                        "metadata": meta,
                        "distance": dist
                    })
        except Exception as e:
            print(f"[VectorStoreManager] Lỗi query vector: {e}")

        all_docs: List[str] = []
        all_metas: List[Dict[str, Any]] = []
        try:
            all_data = self.collection.get(include=["documents", "metadatas"])
            all_docs = all_data.get("documents") or []
            all_metas = all_data.get("metadatas") or [{}] * len(all_docs)
        except Exception as e:
            print(f"[VectorStoreManager] Lỗi đọc toàn bộ chunks: {e}")

        # 4. Exact Token Matching từ bộ sưu tập
        exact_chunks = []
        target_tokens = set(course_codes + article_matches)
        if target_tokens:
            try:
                if all_docs:
                    for doc, meta in zip(all_docs, all_metas):
                        doc_upper = doc.upper()
                        for tok in target_tokens:
                            if tok in doc_upper:
                                # Ưu tiên cao hơn nếu token nằm ở tiêu đề/dòng đầu
                                first_lines = "\n".join(doc.splitlines()[:3]).upper()
                                is_in_title = tok in first_lines
                                dist = 0.02 if is_in_title else 0.08
                                exact_chunks.append({
                                    "text": doc,
                                    "metadata": meta,
                                    "distance": dist
                                })
                                break
            except Exception as e:
                print(f"[VectorStoreManager] Lỗi scan exact token: {e}")

        # 5. Lexical BM25: xếp hạng theo từ khóa tiếng Việt
        lexical_chunks = [
            {"text": all_docs[i], "metadata": all_metas[i], "distance": None}
            for i in bm25_rank(query, all_docs)[:actual_k]
        ]

        # 6. Hợp nhất semantic + lexical bằng Reciprocal Rank Fusion (RRF)
        fused: Dict[str, Dict[str, Any]] = {}
        for ranking in (semantic_chunks, lexical_chunks):
            for rank, item in enumerate(ranking):
                key = item["text"].strip()
                entry = fused.setdefault(key, {**item, "score": 0.0})
                entry["score"] += 1.0 / (60 + rank)
                if entry.get("distance") is None and item.get("distance") is not None:
                    entry["distance"] = item["distance"]
        ranked = sorted(fused.values(), key=lambda x: x["score"], reverse=True)

        # 7. Exact matches luôn đứng đầu, sau đó tới kết quả đã hợp nhất
        seen_texts = set()
        merged = []
        exact_chunks.sort(key=lambda x: x["distance"])
        for item in exact_chunks + ranked:
            normalized_text = item["text"].strip()
            if normalized_text not in seen_texts:
                seen_texts.add(normalized_text)
                item.pop("score", None)
                if item.get("distance") is None:
                    item["distance"] = 1.0
                merged.append(item)

        return merged[:k]

    def get_stats(self) -> Dict[str, Any]:
        """Lấy thống kê trạng thái hiện tại của Vector Store"""
        try:
            if not self.collection:
                self._init_client()
            count = self.collection.count() if self.collection else 0
        except Exception:
            self._init_client()
            count = self.collection.count() if self.collection else 0

        sources = []
        if self.collection and count > 0:
            try:
                sample = self.collection.get(limit=100)
                if sample and "metadatas" in sample:
                    sources = list(set([m.get("source", "") for m in sample["metadatas"] if m]))
            except Exception:
                pass

        return {
            "collection_name": self.collection_name,
            "embedding_provider": self.provider,
            "total_chunks": count,
            "indexed_sources": sorted(sources),
            "persist_dir": str(self.persist_dir)
        }

vector_store = VectorStoreManager()
