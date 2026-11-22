# IFSS Fault Tolerance Design

## File and version lifecycle

Files are stable user-facing records; each content revision creates an immutable `file_version` with a monotonically increasing version number, size, media type, SHA-256, lifecycle state, and timestamps. `files.current_version_id` changes only after a new version reaches the commit condition. Each version has a replication target and independent `file_replicas` rows.

Upload-session states are persisted as `initiated`, `receiving`, `paused`, `completing`, `committed`, `aborting`, `retry_wait`, `failed`, `aborted`, or `expired`. Normal progress is `initiated` → `receiving` (optionally `paused` and back to `receiving`) → `completing` → `committed`. An accepted abort sets persisted state `aborting` while an idempotent cleanup job removes staged data; transition to `aborted` only after cleanup/reconciliation confirms no staged data remains. `retry_wait` represents a retryable session failure; `failed`, `aborted`, and `expired` are terminal upload-session states. These are the same persisted upload-session values exposed by the API; worker execution states remain separate. Staged parts and file-version states track staging separately. The immutable file-version state follows the schema (`initiated`, `receiving`, `staged`, `verifying`, `committed`, `deleting`, `deleted`, `failed`); retry scheduling is represented by the upload session/job, not an extra file-version state. `committed` is the visibility point and requires at least two verified replicas under initial policy. File-version replication state is `pending` before the committed/degraded phase, `degraded` when committed with fewer than three verified copies, `healthy` at three verified copies, and `lost` when no verified copy remains. Queue execution (`queued`, `running`, `retry_wait`) belongs to `processing_jobs`, not the replication-state field. Failed attempts never replace the current version.

Replica states, matching `database-design.md`, are `planned` → `writing` → `verifying` → `healthy`. Transient write/verification errors enter `retry_wait`; an absent expected object is `missing`; checksum mismatch is `corrupt` and quarantined; a replica on an unreachable node is `unavailable` until the node returns and the object is verified; deletion uses `deleting` → `deleted`. `processing_jobs` records terminal worker failure rather than adding a replica `failed` state. A unique constraint on `(file_version_id, storage_node_id)` ensures a node contributes at most one copy to the replication factor. Operations use unique job idempotency keys derived from operation, version, and target node. Repeating a write verifies the expected checksum and treats an identical existing object as success; a conflicting object is never silently overwritten.

## Crash-safe finalization

1. In a MySQL transaction, create an upload intent, new version in `initiated`, planned replicas, and an outbox/job row. Commit before accepting the body.
2. Stream bytes to a unique staged key on two selected nodes while computing SHA-256 and enforcing declared/actual size limits. Record progress where resumability is supported.
3. Verify size and digest independently against object metadata/readback. Mismatches are quarantined and the attempt fails.
4. Promote staged objects to immutable version keys. In one MySQL transaction, mark the two replicas healthy, version committed, update the file's current version, and enqueue replication/index jobs. This transaction is the visible commit point.
5. If a crash happens at any step, lease expiry and reconciliation inspect the intent and staged/final objects. They resume idempotently or clean up expired staged objects. A crash after the DB commit does not undo the committed version.

If an overwrite arrives, it creates a separate version. The previous current version stays downloadable until the replacement commit succeeds, then retention policy determines its later deletion.

## Concurrent version finalization

At new-version creation (including restore), capture `base_current_version_id` on the `file_versions` row (null for a file with no committed version). Allocate the next `version_number` while holding a lock on the parent `files` row so concurrent requests cannot allocate the same number. At finalization, in a transaction lock that same file row and compare its current pointer with the captured base. Only a match may set `files.current_version_id` to the new committed version. If a competing upload or restore has committed first, the stale version must not replace it: mark the stale version/upload or restore job failed with a safe `concurrent_version_conflict` code and enqueue idempotent cleanup for its staged and verified objects. Synchronous upload completion returns `409`; an already accepted asynchronous restore reports the safe conflict through its job status. Idempotent retries first return the original recorded result; they do not rerun the pointer comparison. This optimistic concurrency rule serializes the commit point without holding a database lock during long object transfers.

## Reconciliation and orphan cleanup

Reconciliation scans MySQL replica intents against MinIO objects and also inventories managed buckets for objects absent from MySQL. Missing expected objects mark replicas `missing`; checksum/size disagreement marks them `corrupt`; both trigger repair and alerts. Unexpected objects are not deleted immediately: classify temporary upload keys, in-flight leased attempts, retained versions, and backup-managed keys first. Delete only after an age grace period longer than the maximum worker lease/retry window, a second confirming scan, and a successful ownership/version lookup. Record cleanup decisions. The scan is paginated and rate-limited to avoid disrupting normal storage traffic.

## Checksums, retry, and worker leases

Compute SHA-256 during upload; store expected digest and size on the version and each replica. Verify after copy and via periodic scrub reads. A mismatch marks the replica `corrupt`, removes it from reads/search eligibility, raises an alert, and triggers repair from a healthy source. Do not infer integrity only from ETag.

Workers atomically claim queued work with a lease and incremented attempt number; they heartbeat/extend the lease while active. Expired leases become eligible again. Use bounded exponential backoff with jitter (initial 5 seconds, maximum 15 minutes, maximum 10 attempts as proposed defaults), then `failed` for operator review. Retry only transient errors; validation, authorization, and checksum-conflict failures need intervention or a new upload. Keep the durable job/outbox row in MySQL so a broker outage cannot lose intent. Final tuning depends on load and provider limits.

## Repair and recovery procedure

1. Health monitor detects a missing/unavailable target; mark replicas unavailable and the version degraded.
2. Select a healthy source replica and a distinct healthy destination with capacity.
3. Copy to a new staged key, verify SHA-256 and size, then atomically record the replacement healthy.
4. Reconcile replica count and placement; alert if no valid destination/source exists or the repair SLO is exceeded.
5. When the failed node returns, inventory its objects and compare version/checksum records. Reuse matching copies, quarantine conflicts, and clean obsolete staged/orphan keys only after retention checks.

If **all replicas are lost**, mark the version `lost`, block downloads and AI retrieval, preserve metadata and audit evidence, and page an operator. Restore only from an independent object backup or user re-upload. Never fabricate bytes or report the file as available. State explicitly that replicated copies alone do not protect against correlated deletion, compromise, or total-site loss.

## Deletion idempotency

Deletion first marks the file/version `deleting` and hides it from downloads/search. A durable job deletes each replica, chunk, embedding, and index entry idempotently; a missing object counts as already deleted. Finalize only after all targets are confirmed or policy-defined retention/tombstone handling is applied. Retries continue safely after crashes; failed deletions remain visible to operators.
