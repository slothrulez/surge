# Development Rules — Payment Failure Auto-Responder

**These rules are non-negotiable. Follow them exactly.**

---

## Rule 1: Deterministic > Heuristic

**Never use AI or heuristics for:**
- Error classification (lookup table)
- Payment eligibility (check policies)
- Action selection (score based on data)

## Rule 2: Explicit Policy > Implicit Defaults

**Never assume merchant wants a feature. Always check policy first.**

## Rule 3: Log Everything > Hope Nothing Goes Wrong

**Every decision, action, and outcome must be logged with full context.**

## Rule 4: Database-Enforced Constraints > Code-Level Checks

**If a constraint is critical, enforce it in database schema.**

## Rule 5: No Secrets in Logs or Responses

**API keys, tokens, sensitive data must NEVER appear in logs or error messages.**

## Rule 6: Never Override a Policy Check

**If merchant policy says "don't do this," don't do it. Ever.**

## Rule 7: All Money-Related Decisions are Hardcoded

**Never let config or AI decide whether to charge customer.**

## Rule 8: Idempotency Keys on Every Action

**Every action that can be called multiple times must have an idempotency key.**

## Rule 9: Configuration Goes in config.py or Database

**Thresholds, limits, and tunable values go in config.py or merchant_policy table. Never hardcode.**

## Rule 10: Use Existing Models, Never Redefine

**All data structures are in models.py (Phase 0). Use them. Don't create new ones.**

## Rule 11: Database-First Approach

**Modify data through migrations, not code. Schema changes require migration files.**

## Rule 12: Test Everything You Create

**Every function, endpoint, workflow must have tests. No exceptions.**

## Rule 13: Error Handling is Explicit

**Catch specific exceptions. Never use bare except:. Always handle errors gracefully.**

## Rule 14: No N+1 Queries

**Fetch all related data in one query. Don't loop and query.**

## Rule 15: Transactional Consistency

**Related changes must happen together. If one fails, all fail (rollback).**

---

**When in doubt:** Can this be exploited? Can this be audited? Can this fail? Can this be tested?

If "no" to any, don't ship it.
