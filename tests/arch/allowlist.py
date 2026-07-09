"""Known architecture violations (the ratchet baseline).

Each entry is (importing file relative to repo root, imported app).
The arch tests fail only on NEW violations; fix debt, then delete its
entry here to tighten the ratchet. Currently clean — keep it that way.
"""

BASELINE = set()
