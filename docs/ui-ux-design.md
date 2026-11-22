# IFSS UI/UX Design Specification

**Status:** Approved design direction; implementation awaits explicit user approval.
**Design concept:** Calm Precision — a distinctive, responsive workspace for file work and distributed-storage operations.

## 1. Product design philosophy

IFSS should feel like a premium, dependable work tool: quiet enough for sustained file work, precise enough for storage operations, and approachable enough for AI-assisted research. Take cues from modern SaaS products for speed and clarity without reproducing their layouts or signature components.

Use whitespace, typography, meaningful density, and subtle dividers to establish hierarchy. Prefer a file list, timeline, or chart over a grid of boxed cards. Use color sparingly. A small three-point “replica signal” motif may identify the three-copy storage model; it must always be accompanied by a readable label or value.

## 2. Visual identity and design tokens

### Color themes

| Token role | Light theme | Dark theme | Use |
|---|---|---|---|
| `canvas` | `#F6F5F1` | `#17191F` | Main application background |
| `surface` | `#FFFFFF` | `#20232B` | Menus, dialogs, preview surfaces |
| `surface-muted` | `#EFEEE9` | `#262A33` | Selected rows and quiet controls |
| `text-primary` | `#20232A` | `#F2F3F6` | Headings and primary content |
| `text-secondary` | `#69707D` | `#A6ABB7` | Metadata and supporting text |
| `divider` | `#E5E3DC` | `#343843` | Section and row boundaries |
| `accent` | `#5263A8` | `#9BAAFF` | Primary actions, focus, selection |
| `success` | `#287A59` | `#72C99F` | Verified/healthy states |
| `warning` | `#A96B18` | `#F1B85D` | Degraded/pending attention |
| `danger` | `#B34D4D` | `#F08080` | Failed/lost/destructive states |

Use semantic color with text and icon cues; never communicate state by color alone. Validate contrast for text, controls, focus indicators, charts, and both themes against WCAG AA before implementation.

### Type, spacing, and shape

- Use Inter or Geist with a restrained hierarchy: compact utility labels, readable body text, and clear page titles. Use tabular numerals for sizes, dates, capacities, and counters.
- Base spacing on a 4px unit, with common 8/12/16/24/32px steps. Align controls and content to a consistent grid.
- Keep radii restrained (roughly 6–12px). Use subtle borders and low-contrast shadows only where elevation clarifies layering.
- Use Lucide icons at consistent 16/20px sizes. Pair less familiar icons with text labels and accessible names.

## 3. Navigation and application shell

### Desktop

- Persistent left rail with IFSS mark/workspace selector and primary destinations: **Overview**, **Files**, **AI Assistant**, **Storage**, and **Activity**.
- Folder navigation and folder management live within Files rather than creating a second global navigation system.
- Settings, profile, help, and theme controls sit at the rail bottom.
- Profile/settings expose the signed-in user's profile and password controls; administrative user or role management is not part of the v1 UI. Theme preference may be stored client-side and is not an authorization setting.
- A compact top command area provides global search, `Ctrl/⌘+K`, and a prominent Upload action.

### Tablet and mobile

- Tablet: collapsible rail and contextual drawers for folders, filters, and details.
- Mobile: compact top bar and bottom navigation for primary destinations; use full-height sheets for folder trees, file details, and upload queue.
- Preserve the same labels, ordering, and actions across breakpoints. Avoid hiding critical node health, replication status, or upload errors on narrow screens.

## 4. Dashboard

Lead with a page title/greeting and one primary action. Use an asymmetric, editorial layout rather than equal card tiles:

- Main column: recent files in a compact list, followed by upload and processing activity.
- Secondary column: storage-use visualization, a node-health summary, and a short list of items requiring attention.
- Include purposeful empty states for a new account, no recent files, no uploads, or no alerts. Explain the next action without inserting sample metrics.

Only show values returned by the backend. Show the data timestamp where freshness matters. If the API is unavailable or has no measurement, display **Unavailable**, **Not reported**, or an empty state—not zero, a guessed value, or a healthy default.

## 5. File Explorer and folder management

### Layout and interaction

On wide screens, use three working regions:

```text
Folder tree             File list and controls             Details / preview
220px                   Flexible central area               ~320px
```

- Folder tree: expandable hierarchy, clear current location, create/rename/move actions, and a compact overflow menu. On small screens, open it as a drawer.
- File area: breadcrumbs, search, filter/sort controls, list/grid toggle, and a dense list as the default. Rows show type/name, modified time, size, and backend-reported availability/replication state.
- Details region: selected file information, preview, version history, and replica status. On mobile, open as a sheet or dedicated route.
- Support multi-select, keyboard navigation, accessible context menus, and explicit confirmation for destructive or bulk actions. The bulk move/delete contract returns a separate result for every file; present completed moves, accepted asynchronous deletions, and failures distinctly, with aggregate counts and per-item safe error text. Partial success must remain visible rather than being reported as all-or-nothing. Offer retry for failed items only as a new idempotent request. Dragging files into folders must also have a non-drag alternative.

Use content-first rows and light separators. Keep folder and file actions discoverable without adding a toolbar of unrelated icon buttons.

### File preview

Use a focused preview route or panel with a consistent header: filename, version, download, and accessible close/back action. Provide:

- Integrated PDF viewer with page navigation and zoom controls.
- Image preview with fit/zoom behavior and accessible alternative text where available.
- Document preview for supported extracted/document formats.
- Video player with keyboard-accessible controls and supported range playback.
- Text and code preview with readable wrapping or horizontal scrolling and language-neutral monospace styling.
- Unsupported formats: show type/size and a clear **Download file** action.

All preview content must be fetched through an authorized API path or a narrowly scoped, short-lived access mechanism consistent with the system architecture. Never put MinIO service credentials, OpenAI keys, or unrestricted object paths in the browser. Show a useful unsupported, loading, permission, and retrieval-error state.

## 6. Upload Manager

Make upload a persistent, inspectable queue rather than a disappearing toast. Support drag-and-drop and file-picker selection for multiple files. The queue exposes active, completed, and failed items with filename, transmitted bytes/total when known, phase, retry action, and resulting file link.

Represent upload and storage lifecycle separately:

1. Waiting/selected.
2. Transferring (show measured byte progress when available; otherwise use indeterminate progress).
3. Verifying checksum.
4. Replicating (show verified replica count and target only when returned by the backend).
5. Available, degraded, or failed.

Allow retry for recoverable failures with the same idempotency intent. Offer pause/resume only if the upload protocol supports resumable transfer; otherwise do not show those controls. A transfer completion is not replication completion. Never invent percentages or show “fully replicated” before verification is reported.

## 7. AI Assistant workspace

The dedicated **AI Assistant** section is an integrated research and conversation workspace with full LLM support, not a generic chat bubble. Its visual structure is a conversation/history rail, a central conversation/evidence canvas, and a contextual source panel that can collapse on smaller screens. A visible mode/scope label distinguishes general AI from document-grounded answers.

### Conversation modes and source selection

- **General AI:** conversational LLM mode without document retrieval unless the user explicitly attaches or selects sources.
- **Documents:** retrieval-augmented conversation over selected authorized files. Make the active scope visible before a question is sent.
- **New chat** starts a conversation with an explicit mode/scope choice. History supports search, rename, archive, and delete according to backend capabilities.
- Attach existing files or select sources from the user's authorized file explorer. A new upload enters the Upload Manager first and becomes selectable only after the backend reports a usable processing state.
- Support PDF summarization from the PDF preview and AI Assistant. Summaries are version-scoped and display job status and source citations when provided.
- Support multi-document comparison by selecting two or more authorized sources. Show which documents are included and cite each comparison claim.
- Provide semantic search as a first-class workspace action with result snippets, source filters, and navigation to the relevant file/page/section.

### Conversation and streaming

Stream model output into the conversation with a visible generating state, stop control, and recoverable interrupted/error state. Distinguish partial streamed text from a completed answer. Render assistant/user messages with safe Markdown, including accessible headings, lists, links, tables, and syntax-styled code blocks with a keyboard-accessible copy action. Sanitize rendered content and never execute embedded HTML or scripts. Render citations only from source references returned/validated by the backend; each citation opens the exact file version and page/section where available. General AI responses have no document citations unless a source was selected.

All document retrieval and citation resolution must be authorization-aware on the backend for every request. The UI's selected source list is a usability control, never an authorization boundary. Do not send API keys or provider credentials to the browser. Do not expose another user's filenames, snippets, or citation metadata in search, history, error, or streaming responses.

## 8. Storage analytics and distributed node monitoring

### Analytics

- Capacity trend over time.
- Stacked used/available capacity by node or storage pool.
- Distribution of files by verified replica count (one/two/three or configured target).
- Optional upload/repair throughput and latency trends when backend telemetry exists.

Pair charts with a text summary or accessible data table. Legends, tooltips, keyboard exploration, and color-independent distinctions are required. Handle missing samples and stale telemetry explicitly; do not interpolate a value that suggests a measurement was received.

### Node health

Use a compact node table with backend-reported state, last successful probe, capacity, latency, and repair activity. Reuse states defined by the storage architecture: `healthy`, `degraded`, `unavailable`, `draining`, and `disabled`. Show failure-domain label and distinguish service/container availability from host/zone risk. Replication indicators show verified copies, not merely planned writes.

Show cluster analytics and node tables only to administrators, matching the `/admin/storage/*` API authorization. Non-admin users see their own quota/usage and per-file replica status only; do not show cluster node data or admin controls.

Never hardcode node counts, health, storage usage, or replication success. Loading displays skeletons; no-data displays “No telemetry received”; stale data displays its age; API errors display unavailable state with retry. Empty, stale, and failed data must not be styled as healthy.

## 9. Interaction and accessibility system

- Use short, purposeful transitions for navigation, drawers, selection, and upload state changes. Respect `prefers-reduced-motion`; no motion is required to understand state.
- Provide keyboard shortcuts for global search, upload, new chat, and closing dialogs/panels. Show shortcut hints in menus and settings; allow conflicts to be avoided.
- Context menus must be keyboard reachable and work on touch through equivalent action sheets.
- Toasts confirm transient actions and errors, but persistent upload/job state remains in its manager or activity view. Do not rely on a toast for critical or destructive confirmation.
- Skeletons match content geometry and are used only while real data is loading; do not place fake values inside them.
- Dialogs use accessible names, focus trapping, Escape behavior where safe, focus restoration, and explicit destructive-action labels.
- Ensure logical landmarks, heading order, visible focus, screen-reader status announcements for uploads/streaming/replication, adequate touch targets, and accessible chart summaries.

## 10. Reusable component system and React boundaries

Organize the eventual frontend by product feature while sharing a small design-system layer:

- **Shell:** app navigation, command/search bar, theme, responsive panels.
- **Files:** folder tree, file table/grid, row actions, preview adapters, version timeline.
- **Uploads:** drop zone, queued item, transfer progress, replication progress, retry controls.
- **AI:** conversation list, mode/scope picker, source selector, streamed message, citations, comparison view, summary view.
- **Storage:** metric/chart primitives, node table, health badge, replica indicator, event timeline.
- **Shared accessible primitives:** buttons, inputs, menus, tabs, dialogs, drawers/sheets, toasts, skeletons, empty/error states.

Keep design tokens centralized for color, type, spacing, radius, elevation, focus, and motion. Components consume typed API state and present `loading`, `empty`, `stale`, `error`, and success states explicitly; avoid duplicating domain status logic in visual components.

## 11. Architecture and API alignment

The visual design follows the current architecture: React calls FastAPI; MinIO and OpenAI credentials remain server-side; MySQL owns file/chat metadata; FAISS is a derived index; document answers use authorization-filtered retrieval and citations.

The API roadmap specifies general-versus-document chat modes, source selection and attachments, conversation history actions, streaming and cancellation, multi-document comparison, PDF summary job status, supported preview/range delivery, and upload pause/resume capability. Frontend implementation should follow these contracts and degrade honestly when an API capability or telemetry field is unavailable.

## 12. States required for every major feature

- **Loading:** content-shaped skeleton or explicit progress, without invented data.
- **Empty:** explain why the view is empty and provide one relevant next action.
- **Error:** safe message, request/correlation ID where useful, retry when idempotent.
- **Stale/unavailable:** show last-update time and distinguish from healthy/zero.
- **Success:** confirm completion and provide the resulting file, conversation, or report link.

This specification defines product behavior and visual direction only. Frontend implementation, dependencies, and API changes remain pending explicit approval.
