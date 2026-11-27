# Design system: "the formulary"

The web app looks like a well-made reference book, not a marketing site. Colour carries meaning
(review status, safety); photographs carry the richness; the chrome stays quiet.

## Direction

- **Product:** veterinary drug reference (generics, brands, manufacturers by country), dose
  calculators and study tools, for vets and students. Every clinical statement shows its source
  and review status.
- **Character:** exact, unhurried, field-ready.
- **World:** the dispensary and the printed formulary: label stock, ink, the brand teal.
- **Moments:** licensed species photographs (homepage plate) and the dose calculator's worked
  formula (units only, never dose values).
- **Signature:** the review mark. Filled dot = clinically reviewed, hollow ring = not yet reviewed.
  `.review-mark` (with `data-reviewed="false"` for the ring); used in `StatusBadge`, the homepage
  legend and the footer. Do not use it as decoration.

## Tokens (`web/src/app/globals.css`)

| Role | Light | Dark |
| --- | --- | --- |
| Page `--bg` | #f6f7f7 | #0d1213 |
| Card `--surface` | #ffffff | #131a1b |
| Raised / input `--surface-2` | #eef1f1 | #1b2425 |
| Border `--border` | #dde3e3 | #2a3537 |
| Text `--text` / `--text-2` / `--text-muted` | #121a1c / #3e4b51 / #56646b | #e9eff0 / #b9c5c8 / #94a3a7 |
| Accent `--primary` | #0b6e6e | #4fb8b3 |

`src/lib/contrast.test.ts` enforces 4.5:1 for every text pair in both themes. Add new pairs there.

- **Type:** IBM Plex Sans (interface, tabular figures), Newsreader (every `h1`, set globally),
  IBM Plex Mono (formulas, codes). Self-hosted in `web/src/app/fonts` (SIL OFL). Weights 400/500,
  600 only for the wordmark. Sentence case, no uppercase tracked labels.
- **Radius:** 6 (badges) / 10 (controls) / 14 (cards) / 18 (panels, sheets).
- **Depth:** hairline borders; one small neutral shadow on light, none on dark.
- **Icons:** lucide, 16-20px, stroke 1.5, neutral (`.icon-chip` is grey, never tinted).
- **Legacy class names** `.glass`, `.neo`, `.neo-inset`, `.prism-edge` still exist so older
  pages adopt the system; they now render flat. Prefer `.card`, `.btn-primary`, `.btn-secondary`.

## Layout

- Content width `max-w-6xl` (1152px), page padding 16 / 24px.
- Desktop: top nav from `lg`. Phones: four tabs plus **More** (bottom sheet, `mobile-more.tsx`),
  never more than five targets. The footer site map (`SITE_MAP` in `app-shell.tsx`) feeds both.
- Lists of equal items are rows (icon, title, one line, arrow), not identical tall cards.

## Motion

One curve (`--ease-out: cubic-bezier(0.22, 1, 0.36, 1)`), durations 140 / 200 / 420ms. One
entrance per page at most (homepage hero `.rise` + `.plate-in`). Hover is a colour or border step;
press is a 0.97-0.985 scale. No scroll-triggered reveals, no looping motion. Everything degrades to
a fade under `prefers-reduced-motion`.
