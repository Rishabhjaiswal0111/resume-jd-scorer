# Design system: "Paper & Ink"

References: hiring scorecards (key takeaways, strengths / concerns, colour-coded per-attribute ratings, evidence for every rating, questions for the next round) and clean SaaS UIs (whitespace over boxes, subtle borders, one accent, Inter).

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

Font: **Inter** (self-hosted via `@fontsource-variable/inter`, system UI stack as fallback), headings `tracking-tight`, weights 400 / 500 / 600 only. Dark-mode values exist for every token (`.dark`).

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
| `FileDropzone` | every file input: drag and drop + keyboard/click fallback + file chip with remove |
| `SegmentedControl` | 2-4 mutually exclusive options (e.g. PDF / Paste text) |
| `Stat` | a labelled number in a `<dl>` (headline counts) |
| `Input`, `Textarea` | every text field (same border, radius and focus ring) |
| `Select` | a native `<select>` styled like `Input` (best on phones and screen readers) |
| `FilesDropzone` | uploading one or many files at once; `compact` makes it a single row above a list |
| `DocumentPreview` | a stored PDF shown inline with a PDF / Text switch and "Open original"; text by default below `md` (phones don't render PDFs inline) |
| `Tabs` | page sections (underline tabs with optional counts); the caller renders the panel |
| `HighlightedText` | search snippets: `\u0001…\u0002` markers become `<mark>`, never HTML |

Score display (`src/components/score/`):

| Component | Use it for |
|---|---|
| `ScoreRing` (`size`: `sm` in lists, `lg` on a result) | every score shown anywhere |
| `VerdictBadge` | every verdict tier |
| `RatingIcon` + `ratingLabel()` | a criterion's outcome: green check / amber minus / red cross / grey question, with words ("Meets", "Partly meets", ...) |
| `scoreBand()` | the band behind any score colour (thresholds match the backend verdicts) |

Brand (`src/components/brand/`): `Logo` (mark + name) in the header.

## Patterns

- **Recruiter language, not engine language.** Strengths / Concerns (not pros / cons), "Questions for the screening call", "Meets / Partly meets / Does not meet". Engine details (points, weights, run id, engine version) live in the collapsed **Scoring details** section.
- **Counts must agree everywhere.** Items still to verify are counted apart ("3 of 4 met · 1 to verify"); red-flag groups say "N clear", never "met".
- **Status is quiet when healthy.** The API status shows only when the service is unreachable.
- **Long work shows honest progress:** a spinner, a plain description of what is happening and a skeleton of the result. No fake percentages.
- **Page:** `PageHeader` → content `Card`s, `space-y-6` (`space-y-8` on the score page).
- **Result (scorecard):** summary card (`ScoreRing`, title, `VerdictBadge`, one-line summary, `Stat`s) → Strengths / Concerns → screening questions → requirements grouped by type with `RatingIcon`s → collapsed Scoring details.
- **Lists:** a `Card` with `divide-y` rows; each row is one link with a `ScoreRing size="sm"`, title + muted meta line, a badge, and a chevron.
- **Expandable groups:** a full-width button with `aria-expanded` and a rotating chevron.
- **Loading / empty / error:** `Skeleton`s shaped like the content / `EmptyState` with an action / a one-line `role="alert"` message.
- **Tables:** desktop table inside `overflow-x-auto`, plus a stacked card list for phones (`md:hidden` / `hidden md:block`).
- **Cards grid:** collections people come back to (jobs) are a `md:grid-cols-2 lg:grid-cols-3` grid of link cards: title, a muted meta line, then a divided footer with status and counts.
- **Background work:** an item being processed shows a `Badge tone="accent"` with a spinning `Loader2` ("Reading job description", "Scoring"); the list polls (~2.5 s) only while something is in progress, and stops on its own.
- **Bulk actions:** checkboxes on rows plus a fixed bottom bar ("N selected", target, primary action); the bar becomes the confirmation with a link to the result.
- **Destructive actions** are ghost icon buttons with an `aria-label` and a `window.confirm` naming what goes and what stays.
- **Query keys** shared between features live in `src/lib/api/query-keys.ts`; dates go through `formatDateTime()` in `src/lib/format.ts`.

Before adding a component, check this list; if something new is reusable, put it in `components/` and add it here.
