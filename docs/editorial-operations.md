# Editorial operations playbook

> Global mandatory controls: [`global-editorial-policy.md`](global-editorial-policy.md) and [`config/editorial_policy.json`](../config/editorial_policy.json). These apply to every channel and platform; channel settings may be stricter but must not weaken them.

## Operating model

The existing MoneyPrinterTurbo fork remains the **media engine**. The editorial control plane owns channel identity, research packets, episode lifecycle, human review, publication intent and performance learning.

Pipeline:

idea -> researched -> scripted -> generated -> review -> approved -> uploaded_private -> public_approved -> published -> measured

rejected and failed are recovery states.

## Pilot channels

### 1. Nexbrain
AI, future technology, automation, future of work and human potential.

- English
- 8–14 minute cinematic documentary
- 1/day target
- 5/week validation cadence
- Standard editorial risk

### 2. Capital Signal
Money systems, markets, macroeconomics, behavioral finance and documented economic/company developments.

- English
- 8–14 minute data-driven cinematic documentary
- 1/day target
- 5/week validation cadence
- High editorial risk

Capital Signal must separate documented facts, estimates and attributed interpretations and must not provide personalized financial advice.

## Daily workflow

1. Research: create the episode and collect current RSS items from the channel's configured sources. Meet the global minimum source count (2 standard / 3 high risk), record URLs/publishers/dates, prefer primary sources and flag unresolved conflicts.
2. Script: write a distinct episode thesis/angle, a concrete viewer payoff, the hook, evidence-backed sections, visual beats and CTA. The first lines of the description must contain a unique episode summary. Do not produce source readouts or interchangeable template episodes.
3. Generate: submit the script to the existing MoneyPrinterTurbo task queue. The editorial layer stores the engine task ID.
4. Sync: poll the engine state. A completed engine task moves the episode to review; it never auto-approves.
5. Review: watch the actual rendered video and verify factual accuracy, source diversity, hook, pacing, audio, subtitles, visual relevance, title/thumbnail promise, description, asset rights/provenance and synthetic-media disclosure. QA warnings must be resolved or explicitly accepted by a reviewer.
6. Approve: send explicit human approval. Bracket placeholders such as [SOURCES] block approval.
7. Private upload: the V1 adapter reuses the existing Upload-Post integration for YouTube and forces privacyStatus=private. This is the only automated YouTube upload step.
8. Final public gate: after the private upload, a human explicitly approves public release. The public transition itself remains a separate human action; the system records the resulting YouTube URL through mark-public.
9. Measure: ingest views, likes, comments, impressions, CTR, average view duration, watch time, retention, returning viewers, subscribers gained, RPM, estimated revenue and production cost where available. Then use the insights endpoint to compare measured performance. Do not change channel rules from a single outlier; wait for at least five measured episodes.

## API

All endpoints are under /api/v1/editorial and inherit the application's API-key middleware when configured.

- GET /channels
- GET /episodes?channel=&state=
- GET /insights?channel=
- POST /episodes
- POST /episodes/{id}/research/collect
- POST /episodes/{id}/research
- POST /episodes/{id}/script
- POST /episodes/{id}/generate
- POST /episodes/{id}/sync
- POST /episodes/{id}/review
- POST /episodes/{id}/publish
- POST /episodes/{id}/metrics
- POST /episodes/{id}/public-approve
- POST /episodes/{id}/mark-public

The metadata store uses SQLite under the application's existing storage/editorial directory, avoiding a new infrastructure dependency in V1.


## Optional Shopping revenue lane

For every researched episode, evaluate whether a product recommendation would genuinely help the target viewer. This is an optional fit check, not a quota. If relevant, prepare a product brief with product identity, seller URL, evidence/offer verification date, audience fit, script placement, commission data when visible, and disclosure notes. Confirm eligibility in YouTube Studio before native YouTube Shopping tagging. Keep native Shopping affiliate links on YouTube; do not redistribute them externally. Record product clicks, orders, commissions and reversals when available. Never invent offer details, imply unperformed tests, or force a product into an unrelated story.
