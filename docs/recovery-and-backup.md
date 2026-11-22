# IFSS Recovery, Backup, and Monitoring

## Proposed recovery objectives

Initial objectives for planning only; they require owner approval and a measured restore exercise before production promises:

| Failure | Proposed RPO | Proposed RTO |
|---|---:|---:|
| One application-managed MinIO node lost | 0 for acknowledged uploads (two verified copies required) | Reads continue; restore factor 3 within 4 hours |
| MySQL primary/data volume lost | At most 15 minutes using binlog/PITR backups | Core catalog/API restored within 4 hours |
| Complete site loss | Metadata: at most 15 minutes; objects: at most 24 hours, subject to off-site backup cadence | Core service restored within 24 hours |

RPO 0 for one node assumes two acknowledged copies are in genuinely independent failure domains. Three containers on one development host do not satisfy that assumption. MySQL's 15-minute binlog archive target does not make object backups equally current; loss of two or all copies between independent backups may exceed the object RPO. Restore from the independent backup or user re-upload.

## Backup strategy

- **MySQL:** encrypted, consistent full backups daily plus binary-log archiving for point-in-time recovery at least every 15 minutes. Back up schema/migrations and test restore to a clean instance. Keep backups outside the primary host and separate from MinIO data volumes.
- **Objects:** copy committed versions to an independent backup account/site or immutable backup target at least daily, then verify inventory and checksums. This cadence is the basis for the proposed 24-hour object RPO; tighten it if the business requires a lower RPO. Application RF=3 is availability/repair protection, not backup. Protect backup credentials separately and deny normal API deletion rights over retained backup copies.
- **Configuration and secrets:** back up non-secret configuration and recovery procedures; secret material is backed up/escrowed through the approved secret manager with restricted access, not in Git or ordinary backup bundles.
- **FAISS:** preserve snapshots for fast recovery, but rebuild from canonical chunks/embeddings in MySQL if missing or corrupt. Restore deletion tombstones before enabling queries.
- **Storage telemetry:** node and cluster samples are stored in MySQL for 30 days and are covered by database backups. If samples are missing after restore, restart probes and aggregation; dashboard history may have a gap and must show incomplete coverage rather than fabricated values. Telemetry is not required to recover file or replica truth.
- Define retention, encryption, geographic placement, legal hold, and restore access per policy. Proposed schedule (daily full, 15-minute logs) must be validated against size, cost, and compliance requirements.

## Recovery runbooks

1. **Single storage node failure:** alert, remove it from placement, serve verified copies, repair to restore three copies, verify checksums, then re-admit after successful probes.
2. **Suspected corruption:** quarantine the copy, prevent reads from it, compare independent copies and expected digest, repair from a verified source, preserve evidence, and alert.
3. **All copies lost:** mark version lost and search-disabled; page operator; restore from independent object backup or request re-upload. Never claim metadata can reconstruct file bytes.
4. **MySQL loss:** fence the failed primary, restore encrypted full backup and binlogs to a consistent point, validate constraints and object references, reconcile MinIO, then re-enable writes.
5. **Site loss:** provision isolated infrastructure, restore secrets/config through approved recovery, restore MySQL and object backups, reconcile versions/replicas, rebuild FAISS, and enable traffic only after integrity and access checks.

Run restore and failure drills at least quarterly as a proposed operational cadence; frequency and responsibilities must be approved.

## Production decisions to finalize

Before production deployment, owners must approve the numeric RPO/RTO targets and the recovery evidence required to claim them; name the team/role accountable for database and object backup schedules, monitoring, access control, restore execution, and drill sign-off; choose backup region/account, immutability and retention; and set per-user/global quotas and reserve thresholds. The values in this document are planning proposals only.

## Quotas, monitoring, and alerts

Enforce per-user stored-byte and file-count quotas, upload-size limits, and global reserve capacity. Count committed live versions and define treatment of retained historical versions and temporary uploads. The `.env.example` values are local examples only; product defaults remain unresolved.

Monitor API readiness, MySQL connectivity/replication/backup age, MinIO node probe success/latency/capacity, replica factor deficits, checksum failures, repair queue age/retries, orphan cleanup, upload failures, indexing lag/rebuilds, OpenAI errors/spend, quota rejections, and restore-drill results. Storage-dashboard history is sourced from MySQL `storage_node_samples` and `storage_cluster_samples`, sampled each minute and retained for 30 days. Alert on missing backups, stale binlogs, exhausted capacity, unavailable nodes, replica deficit beyond SLO, checksum mismatch, stuck leases/jobs, and unexpected AI cost. Use request/job correlation IDs while redacting credentials and document contents. Alert routing and on-call ownership must be assigned before production.
