"""Import-direction rules: orders may know products; never the reverse.

Ratcheted: only violations not present in allowlist.BASELINE fail the build.
"""
import ast
from pathlib import Path

from tests.arch.allowlist import BASELINE

REPO_ROOT = Path(__file__).resolve().parents[2]

# app -> apps it must not import from. `orders` is the top of the domain
# dependency chain, so anything below it importing upward is a cycle seed.
FORBIDDEN = {
    'products': {'orders', 'accounts', 'config'},
    'accounts': {'orders', 'products', 'config'},
    'orders': {'config'},
}


def imported_top_level_modules(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split('.')[0]


def current_violations():
    violations = set()
    for app, forbidden in FORBIDDEN.items():
        for path in (REPO_ROOT / app).rglob('*.py'):
            for module in imported_top_level_modules(path):
                if module in forbidden:
                    violations.add((str(path.relative_to(REPO_ROOT)), module))
    return violations


def test_no_new_upward_imports():
    new = current_violations() - BASELINE
    assert not new, f'new import-direction violations: {sorted(new)}'


def test_ratchet_baseline_is_not_stale():
    """Fixed debt must be removed from the allowlist, not silently kept."""
    stale = BASELINE - current_violations()
    assert not stale, f'allowlist entries no longer needed: {sorted(stale)}'
