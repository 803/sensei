"""Tests for database operations."""

import hashlib
from uuid import UUID

import pytest

from sensei.database import storage
from sensei.types import Rating, SaveResult


@pytest.mark.asyncio
async def test_save_query(test_db):
	"""Test saving a query."""
	query = "How do I use FastAPI?"
	markdown = "# FastAPI Usage\n\nHere's how..."

	query_id = await storage.save_query(query=query, output=markdown)

	# Retrieve and verify
	retrieved = await storage.get_query(query_id)
	assert retrieved is not None
	assert retrieved.id == query_id
	assert retrieved.query == query
	assert retrieved.output == markdown


@pytest.mark.asyncio
async def test_save_query_with_messages(test_db):
	"""Test saving a query with messages."""
	query = "What is Python?"
	markdown = "# Python\n\nPython is..."
	messages = b'[{"role": "user", "content": "test"}]'

	query_id = await storage.save_query(query=query, output=markdown, messages=messages)

	retrieved = await storage.get_query(query_id)
	assert retrieved is not None
	assert retrieved.messages == '[{"role": "user", "content": "test"}]'


@pytest.mark.asyncio
async def test_save_rating(test_db):
	"""Test saving a rating."""
	# First create a query
	query_id = await storage.save_query(query="test query", output="test response")

	# Save a rating with all fields
	rating1 = Rating(
		query_id=query_id,
		correctness=5,
		relevance=4,
		usefulness=5,
		reasoning="Great response!",
		agent_model="model-x",
		agent_system="agent-y",
		agent_version="1.0",
	)
	await storage.save_rating(rating1)

	# Save another rating without optional fields
	rating2 = Rating(
		query_id=query_id,
		correctness=3,
		relevance=3,
		usefulness=2,
	)
	await storage.save_rating(rating2)


@pytest.mark.asyncio
async def test_get_query_not_found(test_db):
	"""Test retrieving a non-existent query."""
	fake_uuid = UUID("00000000-0000-0000-0000-000000000000")
	retrieved = await storage.get_query(fake_uuid)
	assert retrieved is None


@pytest.mark.asyncio
async def test_save_query_with_parent_and_depth(test_db):
	"""Test saving a sub-query with parent reference and depth."""
	# Create parent query
	parent_id = await storage.save_query(query="Main question?", output="Main answer")

	# Create child query
	child_id = await storage.save_query(
		query="Sub question?",
		output="Sub answer",
		parent_id=parent_id,
		depth=1,
	)

	# Verify child has correct parent and depth
	child = await storage.get_query(child_id)
	assert child is not None
	assert child.parent_id == parent_id
	assert child.depth == 1

	# Verify parent has no parent and depth 0
	parent = await storage.get_query(parent_id)
	assert parent is not None
	assert parent.parent_id is None
	assert parent.depth == 0


@pytest.mark.asyncio
async def test_search_queries(test_db):
	"""Test search queries using ILIKE."""
	# Insert test data
	await storage.save_query(query="How do React hooks work?", output="Answer 1", library="react", version="18")
	await storage.save_query(query="React component lifecycle", output="Answer 2", library="react")
	await storage.save_query(query="Python async await", output="Answer 3", library="python")

	# Search for "React"
	results = await storage.search_queries("React", limit=10)
	assert len(results) == 2

	# Search that matches nothing
	results = await storage.search_queries("nonexistent", limit=10)
	assert len(results) == 0


# =============================================================================
# Document Storage Tests
# =============================================================================


def _hash(content: str) -> str:
	"""Helper to compute content hash."""
	return hashlib.sha256(content.encode()).hexdigest()


@pytest.mark.asyncio
async def test_save_document_insert(test_db):
	"""Test inserting a new document."""
	content = "# React Hooks\n\nuseState is..."
	result = await storage.save_document(
		domain="react.dev",
		url="https://react.dev/docs/hooks/useState",
		path="/docs/hooks/useState",
		content=content,
		content_hash=_hash(content),
		depth=1,
	)

	assert result == SaveResult.INSERTED

	# Verify retrieval
	doc = await storage.get_document_by_url("https://react.dev/docs/hooks/useState")
	assert doc is not None
	assert doc.domain == "react.dev"
	assert doc.path == "/docs/hooks/useState"
	assert doc.content == content
	assert doc.depth == 1


@pytest.mark.asyncio
async def test_save_document_skip_unchanged(test_db):
	"""Test that unchanged documents are skipped."""
	content = "# Original content"
	content_hash = _hash(content)

	# First insert
	result1 = await storage.save_document(
		domain="example.com",
		url="https://example.com/doc",
		path="/doc",
		content=content,
		content_hash=content_hash,
		depth=0,
	)
	assert result1 == SaveResult.INSERTED

	# Same content, same hash - should skip
	result2 = await storage.save_document(
		domain="example.com",
		url="https://example.com/doc",
		path="/doc",
		content=content,
		content_hash=content_hash,
		depth=0,
	)
	assert result2 == SaveResult.SKIPPED


@pytest.mark.asyncio
async def test_save_document_update_changed(test_db):
	"""Test that changed documents are updated."""
	original_content = "# Version 1"
	updated_content = "# Version 2 with changes"

	# Insert original
	result1 = await storage.save_document(
		domain="example.com",
		url="https://example.com/doc",
		path="/doc",
		content=original_content,
		content_hash=_hash(original_content),
		depth=0,
	)
	assert result1 == SaveResult.INSERTED

	# Update with new content
	result2 = await storage.save_document(
		domain="example.com",
		url="https://example.com/doc",
		path="/doc",
		content=updated_content,
		content_hash=_hash(updated_content),
		depth=0,
	)
	assert result2 == SaveResult.UPDATED

	# Verify new content
	doc = await storage.get_document_by_url("https://example.com/doc")
	assert doc is not None
	assert doc.content == updated_content


@pytest.mark.asyncio
async def test_get_document_by_url_not_found(test_db):
	"""Test retrieving a non-existent document."""
	doc = await storage.get_document_by_url("https://nonexistent.com/doc")
	assert doc is None


@pytest.mark.asyncio
async def test_search_documents(test_db):
	"""Test searching documents by content."""
	# Insert test documents
	await storage.save_document(
		domain="react.dev",
		url="https://react.dev/hooks",
		path="/hooks",
		content="# React Hooks\n\nuseState lets you manage state",
		content_hash=_hash("hooks"),
		depth=0,
	)
	await storage.save_document(
		domain="react.dev",
		url="https://react.dev/components",
		path="/components",
		content="# React Components\n\nComponents are building blocks",
		content_hash=_hash("components"),
		depth=0,
	)
	await storage.save_document(
		domain="vue.js.org",
		url="https://vue.js.org/guide",
		path="/guide",
		content="# Vue Guide\n\nVue is a framework",
		content_hash=_hash("vue"),
		depth=0,
	)

	# Search all documents for "React"
	results = await storage.search_documents("React")
	assert len(results) == 2

	# Search with domain filter
	results = await storage.search_documents("React", domain="react.dev")
	assert len(results) == 2

	# Search for "Vue" with react domain - should find nothing
	results = await storage.search_documents("Vue", domain="react.dev")
	assert len(results) == 0

	# Search with limit
	results = await storage.search_documents("React", limit=1)
	assert len(results) == 1


@pytest.mark.asyncio
async def test_delete_documents_by_domain(test_db):
	"""Test deleting all documents for a domain."""
	# Insert documents for multiple domains
	await storage.save_document(
		domain="react.dev",
		url="https://react.dev/doc1",
		path="/doc1",
		content="React doc 1",
		content_hash=_hash("r1"),
		depth=0,
	)
	await storage.save_document(
		domain="react.dev",
		url="https://react.dev/doc2",
		path="/doc2",
		content="React doc 2",
		content_hash=_hash("r2"),
		depth=0,
	)
	await storage.save_document(
		domain="vue.js.org",
		url="https://vue.js.org/doc1",
		path="/doc1",
		content="Vue doc",
		content_hash=_hash("v1"),
		depth=0,
	)

	# Delete react.dev documents
	count = await storage.delete_documents_by_domain("react.dev")
	assert count == 2

	# Verify react.dev docs are gone
	doc1 = await storage.get_document_by_url("https://react.dev/doc1")
	doc2 = await storage.get_document_by_url("https://react.dev/doc2")
	assert doc1 is None
	assert doc2 is None

	# Verify vue.js.org doc still exists
	vue_doc = await storage.get_document_by_url("https://vue.js.org/doc1")
	assert vue_doc is not None


@pytest.mark.asyncio
async def test_delete_documents_by_domain_none_exist(test_db):
	"""Test deleting documents for a domain with no documents."""
	count = await storage.delete_documents_by_domain("nonexistent.com")
	assert count == 0


# =============================================================================
# Migration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_migration_schema_matches_models(test_db):
	"""Verify that migrations create the schema matching our models."""
	from sqlalchemy import inspect

	async with test_db.connect() as conn:
		# Get inspector in sync context
		def get_tables(connection):
			inspector = inspect(connection)
			return inspector.get_table_names()

		tables = await conn.run_sync(get_tables)

	# Check all expected tables exist
	expected_tables = {"queries", "ratings", "documents", "alembic_version"}
	assert set(tables) == expected_tables


@pytest.mark.asyncio
async def test_migration_queries_columns(test_db):
	"""Verify queries table has all expected columns."""
	from sqlalchemy import inspect

	async with test_db.connect() as conn:

		def get_columns(connection):
			inspector = inspect(connection)
			return {col["name"] for col in inspector.get_columns("queries")}

		columns = await conn.run_sync(get_columns)

	expected_columns = {
		"id",
		"query",
		"language",
		"library",
		"version",
		"output",
		"messages",
		"parent_id",
		"depth",
		"inserted_at",
		"updated_at",
	}
	assert columns == expected_columns


@pytest.mark.asyncio
async def test_migration_ratings_columns(test_db):
	"""Verify ratings table has all expected columns."""
	from sqlalchemy import inspect

	async with test_db.connect() as conn:

		def get_columns(connection):
			inspector = inspect(connection)
			return {col["name"] for col in inspector.get_columns("ratings")}

		columns = await conn.run_sync(get_columns)

	expected_columns = {
		"id",
		"query_id",
		"correctness",
		"relevance",
		"usefulness",
		"reasoning",
		"agent_model",
		"agent_system",
		"agent_version",
		"inserted_at",
		"updated_at",
	}
	assert columns == expected_columns


@pytest.mark.asyncio
async def test_migration_documents_columns(test_db):
	"""Verify documents table has all expected columns."""
	from sqlalchemy import inspect

	async with test_db.connect() as conn:

		def get_columns(connection):
			inspector = inspect(connection)
			return {col["name"] for col in inspector.get_columns("documents")}

		columns = await conn.run_sync(get_columns)

	expected_columns = {
		"id",
		"domain",
		"url",
		"path",
		"content",
		"content_hash",
		"content_refreshed_at",
		"depth",
		"inserted_at",
		"updated_at",
	}
	assert columns == expected_columns


@pytest.mark.asyncio
async def test_migration_documents_domain_index(test_db):
	"""Verify documents table has domain index."""
	from sqlalchemy import inspect

	async with test_db.connect() as conn:

		def get_indexes(connection):
			inspector = inspect(connection)
			return {idx["name"] for idx in inspector.get_indexes("documents")}

		indexes = await conn.run_sync(get_indexes)

	assert "ix_documents_domain" in indexes


@pytest.mark.asyncio
async def test_migration_ratings_check_constraints(test_db):
	"""Verify ratings constraints are enforced at both Pydantic and DB levels."""
	from pydantic import ValidationError

	query_id = await storage.save_query(query="test", output="test")

	# Pydantic validation catches invalid values before DB
	with pytest.raises(ValidationError):
		Rating(
			query_id=query_id,
			correctness=6,  # Invalid: must be <= 5
			relevance=3,
			usefulness=3,
		)

	with pytest.raises(ValidationError):
		Rating(
			query_id=query_id,
			correctness=0,  # Invalid: must be >= 1
			relevance=3,
			usefulness=3,
		)

	# Valid rating should work
	valid_rating = Rating(
		query_id=query_id,
		correctness=5,
		relevance=5,
		usefulness=5,
	)
	await storage.save_rating(valid_rating)  # Should not raise


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_save_query_with_all_optional_fields(test_db):
	"""Test saving a query with all optional fields populated."""
	query_id = await storage.save_query(
		query="How to use TypeScript generics?",
		output="# Generics\n\nGeneric types allow...",
		messages=b'[{"role": "assistant", "content": "Let me explain..."}]',
		language="typescript",
		library="typescript",
		version="5.0",
	)

	retrieved = await storage.get_query(query_id)
	assert retrieved is not None
	assert retrieved.language == "typescript"
	assert retrieved.library == "typescript"
	assert retrieved.version == "5.0"


@pytest.mark.asyncio
async def test_save_query_unicode_content(test_db):
	"""Test saving queries with unicode characters."""
	query = "Comment utiliser les hooks React? 你好 🚀"
	output = "# React Hooks\n\nLes hooks permettent... émojis: 🎉 汉字"

	query_id = await storage.save_query(query=query, output=output)

	retrieved = await storage.get_query(query_id)
	assert retrieved is not None
	assert retrieved.query == query
	assert retrieved.output == output


@pytest.mark.asyncio
async def test_save_document_unicode_content(test_db):
	"""Test saving documents with unicode content."""
	content = "# 日本語ドキュメント\n\nこれはテストです。Émojis: 🔥💡"
	result = await storage.save_document(
		domain="example.com",
		url="https://example.com/japanese",
		path="/japanese",
		content=content,
		content_hash=_hash(content),
		depth=0,
	)

	assert result == SaveResult.INSERTED
	doc = await storage.get_document_by_url("https://example.com/japanese")
	assert doc is not None
	assert doc.content == content


@pytest.mark.asyncio
async def test_search_queries_case_insensitive(test_db):
	"""Test that search is case insensitive."""
	await storage.save_query(query="How do REACT hooks work?", output="Answer")

	# Should find regardless of case
	results = await storage.search_queries("react")
	assert len(results) == 1

	results = await storage.search_queries("REACT")
	assert len(results) == 1

	results = await storage.search_queries("ReAcT")
	assert len(results) == 1


@pytest.mark.asyncio
async def test_search_queries_partial_match(test_db):
	"""Test that search matches partial terms."""
	await storage.save_query(query="Understanding useState in React", output="Answer")

	# Should match partial term
	results = await storage.search_queries("State")
	assert len(results) == 1

	results = await storage.search_queries("stand")
	assert len(results) == 1


@pytest.mark.asyncio
async def test_search_queries_respects_limit(test_db):
	"""Test that search limit is respected."""
	# Insert many queries
	for i in range(10):
		await storage.save_query(query=f"React question {i}", output=f"Answer {i}")

	# Verify limit works
	results = await storage.search_queries("React", limit=3)
	assert len(results) == 3

	results = await storage.search_queries("React", limit=5)
	assert len(results) == 5


@pytest.mark.asyncio
async def test_document_url_uniqueness(test_db):
	"""Test that document URLs are unique - updating replaces existing."""
	url = "https://unique.com/doc"
	content1 = "Version 1"
	content2 = "Version 2"

	# Insert first version
	result1 = await storage.save_document(
		domain="unique.com",
		url=url,
		path="/doc",
		content=content1,
		content_hash=_hash(content1),
		depth=0,
	)
	assert result1 == SaveResult.INSERTED

	# Update with second version (same URL)
	result2 = await storage.save_document(
		domain="unique.com",
		url=url,
		path="/doc",
		content=content2,
		content_hash=_hash(content2),
		depth=0,
	)
	assert result2 == SaveResult.UPDATED

	# Should only have one document
	doc = await storage.get_document_by_url(url)
	assert doc is not None
	assert doc.content == content2


@pytest.mark.asyncio
async def test_query_parent_child_chain(test_db):
	"""Test multi-level parent-child query chain."""
	# Create chain: root -> child1 -> grandchild
	root_id = await storage.save_query(query="Root query", output="Root answer", depth=0)

	child_id = await storage.save_query(
		query="Child query",
		output="Child answer",
		parent_id=root_id,
		depth=1,
	)

	grandchild_id = await storage.save_query(
		query="Grandchild query",
		output="Grandchild answer",
		parent_id=child_id,
		depth=2,
	)

	# Verify chain
	root = await storage.get_query(root_id)
	child = await storage.get_query(child_id)
	grandchild = await storage.get_query(grandchild_id)

	assert root.parent_id is None
	assert root.depth == 0

	assert child.parent_id == root_id
	assert child.depth == 1

	assert grandchild.parent_id == child_id
	assert grandchild.depth == 2


@pytest.mark.asyncio
async def test_save_rating_foreign_key_constraint(test_db):
	"""Test that rating requires valid query_id."""
	import sqlalchemy.exc

	fake_query_id = UUID("11111111-1111-1111-1111-111111111111")

	# Should fail due to foreign key constraint
	rating = Rating(
		query_id=fake_query_id,
		correctness=3,
		relevance=3,
		usefulness=3,
	)

	with pytest.raises(sqlalchemy.exc.IntegrityError):
		await storage.save_rating(rating)


@pytest.mark.asyncio
async def test_large_content_storage(test_db):
	"""Test storing large content."""
	# Create a large document (~100KB)
	large_content = "# Large Document\n\n" + ("Lorem ipsum dolor sit amet. " * 5000)

	result = await storage.save_document(
		domain="large.com",
		url="https://large.com/big-doc",
		path="/big-doc",
		content=large_content,
		content_hash=_hash(large_content),
		depth=0,
	)

	assert result == SaveResult.INSERTED

	doc = await storage.get_document_by_url("https://large.com/big-doc")
	assert doc is not None
	assert len(doc.content) == len(large_content)
	assert doc.content == large_content
