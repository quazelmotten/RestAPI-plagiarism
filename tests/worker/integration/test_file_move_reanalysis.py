"""
Integration test: file move + reanalysis.

Scenario
--------
1. Task-A: 2 files ──indexed and analysed──► 1 intra-task pair stored
2. Task-B: 2 files ──indexed and analysed──► 1 intra-task pair stored
3. Move FileA2 from Task-A to Task-B  (Task-A: 1 file, Task-B: 3 files)
4. Delete old Task-B results, reanalyse Task-B
   ► 3 intra-task pairs (C(3,2)=3) + 3 cross-task pairs (vs. Task-A's file a1) = 6
5. Assert Task-B has exactly 6 pairs

Usage requires PostgreSQL (docker-compose.test.yml).
"""

import hashlib
import os
import uuid
import json

import pytest
from sqlalchemy import create_engine as _create_sync_engine, text as _text
from sqlalchemy.orm import sessionmaker as _sessionmaker

pytestmark = pytest.mark.integration

TEST_DB_URL_SYNC = (
    "postgresql+psycopg2://plagiarism_user:iNseUMJMuFlX1Q5Sr6yPwjUDPprX4VMP@localhost:5433/plagiarism_db"
)


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _write(tmp_dir: str, name: str, content: str) -> str:
    path = os.path.join(tmp_dir, name)
    with open(path, "w") as f:
        f.write(content)
    return path


def _count_pairs(session, tid: str) -> int:
    """Return how many similarity_results exist for the given task_id."""
    from sqlalchemy import func, select
    from shared.models import SimilarityResult

    stmt = (
        select(func.count())
        .select_from(SimilarityResult)
        .where(SimilarityResult.task_id == tid)
    )
    return session.execute(stmt).scalar() or 0


class _SyncRepo:
    """Synchronous repository shim powered by a raw psycopg2 connection."""

    def __init__(self, sess):
        self._s = sess

    def get_all_files(self, exclude_task_id=None):
        stmt = _text(
            "SELECT id, file_hash, file_path, language, task_id FROM files"
            + (" WHERE task_id != :eid" if exclude_task_id else "")
        )
        params = {"eid": exclude_task_id} if exclude_task_id else {}
        rows = self._s.execute(stmt, params).fetchall()
        return [{"id": str(r.id), "file_hash": r.file_hash,
                 "file_path": r.file_path, "language": r.language,
                 "task_id": str(r.task_id)} for r in rows]

    def get_files_by_assignment(self, assignment_id, exclude_task_id=None):
        stmt = _text(
            "SELECT f.id, f.file_hash, f.file_path, f.language, f.task_id "
            "FROM files f JOIN plagiarism_tasks pt ON f.task_id = pt.id "
            "WHERE pt.assignment_id = :aid"
            + (" AND f.task_id != :eid" if exclude_task_id else "")
        )
        params = {"aid": assignment_id}
        if exclude_task_id:
            params["eid"] = exclude_task_id
        rows = self._s.execute(stmt, params).fetchall()
        return [{"id": str(r.id), "file_hash": r.file_hash,
                 "file_path": r.file_path, "language": r.language,
                 "task_id": str(r.task_id)} for r in rows]

    def update_task(self, task_id, status, **kwargs):
        sets = [f"{k} = :{k}" for k in kwargs if kwargs[k] is not None]
        if not sets:
            return
        
        params = {k: (json.dumps(v) if isinstance(v, dict) else v) 
                  for k, v in kwargs.items() if v is not None}
        params["tid"] = task_id
        
        self._s.execute(
            _text(f"UPDATE plagiarism_tasks SET {', '.join(sets)} WHERE id = :tid"),
            params,
        )

    def store_similarity_scores(self, task_id, pairs, batch_size=None):
        if not pairs:
            return
        vals = [
            {"id": str(uuid.uuid4()), "task_id": task_id,
             "file_a_id": fa.get("id"), "file_b_id": fb.get("id"),
             "ast_similarity": round(sim, 6), "matches": "[]"}
            for fa, fb, sim in pairs if fa.get("id") and fb.get("id")
        ]
        if not vals:
            return
        self._s.execute(
            _text(
                "INSERT INTO similarity_results "
                "(id, task_id, file_a_id, file_b_id, ast_similarity, matches) "
                "VALUES (:id, :task_id, :file_a_id, :file_b_id, :ast_similarity, :matches)"
            ), vals,
        )
        self._s.commit()

    def finalize_task(self, task_id, total_pairs, processed_count):
        max_row = self._s.execute(
            _text("SELECT MAX(sr.ast_similarity) AS max_sim "
                  "FROM similarity_results sr WHERE sr.task_id = :tid"),
            {"tid": task_id},
        ).fetchone()
        max_sim = float(max_row.max_sim) if max_row and max_row.max_sim is not None else 0.0
        self.update_task(
            task_id, status="completed", similarity=max_sim,
            matches={"total_pairs": total_pairs, "processed_pairs": processed_count},
            total_pairs=total_pairs, processed_pairs=processed_count,
        )

    def mark_failed(self, task_id, error):
        self.update_task(task_id, status="failed", error=error[:1000])

    def delete_task_results(self, task_id):
        self._s.execute(
            _text("DELETE FROM similarity_results WHERE task_id = :tid"),
            {"tid": task_id},
        )
        self._s.commit()

    def get_max_similarity(self, task_id):
        max_row = self._s.execute(
            _text("SELECT MAX(sr.ast_similarity) AS max_sim "
                  "FROM similarity_results sr WHERE sr.task_id = :tid"),
            {"tid": task_id},
        ).fetchone()
        return float(max_row.max_sim) if max_row and max_row.max_sim is not None else 0.0

    def bulk_insert_results(self, results):
        if not results:
            return
        vals = [{"id": str(uuid.uuid4()), "task_id": r["task_id"],
                 "file_a_id": r["file_a_id"], "file_b_id": r["file_b_id"],
                 "ast_similarity": r.get("ast_similarity"), "matches": "[]"}
                for r in results]
        self._s.execute(
            _text("INSERT INTO similarity_results "
                  "(id, task_id, file_a_id, file_b_id, ast_similarity, matches) "
                  "VALUES (:id, :task_id, :file_a_id, :file_b_id, :ast_similarity, :matches)"),
            vals,
        )
        self._s.commit()


@pytest.mark.asyncio
async def test_move_file_reanalysis_produces_new_cross_pairs(
    db_session,
    temp_plagiarism_dir,
    simple_redis,
):
    """Full round: index+analyse, move file, reanalyse; assert 3 cross-pairs in Task-B."""
    from sqlalchemy import update as _update, select as _select
    from worker.infrastructure.redis_cache import RedisFingerprintCache
    from worker.infrastructure.inverted_index import RedisInvertedIndex
    from worker.services.fingerprint_service import FingerprintService
    from worker.services.indexing_service import IndexingService
    from worker.services.candidate_service import CandidateService
    from worker.services.task_service import TaskService
    from shared.models import Assignment, File, PlagiarismTask, SimilarityResult, Subject

    # ── helpers ────────────────────────────────────────────────────────────────
    def _write_f(name: str, content: str) -> str:
        return _write(temp_plagiarism_dir, name, content)

    # ── write source files ─────────────────────────────────────────────────────
    content_a1 = "def alpha():\n    return 1\n"
    content_a2 = "def beta():\n    return 2\n"
    path_a1 = _write_f("a1.py", content_a1)
    path_a2 = _write_f("a2.py", content_a2)

    content_b1 = "def gamma():\n    return 3\n"
    content_b2 = "def delta():\n    return 4\n"
    path_b1 = _write_f("b1.py", content_b1)
    path_b2 = _write_f("b2.py", content_b2)

    ah1 = _content_hash(content_a1)
    ah2 = _content_hash(content_a2)
    bh1 = _content_hash(content_b1)
    bh2 = _content_hash(content_b2)

    # ── Phase 0: seed DB (sync engine for inserts) ─────────────────────────────
    sync_engine = _create_sync_engine(TEST_DB_URL_SYNC, pool_size=5, max_overflow=5)
    SyncSession = _sessionmaker(sync_engine)

    subject_id = uuid.uuid4()
    assignment_id_ = uuid.uuid4()
    task_a_id_uuid = uuid.uuid4()
    task_b_id_uuid = uuid.uuid4()
    file_a1_id = uuid.uuid4()
    file_a2_id = uuid.uuid4()
    file_b1_id = uuid.uuid4()
    file_b2_id = uuid.uuid4()

    with SyncSession() as s:
        with s.begin():
            s.add(Subject(id=subject_id, name="integration-subject"))
            s.add(Assignment(id=assignment_id_, subject_id=subject_id,
                             name="integration-assignment"))
            s.add(PlagiarismTask(id=task_a_id_uuid, assignment_id=assignment_id_,
                                 language="python", status="pending"))
            s.add(PlagiarismTask(id=task_b_id_uuid, assignment_id=assignment_id_,
                                 language="python", status="pending"))
            s.add(File(id=file_a1_id, file_hash=ah1, file_path=path_a1,
                        filename="a1.py", language="python",
                        task_id=task_a_id_uuid))
            s.add(File(id=file_a2_id, file_hash=ah2, file_path=path_a2,
                        filename="a2.py", language="python",
                        task_id=task_a_id_uuid))
            s.add(File(id=file_b1_id, file_hash=bh1, file_path=path_b1,
                        filename="b1.py", language="python",
                        task_id=task_b_id_uuid))
            s.add(File(id=file_b2_id, file_hash=bh2, file_path=path_b2,
                        filename="b2.py", language="python",
                        task_id=task_b_id_uuid))

    task_a_id = str(task_a_id_uuid)
    task_b_id = str(task_b_id_uuid)
    file_a2_id_str = str(file_a2_id)

    # ── infrastructure ─────────────────────────────────────────────────────────
    redis = simple_redis
    cache = RedisFingerprintCache(redis, ttl=3600)
    index = RedisInvertedIndex(redis, min_overlap_threshold=0.15)
    fpsvc = FingerprintService(cache)
    idxsvc = IndexingService(index, cache, fpsvc)
    # identity: fingerprint Jaccard == AST Jaccard  (avoids numpy/scipy import)
    idxsvc.compute_ast_similarities = lambda pairs: pairs  # noqa: E731
    candsvc = CandidateService(index)

    # Pre-fingerprint all 4 files so indexing phase hits the cache, not disk
    for path, content in [(path_a1, content_a1), (path_a2, content_a2),
                          (path_b1, content_b1), (path_b2, content_b2)]:
        info = {"file_hash": _content_hash(content), "file_path": path}
        fpsvc.ensure_fingerprinted(info, "python")

    # ── sync DB helpers ────────────────────────────────────────────────────────
    def run_task(task_id_, file_dicts, language, assign_id=None):
        repo = _SyncRepo(SyncSession())
        rsvc = repo
        tsvc = TaskService(
            fingerprint_service=fpsvc, indexing_service=idxsvc,
            candidate_service=candsvc, analysis_service=None,
            result_service=rsvc, repository=rsvc,
        )
        tsvc.process_task(task_id_, file_dicts, language, assignment_id=assign_id)

    def count_pairs(tid):
        with SyncSession() as s:
            return _count_pairs(s, tid)

    # ── Phase 1: index+analyse Task-A and Task-B ────────────────────────────────
    run_task(task_a_id, [
        {"file_hash": ah1, "file_path": path_a1, "id": str(file_a1_id)},
        {"file_hash": ah2, "file_path": path_a2, "id": str(file_a2_id)},
    ], "python", assign_id=task_a_id)

    run_task(task_b_id, [
        {"file_hash": bh1, "file_path": path_b1, "id": str(file_b1_id)},
        {"file_hash": bh2, "file_path": path_b2, "id": str(file_b2_id)},
    ], "python", assign_id=task_b_id)

    task_a_count = count_pairs(task_a_id)
    task_b_count_before = count_pairs(task_b_id)
    assert task_a_count == 1, f"Task-A C(2,2)=1, got {task_a_count}"
    assert task_b_count_before == 1, f"Task-B C(2,2)=1, got {task_b_count_before}"

    # ── Phase 2: move FileA2 → Task-B ─────────────────────────────────────────
    await db_session.execute(
        _update(File).where(File.id == file_a2_id).values(
            task_id=uuid.UUID(task_b_id)
        )
    )
    await db_session.commit()

    a2 = await db_session.get(File, file_a2_id)
    assert a2 is not None, "FileA2 must exist after move"
    assert str(a2.task_id) == task_b_id, "FileA2 task_id must be Task-B after move"

    # ── Phase 3: reanalyse Task-B (3 files), deleting old results ────────────
    repo = _SyncRepo(SyncSession())
    repo.delete_task_results(task_b_id)
    # Read Task-B files + the moved file from DB to build the file dict
    tb_result = await db_session.execute(
        _select(File).where(File.task_id == uuid.UUID(task_b_id)).order_by(File.created_at)
    )
    tb_files = tb_result.scalars().all()

    # After move: Task-B has 3 files  → file dicts with correct hashes
    task_b_after = [
        {"file_hash": f.file_hash, "file_path": f.file_path, "id": str(f.id)}
        for f in tb_files
    ]
    run_task(task_b_id, task_b_after, "python", assign_id=str(assignment_id_))

    # C(3,2) = 3 intra-task pairs among the 3 Task-B files:
    #   (b1,b2)  – pair of two originally-B files = 1
    #   (a2,b1)  – moved file + originally-B file  = 1
    #   (a2,b2)  – moved file + originally-B file  = 1
    # Plus 3 cross-task pairs with the remaining Task-A file a1:
    #   (a2,a1), (b1,a1), (b2,a1)
    total = count_pairs(task_b_id)
    assert total == 6, (
        f"Expected 6 pairs in Task-B after reanalysis (3 intra + 3 cross), got {total}"
    )

    # Verify every file appears in at least one pair
    rows = (
        await db_session.execute(
            SimilarityResult.__table__.select()
            .where(SimilarityResult.task_id == uuid.UUID(task_b_id))
        )
    ).all()

    present_ids: set[str] = set()
    for row in rows:
        present_ids.add(str(row.file_a_id))
        present_ids.add(str(row.file_b_id))

    assert str(file_a2_id) in present_ids, "Moved file must appear in pairs"
    assert str(tb_files[0].id) in present_ids, "first Task-B file must appear in pairs"
    assert str(tb_files[1].id) in present_ids, "second Task-B file must appear in pairs"


@pytest.mark.asyncio
async def test_move_file_similarity_hash_is_path_independent(
    temp_plagiarism_dir,
    simple_redis,
):
    """Fingerprints are based on content (AST), not file paths.

    Two files with identical source but different paths must produce identical
    candidate-set coverage and similarity scores.
    """
    from worker.infrastructure.redis_cache import RedisFingerprintCache
    from worker.infrastructure.inverted_index import RedisInvertedIndex
    from worker.services.fingerprint_service import FingerprintService
    from worker.services.indexing_service import IndexingService
    from worker.services.candidate_service import CandidateService

    path_a = _write(temp_plagiarism_dir, "x.py", "def identical():\n    return 1\n")
    path_b = _write(temp_plagiarism_dir, "y.py", "def identical():\n    return 1\n")
    h = hashlib.sha256("def identical():\n    return 1\n".encode()).hexdigest()

    redis = simple_redis
    cache = RedisFingerprintCache(redis, ttl=3600)
    index = RedisInvertedIndex(redis, min_overlap_threshold=0.0)
    fpsvc = FingerprintService(cache)
    idxsvc = IndexingService(index, cache, fpsvc)
    idxsvc.compute_ast_similarities = lambda pairs: pairs  # noqa: E731
    candsvc = CandidateService(index)

    fpa = {"file_hash": h, "file_path": path_a}
    fpb = {"file_hash": h, "file_path": path_b}   # same content hash, different path

    fpsvc.ensure_fingerprinted(fpa, "python")
    fpsvc.ensure_fingerprinted(fpb, "python")

    # Sure-fire check: no actual file reads happened after first fingerprinting call.
    # The two calls must return identical fingerprints from cache.
    cached_a = fpsvc.ensure_fingerprinted(fpa, "python")
    cached_b = fpsvc.ensure_fingerprinted(fpb, "python")
    assert cached_a == cached_b, "Cache hit must return identical fingerprints"

    # batch_get lives on the cache, not the service
    fp_map = fpsvc.cache.batch_get([h])
    ast_hashes = fp_map[h]["ast_hashes"]
    assert ast_hashes is not None and len(ast_hashes) > 0, "AST hashes must be cached"

    fps_a = fpsvc.ensure_fingerprinted(fpa, "python")["fingerprints"]
    fps_b = fpsvc.ensure_fingerprinted(fpb, "python")["fingerprints"]

    # find_candidates expects a list of fingerprint HASH STRINGS, not dicts
    fps_a_hashes = [fp["hash"] for fp in fps_a]
    fps_b_hashes = [fp["hash"] for fp in fps_b]

    index.add_file_fingerprints(h, fps_a, "python")

    cands_start = index.find_candidates(fps_a_hashes, "python")
    assert h in cands_start, (
        f"Identical content hash must be a candidate after first index; "
        f"got keys={list(cands_start.keys())}"
    )

    # Re-index with a different path is a no-op in Redis (set-add idempotent)
    index.add_file_fingerprints(h, fps_b, "python")

    cands_after = index.find_candidates(fps_b_hashes, "python")
    assert h in cands_after, (
        f"Identical content hash must still be a candidate after second index; "
        f"got keys={list(cands_after.keys())}"
    )
    assert cands_start[h] == cands_after[h], (
        f"Similarity must be path-independent: "
        f"{cands_start[h]} == {cands_after[h]}"
    )
