import copy
import unittest

from ahat_benchmark.pddl import full_problem, simulate
from ahat_benchmark.val.validator import build_problem
from helpers import DOMAIN, PLAN, scene


class PDDLTests(unittest.TestCase):
    def test_full_scene_is_plan_independent_and_does_not_mutate_inputs(self):
        graph = scene(blocked=True)
        original = copy.deepcopy(graph)
        first = build_problem(graph, PLAN, DOMAIN)
        self.assertEqual(first, build_problem(graph, ['(navigate agent_0 cup_1 table_1)'], DOMAIN))
        self.assertIn('lid_1 - object', first)
        self.assertIn('(item_on_surface lid_1 cup_1)', first)
        self.assertEqual(graph, original)

    def test_incompatible_initial_fact_is_dropped_and_recorded(self):
        graph = scene()
        graph['objects'][0]['states']['require_floor_cleaner'] = True
        dropped = []
        problem = full_problem(graph, DOMAIN, dropped)
        self.assertNotIn('(require_floor_cleaner cup_1)', problem)
        self.assertIn(['require_floor_cleaner', 'cup_1'], dropped)

    def test_exact_effects_preserve_domain_omissions(self):
        actions = {'place': {
            'parameters': {'?a': 'agent'},
            'effect': ['and', ['handempty', '?a'], ['not', ['agent_at', '?a', 'old']], ['agent_at', '?a', 'new']],
        }}
        problem = '(define (problem p) (:init (holding robot cup) (agent_at robot old)))'
        state = simulate(problem, ['(place robot)'], actions)
        self.assertIn(['holding', 'robot', 'cup'], state)
        self.assertIn(['handempty', 'robot'], state)
        self.assertIn(['agent_at', 'robot', 'new'], state)
        self.assertNotIn(['agent_at', 'robot', 'old'], state)

    def test_add_and_delete_are_simultaneous(self):
        actions = {'test': {'parameters': {}, 'effect': ['and', ['p'], ['not', ['p']]]}}
        self.assertIn(['p'], simulate('(define (problem p) (:init))', ['(test)'], actions))

    def test_unknown_wrong_arity_unbound_and_conditional_effects_fail(self):
        problem = '(define (problem p) (:init))'
        actions = {'test': {'parameters': {'?a': 'agent'}, 'effect': ['p', '?a']}}
        with self.assertRaises(KeyError):
            simulate(problem, ['(unknown robot)'], actions)
        with self.assertRaises(ValueError):
            simulate(problem, ['(test robot cup)'], actions)
        actions['test']['effect'] = ['p', '?unbound']
        with self.assertRaises(ValueError):
            simulate(problem, ['(test robot)'], actions)
        actions['test']['effect'] = ['when', ['p'], ['q']]
        with self.assertRaises(ValueError):
            simulate(problem, ['(test robot)'], actions)
