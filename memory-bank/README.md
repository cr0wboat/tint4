# Memory Bank — tint4

Tier-2 local persistence for this project. See the global Cline rules
(`05-memory-bank-protocol.md`) for the read/write protocol.

| File | Purpose |
|------|---------|
| activeContext.md | current task, constraints, hardware state |
| systemPatterns.md | pinouts, topology, recurring patterns, quirks |
| progress.md | done / in-progress / next / blockers |
| decisionLog.md | [Decision] -> [Constraint] -> [Alternative Failure Path] |

## Long-term memory
Durable, cross-project knowledge ("reusable components", user profile,
lab inventory) lives in the shared Tier-1 store, NOT here. Use:

    bd components add "..." --tags "..." --origin tint4
    bd components search "query"
