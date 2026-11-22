"""New resident rendering policy; original lifecycle tests are not duplicated."""
import ast
import unittest

from tools.d_recipe.resident_bootstrap import render_sbatch


class ResidentRenderingTests(unittest.TestCase):
    def test_argv_and_environment_remain_literal(self):
        text = "literal ' quote\n$(never-a-shell-command)"
        rendered = render_sbatch(
            ["/usr/bin/python3", "-c", text], "pass",
            child_environment={"D_LITERAL": text},
            directives=["#SBATCH --cpus-per-task=1"])
        self.assertTrue(rendered.startswith("#!/usr/bin/python3 -ISB\n"))
        values = {node.targets[0].id: ast.literal_eval(node.value)
                  for node in ast.parse(rendered).body
                  if isinstance(node, ast.Assign)
                  and isinstance(node.targets[0], ast.Name)
                  and node.targets[0].id in ("_WORKER_COMMAND", "_CHILD_ENV")}
        self.assertEqual(values["_WORKER_COMMAND"][-1], text)
        self.assertEqual(values["_CHILD_ENV"]["D_LITERAL"], text)
        self.assertNotIn("shell=True", rendered)

    def test_directives_cannot_inject_a_python_line(self):
        with self.assertRaises(ValueError):
            render_sbatch(["/bin/true"], "pass",
                          directives=["#SBATCH --nodes=1\ninjected()"])

    def test_missing_command_and_cleanup_allowance_are_rejected(self):
        with self.assertRaises(ValueError):
            render_sbatch(["relative"], "pass")
        with self.assertRaises(ValueError):
            render_sbatch(["/bin/true"], "pass", cleanup_seconds=179)


if __name__ == "__main__":
    unittest.main()
