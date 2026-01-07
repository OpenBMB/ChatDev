import hashlib
import json
import os
import re
import time
from typing import List

from entity.configs import MemoryStoreConfig
from entity.configs.node.memory import SimpleMemoryConfig
from runtime.node.agent.memory.memory_base import (
    MemoryBase,
    MemoryContentSnapshot,
    MemoryItem,
    MemoryWritePayload,
)
import faiss
import numpy as np

class SimpleMemory(MemoryBase):
    def __init__(self, store: MemoryStoreConfig):
        config = store.as_config(SimpleMemoryConfig)
        if not config:
            raise ValueError("SimpleMemory requires a simple memory store configuration")
        super().__init__(store)
        self.config = config
        # Optimized prompt templates for clarity
        self.retrieve_prompt = "Query: {input}"
        self.update_prompt = "Input: {input}\nOutput: {output}"
        self.memory_path = self.config.memory_path  # auto
        
        # Content extraction configuration
        self.max_content_length = 500  # Maximum content length
        self.min_content_length = 20   # Minimum content length
        
    def _extract_key_content(self, content: str) -> str:
        """Extract key content while stripping redundant text."""
        # Remove redundant whitespace
        content = re.sub(r'\s+', ' ', content.strip())
        
        # Skip heavy processing for short snippets
        if len(content) <= 100:
            return content
        
        # Remove common templated instructions
        content = re.sub(r'(?:Agent|Model) Role:.*?\n\n', '', content)
        content = re.sub("(?:You are|\u4f60\u662f\u4e00\u4f4d).*?(?:,|\uff0c)", '', content)
        content = re.sub("(?:User will input|\u7528\u6237\u4f1a\u8f93\u5165).*?(?:,|\uff0c)", '', content)
        content = re.sub("(?:You need to|\u4f60\u9700\u8981).*?(?:,|\uff0c)", '', content)
        
        # Extract key sentences while skipping very short ones
        sentences = re.split(r'[\u3002\uff01\uff1f\uff1b\n]', content)
        key_sentences = [s.strip() for s in sentences if len(s.strip()) >= self.min_content_length]
        
        # Fallback to original content when no sentence survives
        if not key_sentences:
            return content[:self.max_content_length]
        
        # Recombine and limit the number of sentences (max 3)
        extracted_content = '\u3002'.join(key_sentences[:3])
        if len(extracted_content) > self.max_content_length:
            extracted_content = extracted_content[:self.max_content_length] + "..."
            
        return extracted_content.strip()
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate a content hash used for deduplication."""
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:8]

    def load(self) -> None:
        if self.memory_path and os.path.exists(self.memory_path) and self.memory_path.endswith(".json"):
            try:
                with open(self.memory_path) as file:
                    raw_data = json.load(file)
                contents = []
                for raw in raw_data:
                    try:
                        contents.append(MemoryItem.from_dict(raw))
                    except Exception:
                        continue
                self.contents = contents
            except Exception:
                self.contents = []

    def save(self) -> None:
        if self.memory_path and self.memory_path.endswith(".json"):
            os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
            with open(self.memory_path, "w") as file:
                json.dump([item.to_dict() for item in self.contents], file, indent=2, ensure_ascii=False)

    def retrieve(
        self,
        agent_role: str,
        query: MemoryContentSnapshot,
        top_k: int,
        similarity_threshold: float,
    ) -> List[MemoryItem]:
        if self.count_memories() == 0 or not self.embedding:
            return []
        
        # Build an optimized query for retrieval
        query_text = self.retrieve_prompt.format(input=query.text)
        query_text = self._extract_key_content(query_text)
        
        inputs_embedding = self.embedding.get_embedding(query_text)
        if isinstance(inputs_embedding, list):
            inputs_embedding = np.array(inputs_embedding, dtype=np.float32)
        inputs_embedding = inputs_embedding.reshape(1, -1)
        faiss.normalize_L2(inputs_embedding)

        memory_embeddings = []
        valid_items = []
        for item in self.contents:
            if item.embedding is not None:
                memory_embeddings.append(item.embedding)
                valid_items.append(item)
        
        if not memory_embeddings:
            return []
            
        memory_embeddings = np.array(memory_embeddings, dtype=np.float32)

        # Use an efficient inner-product index
        index = faiss.IndexFlatIP(memory_embeddings.shape[1])
        index.add(memory_embeddings)

        # Retrieve extra candidates for reranking
        retrieval_k = min(top_k * 3, len(valid_items))
        similarities, indices = index.search(inputs_embedding, retrieval_k)
        
        # Filter and rerank the candidates
        candidates = []
        for i in range(len(indices[0])):
            idx = indices[0][i]
            similarity = similarities[0][i]

            if idx != -1 and similarity >= similarity_threshold:
                item = valid_items[idx]
                # Calculate an auxiliary semantic similarity score
                semantic_score = self._calculate_semantic_similarity(query_text, item.content_summary)
                # Combine similarity metrics
                combined_score = 0.7 * similarity + 0.3 * semantic_score
                candidates.append((item, combined_score))
        
        # Sort by the combined score and return the top_k items
        candidates.sort(key=lambda x: x[1], reverse=True)
        results = [item for item, score in candidates[:top_k]]
        
        return results
    
    def _calculate_semantic_similarity(self, query: str, content: str) -> float:
        """Compute a semantic similarity value."""
        # Enhanced semantic similarity computation
        query_lower = query.lower()
        content_lower = content.lower()
        
        # 1. Token overlap (Jaccard similarity)
        query_words = set(query_lower.split())
        content_words = set(content_lower.split())
        
        if not query_words or not content_words:
            jaccard_sim = 0.0
        else:
            intersection = query_words & content_words
            union = query_words | content_words
            jaccard_sim = len(intersection) / len(union) if union else 0.0
        
        # 2. Longest common subsequence similarity
        lcs_sim = self._calculate_lcs_similarity(query_lower, content_lower)
        
        # 3. Keyword match score
        keyword_sim = self._calculate_keyword_similarity(query_lower, content_lower)
        
        # 4. Length penalty factor (avoid overly short/long matches)
        length_factor = self._calculate_length_factor(query_lower, content_lower)
        
        # Weighted final score
        final_score = (0.4 * jaccard_sim + 
                      0.3 * lcs_sim + 
                      0.2 * keyword_sim + 
                      0.1 * length_factor)
        
        return min(final_score, 1.0)
    
    def _calculate_lcs_similarity(self, s1: str, s2: str) -> float:
        """Compute longest common subsequence similarity."""
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        
        lcs_length = dp[m][n]
        return lcs_length / max(len(s1), len(s2)) if max(len(s1), len(s2)) > 0 else 0.0
    
    def _calculate_keyword_similarity(self, query: str, content: str) -> float:
        """Compute keyword match similarity."""
        # Extract potential keywords (length >= 2)
        query_keywords = set(word for word in query.split() if len(word) >= 2)
        content_keywords = set(word for word in content.split() if len(word) >= 2)
        
        if not query_keywords:
            return 0.0
        
        matches = query_keywords & content_keywords
        return len(matches) / len(query_keywords)
    
    def _calculate_length_factor(self, query: str, content: str) -> float:
        """Penalize matches that deviate too much in length."""
        query_len = len(query)
        content_len = len(content)
        
        if content_len == 0:
            return 0.0
        
        # Ideal length ratio range
        ideal_ratio_min = 0.5
        ideal_ratio_max = 2.0
        
        ratio = content_len / query_len
        
        if ideal_ratio_min <= ratio <= ideal_ratio_max:
            return 1.0
        elif ratio < ideal_ratio_min:
            return ratio / ideal_ratio_min
        else:
            return max(0.1, ideal_ratio_max / ratio)

    def update(self, payload: MemoryWritePayload) -> None:
        if not self.embedding:
            return

        snapshot = payload.output_snapshot
        if not snapshot or not snapshot.text.strip():
            return

        raw_content = self.update_prompt.format(
            input=payload.inputs_text,
            output=snapshot.text,
        )
        extracted_content = self._extract_key_content(raw_content)

        if len(extracted_content) < self.min_content_length:
            return

        content_hash = self._generate_content_hash(extracted_content)
        for existing_item in self.contents:
            existing_hash = self._generate_content_hash(existing_item.content_summary)
            if existing_hash == content_hash:
                return

        embedding_vector = self.embedding.get_embedding(extracted_content)
        if isinstance(embedding_vector, list):
            embedding_vector = np.array(embedding_vector, dtype=np.float32)
        if embedding_vector is None:
            return
        embedding_array = np.array(embedding_vector, dtype=np.float32).reshape(1, -1)
        faiss.normalize_L2(embedding_array)

        metadata = {
            "agent_role": payload.agent_role,
            "input_preview": (payload.inputs_text or "")[:200],
            "content_length": len(extracted_content),
            "attachments": snapshot.attachment_overview(),
        }

        memory_item = MemoryItem(
            id=f"{content_hash}_{int(time.time())}",
            content_summary=extracted_content,
            metadata=metadata,
            embedding=embedding_array.tolist()[0],
            input_snapshot=payload.input_snapshot,
            output_snapshot=snapshot,
        )

        self.contents.append(memory_item)

        max_memories = 1000
        if len(self.contents) > max_memories:
            self.contents = self.contents[-max_memories:]
