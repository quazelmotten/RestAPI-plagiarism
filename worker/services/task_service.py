"""
Task service - orchestrates the complete plagiarism analysis task.

Coordinates:
1. File fingerprinting & indexing
2. Candidate pair generation  
3. Detailed AST analysis
4. Result persistence
"""

import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)


class TaskService:
    """
    Orchestrates plagiarism detection tasks.

    This is the main entry point for processing a task. It coordinates
    all sub-services to complete the analysis workflow.
    """

    def __init__(
        self,
        fingerprint_service,
        indexing_service,
        candidate_service,
        analysis_service,
        result_service,
        repository
    ):
        """
        Initialize task service with all dependencies.

        Args:
            fingerprint_service: Generates fingerprints
            indexing_service: Manages inverted index
            candidate_service: Finds candidate pairs
            analysis_service: Performs AST analysis
            result_service: Persists results
            repository: Database operations
        """
        self.fingerprint_svc = fingerprint_service
        self.indexing_svc = indexing_service
        self.candidate_svc = candidate_service
        self.analysis_svc = analysis_service
        self.result_svc = result_service
        self.repository = repository

    def process_task(
        self,
        task_id: str,
        files: List[Dict[str, Any]],
        language: str
    ) -> None:
        """
        Process a plagiarism detection task.

        Args:
            task_id: Unique task identifier
            files: List of file info dicts with 'hash'/'file_hash' and 'path'/'file_path'
            language: Programming language (e.g., 'python', 'cpp')
        """
        logger.info(f"[Task {task_id}] Starting task with {len(files)} files")

        try:
            # Phase 1: Index all files
            self.repository.update_task(
                task_id=task_id,
                status="indexing",
                processed_pairs=0,
                total_pairs=None
            )

            existing_files = self.repository.get_all_files(exclude_task_id=task_id)
            logger.info(f"[Task {task_id}] Found {len(existing_files)} existing files in database")

            fingerprint_map = self.indexing_svc.ensure_files_indexed(
                files=files,
                language=language,
                existing_files=existing_files
            )

            # Phase 2: Generate candidate pairs
            self.repository.update_task(
                task_id=task_id,
                status="finding_pairs",
                processed_pairs=0,
                total_pairs=None
            )

            # Find intra-task pairs (within the same task)
            intra_pairs = self.candidate_svc.find_candidate_pairs(
                files_a=files,
                language=language,
                deduplicate=True
            )

            # Find cross-task pairs (new files vs existing files from other tasks)
            cross_pairs = self.candidate_svc.find_candidate_pairs(
                files_a=files,
                files_b=existing_files,
                language=language,
                deduplicate=False
            )

            all_pairs = intra_pairs + cross_pairs
            total_pairs = len(all_pairs)

            logger.info(f"[Task {task_id}] Total candidate pairs: {total_pairs}")

            if total_pairs == 0:
                self.result_svc.finalize_task(task_id, 0, 0)
                return

            # Phase 3: Store similarity percentages (quick fingerprint overlap)
            self.repository.update_task(
                task_id=task_id,
                status="processing",
                total_pairs=total_pairs,
                processed_pairs=0
            )

            self.result_svc.store_similarity_scores(task_id, all_pairs)

            # Note: Full AST analysis is NOT done synchronously in this implementation.
            # The system only calculates fingerprint overlap similarity.
            # For full AST analysis, additional processing would be needed.

            # Phase 4: Complete
            self.result_svc.finalize_task(task_id, total_pairs, total_pairs)

            logger.info(f"[Task {task_id}] COMPLETED successfully")

        except Exception as e:
            logger.exception(f"[Task {task_id}] FAILED")
            self.result_svc.mark_failed(task_id, str(e))
            raise
