# IFSS Development Roadmap

This roadmap sequences implementation after architecture approval. Each milestone has concrete deliverables and acceptance criteria. Milestone completion requires review before moving forward. The architecture and production decision gates are described in the linked design documents.

## Milestone 1 — Project initialization and security configuration

**Deliverables:** Initialize the repository's React/FastAPI project layout; add configuration loading and validation; retain `.env.example` with placeholders only; verify `.env` is ignored; define safe logging defaults, CORS policy placeholders, security headers, and secret-handling guidance. Add only dependencies needed for the initialization slice.

**Acceptance:** Clean local startup of the skeleton; no credentials in code or frontend artifacts; `.env` remains untracked while `.env.example` is trackable; invalid/missing required configuration fails clearly without printing secret values.

## Milestone 2 — FastAPI backend and MySQL integration

**Deliverables:** Create the modular API foundation, MySQL connection/configuration, schema migration baseline, health endpoints, structured errors/logging, user identity/session foundation, and file/catalog schema including immutable file versions, replica/job records, and outbox semantics.

**Acceptance:** API readiness accurately reflects required database access; migrations work on a clean database; transaction boundaries and version states are documented; authorization scaffolding denies access by default; credentials and tokens are not logged.

## Milestone 3 — Multi-node MinIO storage infrastructure

**Deliverables:** Configure three separate MinIO service instances, each with its own persistent volume, private bucket, internal endpoint, and distinct placeholder-configured credentials. Add the storage-node registry/configuration model, 30-second health probes, one-minute MySQL telemetry samples, 30-day history retention, capacity signals, and environment-specific failure-domain labels. Development may place all services on one host; production topology remains configurable.

**Acceptance:** Each service can be addressed independently and retains its data through container restart; a service/container failure can be detected and isolated; node and cluster telemetry is sampled, queryable, and purged according to the 30-day policy; documentation and operator output state clearly that one-host development does not survive complete host failure. No production host/zone resilience claim is made without configured independent domains.

## Milestone 4 — File replication and fault tolerance

**Deliverables:** Implement immutable file versions, RF=3 placement, two-verified-copy upload commit, asynchronous third-copy replication, SHA-256 verification, idempotent workers and leases, health-aware reads, reconciliation, orphan cleanup, repair, draining, deletion, and explicit degraded/lost states.

**Acceptance:** An acknowledged upload remains readable after one MinIO service/container failure; retries and crash recovery do not create conflicting copies or false success; checksum corruption is detected and repaired from a verified replica; all-replicas-lost is reported as lost; RF=3 restoration and failure metrics are observable.

## Milestone 5 — React frontend and dashboard

**Deliverables:** Build responsive sign-in and file dashboard flows, upload progress, file/version details, download/delete actions, processing status, and authorized storage health/replication summaries. Use the approved session and API contracts.

**Acceptance:** UI works at supported viewport sizes; every file action relies on server authorization; no MinIO/OpenAI secrets or arbitrary object keys reach the browser; upload failures and degraded/lost state are understandable.

## Milestone 6 — AI document processing

**Deliverables:** First establish the backend AI provider boundary, durable chat sessions/messages, and authenticated streaming/cancellation infrastructure for general conversations. Then add the approved document-format allowlist, bounded extraction, chunking with source locators, configurable embedding model, and durable chunk/vector records. Do not enable document retrieval until the ingestion records are authorization-safe and indexable.

**Acceptance:** General conversations stream and persist with safe retry/cancellation states; unsupported, corrupt, or resource-intensive files fail safely without blocking storage; processing retries are idempotent; source version and model metadata are recorded; provider use is policy-gated and content is not logged.

## Milestone 7 — RAG, semantic search, and AI chatbot

**Deliverables:** In order, implement FAISS generation/persistence/rebuild and authorization-aware semantic search; then version-specific PDF summaries using the durable summary records; then multi-document comparison and document-grounded chat with citations. Add deletion/replacement invalidation, prompt-injection-aware context handling, and rate/cost controls throughout.

**Acceptance:** Index rebuilds from canonical records; search, summaries, comparison, and chat cannot cross ownership/tenant boundaries; every citation references authorized source evidence; deleted or unauthorized content is excluded before prompt construction; index lag/failure is visible.

### AI feature dependency order

The cross-milestone sequence is: (1) chat persistence/provider/streaming foundation in Milestone 6; (2) document extraction, chunking, and embeddings in Milestone 6; (3) FAISS synchronization and semantic search in Milestone 7; (4) PDF summarization; (5) multi-document comparison and document-grounded RAG/chat. Summarization is scheduled after search as the agreed delivery order, although its extraction dependency is available earlier. Keep general chat usable independently of document processing.

## Milestone 8 — Testing, monitoring, and deployment

**Deliverables:** Exercise storage/database/AI failure cases; add operational metrics and alerts; finalize backups and restore runbooks; conduct recovery drills; review security, quotas, retention, deployment, and production topology; prepare operator documentation.

**Acceptance:** Agreed RPO/RTO targets are demonstrated in restore drills; alert thresholds and ownership are documented; production failure-domain requirements are configured; quotas and tenant/AI data policies are approved; no unresolved production decision is represented as a guaranteed capability.

## Approval and production gates

Architecture approval is a gate before Milestone 1. Production deployment additionally requires documented decisions for host/zone failure domains, RPO/RTO, quota values, backup owner and restore responsibility, tenant/sharing policy, retention, and AI provider/data handling. See [storage architecture](storage-architecture.md), [security design](security-design.md), [AI/RAG architecture](ai-rag-architecture.md), and [recovery and backup](recovery-and-backup.md).
