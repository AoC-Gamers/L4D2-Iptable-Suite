#!/usr/bin/env python3
"""Documentation-checker fixtures only; no firewall, service or network access."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("check_docs", Path(__file__).with_name("check_docs.py"))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class DocumentationChecks(unittest.TestCase):
    def check(self, files):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, text in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            tracked = "\0".join(p for p in files if p.endswith(".md")).encode()
            output = io.StringIO()
            with patch.object(checker, "ROOT", root), patch.object(checker.subprocess, "check_output", return_value=tracked):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    status = checker.main()
            return status, output.getvalue()

    def test_relative_reference_image_unicode_duplicate_and_explicit_anchors(self):
        status, output = self.check({
            "docs/README.md": '# Inicio\n[Guía][ref]\n[ref]: guide.md#configuración-1\n![muestra](image.svg)\n<a href="guide.md#manual">Manual</a>\n```sh\n[ignorado](no-existe.md)\n```\n',
            "docs/guide.md": '# Configuración\n## Configuración\n<a id="manual"></a>\n',
            "docs/image.svg": '<svg xmlns="http://www.w3.org/2000/svg"/>',
        })
        self.assertEqual(status, 0, output)

    def test_missing_anchor_and_image_fail(self):
        status, output = self.check({"docs/README.md": '# Inicio\n[error](#ausente)\n![imagen](missing.svg)\n'})
        self.assertEqual(status, 1)
        self.assertIn("missing anchor", output)
        self.assertIn("missing target", output)

    def test_undefined_reference_fails(self):
        status, output = self.check({"docs/README.md": "# Inicio\n[Guía][undefined]\n"})
        self.assertEqual(status, 1)
        self.assertIn("Undefined reference", output)

    def test_map_does_not_exempt_unreachable_current_page(self):
        status, output = self.check({
            "docs/README.md": "# Inicio\n[Mapa](migration/documentation-map.md)\n",
            "docs/migration/documentation-map.md": "# Mapa\n`docs/guide.md`\n",
            "docs/guide.md": "# Guía vigente\n",
        })
        self.assertEqual(status, 1)
        self.assertIn("Not reachable", output)

    def test_map_does_not_exempt_unreachable_notice(self):
        files = {
            "docs/README.md": "# Inicio\n[Mapa](migration/documentation-map.md)\n",
            "docs/migration/documentation-map.md": "# Mapa\n`docs/old.md`\n",
            "docs/old.md": "# Documento trasladado\n[Inicio](README.md)\n",
        }
        status, output = self.check(files)
        self.assertEqual(status, 1)
        self.assertIn("Not reachable", output)

    def test_systemd_documentation(self):
        files = {
            "docs/README.md": "# Inicio\n",
            "systemd/test.service": "[Unit]\nDocumentation=file:/opt/l4d2-firewall/docs/README.md\n",
        }
        self.assertEqual(self.check(files)[0], 0)
        files["systemd/test.service"] = "[Unit]\nDocumentation=file:/opt/l4d2-firewall/docs/missing.md\n"
        status, output = self.check(files)
        self.assertEqual(status, 1)
        self.assertIn("missing Documentation target", output)


if __name__ == "__main__":
    unittest.main()
