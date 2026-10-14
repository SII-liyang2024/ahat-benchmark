import json
from pathlib import Path
from types import SimpleNamespace

from ahat_benchmark.judge.prompts import PROMPTS


PROJECT = Path(__file__).resolve().parents[1]
DOMAIN = PROJECT / 'vendor/pddl/domain_0102_test.pddl'
VAL = PROJECT / 'vendor/val/Validate'


def scene(blocked=False):
    links = [['room_1', 'table_1', 'in'], ['table_1', 'cup_1', 'on']]
    if blocked:
        links.append(['cup_1', 'lid_1', 'on'])
    return {
        'rooms': [{'name': 'room_1', 'states': {}}],
        'furnitures': [{'name': 'table_1', 'states': {}}],
        'objects': [{'name': 'cup_1', 'states': {}}, {'name': 'lid_1', 'states': {}}],
        'agent': [{'name': 'agent_0', 'location': 'cup_1', 'holding': None}],
        'person': [], 'links': links,
    }


PLAN = ['(pick_from_surface agent_0 cup_1 table_1)']


class FakeClient:
    def __init__(self, responder=None, base_url='https://judge.example/v1'):
        self.base_url = base_url
        self.responder = responder
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        dimension = next(key for key, prompt in PROMPTS.items() if prompt == kwargs['messages'][0]['content'])
        count = sum(call['messages'][0]['content'] == PROMPTS[dimension] for call in self.calls)
        raw = self.responder(dimension, count) if self.responder else {
            'score': 1, 'rationale': 'checked', 'critical_failure': False,
        }
        if isinstance(raw, Exception):
            raise raw
        return SimpleNamespace(
            id='response-id', model='test-judge',
            usage=SimpleNamespace(model_dump=lambda: {'total_tokens': 12}),
            choices=[SimpleNamespace(message=SimpleNamespace(content=raw if isinstance(raw, str) else json.dumps(raw)))],
        )
