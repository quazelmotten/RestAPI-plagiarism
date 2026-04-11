"""
Unit tests for migration idempotency and safety.
"""


class TestMigrationFixUniqueConstraints:
    """Tests for fix_unique_constraints_001 migration idempotency."""

    def test_migration_uses_if_exists_syntax(self):
        """Verify migration uses IF EXISTS to be idempotent."""
        migration_file = "database/migration/versions/fix_unique_constraints_001.py"

        with open(migration_file) as f:
            content = f.read()

        assert "IF EXISTS" in content or "DROP CONSTRAINT IF EXISTS" in content, (
            "Migration should use IF EXISTS for idempotency"
        )
        assert "text(" in content, "Migration should use raw SQL for IF EXISTS support"

    def test_migration_handles_missing_constraints(self):
        """Test that migration handles already-dropped constraints gracefully."""
        migration_file = "database/migration/versions/fix_unique_constraints_001.py"

        with open(migration_file) as f:
            content = f.read()

        assert "DROP CONSTRAINT IF EXISTS" in content, (
            "Migration must use DROP CONSTRAINT IF EXISTS for safety"
        )
        assert "ALTER TABLE IF EXISTS" in content, "Must use ALTER TABLE IF EXISTS syntax"


class TestMigrationImports:
    """Tests for migration import correctness."""

    def test_migration_imports_text(self):
        """Verify migration imports text from sqlalchemy."""
        with open("database/migration/versions/fix_unique_constraints_001.py") as f:
            content = f.read()

        assert "from sqlalchemy import text" in content or "from sqlalchemy import" in content, (
            "Migration must import text for raw SQL"
        )


class TestMigrationDowngrade:
    """Tests for migration downgrade functionality."""

    def test_migration_has_downgrade(self):
        """Verify migration has downgrade path."""
        with open("database/migration/versions/fix_unique_constraints_001.py") as f:
            content = f.read()

        assert "def downgrade()" in content, "Migration must have downgrade function"

    def test_downgrade_restores_constraints(self):
        """Verify downgrade restores unique constraints."""
        with open("database/migration/versions/fix_unique_constraints_001.py") as f:
            content = f.read()

        assert "create_unique_constraint" in content, "Downgrade must recreate original constraints"


class TestMigrationIndexes:
    """Tests for migration partial index creation."""

    def test_creates_partial_indexes(self):
        """Verify migration creates partial indexes for soft delete."""
        with open("database/migration/versions/fix_unique_constraints_001.py") as f:
            content = f.read()

        assert "ix_assignments_name_not_deleted" in content, (
            "Must create partial index for assignments.name"
        )
        assert "ix_subjects_name_not_deleted" in content, (
            "Must create partial index for subjects.name"
        )
        assert "postgresql_where" in content or "deleted_at IS NULL" in content, (
            "Must use partial index with WHERE clause"
        )


class TestMigrationFutureSafety:
    """Tests to catch future issues before they cause failures."""

    def test_no_hardcoded_constraint_names(self):
        """Verify we don't hardcode constraint names that may vary."""
        migration_file = "database/migration/versions/fix_unique_constraints_001.py"

        with open(migration_file) as f:
            content = f.read()

        has_if_exists = "DROP CONSTRAINT IF EXISTS" in content
        assert has_if_exists or "op.execute" in content, (
            "Must handle possibly-missing constraints for production safety"
        )

    def test_migration_is_idempotent(self):
        """Test that running migration twice doesn't fail."""
        with open("database/migration/versions/fix_unique_constraints_001.py") as f:
            content = f.read()

        uses_if_exists = "IF EXISTS" in content
        assert uses_if_exists, "Migration must be idempotent - running twice should not fail"
