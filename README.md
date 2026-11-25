# Intelligent File Storage System (IFSS)

IFSS is planned as an authenticated file platform with replicated object storage, health monitoring, semantic search, and document Q&A. Authentication and the other product features are not implemented yet. Milestone 1 provides a minimal FastAPI and React/TypeScript foundation with security-oriented configuration.

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

## Run the Milestone 1 development shell

If `.env` does not already exist, copy `.env.example` to `.env` (do not overwrite an existing local file), then run Docker Compose from the repository root:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose --env-file .env -f deploy/compose.yaml up --build
```

Open `http://localhost:5173` for the frontend shell. It checks `GET /health` at the configured `VITE_API_BASE_URL` and displays whether the API process responds. This process-level check is not a dependency readiness probe. Run `npm test` from `frontend/` for the health-client connectivity tests. This Compose file starts only the frontend and backend. MySQL, MinIO, authentication, file operations, and AI are introduced in later milestones. Use local placeholder values only; production secrets must come from a deployment secret store.
