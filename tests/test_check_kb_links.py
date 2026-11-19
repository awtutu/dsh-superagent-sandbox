"""Tests for tools/check_kb_links.py.

Every test builds a small Markdown tree in a temporary directory, so the
suite is repeatable and independent of the repository contents.

Run with either ``python3 -m unittest discover -s tests`` or
``python3 -m pytest tests``.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "check_kb_links.py"


def load_module():
    spec = importlib.util.spec_from_file_location("check_kb_links", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check_kb_links = load_module()


class TempTreeTestCase(unittest.TestCase):
    """Provides ``self.tree`` helpers to write files into a temp directory."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write(self, relative: str, content: str = "") -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content), encoding="utf-8")
        return path

    def run_main(self, *paths: str):
        """Run ``main`` in-process against paths inside the temp tree."""
        args = [str(self.root / p) if p != "." else "." for p in paths] or ["."]
        stdout, stderr = io.StringIO(), io.StringIO()
        cwd = Path.cwd()
        stdout_capture = contextlib.redirect_stdout(stdout)
        stderr_capture = contextlib.redirect_stderr(stderr)
        try:
            os.chdir(self.root)
            with stdout_capture, stderr_capture:
                code = check_kb_links.main(args)
        finally:
            os.chdir(cwd)
        return code, stdout.getvalue(), stderr.getvalue()


class BrokenLinkTests(TempTreeTestCase):
    def test_broken_link_returns_non_zero_and_prints_path(self):
        self.write("docs/guide.md", "exists\n")
        self.write("docs/index.md", "[guide](guide.md)\n[missing](missing.md)\n")

        code, out, _ = self.run_main("docs")

        self.assertEqual(code, 1)
        self.assertIn("missing.md", out)
        self.assertIn("index.md:2", out)
        self.assertNotIn("guide.md ->", out)

    def test_broken_image_is_reported(self):
        self.write("docs/index.md", "![diagram](img/diagram.png)\n")

        code, out, _ = self.run_main("docs")

        self.assertEqual(code, 1)
        self.assertIn("img/diagram.png", out)

    def test_broken_link_in_other_directory_reports_target_path(self):
        self.write(
            "kb/chapter/notes.md",
            "[back](../other/missing.md)\n",
        )

        code, out, _ = self.run_main("kb")

        self.assertEqual(code, 1)
        self.assertIn("missing.md", out)

    def test_multiple_broken_links_are_all_reported(self):
        self.write("a.md", "[x](one.md)\n")
        self.write("b.md", "[y](two.md)\n")

        code, out, _ = self.run_main(".")

        self.assertEqual(code, 1)
        self.assertIn("one.md", out)
        self.assertIn("two.md", out)
        self.assertIn("FAILED: 2 broken link(s)", out)


class ValidLinkTests(TempTreeTestCase):
    def test_existing_links_return_zero(self):
        self.write("docs/index.md", "[guide](guide.md)\n[badge](assets/badge.svg)\n")
        self.write("docs/guide.md", "[home](../README.md)\n")
        self.write("docs/assets/badge.svg", "<svg/>\n")
        self.write("README.md", "[docs](docs/index.md#start)\n")

        code, out, _ = self.run_main(".")

        self.assertEqual(code, 0, out)
        self.assertIn("OK:", out)

    def test_ignored_link_kinds_are_not_reported(self):
        self.write(
            "docs/index.md",
            """\
            [web](https://example.com/missing.md)
            [mail](mailto:someone@example.com)
            [anchor](#section)
            [protocol](//cdn.example.com/x.png)
            [root](/absolute/path.md)
            """,
        )

        code, out, _ = self.run_main("docs")

        self.assertEqual(code, 0, out)

    def test_directory_link_resolves(self):
        self.write("index.md", "[folder](sub/)\n")
        self.write("sub/page.md", "hello\n")

        code, _, _ = self.run_main(".")

        self.assertEqual(code, 0)

    def test_percent_encoded_and_angle_bracket_links(self):
        self.write("index.md", "[a](my%20file.md)\n[b](<other file.md>)\n")
        self.write("my file.md", "x\n")
        self.write("other file.md", "x\n")

        code, _, _ = self.run_main(".")

        self.assertEqual(code, 0)

    def test_reference_definitions_and_html_attributes(self):
        self.write(
            "index.md",
            """\
            See [the guide][g] and <a href="missing.html">x</a>.
            ![logo][l]

            [g]: guide.md "Guide"
            [l]: <logo.png>
            """,
        )
        self.write("guide.md", "ok\n")

        code, out, _ = self.run_main(".")

        self.assertEqual(code, 1)
        self.assertIn("logo.png", out)
        self.assertIn("missing.html", out)
        self.assertNotIn("guide.md", out)


class ParsingTests(TempTreeTestCase):
    def test_links_inside_fenced_code_are_ignored(self):
        self.write(
            "index.md",
            """\
            Example:

            ```markdown
            [not a real link](nope.md)
            ```

            ~~~
            [also ignored](nope2.md)
            ~~~

            [real](missing.md)
            """,
        )

        code, out, _ = self.run_main(".")

        self.assertEqual(code, 1)
        self.assertIn("missing.md", out)
        self.assertNotIn("nope.md", out)
        self.assertNotIn("nope2.md", out)

    def test_link_with_title_and_nested_parens(self):
        self.write("index.md", '[a](file(1).md "Title")\n[b](other.md \'single\')\n')
        self.write("file(1).md", "x\n")

        code, out, _ = self.run_main(".")

        self.assertEqual(code, 1)
        self.assertIn("other.md", out)
        self.assertNotIn("file(1).md", out)

    def test_missing_root_returns_two(self):
        code, _, err = self.run_main("does-not-exist")

        self.assertEqual(code, 2)
        self.assertIn("no such file", err)

    def test_single_markdown_file_argument(self):
        self.write("only.md", "[x](gone.md)\n")
        self.write("other.md", "[y](also-gone.md)\n")

        code, out, _ = self.run_main("only.md")

        self.assertEqual(code, 1)
        self.assertIn("gone.md", out)
        self.assertNotIn("also-gone.md", out)


class CommandLineTests(TempTreeTestCase):
    def run_script(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

    def test_script_exit_codes(self):
        self.write("kb/a.md", "[ok](b.md)\n")
        self.write("kb/b.md", "fine\n")

        ok = self.run_script("kb")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)

        self.write("kb/a.md", "[bad](zzz.md)\n")
        bad = self.run_script("kb")
        self.assertEqual(bad.returncode, 1, bad.stdout + bad.stderr)
        self.assertIn("zzz.md", bad.stdout)


if __name__ == "__main__":
    unittest.main()
