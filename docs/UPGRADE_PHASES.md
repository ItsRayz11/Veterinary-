# In-place upgrade: phases, rollout and rollback

Everything here extends the running VetRef system: same repo, database, auth, routes and review
workflow. `/admin-panel` remains the admin destination; Django admin remains the advanced editor.

## Audit summary (what was reused)

| Need | Reused |
| --- | --- |
| Admin shell | `web/src/components/admin/*`, `/staff/*` API in `apps/staff` |
| Source registry | `automation.DataSource` (extended), `Feed`, `SourceHealth`, `JobRun`, `safe_http` |
| Moderation | existing review statuses, `PriceSubmission`, `QuestionReport`, `AuditLog` |
| Auth / roles | `accounts.Role`, `HasRole`, MFA for staff |
| Prices | `pricing.PriceRecord` (append-only) |

## Phase 1: sidebar admin (commit 82fbbe8)
Collapsible, searchable, responsive sidebar; Dashboard with real counts; `?section=` deep links
(old `?tab=` still works). No API change. Rollback: revert the commit.

## Phase 2: source registry and automation foundation
- `DataSource` gains registry fields (migration `automation/0004`): content type, geography,
  method, robots status, extraction scope, credentials *reference* (env var name, validated),
  import destination, priority, rate limit, `paused`. All additive with defaults.
- `/staff/sources/` (admin only): create, edit, pause, resume, run now, retry, confirm terms,
  import now. Every action writes `AuditLog`. Paused sources are skipped by the scheduler and
  importer. Import cannot be enabled while robots status is "restricted" or terms are unconfirmed.
- `automation/policy.py`: deterministic publish decision. Dosage, treatment, diagnosis,
  regulatory, safety and unknown kinds are never auto-published; AI confidence is recorded but
  never used to publish. Price-outlier helper is plain arithmetic.
- Provenance states are defined in `policy.Provenance`; existing review statuses are unchanged.
- Rollback: `migrate automation 0003` (drops only the new columns).

## Phase 3: AI layer (new app `apps/ai`, migration `ai/0001`)
- `AIProvider` (OpenAI, OpenRouter, AgentRouter), `AITaskRoute` (task to provider/model/fallback),
  `AIUsage` (append-only ledger of sizes and estimated cost; prompts are not stored).
- Keys are read from server environment variables named in the provider row. The API only ever
  reports whether a key is present. Calls need https, a public address (SSRF guard), obey a
  per-provider rate limit and monthly budget (0 = no spend), and fall back once.
- **AgentRouter**: treated as a generic OpenAI-compatible endpoint with an admin-supplied https
  base URL. Its API was not verified from this environment; confirm its documentation and your
  account's capabilities before enabling. No scraping endpoint is assumed: AI only classifies,
  drafts and suggests, never fetches websites.
- Cost figures are planning estimates from token counts, not invoices.
- `apps/ai/triage.py`: deterministic triage of question reports (spam, duplicate, clinical,
  needs-citation); clinical items are flagged for a veterinarian reviewer. Shown in the
  Question reports section; nothing is auto-resolved.
- Env needed to use AI: e.g. `OPENAI_API_KEY`, `OPENROUTER_API_KEY`. None is required for the site.
- Rollback: remove providers in admin or `migrate ai zero`.

## Phase 4: content and market data
- `apps/content` (migration `content/0001`): `Article`, `ArticleRevision`, `TopicSuggestion`.
  Statuses draft, review, scheduled, published, rejected. Plain text with a small markdown
  subset; HTML is stripped on save and never rendered; only https links and same-site images
  render. Contributors submit (throttled, max 5 open); editors publish. Clinical articles (flagged
  by the author/editor or auto-flagged by wording) need a veterinarian reviewer or admin and
  cited references. Editing a published article returns it to review. Revisions are kept.
- Editorial assistant: gap ideas from VetRef data (labelled "catalogue gap") and, if an AI route
  exists, model ideas (labelled "general AI suggestion, not trend data"). VetRef has no trend feed,
  so nothing is labelled as trend data. AI drafts are saved unpublished, AI-assisted and
  clinical-flagged.
- `apps/marketplace` (migration `marketplace/0001`): `Retailer`, `RetailerOffer` (history kept),
  `FxRate`. Public `/products/<slug>/offers/` shows only approved + verified offers from approved
  retailers; stock reads Unknown unless confirmed within 14 days. `/price-comparison/` compares
  like-for-like per pack in local currency; conversion appears only when an admin entered rates,
  with their date. No rates, stock or prices are invented or fetched.
- Public pages: `/blog`, `/blog/[slug]`, `/blog/submit`; product page sections "Compare prices
  by country" and "Where to buy".

## Phase 5: 3D catalogs
- `Supplier`, `Catalog3D` (GLB stored in the database, 3 MB, structure-validated glTF 2.0),
  `CatalogPlan`, `Lead`. Suppliers must be approved; models are public only after moderator
  approval and confirmed rights. Assets are served with `nosniff` from the API; the viewer
  (`@google/model-viewer`, bundled) loads only on pages that show a model and falls back to an
  image. CSP gained `blob:` for `img-src`, `connect-src` and `worker-src` (no remote origins).
- **Payments are OFF.** Plans display a price but the only action is an enquiry (`Lead`). No
  checkout, invoice or webhook exists. Enable only after provider, tax, invoicing and refund
  rules are configured and tested.
- **Upload scanning** (`marketplace/scan.py`, migration `marketplace/0002`): every upload is
  hashed and scanned before it is stored. Built-in layer (always on): well-formed glTF 2.0, no
  external or script-bearing URIs, only allow-listed extensions (Draco and meshopt are rejected
  because their decoders would load from a remote CDN, which the CSP forbids), sane counts, no
  script markers. Optional layers: ClamAV (`CLAMD_HOST`, `CLAMD_PORT`) and a VirusTotal hash lookup
  (`VIRUSTOTAL_API_KEY`; the file itself is never uploaded and an unknown hash is not a
  clearance). Unsafe files are rejected and the attempt is audited. A model can be approved only
  with a clean scan and confirmed rights; staff can rescan. Nothing can prove a file safe, so
  moderators still look at each model. The 3 MB limit comes from the 4.5 MB serverless body cap
  (base64 adds a third) and `DATA_UPLOAD_MAX_MEMORY_SIZE` (now 4 MB).
- **Prices**: a catalog can carry a reference price (amount + currency) shown on its card and
  plans are listed with prices. Buying is still by enquiry (`Lead`, optionally naming the model);
  no checkout exists.

## Round 2: cross-check fixes and additions
- Upload size limits fixed (8 MB could never pass the 3 MB body cap); rights confirmation is now
  enforced on the server at upload, not just in the form.
- Source registry: `robots_status` is now set to "allowed" when a check passes robots.txt;
  imports refuse sources marked restricted; `record_count` is filled after each import.
- Feeds: postings with payment-demand markers (fees, Western Union, etc.) are not created and are
  counted in the feed result (`policy.looks_suspicious`).
- Dashboard: tiles for articles, price records, retailer offers, 3D models/suppliers/enquiries and
  (admins) AI calls and estimated spend, each linking to its section.
- Admin UI: link-check results appear inline instead of a browser alert; article audit entries no
  longer copy the whole body.
- Trends: `content/trends.py` reads Wikimedia Pageviews (official, CC0). It is registered as a
  disabled source (`wikimedia-pageviews`, migration `automation/0005`); an admin enables it and
  confirms its terms in the registry, after which "Find new topic ideas" adds ideas labelled
  "From a registered trend source" with the real 30-day numbers and a link. These are general
  public-interest signals, not veterinary-specific demand.
- Release gate: `.github/workflows/release.yml` (manual) runs all checks in the `staging`
  environment, then waits for the required reviewer on the `production-approval` environment
  before applying migrations to production (needs secrets `DATABASE_URL`, `SECRET_KEY`). Vercel
  still builds every push to main; to make approval the only path to production, change the
  Vercel project's production branch or ignored-build-step setting (a Vercel dashboard change).
- AgentRouter (agentrouter.org): the site home is a script-only page, but /docs is readable
  (Chinese; our translation, unverified). It presents a free service for developer coding tools
  (Claude Code and similar) with an OpenAI-compatible path ending in /v1 for some models, keys
  and the live model list in a separate console, and terms that restrict batch/synthetic content,
  bulk marketing or SEO text, mostly single-turn general Q&A, and rate-limit bypassing, with
  quotas and suspension at its discretion. VetRef's server-side tasks may breach those terms, so
  it is NOT enabled and no base URL is preset. Technically it fits: the OpenAI-compatible base is
  `https://agentrouter.org/v1` (`POST /v1/chat/completions`, `Authorization: Bearer`), keys and the
  live model list come from its console, and `/models` is undocumented, so "Test connection"
  falls back to a one-token call using the preferred model. Model names must match its list exactly
  (a wrong name returns 503). Use OpenAI or OpenRouter for production unless
  AgentRouter confirms in writing that this use is allowed.

## Rollout and rollback
1. Take a Neon snapshot (see `ADMIN.md`). 2. Deploy to a preview/staging environment, run
`migrate` (all migrations are additive: new tables and defaulted columns). 3. Verify:
`/admin-panel` sections, review queue count unchanged, public search, calculators, study pages,
universities, login. 4. Promote to production with explicit approval.
Rollback: redeploy the previous Vercel deployment; restore the snapshot if data must be undone.
Existing review-queue rows are never modified by these migrations.

## Feature flags
Nothing user-visible is on by default: AI providers are off until added and enabled, sources
import only when terms are confirmed, plans are hidden until `active`, offers/articles/models are
hidden until approved.

## Known gaps (not implemented, by design or pending input)
Automatic discovery/parsing beyond the existing importers and feeds; retailer self-service offer
sync (staff enter offers today); payments; auto-publishing of feed items (the policy module only
filters scams today; items stay pending for review); screenshots; Vercel-side deploy gating.

## AI keys managed in the admin panel
Admins can paste, replace or remove a provider's API key from `/admin-panel` (AI providers, row
action "API key and model"). Keys are stored encrypted in the database (Fernet, derived from
`AI_KEY_ENCRYPTION_SECRET`, or `SECRET_KEY` if unset), are write-only (no API ever returns them),
and set/remove events are audited without the value. A stored key wins over an environment
variable reference. If `SECRET_KEY` is rotated, stored keys stop decrypting and must be re-entered.
"Load models from provider" lists the provider's real model ids so one can be selected.
