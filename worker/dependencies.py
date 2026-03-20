"""
Dependency Injection composition root.

Factory functions for creating service instances with proper dependencies.
Uses singleton patterns for shared resources (Redis client, etc.).
"""

import logging
from functools import lru_cache

import redis

from worker.config import settings as worker_settings
from shared.interfaces import (
    FingerprintCache,
    CandidateIndex,
    TaskRepository,
    LockManager
)
from worker.infrastructure.redis_cache import RedisFingerprintCache
from worker.infrastructure.inverted_index import RedisInvertedIndex
from worker.infrastructure.lock_manager import RedisLockManager
from worker.infrastructure.postgres_repository import PostgresRepository
from plagiarism_core.analyzer import Analyzer as CoreAnalyzer

logger = logging.getLogger(__name__)


@lru_cache()
def get_redis_client() -> redis.Redis:
    """Get or create singleton Redis client."""
    client = redis.Redis(
        host=worker_settings.redis_host,
        port=worker_settings.redis_port,
        db=worker_settings.redis_db,
        password=worker_settings.redis_password,
        ssl=worker_settings.redis_use_ssl,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        health_check_interval=30,
    )
    logger.info(f"Redis client initialized for {worker_settings.redis_host}:{worker_settings.redis_port}")
    return client


@lru_cache()
def get_cache() -> FingerprintCache:
    """Get or create singleton fingerprint cache."""
    client = get_redis_client()
    cache = RedisFingerprintCache(client, ttl=worker_settings.redis_ttl)
    logger.info("Fingerprint cache initialized")
    return cache


@lru_cache()
def get_index() -> CandidateIndex:
    """Get or create singleton inverted index."""
    client = get_redis_client()
    index = RedisInvertedIndex(
        client,
        min_overlap_threshold=worker_settings.inverted_index_min_overlap_threshold
    )
    logger.info("Inverted index initialized")
    return index


@lru_cache()
def get_lock_manager() -> LockManager:
    """Get or create singleton lock manager."""
    client = get_redis_client()
    lock_mgr = RedisLockManager(client)
    logger.info("Lock manager initialized")
    return lock_mgr


@lru_cache()
def get_repository() -> TaskRepository:
    """Get or create singleton task repository."""
    from worker.database import engine
    # Ensure models are created
    from worker.models import Base
    Base.metadata.create_all(bind=engine)

    repo = PostgresRepository()
    logger.info("Task repository initialized")
    return repo


@lru_cache()
def get_analyzer() -> CoreAnalyzer:
    """Get or create singleton core analyzer."""
    analyzer = CoreAnalyzer(ast_threshold=0.15)
    logger.info("Core analyzer initialized")
    return analyzer


def get_fingerprint_service() -> 'FingerprintService':
    """Create fingerprint service with dependencies."""
    from worker.services.fingerprint_service import FingerprintService
    cache = get_cache()
    return FingerprintService(cache)


def get_indexing_service() -> 'IndexingService':
    """Create indexing service with dependencies."""
    from worker.services.indexing_service import IndexingService
    cache = get_cache()
    index = get_index()
    fingerprint_svc = get_fingerprint_service()
    return IndexingService(index, cache, fingerprint_svc)


def get_candidate_service() -> 'CandidateService':
    """Create candidate service with dependencies."""
    from worker.services.candidate_service import CandidateService
    index = get_index()
    return CandidateService(index)


def get_analysis_service() -> 'AnalysisService':
    """Create analysis service with dependencies."""
    from worker.services.analysis_service import AnalysisService
    cache = get_cache()
    return AnalysisService(cache)


def get_result_service() -> 'ResultService':
    """Create result service with dependencies."""
    from worker.services.result_service_new import ResultService
    repository = get_repository()
    return ResultService(repository)


def get_task_service() -> 'TaskService':
    """
    Create the main task service (orchestrator) with all dependencies.

    This is the composition root that wires everything together.
    """
    from worker.services.task_service import TaskService

    fingerprint_svc = get_fingerprint_service()
    indexing_svc = get_indexing_service()
    candidate_svc = get_candidate_service()
    analysis_svc = get_analysis_service()
    result_svc = get_result_service()
    repository = get_repository()

    task_service = TaskService(
        fingerprint_service=fingerprint_svc,
        indexing_service=indexing_svc,
        candidate_service=candidate_svc,
        analysis_service=analysis_svc,
        result_service=result_svc,
        repository=repository
    )

    logger.info("Task service initialized with all dependencies")
    return task_service
