# CLIPER Studio — web product brief

## Product direction

A quiet production workspace for a single operator: browse sources, make editorial decisions, finish assets and manage distribution. Warm paper surfaces, dark ink, thin rules, restrained green status accents. No glow, gradient cards, fabricated analytics or decorative dashboards. Content previews provide the color. Use typography, spacing and grouping to establish hierarchy.

## Information architecture

- **Studio:** live project library, URL intake, uploads, search/filter, queue state and job actions.
- **Project workspace:** source context, analyzed coverage, shortlist, hook/timestamp/caption/music editing, selective rendering, video preview, transcript and exports.
- **Carousels:** generation, per-niche brand/reference settings, running jobs and finished slide review.
- **Publishing:** approval inbox, scheduled queue, caption editing, scheduling, reject/approve and published history.
- **Music:** category library, audio previews and upload.
- **Settings:** all per-owner engine/editing preferences, AI providers, feature switches, automation, connections and system configuration/status.

Use one persistent left navigation, a thin global header, and a contextual detail panel. Inputs have visible labels. Primary actions occupy predictable locations. Forms save deliberately with success/error feedback; polling never replaces a dirty draft. Destructive or publishing decisions identify the exact item. Status is expressed with text as well as color. Dialogs support Escape, focus containment and return focus. Mobile uses a collapsible navigation and stacked detail view.

## Implementation

React + TypeScript + Vite, custom CSS tokens and Lucide icons. FastAPI serves the built frontend and a same-origin API over the existing stores, pipeline and publication state machine. Avoid a second database or engine rewrite. Browser sessions are protected by a local launch token, HttpOnly cookie and CSRF header. Bind only to loopback. API responses do not expose credentials. The worker lock remains authoritative: attach to an existing bot, or process web-origin jobs locally. Starting the preview for development does not start production or publish anything.

Web-origin jobs use `chat=0`; Telegram jobs retain their chat destination. Standalone web workers claim web-origin work only. With the updated Telegram bot running, it can process both, delivering web outputs locally. Media endpoints resolve approved artifacts within their managed roots; they do not serve arbitrary filesystem paths. Network configuration is a local control plane, not a public multi-tenant service.

## Research decisions

Linear's documented redesign emphasizes clearer hierarchy, stable navigation, alignment and deliberate density. Those principles inform this workspace; CLIPER keeps its own lighter editorial identity. [Linear design process](https://linear.app/now/how-we-redesigned-the-linear-ui), [2026 refinement](https://linear.app/now/behind-the-latest-design-refresh).

React documents Vite for adding a client interface to an existing system. CLIPER already has a Python engine and needs no SEO or server-rendered marketing pages; a typed client and a small API keep responsibilities clear. [React existing-project guidance](https://react.dev/learn/add-react-to-an-existing-project), [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/).

WCAG 2.2 guides visible keyboard focus, target sizes, contrast, non-color status and alternatives to drag-only interactions. Implementation tests cover keyboard/dialog behavior and responsive overflow; this is not a claim of a complete accessibility certification. [WCAG 2.2](https://www.w3.org/TR/WCAG22/).

## Acceptance checks

Real stored data, functional actions and truthful empty states. API tests for authentication, CSRF, ownership, path containment, validation, state transitions and settings persistence. Frontend typecheck/build. Browser checks for navigation, intake validation, preferences, dialogs, previews, mobile layout and console errors. Production queues remain untouched during verification.
