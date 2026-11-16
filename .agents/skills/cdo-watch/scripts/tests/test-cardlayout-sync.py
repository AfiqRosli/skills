"""Vendored-copy drift check — cardlayout.py is THE one definition of the
alignment taxonomy, vendored into every scripts/ dir that carries it. The
header's own warning: an inline copy drifted once already. This test makes
a drift a test failure instead of a silent fork.

Run: uv run python tests/test-cardlayout-sync.py
"""
import hashlib
import unittest
from pathlib import Path


def project_root() -> Path:
    for p in Path(__file__).resolve().parents:
        if (p / ".agents" / "skills").is_dir():
            return p
    raise RuntimeError("no .agents/skills dir found above the test")


class TestCardlayoutSync(unittest.TestCase):
    def test_all_vendored_copies_byte_identical(self):
        root = project_root()
        copies = sorted(root.glob(".agents/skills/*/scripts/cardlayout.py"))
        self.assertGreater(len(copies), 1,
                           "expected multiple vendored copies")
        digests = {}
        for p in copies:
            digests.setdefault(
                hashlib.sha256(p.read_bytes()).hexdigest(), []).append(p)
        self.assertEqual(
            len(digests), 1,
            "cardlayout.py drifted — update every vendored copy in "
            "lockstep:\n" + "\n".join(
                f"  {d[:8]}: " + ", ".join(
                    str(p.relative_to(root)) for p in ps)
                for d, ps in digests.items()))

    def test_every_scripts_dir_that_imports_it_has_a_copy(self):
        """A scripts/ dir importing cardlayout without vendoring it is a
        latent ImportError — flag it here, not at runtime."""
        root = project_root()
        missing = []
        for py in root.glob(".agents/skills/*/scripts/**/*.py"):
            if py.name == "cardlayout.py" or "tests" in py.parts:
                continue
            try:
                src = py.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "cardlayout" in src:
                vendored = py.parent / "cardlayout.py"
                if not vendored.is_file():
                    missing.append(str(py.relative_to(root)))
        self.assertEqual(missing, [],
                         "scripts import cardlayout without a vendored "
                         "copy: " + ", ".join(missing))


if __name__ == "__main__":
    unittest.main()
