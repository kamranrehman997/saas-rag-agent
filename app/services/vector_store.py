import chromadb
from app.config import settings

class VectorStoreService:
    def __init__(self):
        # Persistent client stores vector indexes locally in chroma_db/
        self.client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIRECTORY)

    def _get_tenant_collection(self, tenant_id: str):
        safe_name = f"tenant_{tenant_id.replace('-', '_')}"
        return self.client.get_or_create_collection(name=safe_name)

    def ingest_onboarding_data(self, tenant_id: str, scraped_pages: dict[str, str], owner_answers: dict[str, str]):
        collection = self._get_tenant_collection(tenant_id)
        
        documents = []
        metadatas = []
        ids = []

        # 1. Ingest scraped pages (chunked for optimal retrieval)
        idx = 0
        for page_name, text in scraped_pages.items():
            chunks = [text[i:i+1000] for i in range(0, len(text), 800)]
            for chunk_idx, chunk in enumerate(chunks):
                documents.append(chunk)
                metadatas.append({"source": f"website_{page_name}", "type": "scraped_content"})
                ids.append(f"scrape_{page_name}_{chunk_idx}")
                idx += 1

        # 2. Ingest owner answers to follow-up questions
        for q_idx, (question, answer) in enumerate(owner_answers.items()):
            qa_doc = f"Question: {question}\nAnswer: {answer}"
            documents.append(qa_doc)
            metadatas.append({"source": "owner_qa", "type": "direct_policy"})
            ids.append(f"owner_qa_{q_idx}")

        # Upsert documents into the tenant's isolated collection
        collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        return {"status": "success", "total_documents_indexed": len(documents)}

    def similarity_search(self, tenant_id: str, query: str, n_results: int = 4) -> list[str]:
        collection = self._get_tenant_collection(tenant_id)
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        if results and "documents" in results and results["documents"]:
            return results["documents"][0]
        return []