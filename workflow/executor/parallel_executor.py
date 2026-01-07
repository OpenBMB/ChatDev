"""Parallel execution helpers that eliminate duplicated code."""

import concurrent.futures
from typing import Any, Callable, List, Tuple

from utils.log_manager import LogManager


class ParallelExecutor:
    """Manage parallel execution for workflow nodes.
    
    Provides shared logic for parallel batches and serializes Human nodes when needed.
    """
    
    def __init__(self, log_manager: LogManager, nodes_dict: dict):
        """Initialize the parallel executor.
        
        Args:
            log_manager: Logger instance
            nodes_dict: Mapping of ``node_id`` to ``Node``
        """
        self.log_manager = log_manager
        self.nodes_dict = nodes_dict
    
    def execute_items_parallel(
        self,
        items: List[Any],
        executor_func: Callable,
        item_desc_func: Callable[[Any], str],
        has_blocking_func: Callable[[Any], bool] | None = None,
    ) -> None:
        """Execute a list of items in parallel when possible.
        
        Args:
            items: Items to execute
            executor_func: Callable that executes a single item
            item_desc_func: Callable for logging a human-readable description
            has_blocking_func: Optional callable to decide if an item requires serialization
        """
        blocking_items, parallel_items = self._partition_blocking_items(items, has_blocking_func)
        
        if parallel_items:
            self._execute_parallel_batch(parallel_items, executor_func, item_desc_func)
        
        if blocking_items:
            self._execute_sequential_batch(blocking_items, executor_func, item_desc_func)
    
    def execute_nodes_parallel(
        self,
        node_ids: List[str],
        executor_func: Callable[[str], None]
    ) -> None:
        """Execute a list of nodes in parallel.
        
        Convenience wrapper around ``execute_items_parallel`` specialized for nodes.
        
        Args:
            node_ids: List of node identifiers
            executor_func: Callable that executes a single node
        """
        def item_desc_func(node_id: str) -> str:
            return f"node {node_id}"
        
        def has_blocking_func(node_id: str) -> bool:
            return False
        
        self.execute_items_parallel(
            node_ids,
            executor_func,
            item_desc_func,
            has_blocking_func
        )
    
    def _partition_blocking_items(
        self,
        items: List[Any],
        has_blocking_func: Callable[[Any], bool] | None
    ) -> Tuple[List[Any], List[Any]]:
        """Split items into blocking and parallelizable lists."""
        blocking_items = []
        parallel_items = []
        
        for item in items:
            if has_blocking_func and has_blocking_func(item):
                blocking_items.append(item)
            else:
                parallel_items.append(item)
        
        return blocking_items, parallel_items
    
    def _execute_parallel_batch(
        self,
        items: List[Any],
        executor_func: Callable,
        item_desc_func: Callable[[Any], str]
    ) -> None:
        """Execute a batch of items in parallel.
        
        Args:
            items: Items to execute
            executor_func: Callable per item
            item_desc_func: Callable returning a readable description
        """
        self.log_manager.debug(f"Executing {len(items)} items in parallel")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(items)) as executor:
            futures = []
            for item in items:
                future = executor.submit(executor_func, item)
                futures.append((item, future))
            
            # Wait for every future to finish
            for item, future in futures:
                try:
                    future.result()
                    self.log_manager.debug(f"{item_desc_func(item)} completed successfully")
                except Exception as e:
                    self.log_manager.error(f"{item_desc_func(item)} failed: {str(e)}")
                    raise
    
    def _execute_sequential_batch(
        self,
        items: List[Any],
        executor_func: Callable,
        item_desc_func: Callable[[Any], str]
    ) -> None:
        """Execute a batch of items sequentially.
        
        Args:
            items: Items to execute
            executor_func: Callable per item
            item_desc_func: Callable returning a readable description
        """
        for item in items:
            self.log_manager.debug(f"Executing {item_desc_func(item)} (sequential)")
            try:
                executor_func(item)
                self.log_manager.debug(f"{item_desc_func(item)} completed successfully")
            except Exception as e:
                self.log_manager.error(f"{item_desc_func(item)} failed: {str(e)}")
                raise
