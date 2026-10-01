# Editorial operations playbook

## Operating model

The existing MoneyPrinterTurbo fork remains the **media engine**. The editorial control plane owns channel identity, research packets, episode lifecycle, human review, publication intent and performance learning.

Pipeline:

idea -> researched -> scripted -> generated -> review -> approved -> published -> measured

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

1. Research: create the episode and collect current RSS items from the channel's configured sources.
2. Script: write the hook, thesis, evidence-backed sections, visual beats and CTA. The first lines of the description must contain a unique episode summary.
3. Generate: submit the script to the existing MoneyPrinterTurbo task queue. The editorial layer stores the engine task ID.
4. Sync: poll the engine state. A completed engine task moves the episode to review; it never auto-approves.
5. Review: watch the actual rendered video and verify factual accuracy, sources, hook, pacing, audio, subtitles, visual relevance, title/thumbnail promise, description and synthetic-media disclosure.
6. Approve: send explicit human approval. Bracket placeholders such as [SOURCES] block approval.
7. Publish: the V1 adapter reuses the existing Upload-Post integration for YouTube. Default privacy is unlisted.
8. Measure: ingest views, likes, comments, impressions, CTR, average view duration, watch time, retention and subscribers gained.
9. Learn: use the insights endpoint to compare measured performance. Do not change channel rules from a single outlier; wait for at least five measured episodes.

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

The metadata store uses SQLite under the application's existing storage/editorial directory, avoiding a new infrastructure dependency in V1.
