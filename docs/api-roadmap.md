# IFSS API Contracts

**Status:** Proposed v1 contract for implementation planning. No endpoints are implemented by this document.

Base path: `/api/v1` for product routes. Liveness/readiness probes are intentionally unversioned at `/health/live` and `/health/ready` for infrastructure probes. JSON control responses use UTF-8. File parts are binary. All timestamps are UTC ISO-8601. IDs are opaque UUIDs. Request and response examples below define fields, not credentials or production values.

## Common contract rules

### Authentication and authorization

- Protected routes require `Authorization: Bearer <short-lived-access-JWT>`, except cookie refresh/logout additionally require the CSRF header. Login/registration and liveness are public; all other user routes authenticate.
- Refresh tokens are Secure, HttpOnly, SameSite cookies; never return their value in JSON. Login/refresh responses return an access token, expiry, and CSRF token. Mutating cookie-authenticated requests require `X-CSRF-Token` and strict Origin validation.
- Every file, version, folder, upload, job, chat session, source, and citation is owner-scoped in the service layer and SQL query. An opaque ID is not authorization. Admin routes require an admin role. MinIO endpoints, object keys, credentials, and OpenAI keys are never returned.
- V1 user management is self-service (`/users/me`, password change) plus public registration when enabled. There is no public role-assignment or administrative user-management API; initial admin provisioning is an operator-controlled deployment action and must be audited.
- CORS uses exact configured origins only: development `http://localhost:5173` and `http://127.0.0.1:5173`; production exact HTTPS origins supplied by deployment configuration. Never use or reflect `*`; wildcard origins are prohibited with credentials. See [security design](security-design.md).

For cross-origin file previews, the CORS allowlist also permits the `Range` request header and exposes `Accept-Ranges` and `Content-Range` in addition to `Content-Disposition`, `ETag`, and `X-Request-ID`. Keep the methods and credentials policy from [security design](security-design.md) aligned with the deployed client.

### Response and error envelopes

Successful JSON responses return the route's documented resource. Lists use `{items, next_cursor}`; a missing next page is `null`. Errors use `{error:{code,message,request_id,details?}}`; `message` and `details` are safe for clients and never contain secrets, raw provider errors, SQL, or internal object paths.

Common status meanings: `400` malformed request/range; `401` missing/invalid/expired auth; `403` authenticated but forbidden/CSRF rejected; `404` absent or not visible to caller; `409` state/idempotency/version conflict; `413` request or file too large; `415` unsupported media; `416` requested byte range is unsatisfiable; `422` field validation; `429` rate/quota limit; `500` unexpected internal failure; `502` upstream storage/provider failure; `503` required service unavailable; `504` bounded upstream timeout. Each endpoint below lists its expected applicable errors. Never return a different user's existence as a distinguishable `403` where a scoped `404` is safer.

### Persisted states and transient operation states

Fields named `state` on a resource report its persisted lifecycle value from the matching database model. A transient command/worker phase is returned separately as `operation_state`; it does not add a database enum value. Upload status responses (`GET /uploads` and `GET /uploads/{upload_id}`) use exactly these persisted upload-session states: `initiated`, `receiving`, `paused`, `completing`, `committed`, `aborting`, `retry_wait`, `failed`, `aborted`, and `expired`; transitions are defined in [fault-tolerance design](fault-tolerance-design.md). In particular, upload abort uses the persisted state `aborting`; chat cancellation acknowledges `operation_state:"cancelling"` while the message remains persisted as `streaming` with `cancel_requested_at`; node enablement is an `action`, not a persisted `enabled` node state; and restore reports a persisted job state plus transient `operation_state:"copying"`. Job states remain `queued`, `running`, `retry_wait`, `succeeded`, `failed`, or `cancelled`.

### Idempotency

Authenticated mutating create/complete/retry operations accept `Idempotency-Key` (opaque client-generated value), persisted in the owner- and operation-scoped `idempotency_records` table. Same key plus same canonical request returns the original resource/result; same key with a different request hash returns `409 idempotency_conflict`. Insert before side effects and retain through the documented terminal/expiry window. Auth routes that issue credentials are excluded from generic replay to avoid storing or replaying token responses. Upload-part retries use `(upload_id, part_number)` plus the supplied SHA-256 digest: an identical verified part returns the existing result; different bytes for that part return `409 part_conflict`. The client must not generate a new key for an uncertain retry.

## Authentication and user management

### `POST /auth/register`

- **Request:** `{email,password,display_name}`. Registration may be disabled by deployment policy.
- **Response:** `201 {user:{id,email,display_name,role,status,created_at}}`; never return password/hash.
- **Access:** public, rate limited; password validated and adaptively hashed.
- **Errors:** `403 registration_disabled`, `409 email_unavailable`, `422 validation_error`, `429 rate_limited`, `500 internal_error`.

### `POST /auth/login`

- **Request:** `{email,password}`.
- **Response:** `200 {access_token,token_type:"Bearer",expires_in,csrf_token,user:{id,email,display_name,role}}`; sets rotated refresh cookie.
- **Access:** public, rate limited; generic invalid-credential message.
- **Errors:** `401 invalid_credentials`, `403 account_disabled`, `422 validation_error`, `429 rate_limited`, `500 internal_error`.

### `POST /auth/refresh`

- **Request:** refresh cookie plus `X-CSRF-Token`; no refresh token in JSON.
- **Response:** `200 {access_token,token_type:"Bearer",expires_in,csrf_token}` and rotated refresh cookie.
- **Access:** valid refresh session and CSRF/origin checks; reuse revokes token family.
- **Errors:** `401 refresh_invalid_or_expired`, `403 csrf_rejected`, `429 rate_limited`, `500 internal_error`.

### `POST /auth/logout`

- **Request:** refresh cookie and `X-CSRF-Token`.
- **Response:** `204`; revokes session/family and expires cookie. Safe to repeat.
- **Access:** refresh session or already logged-out state; CSRF/origin checks.
- **Errors:** `403 csrf_rejected`, `429 rate_limited`.

### `GET /users/me`

- **Request:** none.
- **Response:** `200 {id,email,display_name,role,status,created_at,storage_usage?}`; usage omitted if unavailable.
- **Access:** authenticated user; returns only self.
- **Errors:** `401`, `503 database_unavailable`.

### `GET /dashboard/summary`

- **Parameters:** none; response is caller-scoped.
- **Response:** `200 {recent_files:[...],storage_usage:{used_bytes,quota_bytes,as_of},active_upload_count,processing_job_count,attention_items:[...]}`. Any unavailable metric is null/omitted with `as_of`; never substitute sample values.
- **Access:** authenticated user; counts/files scoped to caller.
- **Errors:** `401`, `503 database_or_telemetry_unavailable`.

### `PATCH /users/me`

- **Request:** `{display_name?}`; email change is excluded until verification workflow is defined.
- **Response:** `200 {id,email,display_name,updated_at}`.
- **Access:** authenticated self; CSRF applies when cookie-authenticated.
- **Errors:** `401`, `403 csrf_rejected`, `422 validation_error`, `503 database_unavailable`.

### `POST /users/me/password`

- **Request:** `{current_password,new_password}`.
- **Response:** `204`; revokes other refresh sessions.
- **Access:** authenticated self and CSRF/origin checks.
- **Errors:** `401 current_password_invalid`, `403 csrf_rejected`, `422 password_policy_failed`, `429 rate_limited`.

## Folder management

Folders are owner-scoped. Root is represented by `parent_id:null`. Folder delete is allowed only when empty; move/rename is atomic. Folder paths are not authorization credentials.

### `POST /folders`

- **Request:** `{name,parent_id?}`.
- **Response:** `201 {id,name,parent_id,state,created_at}`.
- **Access:** authenticated owner; parent must belong to caller.
- **Errors:** `401`, `404 parent_not_found`, `409 duplicate_name_or_parent_cycle`, `422 validation_error`, `429 quota_limit`, `503 database_unavailable`.

### `GET /folders`

- **Parameters:** `parent_id?`, `q?`, `cursor?`, `limit?` (server capped).
- **Response:** `{items:[{id,name,parent_id,child_folder_count,file_count,updated_at}],next_cursor}`.
- **Access:** authenticated owner; counts include only caller's files.
- **Errors:** `401`, `404 parent_not_found`, `422 invalid_cursor`, `503 database_unavailable`.

### `GET /folders/{folder_id}`

- **Request:** none.
- **Response:** `200 {id,name,parent_id,breadcrumbs,state,created_at,updated_at}`.
- **Access:** authenticated owner.
- **Errors:** `401`, `404 folder_not_found`, `503 database_unavailable`.

### `PATCH /folders/{folder_id}`

- **Request:** `{name?,parent_id?}`; at least one mutable field required.
- **Response:** `200 {id,name,parent_id,breadcrumbs,updated_at}`.
- **Access:** authenticated owner; destination parent must belong to caller.
- **Errors:** `401`, `404 folder_or_parent_not_found`, `409 duplicate_name_or_parent_cycle`, `422 validation_error`, `503 database_unavailable`.

### `DELETE /folders/{folder_id}`

- **Request:** none; only empty folders may be deleted.
- **Response:** `204`.
- **Access:** authenticated owner.
- **Errors:** `401`, `404 folder_not_found`, `409 folder_not_empty`, `503 database_unavailable`.

## Files and versions

File records are stable identities; content is immutable `file_versions`. A current version changes only after upload finalization with two verified replicas. A folder move/rename does not change bytes or version identity.

### `POST /files`

- **Request:** `{name,folder_id?,media_type?,size_bytes,sha256?}` plus `Idempotency-Key`.
- **Response:** `201 {file:{id,name,folder_id,state:"active",created_at},version:{id,version_number,state:"initiated"},upload:{id,state:"initiated",part_size_bytes,expires_at}}`.
- **Access:** authenticated owner; folder must belong to caller; enforce quota and max size before body transfer.
- **Errors:** `401`, `404 folder_not_found`, `409 idempotency_conflict`, `413 file_too_large`, `415 unsupported_media_type`, `422 validation_error`, `429 quota_or_rate_limit`, `503 fewer_than_two_storage_services`.

### `GET /files`

- **Parameters:** `folder_id?` (`null` means root), `q?`, `media_type?`, `state?`, `cursor?`, `limit?`, `sort?`.
- **Response:** `{items:[{id,name,folder_id,media_type,size_bytes,modified_at,current_version_id,state,replication:{verified,target,state}}],next_cursor}`. Replica values only from current backend records.
- **Access:** authenticated owner; query is owner-scoped.
- **Errors:** `401`, `404 folder_not_found`, `422 invalid_filter_or_cursor`, `503 database_unavailable`.

### `GET /activity`

- **Parameters:** `cursor?`, `limit?`, `kind?`.
- **Response:** `{items:[{id,kind,entity_id,display_name?,state,occurred_at}],next_cursor}`; safe user-visible activity only, without document text or internal node details.
- **Access:** authenticated user; only caller-owned file/upload/chat activity.
- **Errors:** `401`, `422 invalid_cursor_or_filter`, `503 database_unavailable`.

### `GET /files/{file_id}`

- **Response:** `200 {id,name,folder_id,media_type,size_bytes,state,current_version:{id,version_number,checksum,created_at}? ,replication,created_at,updated_at}`.
- **Access:** authenticated owner.
- **Errors:** `401`, `404 file_not_found`, `503 database_unavailable`.

### `PATCH /files/{file_id}`

- **Request:** `{name?,folder_id?}`.
- **Response:** `200 {id,name,folder_id,updated_at}`.
- **Access:** authenticated owner; destination folder must belong to caller.
- **Errors:** `401`, `404 file_or_folder_not_found`, `409 duplicate_name_or_state_conflict`, `422 validation_error`, `503 database_unavailable`.

### `DELETE /files/{file_id}`

- **Request:** optional `{purge_after_retention?:boolean}`; deletion starts an idempotent asynchronous workflow.
- **Response:** `202 {file_id,state:"deleting",job_id}`.
- **Access:** authenticated owner; CSRF for cookie auth.
- **Errors:** `401`, `403 csrf_rejected`, `404 file_not_found`, `409 deletion_already_conflicting`, `503 job_queue_unavailable`.

### `POST /files/bulk-operations`

- **Request:** `{operation:"move"|"delete",file_ids:[id,...],folder_id?:id|null}` plus `Idempotency-Key`. Require 1–100 unique file IDs. `folder_id` is required for `move` (`null` means root) and is not accepted for `delete`.
- **Response:** `200 {operation,status:"completed"|"partial"|"failed",succeeded_count,accepted_count,failed_count,results:[{file_id,status:"succeeded"|"accepted"|"failed",http_status,result?:{folder_id?,job_id?,state?},error?:{code,message}}]}`. Move items report `succeeded` after their individual metadata transaction commits. Delete items report `accepted` with a deletion `job_id` and persisted `state:"deleting"`; this is not a claim that object removal has finished. Failed items include only safe errors. `status` is `completed` if there are no failed items, `partial` if some items fail, and `failed` if all items fail.
- **Access:** authenticated owner; authorize each file independently. Move additionally requires the destination folder to belong to the caller. CSRF applies to cookie-authenticated requests.
- **Errors:** `401`, `403 csrf_rejected`, `404` for request-level destination lookup, `409 idempotency_conflict`, `413 too_many_files`, `422 invalid_operation_or_duplicate_ids`, `429 rate_limited`, `503 database_or_job_service_unavailable`.
- **Partial failure and retry:** Validate the envelope and idempotency key before processing. Then execute each file independently in its own transaction/job intent; one item's failure does not roll back other items. Per-item inaccessible or absent files return the same `404 file_not_found`. Repeat with the same key and identical canonical request replays the complete ordered result. To retry only failed items, submit that subset as a new request with a new key. Each delete job remains independently idempotent and is tracked through the normal job API.

### `GET /files/{file_id}/versions`

- **Parameters:** `cursor?`, `limit?`.
- **Response:** `{items:[{id,version_number,state,replication_state,size_bytes,sha256,created_at,committed_at}],next_cursor}`.
- **Access:** authenticated owner.
- **Errors:** `401`, `404 file_not_found`, `422 invalid_cursor`, `503 database_unavailable`.

### `GET /files/{file_id}/versions/{version_id}`

- **Response:** `200 {id,file_id,version_number,state,replication_state,size_bytes,media_type,sha256,replicas:{verified,target},created_at,committed_at}`.
- **Access:** authenticated owner; version must belong to file.
- **Errors:** `401`, `404 file_or_version_not_found`, `503 database_unavailable`.

### `GET /files/{file_id}/preview`

- **Parameters:** `version_id?`; defaults to current committed version.
- **Response:** `200 {file_id,version_id,preview_kind:"pdf"|"image"|"video"|"text"|"document"|"unsupported",media_type,size_bytes,content_url,download_url,range_supported,extracted_text?}`. URLs are same-origin authorized API routes, not MinIO endpoints. `extracted_text` is returned only for explicitly supported safe previews and within a bounded response size.
- **Access:** authenticated owner; committed readable version only.
- **Errors:** `401`, `404`, `409 version_unavailable`, `413 preview_too_large`, `415 preview_unsupported` (download remains available), `502`, `503`, `504`.

### `POST /files/{file_id}/versions`

- **Request:** `{size_bytes,media_type?,sha256?}` plus `Idempotency-Key`; creates a new immutable version and upload session. The server captures the current version ID as the upload's `base_current_version_id` (null for the first version).
- **Response:** `201 {version:{id,version_number,state:"initiated"},upload:{id,state,part_size_bytes,expires_at}}`.
- **Access:** authenticated owner; quota checked; existing current version remains available until commit.
- **Errors:** `401`, `404 file_not_found`, `409 idempotency_conflict_or_file_deleting`, `413`, `415`, `422`, `429`, `503 fewer_than_two_storage_services`.

### `POST /files/{file_id}/versions/{version_id}/restore`

- **Request:** `{}` plus `Idempotency-Key`; restores by creating a new version from the selected committed version, never rewrites history. Capture the file's current version ID as the new version's `base_current_version_id` when the restore is accepted.
- **Response:** `202 {new_version_id,job_id,state:"queued",operation_state:"copying"}`. `state` is the persisted `processing_jobs.state`; `operation_state` describes the current restore phase and is not stored as a job-state enum. Subsequent job reads return the persisted job state and measured progress only.
- **Access:** authenticated owner; both versions must belong to file; source must be readable.
- **Errors:** `401`, `404`, `409 source_unavailable_or_idempotency_conflict`, `429 quota_limit`, `503`.
- A concurrency conflict discovered after the accepted restore job starts is reported as job state `failed` with safe error code `concurrent_version_conflict` through `GET /files/{file_id}/jobs`.

## Resumable and multipart uploads

Upload bytes flow through the authenticated API. The backend stages each accepted part on two selected MinIO services, records part/checksum state in MySQL, assembles/commits the immutable object, verifies SHA-256, and queues the third copy. Browser clients never receive MinIO credentials or raw multipart upload IDs.

### `GET /uploads/{upload_id}`

- **Response:** `200 {id,file_id,file_version_id,state,expected_size_bytes,part_size_bytes,parts:[{part_number,size_bytes,sha256,state,verified_copy_count}],expires_at}`.
- **Access:** authenticated upload owner.
- **Errors:** `401`, `404 upload_not_found`, `503 database_unavailable`.

### `GET /uploads`

- **Parameters:** `state?`, `cursor?`, `limit?`.
- **Response:** `{items:[{id,file_id,file_version_id,state,expected_size_bytes,received_bytes?,verified_parts,total_parts,replication_state?,created_at,expires_at}],next_cursor}`. Byte progress is present only when measured; replication is shown only after version finalization.
- **Access:** authenticated owner.
- **Errors:** `401`, `422 invalid_filter_or_cursor`, `503 database_unavailable`.

### `PUT /uploads/{upload_id}/parts/{part_number}`

- **Headers/body:** binary body; `Content-Range: bytes start-end/total`; `Digest: sha-256=<base64 digest>`; `Idempotency-Key`; bounded part size.
- **Response:** `200 {upload_id,part_number,size_bytes,sha256,state:"verified",verified_copy_count}` only after both staged copies verify.
- **Access:** authenticated owner; part number/range must match session bounds.
- **Errors:** `401`, `403 upload_owner_mismatch`, `404`, `409 part_conflict_or_wrong_state`, `413 part_too_large`, `422 invalid_range_or_digest`, `429`, `502 storage_write_failed`, `503 fewer_than_two_storage_services`, `504 storage_timeout`.

### `POST /uploads/{upload_id}/complete`

- **Request:** `{parts:[{part_number,sha256}],sha256}` plus `Idempotency-Key`.
- **Response:** `202 {upload_id,file_id,file_version_id,state:"committed",replication_state:"degraded",verified_replicas:2,target_replicas:3,replication_job_id}` once two copies verify and MySQL commit transaction succeeds. Replication state may already be `healthy` if the third copy completes quickly.
- **Access:** authenticated owner; all expected parts and final digest must match.
- **Errors:** `401`, `404`, `409 incomplete_or_conflicting_upload_or_concurrent_version_conflict`, `422 checksum_mismatch`, `429`, `502`, `503`, `504`.

### `POST /uploads/{upload_id}/pause`

- **Request:** `{}`.
- **Response:** `200 {upload_id,state:"paused",received_parts}`.
- **Access:** authenticated owner; only if upload transport supports resumable pause.
- **Errors:** `401`, `404`, `409 pause_unsupported_or_wrong_state`, `503`.

### `POST /uploads/{upload_id}/resume`

- **Request:** `{}`.
- **Response:** `200 {upload_id,state:"receiving",missing_parts,expires_at}`.
- **Access:** authenticated owner.
- **Errors:** `401`, `404`, `409 expired_or_terminal`, `503`.

### `POST /uploads/{upload_id}/abort`

- **Request:** `{}`.
- **Response:** `202 {upload_id,state:"aborting",job_id}`; `aborting` is persisted on `upload_sessions` while staged-object cleanup runs. The job itself uses the normal persisted job states. After cleanup/reconciliation, the upload transitions to persisted `aborted`; repeated abort is safe and returns the same operation.
- **Access:** authenticated owner; CSRF for cookie auth.
- **Errors:** `401`, `403 csrf_rejected`, `404`, `409 already_committed`, `503`.

Upload completion is idempotent. Under a file-row lock, finalization compares `base_current_version_id` with `files.current_version_id`; it advances the pointer only when they match. If another upload committed first, return `409 concurrent_version_conflict`, leave the newer current version intact, mark the stale upload/version failed, and enqueue idempotent staged/final object cleanup. A crash before MySQL commit leaves an intent that workers/reconciliation can resume or expire; a crash after commit returns the original committed result on retry. An idempotent replay is resolved before checking the current pointer. A mismatched retry payload is `409`, never a silent overwrite. Pause/resume is available only while staged parts and session have not expired.

## File previews and downloads

### `GET /files/{file_id}/content`

- **Parameters/headers:** `version_id?` (defaults to current committed version); support `Range` for media playback; `If-None-Match?`.
- **Response:** authorized binary stream `200` or `206`, with `Content-Type`, safe `Content-Disposition`, `ETag`, `Accept-Ranges` where supported, and `Content-Range` for partial content.
- **Access:** authenticated owner; version committed and at least one verified replica. API proxies/streams or issues a narrowly scoped expiring URL after authorization; never expose credentials or arbitrary keys.
- **Errors:** `401`, `404`, `409 version_unavailable`, `416 invalid_range`, `502`, `503`, `504`.

### `HEAD /files/{file_id}/content`

- **Parameters:** same version selection as GET.
- **Response:** `200` with safe metadata headers; no body.
- **Access:** same authorization and availability checks as GET.
- **Errors:** `401`, `404`, `409`, `503`.

### `GET /files/{file_id}/replication`

- **Parameters:** `version_id?` defaults to current committed version.
- **Response:** `200 {file_id,version_id,state,verified_replicas,target_replicas,replicas:[{node_id,display_name,failure_domain_label,state,verified_at,last_error_code?}],updated_at}`. `replicas[].state` uses the lifecycle defined in [database design](database-design.md); counts include at most one replica per version/node. Never include endpoints, bucket keys, or credentials.
- **Access:** authenticated owner; admin can inspect all files through admin endpoints.
- **Errors:** `401`, `404`, `503 database_unavailable`.

### `GET /files/{file_id}/jobs`

- **Parameters:** `state?`, `cursor?`, `limit?`.
- **Response:** `{items:[{id,kind,state,created_at,updated_at,safe_error_code?}],next_cursor}`; includes only jobs associated with this file and caller.
- **Access:** authenticated file owner; no internal worker payloads.
- **Errors:** `401`, `404 file_not_found`, `422`, `503 database_unavailable`.

## Storage analytics and node monitoring

### `GET /storage/usage`

- **Response:** `200 {owner_id,used_bytes,quota_bytes,file_count,as_of}`; nullable measurements are returned as null, never fabricated.
- **Access:** authenticated user, self only.
- **Errors:** `401`, `503 telemetry_unavailable`.

### `GET /admin/storage/analytics`

- **Parameters:** `from`, `to` (UTC; maximum 30-day range), `interval` (`1m|5m|1h|1d`), `node_id?`.
- **Response:** `200 {series:[{timestamp,capacity_bytes,used_bytes,available_bytes,verified_replica_counts:{one,two,three},upload_bytes_delta,repairs_completed_delta,coverage_state}],as_of,interval,retention_days:30}`. Capacity data comes from `storage_node_samples`; cluster replica counts and interval deltas come from `storage_cluster_samples`. If `node_id` is supplied, capacity fields are for that node while replica distribution remains cluster-wide. Missing data is null/omitted with `coverage_state:"partial"`; do not interpolate missing samples.
- **Access:** admin role; metrics must come from actual storage telemetry.
- **Errors:** `401`, `403 admin_required`, `422 invalid_time_range_or_interval`, `503 telemetry_unavailable`.

### `GET /admin/storage/nodes`

- **Parameters:** `state?`, `cursor?`, `limit?`.
- **Response:** `{items:[{id,name,state,failure_domain_label,capacity_bytes,used_bytes,latency_ms,last_probe_at,verified_replica_count}],next_cursor,as_of}`.
- **Access:** admin role; values are backend telemetry, not UI defaults.
- **Errors:** `401`, `403`, `422`, `503 telemetry_unavailable`.

### `GET /admin/storage/nodes/{node_id}`

- **Response:** `200 {id,name,state,failure_domain_label,capacity_bytes,used_bytes,last_probe_at,probe_history,replica_counts,recent_safe_errors}`. `probe_history` reads `storage_node_samples` and is retained for 30 days.
- **Access:** admin role; no endpoint credentials or secret refs.
- **Errors:** `401`, `403`, `404`, `503`.

### `POST /admin/storage/nodes`

- **Request:** `{name,endpoint_ref,failure_domain_label,region?}`; endpoint must be from approved configuration/secret reference. Never accept raw keys/passwords.
- **Response:** `201 {id,name,state:"disabled",failure_domain_label}`; require a separate explicit enable action after probe.
- **Access:** admin role; audited.
- **Errors:** `401`, `403`, `409 duplicate_node`, `422 endpoint_not_approved`, `502 probe_failed`, `503`.

### `PATCH /admin/storage/nodes/{node_id}`

- **Request:** `{action:"drain"|"disable"|"enable",failure_domain_label?}`. These are commands, not node states. The only persisted node states are `healthy`, `degraded`, `unavailable`, `draining`, and `disabled`.
- **Response:** `202 {node_id,state:"healthy"|"degraded"|"unavailable"|"draining"|"disabled",operation_state?:"probing"|"rebalancing",job_id?}`. For `enable`, retain persisted `disabled` while the probe runs (`operation_state:"probing"`); on success persist the probe-reported `healthy` or `degraded` state, and on failure remain disabled. `drain` persists `draining` while replicas are rebalanced; `disable` persists `disabled` only when its safety preconditions pass.
- **Access:** admin role; audited; enabling requires a successful health probe, and disabling a node with required replicas must first drain/repair them.
- **Errors:** `401`, `403`, `404`, `409 invalid_transition`, `422`, `503`.

### `GET /admin/storage/jobs`

- **Parameters:** `state?`, `kind?`, `cursor?`, `limit?`.
- **Response:** `{items:[{id,kind,state,attempts,available_at,lease_until,last_error_code}],next_cursor}`.
- **Access:** admin role; safe error codes only.
- **Errors:** `401`, `403`, `422`, `503`.

### `GET /health/live` and `GET /health/ready`

- **Response:** liveness `200 {status:"ok"}`; readiness `200 {status:"ready"}` or `503 {status:"not_ready"}`. No dependency names, hostnames, or secrets.
- **Access:** public/internal probe; readiness body is deliberately non-diagnostic.
- **Errors:** readiness returns `503` when required services are unavailable.

## AI Assistant, search, and document operations

### `POST /chat/sessions`

- **Request:** `{mode:"general"|"documents",title?,source_version_ids?:[id],provider_id?,model_id?}` plus idempotency key. Provider/model IDs must be server allowlisted, never credentials.
- **Response:** `201 {id,mode,title,state,source_versions:[{file_id,version_id,name}],created_at}`.
- **Access:** authenticated owner; each source must be owned, committed, and usable.
- **Errors:** `401`, `404 source_not_found`, `409 idempotency_conflict`, `422 invalid_mode_or_model`, `429`, `503`.

### `GET /chat/sessions`

- **Parameters:** `cursor?`, `limit?`, `q?`, `state?`.
- **Response:** `{items:[{id,mode,title,state,updated_at,last_message_preview}],next_cursor}`.
- **Access:** owner-scoped authenticated user.
- **Errors:** `401`, `422 invalid_cursor`, `503`.

### `GET /chat/sessions/{session_id}`

- **Response:** `200 {id,mode,title,state,source_versions,created_at,updated_at}`.
- **Access:** session owner only.
- **Errors:** `401`, `404 session_not_found`, `503`.

### `PATCH /chat/sessions/{session_id}`

- **Request:** `{title?,state:"active"|"archived"?,mode?}`. Mode change must explicitly clear or replace document sources.
- **Response:** `200 {id,mode,title,state,updated_at}`.
- **Access:** session owner; CSRF for cookie auth.
- **Errors:** `401`, `403 csrf_rejected`, `404`, `409 generation_active_or_invalid_transition`, `422`, `503`.

### `DELETE /chat/sessions/{session_id}`

- **Response:** `204`; logically deletes session/history per configured retention policy; idempotent.
- **Access:** session owner; CSRF.
- **Errors:** `401`, `403`, `404`, `409 retention_hold`, `503`.

### `PUT /chat/sessions/{session_id}/sources`

- **Request:** `{file_version_ids:[id]}` replaces the persistent source selection atomically.
- **Response:** `200 {session_id,sources:[{file_id,version_id,name,state}]}`.
- **Access:** session owner; each version revalidated for ownership and availability.
- **Errors:** `401`, `403 csrf_rejected`, `404 source_not_found`, `409 source_unavailable`, `413 too_many_sources`, `422`, `503`.

### `GET /chat/sessions/{session_id}/messages`

- **Parameters:** `before?`, `limit?`.
- **Response:** `{items:[{id,sequence_number,role,content,state,created_at,provider_id?,model_id?,citations:[{file_id,file_version_id,file_name,page?,section?,chunk_id}]}],next_cursor}`.
- **Access:** session owner; citations reauthorized and hidden if source no longer available.
- **Errors:** `401`, `404`, `422`, `503`.

### `POST /chat/sessions/{session_id}/messages`

- **Request:** `{client_request_id,content,attachment_version_ids?:[id],stream?:boolean}`. Mode is taken from the session. `Accept: text/event-stream` streams; otherwise returns a persisted result/job state. General mode performs no retrieval unless sources are explicitly attached/selected.
- **Response:** non-stream `201 {user_message,assistant_message:{id,state:"pending"|"complete",content?,citations?,generation_id?}}`; streaming response contract below.
- **Access:** session owner. Recheck authorization of every attached/selected file version and every retrieved chunk before prompt assembly. CSRF for cookie auth; rate/cost limits apply.
- **Errors:** `401`, `403 csrf_rejected`, `404 session_or_source_not_found`, `409 idempotency_conflict_or_active_generation`, `413 context_too_large`, `422 invalid_mode_or_attachment`, `429`, `502 provider_error`, `503 provider_or_index_unavailable`, `504 provider_timeout`.

### `DELETE /chat/sessions/{session_id}/generations/{generation_id}`

- **Request:** none; client may call after `generation.started`.
- **Response:** `202 {generation_id,operation_state:"cancelling",message_state:"streaming"}`; `cancelling` is a transient acknowledgement, not a persisted message state. Persist `cancel_requested_at` and leave the message `streaming` until the worker observes cancellation; then persist `cancelled` and emit `generation.cancelled`. If completion wins the race, persist `complete` and return/emit the completed outcome. Repeating cancellation is safe.
- **Access:** session owner; cancellation is scoped to that session.
- **Errors:** `401`, `403 csrf_rejected`, `404`, `409 already_complete`, `503`.

### `POST /search`

- **Request:** `{query,folder_id?,file_version_ids?:[id],media_types?:[string],limit?,cursor?}`.
- **Response:** `200 {items:[{file_id,file_version_id,file_name,score,snippet,source_locator:{page?,section?,offset?},chunk_id}],next_cursor,as_of}`.
- **Access:** authenticated owner; filter by ACL before text fetch/prompt; every result rechecked in MySQL.
- **Errors:** `401`, `404 folder_or_source_not_found`, `413 query_too_large`, `422`, `429`, `503 index_unavailable`, `504 embedding_timeout`.

### `POST /files/{file_id}/summary`

- **Request:** `{version_id?,force?:boolean}` plus idempotency key; default is current committed version.
- **Response:** `202 {job_id,file_id,version_id,state:"queued"}` or `200 {summary_id,version_id,state:"succeeded",summary,citations,model_id}` if already complete. Summary status uses the processing-job vocabulary (`queued`, `running`, `retry_wait`, `succeeded`, `failed`, `cancelled`); completed results are stored in `document_summaries`, with citations from `document_summary_sources`, and returned by the job-status result contract.
- **Access:** file owner; policy must allow external processing where applicable.
- **Errors:** `401`, `404`, `409 version_unavailable`, `413 document_too_large`, `415 unsupported_document`, `422`, `429`, `503 provider_or_worker_unavailable`.

### `POST /ai/comparisons`

- **Request:** `{file_version_ids:[at least two IDs],question?}` plus idempotency key.
- **Response:** `202 {job_id,state:"queued",source_versions:[{file_id,version_id,name}]}`; completion is read from `/ai/jobs/{job_id}`.
- **Access:** authenticated user; all versions owner-authorized, committed, and within configured source/context limits.
- **Errors:** `401`, `404 source_not_found`, `409 source_unavailable`, `413 context_too_large`, `422 too_few_sources_or_invalid_request`, `429`, `503 provider_or_worker_unavailable`.

### `GET /ai/jobs/{job_id}`

- **Response:** `200 {id,kind,state,progress?,result?:{summary?,comparison?,citations?},safe_error_code?,created_at,updated_at}`. Summary results come from `document_summaries` and citations from `document_summary_sources`; comparison results come from `document_comparisons` and citations from `document_comparison_sources`. Progress is omitted unless measured.
- **Access:** owner of every associated file/session; admin may inspect safe job metadata.
- **Errors:** `401`, `404 job_not_found`, `503`.

## Streaming event format

Use authenticated HTTPS `fetch()` streaming with `Content-Type: text/event-stream`, `Cache-Control: no-store`, and proxy buffering disabled. `POST` streaming is preferred over native `EventSource` because requests require bearer/CSRF headers. UTF-8 SSE frames are `event: <name>\ndata: <JSON>\n\n`.

1. `generation.started`: `{generation_id,session_id,user_message_id,assistant_message_id}`.
2. `message.delta`: `{generation_id,assistant_message_id,sequence,delta}`; append plain text only.
3. `citation`: `{generation_id,citation:{file_id,file_version_id,file_name,chunk_id,page?,section?,source_locator}}`; each citation is validated against retrieved authorized chunks.
4. `generation.completed`: `{generation_id,assistant_message_id,state:"complete",usage?,citations:[...]}`.
5. `generation.error`: `{generation_id,assistant_message_id,code,safe_message,retryable}`; no provider internals.
6. `generation.cancelled`: `{generation_id,assistant_message_id,state:"cancelled"}`.
7. `heartbeat`: `{generation_id}`; no content.

`generation_id` is the persisted `assistant_message_id` UUID and is the cancellation identifier; no separate generation row is implied. The first event supplies it. Disconnect attempts cancellation, but clients should call the DELETE cancellation route if the connection is already closed. Persist user and assistant rows before streaming; persist final state/citations on completion. A partial assistant response is explicitly `interrupted`/`cancelled`, never `complete`. Retrying uses the same `client_request_id`; replay the stored result or current generation instead of creating duplicate messages. Errors before the stream begins use the common JSON error envelope; after it starts, use `generation.error` and close the stream.

## Replication, idempotency, and consistency invariants

- Upload session and idempotency records are committed in MySQL before accepting parts. Identical part retries return the original verified result; conflicting digest/size returns `409`.
- File version becomes committed/available only after two distinct MinIO services have verified SHA-256 and size. The third copy is asynchronous; return truthful `degraded` state until verified. Never claim physical host independence for same-host development instances.
- Every storage copy uses an opaque server-generated object key. User-supplied names never become keys. Missing/corrupt replicas, node states, and analytics come from backend records/telemetry only.
- Deletion immediately blocks downloads/search, then asynchronously removes replicas, chunks, embeddings, summaries, session source links, attachments, and citations according to retention policy. MySQL/MinIO operations are reconciled; retrying delete/repair is idempotent.
- CORS is not authorization. All user and AI retrieval routes recheck ownership/tenant ACL in MySQL before data leaves the backend.

## OpenAPI, sequencing, and unresolved decisions

Generate OpenAPI from FastAPI and version the response models. Follow the development roadmap's dependency order: auth/session and owner middleware; folders/files/versions; upload sessions and file streams; replication/telemetry; chat persistence, provider boundary, and streaming foundation; document extraction/chunking/embeddings; semantic search and authorization-aware retrieval; PDF summarization; then multi-document comparison and document-grounded chat. The frontend must not assume a capability or telemetry field before its contract exists.

Before implementation, decide: registration/password recovery and MFA policy; exact production origin list; maximum upload/file/part/source sizes and upload-session TTL; supported preview formats and range limits; folder-delete/move behavior beyond the empty-folder rule; replica detail visibility to ordinary users; approved provider/model allowlist and chat rate/cost limits; whether comparisons are async-only; stream proxy timeout/heartbeat settings; conversation deletion/retention and source-deletion redaction; tenant/sharing model. Storage dashboard telemetry source and 30-day retention are defined in [database design](database-design.md); operational metrics ownership and alert routing still require an operator. Do not expose unrestricted node administration or arbitrary provider/model choices.
