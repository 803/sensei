# Crawler Refactor Design

**Date:** 2025-12-01
**Beads:** sensei-67v, sensei-kcp, sensei-10i, sensei-ipx

## Problem Statement

The current crawler has several architectural issues:

1. **Storage layer has business logic** - `save_document_metadata` decides whether to skip/update/insert based on content hash comparison
2. **Tree traversal in storage** - `save_sections` contains `save_tree()` which walks the SectionData tree
3. **Orphan documents** - Documents removed from source are never detected/deleted
4. **Partial visibility** - Queries may see incomplete data during crawl

## Solution: Generation-Based Crawls

### Core Concept

Each crawl creates a new "generation" of documents. Queries only see the active generation. After crawl completes, we atomically swap which generation is active.

### Schema Changes

```sql
-- Add columns to documents table
ALTER TABLE documents ADD COLUMN generation_id UUID NOT NULL;
ALTER TABLE documents ADD COLUMN generation_active BOOLEAN NOT NULL DEFAULT false;

-- Partial index for efficient queries on active documents
CREATE INDEX idx_documents_domain_active ON documents (domain) WHERE generation_active = true;

-- View for simplified queries
CREATE VIEW documents_active AS SELECT * FROM documents WHERE generation_active = true;
```

### Data Flow

```
HTTP Response (markdown content)
    ↓
crawler.ingest_domain(domain)
    ├── generation_id = uuid4()
    │
    ├── for each document:
    │   ├── insert_document(domain, url, path, hash, generation_id)
    │   │       └── INSERT with generation_active=false
    │   │
    │   ├── chunk_markdown(content) → SectionData tree
    │   ├── flatten_section_tree(tree, doc.id) → list[Section]
    │   │       └── Client-side UUID generation for parent relationships
    │   └── insert_sections(sections)
    │           └── Bulk INSERT
    │
    ├── on success:
    │   ├── activate_generation(domain, generation_id)
    │   │       └── UPDATE documents SET generation_active = (generation_id = $gen_id) WHERE domain = $domain
    │   └── cleanup_old_generations(domain)
    │           └── DELETE FROM documents WHERE domain = $domain AND NOT generation_active
    │
    └── on failure:
            └── Orphan generation, cleaned up on next crawl or by background job
```

### Layer Responsibilities

**Crawler (crawler.py):**
- Orchestrates crawl flow
- Generates generation_id
- Calls chunker to parse markdown
- Flattens section tree (client-side UUIDs)
- Calls storage functions
- Activates generation on success

**Storage (storage.py):**
- Pure CRUD operations
- `insert_document()` - single INSERT
- `insert_sections()` - bulk INSERT
- `activate_generation()` - single UPDATE
- `cleanup_old_generations()` - DELETE with cascade
- No business logic, no domain model knowledge

**Chunker (chunker.py):**
- Parses markdown into SectionData tree
- No storage interaction

### Storage API

```python
# Document operations
async def insert_document(
    domain: str,
    url: str,
    path: str,
    content_hash: str,
    generation_id: UUID,
) -> Document:
    """Insert a new document. No upsert logic."""

async def activate_generation(domain: str, generation_id: UUID) -> int:
    """Atomically activate a generation, deactivate all others for domain."""

async def cleanup_old_generations(domain: str) -> int:
    """Delete all inactive documents for domain. Cascades to sections."""

# Section operations
async def insert_sections(sections: list[Section]) -> int:
    """Bulk insert sections. Caller provides fully-formed models with IDs."""

# Query operations (use documents_active view)
async def get_sections_by_document(domain: str, path: str) -> list[Section]:
    """Join through documents_active view."""

async def search_sections_fts(domain: str, query: str, ...) -> list[SearchResult]:
    """Join through documents_active view."""
```

### Crawler Function

```python
def flatten_section_tree(root: SectionData, document_id: UUID) -> list[Section]:
    """Convert SectionData tree to flat list with parent relationships.

    Generates UUIDs client-side so we can set parent_section_id
    without database round-trips.
    """
    sections: list[Section] = []
    position = 0

    def walk(node: SectionData, parent_id: UUID | None) -> None:
        nonlocal position
        if not node.content and not node.children:
            return

        section_id = uuid4()
        sections.append(Section(
            id=section_id,
            document_id=document_id,
            parent_section_id=parent_id,
            heading=node.heading,
            level=node.level,
            content=node.content,
            position=position,
        ))
        position += 1

        for child in node.children:
            walk(child, section_id)

    walk(root, None)
    return sections
```

### What Gets Removed

- `save_document_metadata()` - replaced by `insert_document()`
- `save_sections()` with nested `flatten()`/`save_tree()` - replaced by `insert_sections()` + `flatten_section_tree()`
- `SaveResult` enum - no longer needed
- `depth` column on documents - crawl metadata doesn't belong in storage
- `content_hash` comparison in storage - no skip logic, full re-crawl every time

### Benefits

1. **Atomic visibility** - Queries see complete old set OR complete new set
2. **No orphans** - Old generation deleted after successful swap
3. **Failure safety** - Failed crawl = orphan generation, no impact on queries
4. **Clean separation** - Storage is pure CRUD, crawler owns business logic
5. **Efficient inserts** - Bulk insert with client-side UUIDs, no recursive flush
6. **Rollback capability** - Can flip generation_active back if needed

### Migration Path

1. Add `generation_id` and `generation_active` columns (with defaults)
2. Create index and view
3. Mark existing documents as `generation_active=true`
4. Deploy new crawler code
5. Remove `depth` column
6. Remove old storage functions
