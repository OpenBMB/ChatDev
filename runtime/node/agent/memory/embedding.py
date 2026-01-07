from abc import ABC, abstractmethod
import re
import logging
from typing import List, Optional

import openai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)

from entity.configs import EmbeddingConfig

logger = logging.getLogger(__name__)


class EmbeddingBase(ABC):
    def __init__(self, embedding_config: EmbeddingConfig):
        self.config = embedding_config

    @abstractmethod
    def get_embedding(self, text):
        ...

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text to improve embedding quality."""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove special characters and emoji
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
        
        # Clean up whitespace again
        text = re.sub(r'\s+', ' ', text.strip())
        
        return text

    def _chunk_text(self, text: str, max_length: int = 500) -> List[str]:
        """Split long text into chunks to improve embedding quality."""
        if len(text) <= max_length:
            return [text]
        
        # Split by sentence boundaries
        sentences = re.split(r'[\u3002\uff01\uff1f\uff1b\n]', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if len(current_chunk + sentence) <= max_length:
                current_chunk += sentence + "\u3002"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + "\u3002"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

class EmbeddingFactory:
    @staticmethod
    def create_embedding(embedding_config: EmbeddingConfig) -> EmbeddingBase:
        model = embedding_config.provider
        if model == 'openai':
            return OpenAIEmbedding(embedding_config)
        elif model == 'local':
            return LocalEmbedding(embedding_config)
        else:
            raise ValueError(f"Unsupported embedding model: {model}")

class OpenAIEmbedding(EmbeddingBase):
    def __init__(self, embedding_config: EmbeddingConfig):
        super().__init__(embedding_config)
        self.base_url = embedding_config.base_url
        self.api_key = embedding_config.api_key
        self.model_name = embedding_config.model or "text-embedding-3-small"  # Default model
        self.max_length = embedding_config.params.get('max_length', 8191)
        self.use_chunking = embedding_config.params.get('use_chunking', False)
        self.chunk_strategy = embedding_config.params.get('chunk_strategy', 'average')

        if self.base_url:
            self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            self.client = openai.OpenAI(api_key=self.api_key)

    @retry(wait=wait_random_exponential(min=2, max=5), stop=stop_after_attempt(10))
    def get_embedding(self, text):
        # Preprocess the text
        processed_text = self._preprocess_text(text)
        
        if not processed_text:
            logger.warning("Empty text after preprocessing")
            return [0.0] * 1536  # Return a zero vector
        
        # Handle long text via chunking
        if self.use_chunking and len(processed_text) > self.max_length:
            return self._get_chunked_embedding(processed_text)
        
        # Truncate text
        truncated_text = processed_text[:self.max_length]
        
        try:
            response = self.client.embeddings.create(
                input=truncated_text, 
                model=self.model_name,
                encoding_format="float"
            )
            embedding = response.data[0].embedding
            return embedding
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return [0.0] * 1536  # Return zero vector as fallback

    def _get_chunked_embedding(self, text: str) -> List[float]:
        """Chunk long text, embed each chunk, then aggregate."""
        chunks = self._chunk_text(text, self.max_length // 2)  # Halve the chunk length
        
        if not chunks:
            return [0.0] * 1536
        
        chunk_embeddings = []
        for chunk in chunks:
            try:
                response = self.client.embeddings.create(
                    input=chunk,
                    model=self.model_name,
                    encoding_format="float"
                )
                chunk_embeddings.append(response.data[0].embedding)
            except Exception as e:
                logger.warning(f"Error getting chunk embedding: {e}")
                continue
        
        if not chunk_embeddings:
            return [0.0] * 1536
        
        # Aggregation strategy
        if self.chunk_strategy == 'average':
            # Mean aggregation
            return [sum(chunk[i] for chunk in chunk_embeddings) / len(chunk_embeddings) 
                   for i in range(len(chunk_embeddings[0]))]
        elif self.chunk_strategy == 'weighted':
            # Weighted aggregation (earlier chunks weigh more)
            weights = [1.0 / (i + 1) for i in range(len(chunk_embeddings))]
            total_weight = sum(weights)
            return [sum(chunk[i] * weights[j] for j, chunk in enumerate(chunk_embeddings)) / total_weight 
                   for i in range(len(chunk_embeddings[0]))]
        else:
            # Default to the first chunk
            return chunk_embeddings[0]

class LocalEmbedding(EmbeddingBase):
    def __init__(self, embedding_config: EmbeddingConfig):
        super().__init__(embedding_config)
        self.model_path = embedding_config.params.get('model_path')
        self.device = embedding_config.params.get('device', 'cpu')
        
        if not self.model_path:
            raise ValueError("LocalEmbedding requires model_path parameter")
        
        # Load the local embedding model (e.g., sentence-transformers)
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_path, device=self.device)
        except ImportError:
            raise ImportError("sentence-transformers is required for LocalEmbedding")

    def get_embedding(self, text):
        # Preprocess text before encoding
        processed_text = self._preprocess_text(text)
        
        if not processed_text:
            return [0.0] * 768  # Return zero vector
        
        try:
            embedding = self.model.encode(processed_text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error getting local embedding: {e}")
            return [0.0] * 768  # Return zero vector as fallback
