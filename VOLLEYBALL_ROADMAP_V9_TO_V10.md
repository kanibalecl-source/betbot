# Volleyball roadmap: v9.0 to v10.0

Every release is cumulative, shadow-only, isolated under `/data/volleyball`,
backed up before startup, and deployed only after the previous gate passes.

| Version | Deliverable | Promotion gate |
|---|---|---|
| v9.0 | Isolated storage, Elo baseline, picks and immutable settlement evidence | Football unaffected; module disabled by default |
| v9.1 | Provider resilience and measurable games/results/odds coverage | 7 healthy collection days; no unexplained gaps |
| v9.2 | Canonical team/league identities, deduplication and quarantine | identity conflicts below threshold |
| v9.3 | Complete autonomous settlement and reconciliation | settlement accuracy audited on reviewed sample |
| v9.4 | Point-in-time feature store with leakage guards | feature timestamps strictly precede match start |
| v9.5 | Multiple bookmaker snapshots, no-vig consensus and immutable CLV (implemented) | sufficient closing-line coverage |
| v9.6 | Candidate training pipeline and reproducible model registry (implemented) | minimum settled sample and reproducible artifact |
| v9.7 | Walk-forward Champion-Challenger validation (implemented) | positive out-of-sample Brier/log-loss and calibration |
| v9.8 | Segment stability, drift detection and automatic rollback | no weak league/market slice breaches |
| v9.9 | Autonomous learning governor; candidate creation only | repeated positive shadow validations |
| v10.0 | Self-improving volleyball shadow system | quality depends on new verified data; real betting remains disabled |

## Non-negotiable rules

1. No release overwrites football history, models, training files or databases.
2. No model trains on bookmaker odds as a target or on post-kickoff information.
3. A candidate never replaces the champion without positive walk-forward and
   live-shadow validation.
4. Data quality failure pauses learning; it never deletes evidence.
5. v10.0 means autonomous data collection, settlement, training, validation,
   promotion and rollback in shadow mode. It does not authorize real betting.
