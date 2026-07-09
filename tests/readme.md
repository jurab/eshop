# Test Suite

## Quick start

```bash
make test          # fast, CI-safe unit tests
make test-all      # everything
```

## Test commands

Each command runs pytest against a specific folder.

### Unit tests (`tests/unit/`)

Pure logic on unsaved model instances and serializer validators. No database
touched — enforced by a meta-test. CI-safe.

```bash
make test
# or directly:
.venv/bin/pytest tests/unit -q
```

### Database tests (`tests/db/`)

Real ORM queries against a throwaway test database. pytest-django wraps each
test in a transaction and rolls it back — no side effects. This is where the
atomic stock reservation and snapshot behavior live.

```bash
make test-db
```

### API tests (`tests/api/`)

Full request/response cycle through the DRF stack (routing, auth, serializers,
permissions) using `APIClient`. Guest checkout, pay/cancel transitions, token
auth, and per-user data isolation.

```bash
make test-api
```

### Architecture tests (`tests/arch/`)

Import-direction rules, AST-based: `orders` may import `products`, never the
reverse; nothing imports `config`.

```bash
make test-arch
```

### Test-suite meta tests (`tests/meta/`)

Meta-tests for the test suite itself: unit tests must not touch the db or the
API client, and every test file must live in a folder the Makefile runs.

```bash
make test-meta
```

## Ratchet policy (arch guards)

Architecture checks use a ratchet so existing tech debt does not block every run.

- Current known violations are stored in `tests/arch/allowlist.py`.
- A ratcheted test compares:
  - `actual violations` from current code
  - `baseline violations` from the allowlist
- The test fails only on `actual - baseline` (new violations).
- A companion test fails on `baseline - actual` (stale allowlist entries), so
  fixed debt must be removed from the baseline — the ratchet only tightens.
- The baseline is currently **empty**. Keep it that way.

### Run everything

```bash
make test-all
```

Runs all suites in this order:
1. `tests/meta/`
2. `tests/arch/`
3. `tests/unit/`
4. `tests/db/`
5. `tests/api/`

## Test quality guidelines (for new tests)

Use this section when adding or reviewing new tests.

### What is a low-quality test

- Tests only that a mocked method was called (`assert_called_once`) without checking business outcome.
- Tests SQL/query shape or implementation details that can change during refactor without behavior change.
- Pass-through tests that just restate current code path (`input -> same output`) with no domain assertion.
- Over-mocked tests where all collaborators are fake and no meaningful state transition is validated.
- Duplicate tests that cover the same branch with different names but no new risk coverage.

### What makes a high-quality test

- Verifies user-visible or business-critical behavior (state transitions, money totals, eligibility, status).
- Asserts end-state, not just interactions (DB rows, returned schema, side effects, persisted flags).
- Covers real failure modes and edge cases (empty, invalid, partial failure, retries, idempotency).
- Encodes invariants that should survive refactors (contract/schema, domain rules, constraints).
- Uses the lowest mocking level possible while keeping speed and determinism.

### Writing standard for new tests

- Prefer **behavior-first assertions**:
  - Good: "order moves to `paid` and a `Payment` row exists".
  - Weak: "method `pay` was called once".
- Include at least one **negative or boundary** case for new logic.
- For bug fixes, add a test that fails before the fix and passes after.
- Keep one test focused on one behavior; avoid large scenario tests with many unrelated assertions.
- Avoid coupling to private helpers or exact SQL text unless the SQL shape is the behavior.

### Quick review checklist

- Does this test protect a real user journey or business rule?
- Would the test still be valid after an internal refactor?
- If all mocks returned success, would this test still catch a regression?
- Does the test assert meaningful state/data, not only call wiring?
- Is there a failure-path or boundary-path companion test?

## Structure

```
tests/
├── conftest.py           ← shared fixtures (api_client, make_product, user, auth_client)
├── unit/                 ← pure logic, no db (enforced)
│   ├── test_coupon.py
│   ├── test_order_items.py
│   └── test_order_validation.py
├── db/                   ← real ORM, transaction-wrapped
│   ├── test_stock.py      ← atomic reservation + rollback paths
│   └── test_snapshots.py  ← order history vs product/coupon edits
├── api/                  ← full DRF request cycle
│   ├── test_shop_flow.py  ← browse → order → pay → cancel
│   └── test_auth.py       ← tokens, permissions, data isolation
├── arch/                 ← import-direction rules (ratcheted)
│   ├── allowlist.py
│   └── test_imports.py
└── meta/                 ← rules about the suite itself
    └── test_suite_rules.py
```

## Fixtures (`tests/conftest.py`)

- **`api_client`** — anonymous DRF `APIClient`
- **`auth_client`** — `APIClient` with a valid token for `user`
- **`user`** — a registered shop user
- **`make_product`** — product factory (`make_product(name=, price=, stock=)`)
- **`checkout_fields`** — valid guest checkout address/contact payload
