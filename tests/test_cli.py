import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout

from oci_ootb_instance_power_scheduler.cli import main

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestCli(unittest.TestCase):
    def test_missing_file_exits_1(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["/nonexistent/plan.json"]), 1)

    def test_invalid_json_exits_1(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main([os.path.join(ROOT, "pyproject.toml")]), 1)

    def test_broken_plan_exits_2(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([os.path.join(ROOT, "samples", "broken-power-plan.json")])
        self.assertEqual(code, 2)
        text = out.getvalue()
        self.assertIn("POW001", text)
        self.assertIn("dev-nightly-stop", text)
        self.assertIn("summary:", text)

    def test_corrected_plan_exits_0(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([os.path.join(ROOT, "samples", "corrected-power-plan.json")])
        self.assertEqual(code, 0)
        self.assertIn("0 high", out.getvalue())


if __name__ == "__main__":
    unittest.main()
