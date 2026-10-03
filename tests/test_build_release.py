"""Check that standalone rules work without importing local Python files."""

import ast
from pathlib import Path
import re
import unittest

from build_release import inline_game


class StandaloneTests(unittest.TestCase):
    def test_embedded_rules_run_without_project_imports(self):
        page = inline_game(Path(__file__).resolve().parents[1])
        scripts = re.findall(r'<script type="text/python">\s*(.*?)</script>', page, re.S)
        self.assertEqual(len(scripts), 1)
        module = ast.parse(scripts[0])
        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, {"content", "engine", "game"})

        # Execute the actual embedded data and rules up to the browser UI.
        ui_start = next(index for index, node in enumerate(module.body)
                        if isinstance(node, ast.ImportFrom) and node.module == "browser")
        module.body = module.body[:ui_start]
        namespace = {}
        exec(compile(module, "standalone-rules", "exec"), namespace)
        game = namespace["GameSession"](namespace["SCENARIOS"], seed=27)
        game.start()
        prefixes = set()
        for _ in range(12):
            result = game.answer(game.current["category"])
            self.assertTrue(result["correct"])
            prefixes.add(result["ticket"].split("-")[0])
            game.advance()
        self.assertTrue(game.finished)
        self.assertEqual(game.score, 12)
        self.assertEqual(prefixes, set("АКВНСП"))


if __name__ == "__main__":
    unittest.main()
