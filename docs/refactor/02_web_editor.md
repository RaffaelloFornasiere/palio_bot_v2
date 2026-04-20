# Web Editor — Manual JSON Editing

## Goal
Let a non-technical user edit `leaderboard`, `palio_games_status`, calendar,
and `palio` without seeing raw JSON. Changes commit through core so Telegram
and CLI pick them up automatically.

**Depends on** [`01_core_service_split.md`](./01_core_service_split.md). The
editor is just another core client.

## UX principles
- One hand-crafted screen per file — no generic tree editor, no `@rjsf`.
- Italian UI copy (matches existing tool messages).
- Explicit Salva / Annulla. No autosave — too dangerous for this data.
- Live lock banner: "In modifica da Telegram — sola lettura."
- Raw-JSON Monaco tab as escape hatch for power users.

## Per-file UI

**Leaderboard** — single table: position, contrada, points. Inline edit
points, drag to reorder, add/remove with village picker from the whitelist.

**Games status** — card per game. Each card: status chip, ranked scores
list (drag to reorder, inline edit), collapsible penalties/bonuses section.
Progressive games get a round tabs variant of the scores component.

**Calendar** — agenda list grouped by date. Each row: date + start/end time
pickers + game dropdown + location.

**Palio spec** — mostly read-only. Editable bits: year, contrade chip list
(with "still referenced by X" warning on removal). Rest behind a raw-JSON tab.

## Chrome
Sidebar with 4 tabs. Top bar: year selector, session status
("3 modifiche non salvate" / "In modifica da Telegram"), Salva / Annulla.
Toasts for `file_changed` events from other sessions.

## Save flow
1. "Modifica" → `POST /sessions` + `acquire/{file}` (may 409 → show lock banner).
2. User edits in a local draft (Zustand/useReducer).
3. "Salva" → PUT draft → commit. Draft cleared.
4. "Annulla" → discard session.

WS `/events` drives live cache invalidation (TanStack Query).

## Stack
React 18 + TS + Vite (already in `website/`). TanStack Query for server
state, TanStack Table for grids, React Hook Form + Zod for small forms,
`@dnd-kit/core` for drag-reorder, Monaco lazy-loaded for raw JSON, `ajv`
with Italian messages for client-side validation using core's
`/api/schema/{file}`. Extend the existing React app with an `/edit` route
behind a token prompt.

## Effort
- Leaderboard: 1d
- Games status: 1.5d
- Calendar: 0.5d
- Palio spec (read + contrade editor): 0.5d
- Chrome, WS, Query wiring: 0.5d
- Monaco fallback: 0.25d
- Auth prompt, polish, copy: 0.75d
- **Total: ~5 days** (assumes core is in place).

## Phases
1. Leaderboard only — fastest visible value.
2. Games status.
3. Calendar + palio spec.
4. (Optional) live bot-activity side panel via `agent_update` events.

## Open questions
1. **Calendar file**: embedded in `palio.json` or split to `calendar.json`?
   → **split it out**; its edit cadence is different.
2. **Palio editability**: today `allow_edit=False`. Web needs partial write.
   → split the flag into `allow_agent_edit` vs `allow_human_edit`.
3. **Village whitelist edits**: removing a contrada still referenced elsewhere
   → **block with a modal** listing every reference.
4. **Mobile**: read-only is enough; editing desktop-only.

## Non-goals
Collaborative editing, committed-change undo/history (git is the fallback),
user accounts/roles, mobile editing.
