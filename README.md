# Intelligent File Storage System (IFSS)

IFSS is a planned, authenticated file platform with replicated object storage, health monitoring, semantic search, and document Q&A. This repository currently contains architecture and planning documents only; implementation begins after the architecture is approved.

## Architecture documents

- [System architecture and folder structure](docs/architecture.md)
- [Database design](docs/database-design.md)
- [API roadmap](docs/api-roadmap.md)
- [Development milestones](docs/development-roadmap.md)
- [Storage architecture](docs/storage-architecture.md)
- [Fault tolerance and consistency](docs/fault-tolerance-design.md)
- [Security design](docs/security-design.md)
- [AI and RAG architecture](docs/ai-rag-architecture.md)
- [UI/UX design specification](docs/ui-ux-design.md)
- [Recovery and backup](docs/recovery-and-backup.md)
- [Architecture review summary](docs/architecture-review-summary.md)

## Initial design decisions

- Use a **modular FastAPI application** first, with clear domain boundaries and background workers. Avoid microservices until scale or independent operations justify the added deployment and consistency costs.
- Store file bytes as **MinIO objects**; keep ownership, metadata, replication state, jobs, and authorization in **MySQL**.
- Model storage targets as three separate MinIO instances in development. Replication and recovery are explicit control-plane workflows, not assumptions about MinIO erasure coding.
- Use **FAISS** as a rebuildable search index. MySQL remains the source of truth for document and chunk records.
- Keep secrets outside the repository. Use environment-based configuration for local development and a secrets manager in deployed environments.

The detailed designs define three local MinIO instances with separate volumes and application-managed three-copy replication. Containers on one host are not independent physical failure domains. See the storage, fault-tolerance, security, AI/RAG, and recovery documents before approving implementation.

See the architecture document for assumptions, trade-offs, trust boundaries, and operational behavior.
