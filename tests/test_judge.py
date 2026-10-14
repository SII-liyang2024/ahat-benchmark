import unittest
from collections import Counter
from unittest.mock import patch

from ahat_benchmark.judge.evaluator import RubricEvaluator, compute_final_state
from ahat_benchmark.judge.prompts import PROMPTS
from helpers import DOMAIN, PLAN, FakeClient, scene


class JudgeTests(unittest.TestCase):
    def evaluator(self, client):
        return RubricEvaluator(client=client, model="test-judge", domain_path=DOMAIN, max_attempts=1, dimension_workers=1)

    def test_forward_state_contains_effects(self):
        state = compute_final_state(scene(), PLAN, DOMAIN)
        self.assertIn(["holding", "agent_0", "cup_1"], state)
        self.assertNotIn(["item_on_surface", "cup_1", "table_1"], state)

    def test_four_verbatim_prompts_and_default_api_parameters(self):
        client = FakeClient()
        result = self.evaluator(client).evaluate("Pick up the cup.", scene(), PLAN)
        self.assertEqual(result["score"], 1)
        self.assertEqual(len(client.calls), 4)
        self.assertEqual({c["messages"][0]["content"] for c in client.calls}, set(PROMPTS.values()))
        for call in client.calls:
            self.assertEqual(set(call), {"model", "messages"})
        self.assertEqual(result["dimensions"]["D1"]["usage"], {"total_tokens": 12})

    def test_failed_dimensions_remain_unscored_and_only_failed_dimension_resumes(self):
        def respond(key, attempt):
            score = .61 if key == "D4" and attempt == 1 else 1
            return {"score": score, "rationale": "checked", "critical_failure": False}
        client = FakeClient(respond)
        evaluator = self.evaluator(client)
        updates = []
        first = evaluator.evaluate("Pick up the cup.", scene(), PLAN, on_update=updates.append)
        self.assertIsNone(first["score"])
        self.assertEqual(len(updates), 4)
        self.assertEqual(first["dimensions"]["D4"]["status"], "parse_error")
        second = evaluator.evaluate("Pick up the cup.", scene(), PLAN, previous_dimensions=first["dimensions"])
        self.assertEqual(second["score"], 1)
        counts = Counter(next(k for k, prompt in PROMPTS.items() if c["messages"][0]["content"] == prompt) for c in client.calls)
        self.assertEqual(counts, {"D1": 1, "D2": 1, "D3": 1, "D4": 2})
        self.assertEqual(len(second["dimensions"]["D4"]["attempt_history"]), 2)

    def test_transport_failure_records_error_type_without_credentials(self):
        client = FakeClient(lambda key, count: RuntimeError("Bearer SECRET_CREDENTIAL"))
        result = self.evaluator(client).evaluate("Pick up the cup.", scene(), PLAN)
        self.assertIsNone(result["score"])
        self.assertNotIn("SECRET_CREDENTIAL", str(result))
        self.assertEqual(result["dimensions"]["D1"]["status"], "llm_error")

    def test_invalid_response_is_retried_and_raw_attempts_are_saved(self):
        client = FakeClient(lambda key, count: {"score": .61 if count == 1 else .75, "rationale": "checked", "critical_failure": False})
        evaluator = RubricEvaluator(client=client, model="test-judge", domain_path=DOMAIN, max_attempts=2)
        with patch("ahat_benchmark.judge.evaluator.time.sleep"):
            result = evaluator.evaluate("Pick up the cup.", scene(), PLAN)
        self.assertEqual(result["score"], .75)
        self.assertTrue(all(value["attempts"] == 2 for value in result["dimensions"].values()))
