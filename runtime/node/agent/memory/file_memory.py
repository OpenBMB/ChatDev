"""
FileMemory: Memory system for vectorizing and retrieving file contents
"""
import json
import os
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any
import time

import faiss
import numpy as np

from runtime.node.agent.memory.memory_base import (
    MemoryBase,
    MemoryContentSnapshot,
    MemoryItem,
    MemoryWritePayload,
)
from entity.configs import MemoryStoreConfig, FileSourceConfig
from entity.configs.node.memory import FileMemoryConfig

logger = logging.getLogger(__name__)


class FileMemory(MemoryBase):
    """
    File-based memory system that indexes and retrieves content from files/directories.
    Supports multiple file types, chunking strategies, and incremental updates.
    """

    def __init__(self, store: MemoryStoreConfig):
        config = store.as_config(FileMemoryConfig)
        if not config:
            raise ValueError("FileMemory requires a file memory store configuration")
        super().__init__(store)

        if not config.file_sources:
            raise ValueError("FileMemory requires at least one file_source in configuration")

        self.file_config = config
        self.file_sources: List[FileSourceConfig] = config.file_sources
        self.index_path = self.file_config.index_path  # Path to store the index

        # Chunking configuration
        self.chunk_size = 500  # Characters per chunk
        self.chunk_overlap = 50  # Overlapping characters between chunks

        # File metadata cache {file_path: {hash, chunks_count, ...}}
        self.file_metadata: Dict[str, Dict[str, Any]] = {}

    def load(self) -> None:
        """
        Load existing index or build new one from file sources.
        Validates index integrity and performs incremental updates if needed.
        """
        if self.index_path and os.path.exists(self.index_path):
            logger.info(f"Loading existing index from {self.index_path}")
            self._load_from_file()

            # Validate and update if files changed
            if self._validate_and_update_index():
                logger.info("Index updated due to file changes")
                self.save()
        else:
            logger.info("Building new index from file sources")
            self._build_index_from_sources()
            if self.index_path:
                self.save()

    def save(self) -> None:
        """Persist the memory index to disk"""
        if not self.index_path:
            logger.warning("No index_path specified, skipping save")
            return

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)

        # Prepare data for serialization
        data = {
            "file_metadata": self.file_metadata,
            "contents": [item.to_dict() for item in self.contents],
            "config": {
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap,
            }
        }

        # Save to JSON
        with open(self.index_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Index saved to {self.index_path} ({len(self.contents)} chunks)")

    def retrieve(
        self,
        agent_role: str,
        query: MemoryContentSnapshot,
        top_k: int,
        similarity_threshold: float,
    ) -> List[MemoryItem]:
        """
        Retrieve relevant file chunks based on query.

        Args:
            agent_role: Agent role (not used in file memory)
            inputs: Query text
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score

        Returns:
            List of MemoryItem with file chunks
        """
        if self.count_memories() == 0:
            return []

        # Generate query embedding
        query_embedding = self.embedding.get_embedding(query.text)
        if isinstance(query_embedding, list):
            query_embedding = np.array(query_embedding, dtype=np.float32)
        query_embedding = query_embedding.reshape(1, -1)
        faiss.normalize_L2(query_embedding)

        # Collect embeddings from memory items
        memory_embeddings = []
        valid_items = []
        for item in self.contents:
            if item.embedding is not None:
                memory_embeddings.append(item.embedding)
                valid_items.append(item)

        if not memory_embeddings:
            return []

        memory_embeddings = np.array(memory_embeddings, dtype=np.float32)

        # Build FAISS index and search
        index = faiss.IndexFlatIP(memory_embeddings.shape[1])
        index.add(memory_embeddings)

        similarities, indices = index.search(query_embedding, min(top_k, len(valid_items)))

        # Filter by threshold and return results
        results = []
        for i in range(len(indices[0])):
            idx = indices[0][i]
            similarity = similarities[0][i]

            if idx != -1 and similarity >= similarity_threshold:
                results.append(valid_items[idx])

        return results

    def update(self, payload: MemoryWritePayload) -> None:
        """
        FileMemory is read-only, updates are not supported.
        This method is a no-op to maintain interface compatibility.
        """
        logger.debug("FileMemory.update() called but FileMemory is read-only")
        pass

    # ========== Private Helper Methods ==========

    def _load_from_file(self) -> None:
        """Load index from JSON file"""
        try:
            with open(self.index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.file_metadata = data.get("file_metadata", {})
            raw_contents = data.get("contents", [])
            contents: List[MemoryItem] = []
            for raw in raw_contents:
                try:
                    contents.append(MemoryItem.from_dict(raw))
                except Exception:
                    continue
            self.contents = contents

            # Load config if present
            config = data.get("config", {})
            self.chunk_size = config.get("chunk_size", self.chunk_size)
            self.chunk_overlap = config.get("chunk_overlap", self.chunk_overlap)

            logger.info(f"Loaded {len(self.contents)} chunks from index")
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            self.file_metadata = {}
            self.contents = []

    def _build_index_from_sources(self) -> None:
        """Build index by scanning all file sources"""
        all_chunks = []

        for source in self.file_sources:
            logger.info(f"Scanning source: {source.source_path}")
            files = self._scan_files(source)
            logger.info(f"Found {len(files)} files in {source.source_path}")

            for file_path in files:
                chunks = self._read_and_chunk_file(file_path, source.encoding)
                all_chunks.extend(chunks)

        logger.info(f"Total chunks to index: {len(all_chunks)}")

        # Generate embeddings for all chunks
        self.contents = self._build_embeddings(all_chunks)

        logger.info(f"Index built with {len(self.contents)} chunks")

    def _validate_and_update_index(self) -> bool:
        """
        Validate index integrity and update if files changed.

        Returns:
            True if index was updated, False otherwise
        """
        updated = False
        current_files = set()

        # Scan current files
        for source in self.file_sources:
            files = self._scan_files(source)
            current_files.update(files)

        # Check for deleted files
        indexed_files = set(self.file_metadata.keys())
        deleted_files = indexed_files - current_files

        if deleted_files:
            logger.info(f"Removing {len(deleted_files)} deleted files from index")
            self._remove_files_from_index(deleted_files)
            updated = True

        # Check for new or modified files
        for source in self.file_sources:
            files = self._scan_files(source)

            for file_path in files:
                file_hash = self._compute_file_hash(file_path)

                # New file
                if file_path not in self.file_metadata:
                    logger.info(f"Indexing new file: {file_path}")
                    self._index_file(file_path, source.encoding)
                    updated = True

                # Modified file
                elif self.file_metadata[file_path].get("hash") != file_hash:
                    logger.info(f"Re-indexing modified file: {file_path}")
                    self._remove_files_from_index([file_path])
                    self._index_file(file_path, source.encoding)
                    updated = True

        return updated

    def _scan_files(self, source: FileSourceConfig) -> List[str]:
        """
        Scan file path and return list of matching files.

        Args:
            source: FileSourceConfig with path and filters

        Returns:
            List of absolute file paths
        """
        path = Path(source.source_path).expanduser().resolve()

        # Single file
        if path.is_file():
            if self._matches_file_types(path, source.file_types):
                return [str(path)]
            return []

        # Directory
        if not path.is_dir():
            logger.warning(f"Path does not exist: {source.source_path}")
            return []

        files = []

        if source.recursive:
            # Recursive scan
            for file_path in path.rglob("*"):
                if file_path.is_file() and self._matches_file_types(file_path, source.file_types):
                    files.append(str(file_path))
        else:
            # Non-recursive scan
            for file_path in path.glob("*"):
                if file_path.is_file() and self._matches_file_types(file_path, source.file_types):
                    files.append(str(file_path))

        return files

    def _matches_file_types(self, file_path: Path, file_types: List[str]) -> bool:
        """Check if file matches the file type filter"""
        if file_types is None:
            return True
        return file_path.suffix in file_types

    def _read_and_chunk_file(self, file_path: str, encoding: str = "utf-8") -> List[Dict]:
        """
        Read file and split into chunks.

        Args:
            file_path: Path to file
            encoding: File encoding

        Returns:
            List of chunk dictionaries with content and metadata
        """
        try:
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return []

        if not content.strip():
            return []

        # Compute file hash
        file_hash = self._compute_file_hash(file_path)
        file_size = os.path.getsize(file_path)

        # Chunk the content
        chunks = self._chunk_text(content)

        # Build chunk metadata
        chunk_dicts = []
        for i, chunk_text in enumerate(chunks):
            chunk_dicts.append({
                "content": chunk_text,
                "metadata": {
                    "source_type": "file",
                    "file_path": file_path,
                    "file_name": os.path.basename(file_path),
                    "file_hash": file_hash,
                    "file_size": file_size,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "encoding": encoding,
                }
            })

        # Update file metadata cache
        self.file_metadata[file_path] = {
            "hash": file_hash,
            "size": file_size,
            "chunks_count": len(chunks),
            "indexed_at": time.time(),
        }

        return chunk_dicts

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks with overlap.

        Args:
            text: Input text

        Returns:
            List of text chunks
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                last_sentence = max(
                    chunk.rfind('。'),
                    chunk.rfind('！'),
                    chunk.rfind('？'),
                    chunk.rfind('.'),
                    chunk.rfind('!'),
                    chunk.rfind('?'),
                    chunk.rfind('\n')
                )

                if last_sentence > self.chunk_size // 2:  # Don't break too early
                    chunk = chunk[:last_sentence + 1]
                    end = start + last_sentence + 1

            chunks.append(chunk.strip())

            # Move start with overlap
            start = end - self.chunk_overlap

            if start >= len(text):
                break

        return [c for c in chunks if c]  # Filter empty chunks

    def _build_embeddings(self, chunks: List[Dict]) -> List[MemoryItem]:
        """
        Generate embeddings for chunks and create MemoryItems.

        Args:
            chunks: List of chunk dictionaries

        Returns:
            List of MemoryItem objects
        """
        memory_items = []

        for chunk_dict in chunks:
            content = chunk_dict["content"]
            metadata = chunk_dict["metadata"]

            # Generate embedding
            try:
                embedding = self.embedding.get_embedding(content)
                if isinstance(embedding, list):
                    embedding = np.array(embedding, dtype=np.float32).reshape(1, -1)
                faiss.normalize_L2(embedding)
                embedding_list = embedding.tolist()[0]
            except Exception as e:
                logger.error(f"Error generating embedding for chunk: {e}")
                continue

            # Create MemoryItem
            item_id = f"{metadata['file_hash']}_{metadata['chunk_index']}"
            memory_item = MemoryItem(
                id=item_id,
                content_summary=content,
                metadata=metadata,
                embedding=embedding_list,
                timestamp=time.time(),
            )

            memory_items.append(memory_item)

        return memory_items

    def _compute_file_hash(self, file_path: str) -> str:
        """Compute MD5 hash of file"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()[:16]
        except Exception as e:
            logger.error(f"Error computing hash for {file_path}: {e}")
            return "error"

    def _index_file(self, file_path: str, encoding: str = "utf-8") -> None:
        """Index a single file (helper for incremental updates)"""
        chunks = self._read_and_chunk_file(file_path, encoding)
        if chunks:
            new_items = self._build_embeddings(chunks)
            self.contents.extend(new_items)

    def _remove_files_from_index(self, file_paths: List[str]) -> None:
        """Remove chunks from deleted files"""
        file_paths_set = set(file_paths)

        # Filter out chunks from deleted files
        self.contents = [
            item for item in self.contents
            if item.metadata.get("file_path") not in file_paths_set
        ]

        # Remove from metadata
        for file_path in file_paths:
            self.file_metadata.pop(file_path, None)
