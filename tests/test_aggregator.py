import json
import unittest

from ahat_benchmark.judge.aggregator import aggregate, parse_review, snap_score


def successful(score, *, critical=False):
    return {"status": "success", "score": score, "critical_failure": critical, "rationale": "checked"}


class AggregatorTests(unittest.TestCase):
    def test_paper_weights_and_cap(self):
        dimensions = dict(zip(("D1", "D2", "D3", "D4"), map(successful, (1, .5, .25, 0))))
        self.assertAlmostEqual(aggregate(dimensions)["score"], .55)
        dimensions["D1"]["critical_failure"] = True
        self.assertEqual(aggregate(dimensions)["score"], .2)

    def test_weighted_score_and_label(self):
        dimensions = dict(zip(("D1", "D2", "D3", "D4"), map(successful, (1, 1, .5, .5))))
        self.assertEqual(aggregate(dimensions)["score"], .8)
        self.assertEqual(aggregate(dimensions)["result"], "Good")
        custom = {"D1": .2, "D2": .2, "D3": .2, "D4": .4}
        self.assertEqual(aggregate(dimensions, weights=custom)["score"], .7)

    def test_incomplete_dimension_does_not_become_zero_score(self):
        dimensions = {key: successful(1) for key in ("D1", "D2", "D3", "D4")}
        dimensions["D2"] = {"status": "llm_error", "score": None}
        self.assertIsNone(aggregate(dimensions)["score"])

    def test_reject_invalid_scores_and_incomplete_json(self):
        for score in (True, -.25, .6, 2, "0.5", None, float("nan")):
            with self.subTest(score=score), self.assertRaises(ValueError):
                snap_score(score)
        for value in (
            {"score": 1, "critical_failure": False},
            {"score": 1, "rationale": "", "critical_failure": False},
            {"score": 1, "rationale": "checked", "critical_failure": "false"},
            {"score": 1, "rationale": "checked"},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_review(json.dumps(value), "D1")

    def test_paper_d1_does_not_require_v2_contradiction_fields(self):
        parsed = parse_review('{"score": 0, "rationale": "no evidence", "critical_failure": true}', "D1")
        self.assertTrue(parsed["critical_failure"])

    def test_fenced_json_allowed_but_extra_prose_rejected(self):
        raw = '{"score": 1, "rationale": "checked", "critical_failure": false}'
        fence = chr(96) * 3
        self.assertEqual(parse_review(fence + "json\n" + raw + "\n" + fence, "D1")["score"], 1)
        with self.assertRaises(ValueError):
            parse_review("Here is the review: " + raw, "D1")
