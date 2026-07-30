# Basketball Shadow v1

The module is isolated from football, volleyball, handball and tennis.
Uploading the package does not start it automatically.

Railway variables required for activation:

```text
BETBOT_BASKETBALL_ENABLED=1
BETBOT_BASKETBALL_SHADOW_ONLY=1
BASKETBALL_API_SPORTS_KEY=<server secret>
BETBOT_BASKETBALL_POLL_MINUTES=30
BETBOT_BASKETBALL_BACKFILL_DAYS=30
BETBOT_BASKETBALL_LOOKAHEAD_DAYS=7
```

`API_SPORTS_KEY` can be used instead of `BASKETBALL_API_SPORTS_KEY` when the
same API-Sports account is licensed for basketball.

Expected production logs:

```text
START basketball_shadow: ... -m basketball_v1.runtime
BASKETBALL v1.0 SHADOW START ...
BASKETBALL_SHADOW_CYCLE
HEARTBEAT ... basketball_shadow=True
```

Safety guarantees:

- SQLite storage: `/data/basketball/basketball_shadow.sqlite3`
- no training admission
- no model candidate creation or promotion
- no real-money execution
- invalid records are quarantined
- finished and void games are settled automatically
- overtime is stored explicitly
- existing sport databases are not read or modified
