**Note**: This project uses [bd (beads)](https://github.com/steveyegge/beads)
for issue tracking. Use `bd` commands instead of markdown TODOs.

## Coding style

- **NEVER USE LAZY IMPORTS**. NEVER. Always use module-level imports. If you're facing cycles, use the system-thinking-before-implementing to figure out the correct way to solve the cycle. LAZY IMPORTS ARE ALWAYS A HACK. NEVER USE THEM. NO MATTER WHAT THE REASON.

## Environment Variables

**NEVER suggest modifying environment variables or creating .env files.** Configuration is managed through `sensei/config.py` with hardcoded defaults. The user manages their own environment—do not tell them to set, export, or modify any environment variables.

## ExecPlans

When writing complex features or significant refactors, use an ExecPlan (as described in `.agent/PLANS.md`) from design to implementation. Create ExecPlans in `docs/execplans/`

## Error Handling

Use typed exceptions from `sensei/types.py`. Keep structured errors until the edge—only convert to strings/HTTP codes at API/MCP boundaries.

| Exception | When to Use | Behavior |
|-----------|-------------|----------|
| `BrokenInvariant` | Config/setup errors (missing API key) | Halts agent, HTTP 503 |
| `TransientError` | Temporary failures (network timeout) | Returns string to LLM |
| `ToolError` | Tool failures (bad input, API error) | Returns string to LLM |

**Best practices:**
- **Preserve exception chains** with `raise ... from e` so root cause is traceable
- **Return strings for recoverable errors** so the LLM can reason and try alternatives
- **Only halt on `BrokenInvariant`**—config errors can't be worked around
- **Never return `"Error: ..."` strings**—raise typed exceptions instead

```python
async def search_foo(...) -> Success[str] | NoResults:
    if not api_key:
        raise BrokenInvariant("API key not configured")
    try:
        response = await client.get(...)
    except httpx.TimeoutException as e:
        raise TransientError("Request timed out") from e  # preserve chain

    if not results:
        return NoResults()
    return Success(format_results(...))
```

## Sentry Error Monitoring

Sentry captures exceptions in production (when `SENTRY_DSN` is set). It's a no-op locally.

**When to add `sentry_sdk.capture_exception(e)`:**

Add it in catch blocks that **handle exceptions gracefully** (convert to HTTP responses, return error strings, etc.) but should still be tracked:

```python
except ToolError as e:
    sentry_sdk.capture_exception(e)  # Track it
    logger.error(f"Tool failed: {e}")
    raise HTTPException(status_code=500, detail=str(e))  # Convert for client
```

**When NOT to add it:**

- **Re-raised exceptions** - Sentry auto-captures unhandled exceptions
- **User input errors** (ValidationError, 400s) - Not bugs, don't track
- **Expected failures** (404s, empty results) - Not bugs, don't track

**Instrumented locations:**

| File | What's captured |
|------|-----------------|
| `sensei/api/__init__.py` | API endpoint errors (BrokenInvariant, TransientError, ToolError, ModelHTTPError) |
| `sensei/server.py` | MCP tool errors (same exceptions, converted to MCPToolError) |
| `sensei/tools/common.py` | Tool wrapper errors (TransientError, ToolError) |
| `sensei/tome/crawler.py` | Crawler failures (decode errors, crawl failures, cleanup failures) |
| `sensei/agent.py` | Sub-agent spawn errors (ToolError) |

**Adding new catch blocks:** If you add a catch block that converts an exception (doesn't re-raise), add `sentry_sdk.capture_exception(e)` before converting.

## Result Types

Tools return `Success[T] | NoResults`, never error strings. This separates "found nothing" from "something went wrong"—critical for the LLM to make good decisions.

- `Success[str]` - Tool found data
- `NoResults` - Tool ran successfully but found nothing (not an error)

**Best practices:**
- **Use pattern matching** to handle results—`match result: case Success(data): ...`
- **`NoResults` is not an error**—it means the search worked, just nothing matched
- **Wrap tools for PydanticAI** with `wrap_tool()` from `sensei/tools/common.py`
- **Keep rich types internally**—only stringify at the PydanticAI boundary

## Domain Models

Define domain models once in `sensei/types.py`. Use them across all layers—core, storage, and edges. This is the single source of truth for your domain.

**Best practices:**
- **One definition, used everywhere**—no duplicating fields across API/DB models
- **Pass models, not individual fields**—`save_rating(rating: Rating)` not `save_rating(query_id, correctness, ...)`
- **Convert at the edges only**—API/MCP layers convert wire format ↔ domain models
- **Use Pydantic for validation**—`Field(..., ge=1, le=5)` validates once, everywhere

```python
# In types.py - single source of truth
class Rating(BaseModel):
    query_id: str
    correctness: int = Field(..., ge=1, le=5)
    ...

# In core.py - pass the model
async def handle_rating(rating: Rating) -> None:
    await storage.save_rating(rating)

# In storage.py - accept the model
async def save_rating(rating: Rating) -> None:
    record = RatingModel(**rating.model_dump())
    ...

# At edges - convert from wire format
rating = Rating(**request.model_dump())
await core.handle_rating(rating)
```
