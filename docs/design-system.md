# Design system: "Paper & Ink"

Simple, calm, readable. Every page is built from the shared pieces below; a new page should need **no new colours and few new components**.

## Principles

1. **Calm by default.** Warm off-white paper, white cards, near-black ink. Colour is rare, so it means something.
2. **One accent.** Indigo is the only "brand" colour: primary buttons, the active nav item, focus rings.
3. **Score colours are reserved for scores.** Green / amber / red appear only on scores, outcomes and verdicts, never as decoration.
4. **Content first.** Generous spacing, short labels, numbers in `tabular-nums`, nothing that isn't needed to decide.
5. **Mobile first.** Every view works at 390 px with no horizontal scrolling; wide tables become stacked cards below `md`.
6. **No admin data on user pages.** Cost and model live in the ledger / CLI / a future admin view.

## Tokens (`frontend/src/styles/globals.css`)

| Token | Use |
|---|---|
| `background` / `foreground` | page paper and ink |
| `card` | surfaces (cards, panels) |
| `primary` | the one accent: main actions, active nav, focus `ring` |
| `secondary`, `muted`, `muted-foreground` | quiet fills and secondary text |
| `accent` / `accent-foreground` | indigo tint for selected states |
| `destructive` | errors and "Not eligible" |
| `score-strong` / `score-medium` / `score-weak` | scores ≥ 75 / ≥ 50 / below, outcomes, verdicts |
| `--radius` 0.75 rem | all corners (`rounded-md/lg/xl` derive from it) |

Fonts: the system UI stack (`font-sans`), headings `tracking-tight`. Dark-mode values exist for every token (`.dark`).

**Rule:** components use these semantic classes only (`bg-primary`, `text-muted-foreground`, `bg-score-strong/12`, ...). No hex, rgb or Tailwind palette colours (`bg-blue-500`) in components. A restyle is an edit to `globals.css`.

## Shared components

Generic (`src/components/ui/`):

| Component | Use it for |
|---|---|
| `Button` (`buttonVariants` for links) | every action; one `default` (indigo) button per view |
| `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent` | every content block |
| `Badge` (`tone`: neutral, accent, strong, medium, weak, danger, outline) | short status labels |
| `PageHeader` | the title block at the top of every page |
| `EmptyState` | any list with nothing in it, with the next action |
| `Skeleton` | loading placeholders shaped like the content |

Score display (`src/components/score/`):

| Component | Use it for |
|---|---|
| `ScoreRing` (`size`: `sm` in lists, `lg` on a result) | every score shown anywhere |
| `VerdictBadge` | every verdict tier |
| `scoreBand()` | the band behind any score colour (thresholds match the backend verdicts) |

## Patterns

- **Page:** `PageHeader` → content `Card`s, `space-y-6`.
- **Lists:** a `Card` with `divide-y` rows; each row is one link with a `ScoreRing size="sm"`, title + muted meta line, a badge, and a chevron.
- **Expandable groups:** a full-width button with `aria-expanded` and a rotating chevron.
- **Loading / empty / error:** `Skeleton`s shaped like the content / `EmptyState` with an action / a one-line `role="alert"` message.
- **Tables:** desktop table inside `overflow-x-auto`, plus a stacked card list for phones (`md:hidden` / `hidden md:block`).
- **Query keys** shared between features live in `src/lib/api/query-keys.ts`; dates go through `formatDateTime()` in `src/lib/format.ts`.

Before adding a component, check this list; if something new is reusable, put it in `components/` and add it here.
