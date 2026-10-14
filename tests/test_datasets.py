import json
import tempfile
import unittest
from pathlib import Path

from ahat_benchmark.datasets import align_cases, load_inference
from ahat_benchmark.schemas import EvalCase, InferenceCase, SchemaError


class DatasetTests(unittest.TestCase):
    def test_load_inference_normalizes_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inference.json"
            path.write_text(
                json.dumps({"results": [{"id": "case-1", "plan": "(one)\n(two)"}]}),
                encoding="utf-8",
            )
            _, cases = load_inference(path)
        self.assertEqual(cases["case-1"].plan, ["(one)", "(two)"])

    def test_alignment_rejects_unknown_ids(self):
        eval_cases = [EvalCase("known", "do it", {"rooms": []})]
        inference = {"unknown": InferenceCase("unknown", ["(act)"])}
        with self.assertRaisesRegex(SchemaError, "unknown ids"):
            align_cases(eval_cases, inference)


if __name__ == "__main__":
    unittest.main()
