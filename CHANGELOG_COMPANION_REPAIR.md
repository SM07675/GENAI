# Companion Repair — Audit & Fix Log

Scope: repaired the existing project in place. No new project was created,
nothing was rebuilt from scratch, no mock/fake UI was added.

## Verified working (contrary to the original brief's assumption)

- The Companion **is** a real separate `BrowserWindow` — `alwaysOnTop('screen-saver')`,
  `skipTaskbar: true`, `focusable: false`, click-through via `setIgnoreMouseEvents`,
  and `showInactive()` so it never steals focus from Chrome/VS Code/etc.
  (`electron/main.cjs`)
- NVIDIA vision is a hosted API call (`nvidia/nemotron-nano-12b-v2-vl` via
  `integrate.api.nvidia.com`), not local GPU inference, and it already sends
  images correctly as base64 `image_url` multimodal content, not plain text.
  (`backend/app/companion/vision.py`)

## Bugs found and fixed

1. **Fake "ACTIVE" status.** The UI flipped to "active" the instant a button
   was clicked, with zero confirmation the window existed or was visible.
   `"starting"` was declared in the type union but never used anywhere.
   - Fixed: `companion:show`/`companion:hide` are now `ipcMain.handle` (not
     `ipcMain.on`), returning real verified state (`{ success, visible, error }`).
   - `useCompanion.ts`'s `startCompanion()`/`stopCompanion()` are now async,
     transition `off → starting → active` (or back to `off` on failure) only
     after the main process confirms the window.
   - `App.tsx` and `CompanionConfigView.tsx` now call `startCompanion()`/
     `stopCompanion()` instead of writing `companion.setMode('active')`
     directly — that direct write was the actual root cause of the lie.
   - Both toggle buttons now show a disabled "⏳ STARTING/STOPPING" state
     mid-transition instead of jumping straight to ACTIVE.

2. **Dragging didn't work.** `DesktopCompanionOverlay.tsx` had a doc-comment
   claiming "draggable with position persistence" but no `-webkit-app-region:
   drag` and no mousedown/mousemove handlers anywhere.
   - Fixed: real drag-to-move, implemented by moving the actual OS window
     (`genie.setCompanionPosition` on `mousemove`, using `screenX/screenY`
     deltas from `genie.getBounds()`), not a CSS position. A small movement
     threshold distinguishes a click (opens the expanded card) from a drag.

3. **Position never survived a restart.** `companionPosition` in `main.cjs`
   was an in-memory variable only.
   - Fixed: added `companion-settings.json` in `app.getPath('userData')`,
     debounced writes (250ms, since dragging fires many updates/sec), loaded
     on startup and used as the initial window position/size.

4. **Found while fixing #2 — a real architecture bug:** `companionStore.position`
   (persisted to `localStorage`, shared across windows since same origin) was
   being used as CSS coordinates in *two different-sized windows*: the tiny
   280×340 overlay `BrowserWindow`, and the full main window (where
   `CompanionWindow.tsx` renders a web-fallback preview). A position saved in
   one context could put the avatar completely outside the visible area in
   the other.
   - Fixed: the overlay now anchors the avatar at a fixed point in its own
     window and drives *window* position via IPC only. `companion.position`
     in the store is no longer read by the overlay at all — it's now purely
     the main-window preview's own concern.

5. **Overlay UI didn't match the rest of the app.** `GenieFace.jsx`'s
   `EXPRESSION_THEME` table and `DesktopCompanionOverlay.tsx` were on a
   leftover dark-navy/near-black + teal (`#5EEAD4`) palette, while the rest
   of the app already has a proper light sky-blue glass system (`.sky-glass`
   in `index.css`). This is exactly the "dark rectangle" mismatch visible in
   the screenshot.
   - Fixed: re-themed both files to the same light sky-blue/white glass
     language — face gradients, inset highlight (was a dark vignette, now a
     glass highlight), bubble/hover-bar/expanded-card/context-menu
     backgrounds and text colors, all switched from dark-on-dark to the
     existing design system's palette.

## Found, not fixed (flagged for you to decide on)

- `electron/src/main/*.ts` (`window-manager.ts`, `ipc.ts`,
  `backend-manager.ts`, `shortcuts.ts`, `tray-manager.ts`) is **dead code** —
  not referenced by any build config or import. `main.cjs` is the real,
  live entry point. Left alone rather than deleting blind; worth a decision
  on whether to remove it or finish migrating to it.
- `data/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf` is 71MB. A real
  Q4_K_M-quantized 7B GGUF is normally ~4GB — this looks like a truncated or
  placeholder download. Worth checking whether the local-LLM fallback path
  actually works.
- The "Always on Top" toggle in `CompanionConfigView.tsx` is a static switch
  with an empty `onChange` — not wired to anything (though not *false*,
  since always-on-top actually is hardcoded on in `main.cjs`, it's just
  inert as a control).
- 21 pre-existing TypeScript errors in `src/components/Scene/*.tsx` and
  `CharacterModel.tsx` — a `@react-three/fiber` JSX-intrinsics typings
  mismatch, unrelated to companion work, present before this pass.
- Voice-event wiring (wake-word → waking, STT-start → listening, etc.),
  barge-in, and the vision screenshot pipeline's error/health-check UI
  weren't in scope for this pass — the brief's items #24–#44 are still open.

## How this was verified

- `npm install` (skipping the Electron binary download, not needed for this
  check) + `npm run build` — succeeds, 422 modules, no errors.
- `npx tsc --noEmit` — 21 pre-existing errors, all in files untouched by
  this pass; zero new errors in any edited file.
- `node --check` on `main.cjs`, `preload.cjs`, `companion-preload.cjs` — all
  pass.
- **Not verified:** actually launching the packaged app on Windows, visually
  confirming always-on-top behavior over real applications, or testing drag
  by hand — this environment can't run a Windows GUI. Please smoke-test the
  acceptance flow (§59 of the original brief) once you've pulled this down.
