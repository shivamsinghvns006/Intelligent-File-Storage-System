# IFSS Architecture Review Summary

## Current assessment

- The architecture now has concrete designs for application-managed storage replication, crash recovery, metadata reconciliation, security boundaries, and AI/RAG lifecycle.
- Milestone 1 has been approved; implementation has not started. The initial documentation baseline is prepared for review, and production readiness remains a separate gate.

## Historical findings — resolved in the current documentation

- Three independent MinIO service instances and three named persistent volumes are defined for development, with replication factor 3, placement rules, node health monitoring, and degraded behavior.
- Upload commit, replica verification/repair, retry leases, MySQL/MinIO reconciliation, orphan cleanup, deletion idempotency, and all-replicas-lost behavior are documented.
- File versions, durable chunk/embedding records, FAISS rebuilding, owner-filtered retrieval, citations, and AI deletion are specified.
- Replica uniqueness per version/node, durable summary and comparison results, owner-scoped API idempotency, and optimistic version-finalization concurrency are specified.
- API transient phases are distinguished from persisted upload, message, node, and job states. Processing-job file/version ownership constraints and upload idempotency ownership use composite foreign keys backed by matching unique keys.
- Bulk file move/delete contracts define per-item success, asynchronous acceptance, failures, idempotent replay, and partial-result presentation.
- Storage dashboards use minute-level MySQL node/cluster samples with 30-day retention; current replica truth remains in the canonical file/replica records.
- `.gitignore` excludes `.env` and common local secret/data artifacts; `.env.example` contains placeholders only. JWT refresh rotation, file-level authorization, and key protection are documented.

The earlier audit's pending Milestone 1 approval wording is historical; approval has since been granted. The security and production decisions below remain unresolved deployment gates.

## Accepted development limitations

- The three MinIO services may run on one physical development machine, each with a separate persistent volume. This permits individual service/container failure exercises but **does not protect against complete host, power, controller, or shared-network failure**.
- Development replication across distinct service instances must not be described as physical host- or zone-level fault tolerance.

## Production requirements

- Place replicas on independent physical hosts or infrastructure failure domains. Configure zone separation if zone-outage protection is required, and validate that shared dependencies do not defeat the target.
- Use independent object backups and database point-in-time recovery, and demonstrate agreed RPO/RTO in restore drills.
- Finalize quota enforcement, secret custody, monitoring/alert ownership, and incident/recovery procedures before production deployment.
- Storage time-series source and retention are defined for the initial deployment; production alert routing and on-call ownership still require assignment.

## Remaining architectural decisions

- Approve production MinIO topology, number of hosts/zones, placement constraints, and operational owner.
- Approve RPO/RTO values, backup owner/restore responsibility, backup retention and location.
- Choose tenant and file-sharing policy, retention/deletion policy, and production quota values.
- Approve AI provider/data handling: consent or opt-out, allowed formats, residency/retention, and model choices.
- Confirm expected volume, file sizes, indexing freshness, and capacity targets.

## Recommendation

- **Milestone 1: Approved to begin.** Approval has been granted; implementation proceeds only through the project's milestone review process.
- **Production deployment: Not ready** until the listed production requirements and decisions are approved and tested.
