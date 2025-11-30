"""Database operations for Sensei using SQLAlchemy with async PostgreSQL."""

import logging
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sensei.config import settings
from sensei.database.models import Document, Query
from sensei.database.models import Rating as RatingModel
from sensei.types import CacheHit, Rating, SaveResult

logger = logging.getLogger(__name__)

# Lazy-initialized engine and session factory
_engine = None
_async_session_local = None


def _get_engine():
	"""Get or create the async engine (lazy initialization)."""
	global _engine
	if _engine is None:
		_engine = create_async_engine(
			settings.database_url,
			echo=False,
			future=True,
		)
	return _engine


def _get_session_factory():
	"""Get or create the async session factory (lazy initialization)."""
	global _async_session_local
	if _async_session_local is None:
		_async_session_local = async_sessionmaker(
			_get_engine(),
			class_=AsyncSession,
			expire_on_commit=False,
		)
	return _async_session_local


def AsyncSessionLocal():
	"""Get a session from the lazy-initialized factory."""
	return _get_session_factory()()


async def save_query(
	query: str,
	output: str,
	messages: bytes | None = None,
	language: Optional[str] = None,
	library: Optional[str] = None,
	version: Optional[str] = None,
	parent_id: Optional[UUID] = None,
	depth: int = 0,
) -> UUID:
	"""Save a query and its response to the database.

	Args:
	    query: The user's query string
	    output: The final text output from the agent
	    messages: JSON bytes of all intermediate messages (from result.new_messages_json())
	    language: Optional programming language filter
	    library: Optional library/framework name
	    version: Optional version specification
	    parent_id: Optional parent query ID for sub-queries
	    depth: Recursion depth (0 = top-level)

	Returns:
	    The generated UUID for the saved query
	"""
	logger.info(f"Saving query to database: parent={parent_id}, depth={depth}")
	async with AsyncSessionLocal() as session:
		query_record = Query(
			query=query,
			language=language,
			library=library,
			version=version,
			output=output,
			messages=messages.decode("utf-8") if messages else None,
			parent_id=parent_id,
			depth=depth,
		)
		session.add(query_record)
		await session.commit()
		await session.refresh(query_record)
		logger.debug(f"Query saved: id={query_record.id}, depth={depth}")
		return query_record.id


async def save_rating(rating: Rating) -> None:
	"""Save a rating for a query response."""
	logger.info(f"Saving rating to database: query_id={rating.query_id}")
	async with AsyncSessionLocal() as session:
		rating_record = RatingModel(
			query_id=rating.query_id,
			correctness=rating.correctness,
			relevance=rating.relevance,
			usefulness=rating.usefulness,
			reasoning=rating.reasoning,
			agent_model=rating.agent_model,
			agent_system=rating.agent_system,
			agent_version=rating.agent_version,
		)
		session.add(rating_record)
		await session.commit()
	logger.debug(
		f"Rating saved: query_id={rating.query_id}, scores=({rating.correctness}, {rating.relevance}, {rating.usefulness})"
	)


async def get_query(id: UUID) -> Optional[Query]:
	"""Retrieve a query by its ID.

	Args:
	    id: The query ID to retrieve

	Returns:
	    Query object if found, None otherwise
	"""
	async with AsyncSessionLocal() as session:
		result = await session.execute(select(Query).where(Query.id == id))
		return result.scalar_one_or_none()


async def search_queries(
	search_term: str,
	limit: int = 10,
) -> list[CacheHit]:
	"""Search cached queries using ILIKE.

	Args:
	    search_term: The search term for text search
	    limit: Maximum results to return

	Returns:
	    List of CacheHit objects
	"""
	logger.debug(f"Search: term={search_term}")

	async with AsyncSessionLocal() as session:
		params: dict = {"pattern": f"%{search_term}%", "limit": limit}

		sql = """
            SELECT id, query, library, version, inserted_at
            FROM queries
            WHERE query ILIKE :pattern
            LIMIT :limit
        """

		result = await session.execute(text(sql), params)
		rows = result.fetchall()

		now = datetime.now(UTC)
		hits = []
		for row in rows:
			query_id, query_text, lib, ver, inserted_at = row
			# inserted_at is timezone-aware from DB, no coercion needed
			age_days = (now - inserted_at).days if inserted_at else 0
			hits.append(
				CacheHit(
					query_id=query_id,
					query_truncated=query_text[:100] if query_text else "",
					age_days=age_days,
					library=lib,
					version=ver,
				)
			)
		return hits


async def save_document(
	domain: str,
	url: str,
	path: str,
	content: str,
	content_hash: str,
	depth: int,
) -> SaveResult:
	"""Save or update a document using upsert logic.

	If a document with the same URL exists:
	  - If content_hash matches, skip (SKIPPED)
	  - If content_hash differs, update (UPDATED)
	Otherwise, insert new document (INSERTED)

	Args:
	    domain: Source domain (e.g., "react.dev")
	    url: Full URL of the document
	    path: Path portion of the URL
	    content: Markdown content
	    content_hash: Hash for change detection
	    depth: Crawl depth (0 = llms.txt, 1+ = linked)

	Returns:
	    SaveResult indicating what action was taken
	"""
	async with AsyncSessionLocal() as session:
		result = await session.execute(select(Document).where(Document.url == url))
		existing = result.scalar_one_or_none()

		if existing:
			if existing.content_hash == content_hash:
				logger.debug(f"Document unchanged, skipping: {url}")
				return SaveResult.SKIPPED
			existing.content = content
			existing.content_hash = content_hash
			existing.depth = depth
			existing.content_refreshed_at = datetime.now(UTC)
			await session.commit()
			logger.info(f"Document updated: {url}")
			return SaveResult.UPDATED

		doc = Document(
			domain=domain,
			url=url,
			path=path,
			content=content,
			content_hash=content_hash,
			depth=depth,
		)
		session.add(doc)
		await session.commit()
		logger.info(f"Document saved: {url}")
		return SaveResult.INSERTED


async def get_document_by_url(url: str) -> Optional[Document]:
	"""Retrieve a document by its URL.

	Args:
	    url: The full URL of the document

	Returns:
	    Document if found, None otherwise
	"""
	async with AsyncSessionLocal() as session:
		result = await session.execute(select(Document).where(Document.url == url))
		return result.scalar_one_or_none()


async def search_documents(
	query: str,
	domain: Optional[str] = None,
	limit: int = 10,
) -> list[Document]:
	"""Search documents by content.

	Args:
	    query: Search term
	    domain: Optional domain filter
	    limit: Maximum results

	Returns:
	    List of matching Document objects
	"""
	async with AsyncSessionLocal() as session:
		stmt = select(Document)

		if domain:
			stmt = stmt.where(Document.domain == domain)

		# Use icontains with autoescape for safe wildcard handling
		stmt = stmt.where(Document.content.icontains(query, autoescape=True))
		stmt = stmt.limit(limit)

		result = await session.execute(stmt)
		return list(result.scalars().all())


async def delete_documents_by_domain(domain: str) -> int:
	"""Delete all documents for a domain.

	Useful for re-crawling a domain from scratch.

	Args:
	    domain: The domain to delete documents for

	Returns:
	    Number of documents deleted
	"""
	async with AsyncSessionLocal() as session:
		result = await session.execute(delete(Document).where(Document.domain == domain))
		await session.commit()
		count = result.rowcount
		logger.info(f"Deleted {count} documents for domain: {domain}")
		return count
