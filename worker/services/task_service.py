"""
Task service - orchestrates the complete plagiarism analysis task.

Coordinates:
1. File fingerprinting & indexing
2. Candidate pair generation  
3. Detailed AST analysis
4. Result persistence
"""

import logging
import time
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
        total_files = len(files)
        logger.info(f"[Task {task_id}] Starting task with {total_files} files")
        task_start = time.perf_counter()

        try:
            # Phase 1: Index all files
            phase_start = time.perf_counter()
            self.repository.update_task(
                task_id=task_id,
                status="indexing",
                processed_pairs=0,
                total_pairs=total_files
            )

            existing_files = self.repository.get_all_files(exclude_task_id=task_id)
            logger.info(f"[Task {task_id}] Phase 1: Indexing {total_files} files "
                        f"({len(existing_files)} existing files in database)")

            def on_index_progress(processed: int, total: int) -> None:
                self.repository.update_task(
                    task_id=task_id,
                    status="indexing",
                    processed_pairs=processed,
                    total_pairs=total
                )

            fingerprint_map = self.indexing_svc.ensure_files_indexed(
                files=files,
                language=language,
                existing_files=existing_files,
                on_progress=on_index_progress,
            )

            phase_elapsed = time.perf_counter() - phase_start
            phase_speed = total_files / phase_elapsed if phase_elapsed > 0 else 0
            logger.info(f"[Task {task_id}] Phase 1 COMPLETE: indexed {total_files} files "
                        f"in {phase_elapsed:.2f}s ({phase_speed:.1f} files/sec)")

            # Phase 2a: Find intra-task pairs
            phase_start = time.perf_counter()
            self.repository.update_task(
                task_id=task_id,
                status="finding_intra_pairs",
                processed_pairs=0,
                total_pairs=total_files
            )

            logger.info(f"[Task {task_id}] Phase 2a: Finding intra-task pairs ({total_files} files)")

            def on_intra_progress(processed: int, total: int) -> None:
                self.repository.update_task(
                    task_id=task_id,
                    status="finding_intra_pairs",
                    processed_pairs=processed,
                    total_pairs=total
                )

            intra_pairs = self.candidate_svc.find_candidate_pairs(
                files_a=files,
                language=language,
                deduplicate=True,
                on_progress=on_intra_progress,
            )

            intra_elapsed = time.perf_counter() - phase_start
            logger.info(f"[Task {task_id}] Phase 2a COMPLETE: found {len(intra_pairs)} intra pairs "
                        f"in {intra_elapsed:.2f}s")

            # Phase 2b: Find cross-task pairs
            self.repository.update_task(
                task_id=task_id,
                status="finding_cross_pairs",
                processed_pairs=0,
                total_pairs=total_files
            )

            logger.info(f"[Task {task_id}] Phase 2b: Finding cross-task pairs "
                        f"({total_files} new vs {len(existing_files)} existing)")

            def on_cross_progress(processed: int, total: int) -> None:
                self.repository.update_task(
                    task_id=task_id,
                    status="finding_cross_pairs",
                    processed_pairs=processed,
                    total_pairs=total
                )

            cross_pairs = self.candidate_svc.find_candidate_pairs(
                files_a=files,
                files_b=existing_files,
                language=language,
                deduplicate=False,
                on_progress=on_cross_progress,
            )

            phase_elapsed = time.perf_counter() - phase_start
            cross_elapsed = time.perf_counter() - phase_start
            all_pairs = intra_pairs + cross_pairs
            total_pairs = len(all_pairs)

            logger.info(f"[Task {task_id}] Phase 2b COMPLETE: found {len(cross_pairs)} cross pairs "
                        f"in {cross_elapsed:.2f}s")

            if total_pairs == 0:
                self.result_svc.finalize_task(task_id, 0, 0)
                return

            # Phase 3: Store similarity percentages
            phase_start = time.perf_counter()
            self.repository.update_task(
                task_id=task_id,
                status="storing_results",
                total_pairs=total_pairs,
                processed_pairs=0
            )

            logger.info(f"[Task {task_id}] Phase 3: Storing {total_pairs} similarity results")

            self.result_svc.store_similarity_scores(task_id, all_pairs)

            phase_elapsed = time.perf_counter() - phase_start
            phase_speed = total_pairs / phase_elapsed if phase_elapsed > 0 else 0
            logger.info(f"[Task {task_id}] Phase 3 COMPLETE: stored {total_pairs} results "
                        f"in {phase_elapsed:.2f}s ({phase_speed:.1f} results/sec)")

            # Phase 4: Complete
            self.result_svc.finalize_task(task_id, total_pairs, total_pairs)

            total_elapsed = time.perf_counter() - task_start
            overall_speed = total_pairs / total_elapsed if total_elapsed > 0 else 0
            logger.info(f"[Task {task_id}] COMPLETED successfully in {total_elapsed:.2f}s "
                        f"({total_files} files, {total_pairs} pairs, {overall_speed:.1f} pairs/sec overall)")

        except Exception as e:
            logger.exception(f"[Task {task_id}] FAILED")
            self.result_svc.mark_failed(task_id, str(e))
            raise
