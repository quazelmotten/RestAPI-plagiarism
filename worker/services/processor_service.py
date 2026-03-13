"""
Service for processing candidate file pairs.
Handles fingerprint indexing and candidate generation using inverted index.
"""

import logging
import os
from typing import Dict, List, Tuple, Set, Optional

from inverted_index import inverted_index
from redis_cache import cache

log = logging.getLogger(__name__)


class ProcessorService:
    """Service for processing candidate file pairs."""
    
    def __init__(self, plagiarism_service):
        """
        Initialize processor service.
        
        Args:
            plagiarism_service: PlagiarismService instance for fingerprint generation
        """
        self.plagiarism_service = plagiarism_service
    
    def __setstate__(self, state):
        """Restore state. Ensure Redis cache is connected in subprocess."""
        self.__dict__.update(state)
        # Connect Redis cache in subprocess if not already connected
        if not cache.is_connected:
            try:
                cache.connect()
                log.info(f"Redis cache connected in subprocess (PID: {os.getpid()})")
            except Exception as e:
                log.warning(f"Failed to connect Redis cache in subprocess: {e}")
    
    def index_file_fingerprints(
        self, 
        file_info: Dict, 
        language: str,
        task_id: str
    ) -> bool:
        """
        Index fingerprints for a single file.
        
        Args:
            file_info: File information dict with 'hash', 'path', 'filename', etc.
            language: Programming language
            task_id: Task ID for logging
            
        Returns:
            True if indexing succeeded, False otherwise
        """
        file_hash = file_info.get('hash') or file_info.get('file_hash')
        file_path = file_info.get('path') or file_info.get('file_path')
        filename = file_info.get('filename', 'unknown')
        
        if not file_hash or not file_path:
            log.warning(f"[Task {task_id}] Skipping file with missing hash or path")
            return False
        
        try:
            # Check if already indexed
            if inverted_index.get_file_fingerprints(file_hash, language):
                log.debug(f"[Task {task_id}] File {filename} already in inverted index")
                return True
            
            # Try to acquire lock to prevent duplicate fingerprinting
            lock_acquired = False
            if cache.is_connected:
                lock_acquired = cache.lock_fingerprint_computation(file_hash)
            
            try:
                # Generate fingerprints
                fp_result = self.plagiarism_service.safe_run_cli_fingerprint(file_path, language)
                fingerprints = fp_result.get("fingerprints", [])
                ast_hashes = fp_result.get("ast_hashes", [])
                
                # Prepare fingerprints for indexing
                fingerprints_for_index = [
                    {
                        "hash": fp["hash"],
                        "start": tuple(fp["start"]),
                        "end": tuple(fp["end"])
                    }
                    for fp in fingerprints
                ]
                
                # Add to inverted index
                inverted_index.add_file_fingerprints(file_hash, fingerprints_for_index, language)
                log.debug(f"[Task {task_id}] Indexed {len(fingerprints)} fingerprints for {filename}")
                
                # Cache fingerprints for reuse
                tokens_serializable = fp_result.get("tokens", [])
                tokens = [(t["type"], tuple(t["start"]), tuple(t["end"])) for t in tokens_serializable]
                cache.cache_fingerprints(file_hash, fingerprints_for_index, ast_hashes, tokens)
                
                return True
            finally:
                if lock_acquired:
                    cache.unlock_fingerprint_computation(file_hash)
                    
        except Exception as e:
            log.warning(f"[Task {task_id}] Failed to index file {filename}: {e}")
            return False
    
    def ensure_files_indexed(
        self, 
        files: List[Dict], 
        language: str, 
        task_id: str,
        existing_files: Optional[List[Dict]] = None
    ) -> None:
        """
        Ensure files are indexed in the inverted index.
        
        Args:
            files: List of file info dicts to index
            language: Programming language
            task_id: Task ID for logging
            existing_files: Optional list of existing files from other tasks to ensure indexed
        """
        import time
        from concurrent.futures import as_completed
        
        log.info(f"[Task {task_id}] Indexing fingerprints for new files...")
        start_time = time.time()
        
        # Collect all files that may need indexing
        all_files_to_check = []
        if existing_files:
            all_files_to_check.extend(existing_files)
        all_files_to_check.extend(files)
        
        # Determine which files actually need indexing (not in inverted index and not in progress)
        files_to_index = []
        for file_info in all_files_to_check:
            file_hash = file_info.get('hash') or file_info.get('file_hash')
            file_path = file_info.get('path') or file_info.get('file_path')
            if not file_hash or not file_path:
                continue
            # Check if already indexed in inverted index
            if inverted_index.get_file_fingerprints(file_hash, language):
                continue
            # Check if fingerprints are in cache (if so, we can add to index without recomputation)
            fingerprints = cache.get_fingerprints(file_hash)
            if fingerprints:
                try:
                    inverted_index.add_file_fingerprints(file_hash, fingerprints, language)
                    log.debug(f"[Task {task_id}] Added cached fingerprints for {file_info.get('filename')} to inverted index")
                    continue
                except Exception as e:
                    log.warning(f"[Task {task_id}] Failed to add cached fingerprints: {e}")
            # Need to generate and index
            files_to_index.append(file_info)
        
        # Parallelize fingerprint generation and indexing for files that need it
        if files_to_index:
            log.info(f"[Task {task_id}] Need to generate fingerprints for {len(files_to_index)} files (parallelizing)...")
            executor = self.plagiarism_service.analysis_executor
            if executor is None:
                # Fallback to sequential
                log.warning(f"[Task {task_id}] No executor available, indexing sequentially")
                for file_info in files_to_index:
                    self.index_file_fingerprints(file_info, language, task_id)
            else:
                # Submit all indexing jobs to executor
                futures = {}
                for file_info in files_to_index:
                    future = executor.submit(self.index_file_fingerprints, file_info, language, task_id)
                    futures[future] = file_info
                
                # Collect results
                success_count = 0
                for future in as_completed(futures):
                    file_info = futures[future]
                    filename = file_info.get('filename', 'unknown')
                    try:
                        result = future.result()
                        if result:
                            success_count += 1
                    except Exception as e:
                        log.error(f"[Task {task_id}] Indexing failed for {filename}: {e}")
                log.info(f"[Task {task_id}] Indexed {success_count}/{len(files_to_index)} files successfully")
        
        elapsed = time.time() - start_time
        log.info(f"[Task {task_id}] Finished indexing fingerprints in {elapsed:.2f}s")
    
    def find_intra_task_pairs(
        self, 
        files: List[Dict], 
        language: str, 
        task_id: str
    ) -> List[Tuple[dict, dict]]:
        """
        Generate candidate pairs among files within the same task.
        
        Args:
            files: List of file info dicts in the task
            language: Programming language
            task_id: Task ID for logging
            
        Returns:
            List of (file_a, file_b) tuples representing pairs to analyze
        """
        pairs = []
        log.info(f"[Task {task_id}] Generating intra-task pairs using inverted index...")
        
        for file_a in files:
            file_a_hash = file_a.get('hash') or file_a.get('file_hash')
            file_a_path = file_a.get('path') or file_a.get('file_path')
            
            if not file_a_hash or not file_a_path:
                continue
            
            try:
                # Get fingerprints from cache or generate
                fingerprints = cache.get_fingerprints(file_a_hash)
                if fingerprints is None:
                    fp_result = self.plagiarism_service.safe_run_cli_fingerprint(file_a_path, language)
                    fingerprints = [
                        {
                            "hash": fp["hash"],
                            "start": tuple(fp["start"]),
                            "end": tuple(fp["end"])
                        }
                        for fp in fp_result.get("fingerprints", [])
                    ]
                    ast_hashes = fp_result.get("ast_hashes", [])
                    tokens_serializable = fp_result.get("tokens", [])
                    tokens = [(t["type"], tuple(t["start"]), tuple(t["end"])) for t in tokens_serializable]
                    cache.cache_fingerprints(file_a_hash, fingerprints, ast_hashes, tokens)
                
                # Find candidate files using inverted index
                candidate_hashes = inverted_index.find_candidate_files(fingerprints, language)
                
                if not candidate_hashes:
                    continue
                
                # Create pairs with other files in this task that are candidates
                intra_candidates = [
                    f for f in files 
                    if f != file_a and ((f.get('hash') or f.get('file_hash')) in candidate_hashes)
                ]
                
                for file_b in intra_candidates:
                    pairs.append((file_a, file_b))
                    
            except Exception as e:
                log.warning(f"[Task {task_id}] Error finding intra-task candidates for {file_a.get('filename')}: {e}")
        
        log.info(f"[Task {task_id}] Intra-task pairs: {len(pairs)}")
        return pairs
    
    def find_cross_task_pairs(
        self, 
        new_files: List[Dict], 
        existing_files: List[Dict], 
        language: str, 
        task_id: str
    ) -> List[Tuple[dict, dict]]:
        """
        Generate candidate pairs between new files and existing files from other tasks.
        
        Args:
            new_files: List of new file info dicts
            existing_files: List of existing file info dicts from other tasks
            language: Programming language
            task_id: Task ID for logging
            
        Returns:
            List of (new_file, existing_file) tuples representing pairs to analyze
        """
        pairs = []
        log.info(f"[Task {task_id}] Processing cross-task candidates...")
        
        for new_file in new_files:
            new_file_hash = new_file.get('hash') or new_file.get('file_hash')
            new_file_path = new_file.get('path') or new_file.get('file_path')
            new_file_name = new_file.get('filename', 'unknown')
            
            if not new_file_hash or not new_file_path:
                continue
            
            try:
                # Get or generate fingerprints for new file
                fingerprints = cache.get_fingerprints(new_file_hash)
                if fingerprints is None:
                    lock_acquired = False
                    if cache.is_connected:
                        lock_acquired = cache.lock_fingerprint_computation(new_file_hash)
                    try:
                        fp_result = self.plagiarism_service.safe_run_cli_fingerprint(new_file_path, language)
                        fingerprints = [
                            {
                                "hash": fp["hash"],
                                "start": tuple(fp["start"]),
                                "end": tuple(fp["end"])
                            }
                            for fp in fp_result.get("fingerprints", [])
                        ]
                        ast_hashes = fp_result.get("ast_hashes", [])
                        tokens_serializable = fp_result.get("tokens", [])
                        tokens = [(t["type"], tuple(t["start"]), tuple(t["end"])) for t in tokens_serializable]
                        cache.cache_fingerprints(new_file_hash, fingerprints, ast_hashes, tokens)
                    finally:
                        if lock_acquired:
                            cache.unlock_fingerprint_computation(new_file_hash)
                
                # Find candidate files using inverted index
                candidate_hashes = inverted_index.find_candidate_files(fingerprints, language)
                
                log.info(f"[Task {task_id}] {new_file_name}: fingerprints={len(fingerprints)}, candidate_hashes={len(candidate_hashes) if candidate_hashes else 0}")
                
                if not candidate_hashes:
                    log.info(f"[Task {task_id}] {new_file_name}: 0 candidates")
                    continue
                
                # Find matching existing files
                candidate_files = [
                    f for f in existing_files 
                    if (f.get('hash') or f.get('file_hash')) in candidate_hashes
                ]
                
                for existing_file in candidate_files:
                    pairs.append((new_file, existing_file))
                
                skipped = len(existing_files) - len(candidate_files)
                log.info(f"[Task {task_id}] {new_file_name}: {len(candidate_files)} candidates")
                
            except Exception as e:
                log.error(f"[Task {task_id}] Error counting candidates for {new_file_name}: {e}")
                # Fallback: compare with all existing files if candidate generation fails
                for existing_file in existing_files:
                    pairs.append((new_file, existing_file))
        
        log.info(f"[Task {task_id}] Cross-task pairs: {len(pairs)}")
        return pairs
