# IFSS AI and RAG Architecture

## Ingestion pipeline

AI processing begins only after a file version is committed and policy permits external processing. Workers fetch a verified replica, identify type from content, and extract text in a resource-limited process. The initial supported-format allowlist, OCR needs, parser selection, language support, and malware scanning policy remain to be approved; unsupported or encrypted files receive a visible `unsupported`/`needs_password` processing result without blocking file storage.

Normalize extracted text, preserve page/section/paragraph offsets, then chunk at a configurable starting target of about 800 tokens with 120-token overlap. Store source offsets and chunk index so citations can point to a page/section and stable file version. These are initial tuning values, not final quality claims. Summaries are generated asynchronously from bounded content and versioned with model and source version.

PDF summarization uses the same authorized, versioned extraction pipeline. A short PDF may be summarized inline if it fits configured limits; larger documents use a durable processing job with visible `queued`/`running`/`retry_wait`/`succeeded`/`failed`/`cancelled` state. The summary record mirrors these processing states; `deleted` is reserved for its data lifecycle. Summaries identify the source file version and cite page/section locators persisted through `document_summary_sources`. Multi-document comparison selects an explicit set of authorized file versions, retrieves bounded evidence per source, and labels each source in the output. Completed comparison text is persisted in `document_comparisons`, with chunk citations in `document_comparison_sources` linked to the owner-scoped job and its `processing_job_sources`; it must report when a selected source cannot be processed or does not support a comparison claim.

## Embeddings and durable source records

Use `text-embedding-3-small` as the initial candidate embedding model. OpenAI documents this as an embedding model; verify availability and deployment policy when implementation begins ([model documentation](https://developers.openai.com/api/docs/models/text-embedding-3-small)). Store the exact model identifier, dimensions, chunking version, text hash, and embedding generation status for every chunk. Validate vector dimension at ingestion. Changing the model or chunking version creates a new index generation and requires re-embedding; vectors from different models/dimensions must not be mixed. Confirm provider/privacy policy before sending content to OpenAI.

MySQL is canonical for `document_chunks`: file/version/owner IDs, chunk number, source offsets, text (or durable protected text reference), text hash, embedding model/dimension, and embedding vector bytes. This makes the vector corpus recoverable from database backups and avoids treating a FAISS file as the only copy. At high corpus scale, vector bytes may move to a dedicated durable vector store, but that is a separate architecture decision. MinIO may store large extracted text artifacts under private, version-scoped keys with the same replication and deletion controls as other objects.

## FAISS lifecycle and synchronization

FAISS is a derived acceleration index. A single logical index-writer process owns each index generation; API and worker processes call it through an internal interface rather than concurrently mutating a shared index file. Persist immutable snapshots plus a manifest (generation, model, dimension, chunking version, applied event sequence, checksum) on durable storage. MySQL remains the source corpus.

After a chunk/vector transaction commits, an outbox event schedules an idempotent index update. The writer applies inserts/deletes and records the applied sequence. On startup, corruption, or sequence gap, it rebuilds into a new generation from eligible MySQL rows, validates count/checksum/metadata, then atomically switches the active generation. Periodic full reconciliation detects missed updates. Search is unavailable or explicitly degraded during rebuild; it must not silently return a stale generation past the configured freshness limit. Freshness target and corpus scale remain open.

For initial owner-private files, partition FAISS search by owner (or an equivalent pre-filtering structure), then recheck candidate chunk and file-version ownership/state in MySQL before fetching text. Do not search globally and rely only on post-filtering if it can expose another user's snippets or compromise recall. Future sharing requires an explicit ACL-aware retrieval design.

## Retrieval, answers, citations

Embed the query with the same model/version as the target index. Retrieve authorized candidates, rank within configured limits, and fetch only their text after MySQL authorization/state checks. Send bounded context to the configured answer model with instructions to treat source text as untrusted data. Return answer plus citations containing file ID, immutable version ID, file name, page/section and chunk reference. Validate citations against retrieved chunks; do not invent sources. If no authorized evidence supports an answer, say so.

## Deletion and version replacement

As soon as deletion is requested, mark the file/version unavailable to search and downloads. A durable deletion job removes chunk rows/text references and embedding records, emits index tombstones, and waits for the active index generation to apply them. Rebuild removes deleted IDs as a backstop. Delete derived summaries and caches under the same policy. If a comparison references a deleted source version, hide its result immediately and purge it under the same deletion policy. Backups expire according to documented retention; restore procedures must replay deletion tombstones before serving search. A superseded version follows retention policy and is not confused with its replacement.

## Conversational LLM architecture

### Provider boundary

The first provider adapter uses the OpenAI API for chat generation and embeddings. FastAPI and backend workers make every provider call; the React application never calls OpenAI directly. Introduce backend interfaces such as `ChatProvider.stream_reply(...)` and `EmbeddingProvider.embed(...)`, with an OpenAI adapter first. Provider/model selection is configuration, not frontend logic, so a compatible hosted provider or local model can be added later without coupling chat/session records to provider credentials.

Read credentials from server-side environment configuration (`OPENAI_API_KEY` for the OpenAI adapter; `AI_CHAT_PROVIDER` and `AI_EMBEDDING_PROVIDER` select providers; `OPENAI_CHAT_MODEL` and `OPENAI_EMBEDDING_MODEL` select OpenAI models). Provider selectors are non-secret configuration; add them to `.env.example` when implementation begins. A local `.env` may supply development values and remains Git-ignored; production credentials come from protected deployment secret injection. Never persist API keys in MySQL, browser storage, URLs, telemetry, or logs. Redact provider errors and record only safe provider/model identifiers and request correlation data. Apply timeouts, bounded retries for transient failures, rate and cost limits, and cancellation propagation.

### Conversation modes

- **General conversation:** send authorized conversation history and the current user turn to the configured LLM, without document retrieval unless the user explicitly attaches or selects sources. This is a full conversational experience and supports follow-up context from the same owned session.
- **Document conversation:** validate selected file IDs/versions against the session owner, retrieve relevant chunks from the matching FAISS generation, recheck chunk/file ownership and active state in MySQL, and assemble only authorized evidence with source locators. Re-run retrieval for each follow-up; do not trust prior citations or previously retrieved text as continuing authorization.
- **Summarize:** use the extraction/summary pipeline for a chosen committed version and persist a versioned summary/job state.
- **Compare:** retrieve evidence from each selected source under the same authorization checks, preserve source labels, and generate a bounded comparison with citations.
- **Semantic search:** embed the query, search only the caller's authorized index partition or use an equivalent pre-filter, then verify every candidate in MySQL before returning snippets.

General mode and document mode must be visibly distinct. Switching to general mode clears document context unless the user explicitly keeps sources attached. The UI's source selection is not an authorization boundary; FastAPI checks session ownership and each selected source on every request.

### End-to-end chat data flow

1. The user signs in and creates a new session or opens an owned history record. FastAPI validates JWT/session and checks session ownership.
2. The user chooses general or document mode and optionally attaches/selects files. For each request, FastAPI resolves immutable file versions, checks owner/tenant ACL and file state, and rejects unauthorized, deleted, lost, or not-yet-indexed sources.
3. In a MySQL transaction, persist the user message and an assistant response row in `pending` state with an idempotency key. Persist selected source/attachment references where applicable.
4. In document mode, embed the current question with the index-compatible embedding model, retrieve authorized candidates, recheck each candidate in MySQL, and build a bounded context. In general mode, omit retrieval. Include recent conversation turns within a configured context budget; older history may be summarized, with provenance retained and no cross-session mixing.
5. Send the request from the backend to the configured LLM provider. Stream response events from FastAPI to the browser over an authenticated HTTPS stream (SSE or an equivalent streaming transport). The browser receives generated text and status events, never provider credentials.
6. Validate citation IDs/locators against the retrieved candidate set. Persist the completed assistant message, provider/model identifiers, token usage when available, citations, and final status. On timeout, provider failure, or disconnect, persist `interrupted`/`failed` with safe error metadata; never mark partial text complete. Client retries use the idempotency key to avoid duplicate turns.
7. On conversation-history reads, verify owner/tenant authorization for the session and its sources. A citation click resolves the exact file version and source locator through the normal authorized file API.

Streaming content is untrusted output: render as sanitized Markdown, do not execute HTML, scripts, or code blocks, and do not treat model output as an instruction to invoke privileged storage operations. Document text is untrusted prompt context; explicitly separate evidence from system instructions and defend against prompt injection. The initial chatbot has no unrestricted tools that can delete, share, or change storage state.

## Required database design

The logical schema in `database-design.md` includes the chatbot model, durable version-specific `document_summaries`, and durable `document_comparisons`; physical DDL and migrations must implement and validate them before chatbot, summary, and comparison implementation:

- Extend `chat_sessions` with `mode` (`general`, `documents`), session lifecycle (`active`, `archived`, `deleted`), title/timestamps, and optionally a default model/provider ID that is non-secret. Keep `user_id` as the owner FK. The schema no longer relies on a single optional `file_id` as the only source mechanism; it cannot represent multi-document comparison.
- Add `chat_session_sources(session_id, user_id, file_id, file_version_id, added_at)` for persistent selected sources and `chat_message_attachments(chat_message_id, session_id, user_id, file_id, file_version_id, source_order)` for turn-specific attachments. Composite FKs enforce that the selected version belongs to the file and that the file belongs to the session owner. Index by session/version and retain service-layer authorization checks.
- Extend `chat_messages` with `client_request_id`/idempotency key unique within a session, response lifecycle (`pending`, `streaming`, `complete`, `interrupted`, `failed`, `cancelled`, `deleted`), safe error code, `provider_id`, `model_id`, timestamps, and token usage. Persist a partial response only with an explicit interrupted state; never store credentials or hidden prompts.
- Keep `chat_message_sources` as the normalized citation relation to `document_chunks`, with citation order and source locator snapshot. Enforce FKs and uniqueness so retries cannot duplicate citations. Revalidate access when reading history; citations do not grant access.
- Add indexes supporting owner-scoped session history (`user_id`, `updated_at`), messages (`session_id`, sequence/time), source selection, and idempotency lookups. Conversation history must always be read through an owner-scoped query.

Deletion of a file immediately disables its retrieval and removes its session-source/attachment and citation references through an idempotent job. Conversation text may itself contain derived document content; the product must choose and document whether affected messages are redacted/deleted or retained under a defined legal/retention policy before production. Backups and FAISS rebuild must honor the resulting deletion tombstones.

## API contract dependencies

The API roadmap defines session modes and source selection, attachments, comparison requests, streaming events and cancellation, message idempotency/retry behavior, partial/interrupted response persistence, and per-session history management under the authenticated `/api/v1` API. Implementations must preserve the authorization checks and data-handling rules above. This architecture document does not specify endpoint implementation or credentials.

Implementation order is provider/chat persistence and streaming foundation, document extraction/chunking/embeddings, FAISS synchronization and semantic search, PDF summaries, then multi-document comparison and document-grounded RAG/chat. General conversations remain usable before document indexing is available.

Model choices, extraction formats, OCR, chunk tuning, chat model, external data handling, and freshness SLO remain unresolved product/deployment decisions. Before production, approve tenant/sharing boundaries, provider consent and retention settings, allowed data classes and formats, regional processing constraints, conversation retention, and derived-content deletion/retention policy.
