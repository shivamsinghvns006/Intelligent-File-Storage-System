# IFSS Storage Architecture

**Status:** Proposed design. Development topology is local and is not a production availability claim.

## Initial development topology

Run three separate MinIO service instances, each with its own credentials and persistent volume: `minio-node-1` → `minio_node_1_data`, `minio-node-2` → `minio_node_2_data`, and `minio-node-3` → `minio_node_3_data`. Each instance has a private bucket and is addressed through an internal endpoint. No MinIO credentials or endpoints are exposed to React. The `.env.example` lists placeholder endpoints and credentials; real local values belong only in the ignored `.env`. All three services may run on one physical development machine.

The local setup provides three independent MinIO service processes and separate persistent volumes. Application replication can tolerate an individual service/container failure when another verified copy remains reachable. Because the services may share one host, this setup does **not** protect against complete host, power, host-level storage-controller, or shared-network failure. It is a development fault exercise, not physical host-level fault tolerance.

In production, place replicas on independent physical hosts or infrastructure failure domains. Host separation protects against a single-host failure; zone separation additionally protects against a zone outage only when network, power, control plane, and backup placement are also independent enough for the stated objective. Do not count multiple containers or volumes on one host as separate physical failure domains. Configure the failure-domain labels and required placement at deployment time. Whether production uses separate MinIO deployments or a supported distributed MinIO topology, the number of hosts/zones, and operational ownership remain configurable decisions to approve before production. MinIO's own erasure coding and IFSS's whole-object replication are separate protection layers.

## Replication and placement

- Initial replication factor: **3 verified copies**, one per registered MinIO service. In development, placement uses distinct service instances but all may share one physical-host failure domain. In production, require distinct configured physical/infrastructure failure domains for host-level protection and distinct zones if zone-level protection is required.
- New uploads stream to two chosen healthy nodes synchronously. IFSS commits the file version only after both object writes complete and SHA-256 checksums match. It then queues the third copy. The committed file is available for reads, while its replication health remains `degraded` until the third verified copy exists.
- Placement chooses distinct healthy nodes with sufficient quota/capacity, preferring the least-used eligible node and spreading by region/zone where configured. Placement is persisted per file version and is not recomputed on every request.
- If fewer than two distinct MinIO services are writable, uploads fail closed with a retryable service error. Production policy must additionally require the agreed minimum number of independent physical/zone failure domains. No one-copy success is reported as durable under this policy. Existing files can still be read from any verified healthy copy.
- Temporary object keys are unique per upload attempt and file version. A replica is marked healthy only after a successful read/checksum verification, then the object is promoted to its immutable final key or its staged state is committed.

## Node health

Probe each node's authenticated S3 health and a bounded bucket read/write canary every 30 seconds; collect latency, recent operation failures, used capacity, and last successful probe. Proposed starting thresholds: mark `degraded` after 2 consecutive probe failures and `unavailable` after 3; restore only after 2 consecutive successes. Thresholds are configurable and require tuning. A transient timeout marks a probe failure, not object corruption. Once per minute, persist node snapshots and cluster replica/repair/upload aggregates in MySQL `storage_node_samples` and `storage_cluster_samples`. Retain these dashboard samples for 30 days, then purge them; current node/file/replica records remain authoritative. No external time-series service is required for the initial deployment. Alert on unavailable nodes, low free space, replica deficit, prolonged degraded files, and failed repair jobs.

Node states are `healthy`, `degraded`, `unavailable`, `draining`, and `disabled`. A draining node receives no new placements; replicas are copied and verified elsewhere before removal. On unavailability, reads route to another healthy replica, new placements exclude the node, and repair jobs restore factor 3 when capacity and a healthy source are available. Do not delete the old copy until a replacement is verified.

## Capacity and policy

Enforce configurable per-user byte and file-count quotas plus a global reserve threshold. Reserve space for repair and temporary uploads; reject uploads before accepting bodies when quota or safe capacity is insufficient. Initial local defaults are examples, not approved product limits. Production sizing, quotas, admission thresholds, and retention policy remain unresolved and must be finalized before production deployment.
