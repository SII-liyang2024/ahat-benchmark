"""Full-scene preparation and exact STRIPS simulation from AHAT's audited reviewer."""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from .vendor.scene_graph import PDDLDomainParser, SceneGraphManager


def sexpr(text: str) -> list[Any]:
    tokens = re.findall(r'\(|\)|[^\s()]+', re.sub(r';[^\n]*', '', text).lower())
    stack, roots = [], []
    for token in tokens:
        if token == '(':
            node = []
            (stack[-1] if stack else roots).append(node)
            stack.append(node)
        elif token == ')':
            if not stack:
                raise ValueError('Unbalanced PDDL')
            stack.pop()
        else:
            if not stack:
                raise ValueError('PDDL atom outside expression')
            stack[-1].append(token)
    if stack or len(roots) != 1:
        raise ValueError('Unbalanced or multiple PDDL expressions')
    return roots[0]


def effects(expr: list[Any], bindings: dict[str, str]) -> list[tuple[bool, tuple[str, ...]]]:
    """Refuse unsupported effects instead of silently ignoring them."""
    if not expr:
        raise ValueError('Empty effect expression')
    if expr[0] == 'and':
        result = []
        for child in expr[1:]:
            result.extend(effects(child, bindings))
        return result
    negative = expr[0] == 'not'
    if negative and (len(expr) != 2 or not isinstance(expr[1], list)):
        raise ValueError(f'Malformed negative effect: {expr}')
    atom = expr[1] if negative else expr
    if not atom or atom[0] in {'when', 'forall', 'exists', 'or', 'increase', 'assign'} or any(isinstance(x, list) for x in atom):
        raise ValueError(f'Unsupported effect: {expr}')
    grounded = tuple(bindings.get(x, x) for x in atom)
    if any(x.startswith('?') for x in grounded):
        raise ValueError(f'Unbound effect: {grounded}')
    return [(negative, grounded)]


def full_problem(
    scene_graph: dict[str, Any], domain_path: Path, dropped: list[list[str]] | None = None
) -> str:
    manager = SceneGraphManager(copy.deepcopy(scene_graph), str(domain_path))
    facts = sorted({tuple(p) for obj in manager.object_map.values() for p in obj['data']['predicates']})
    objects = sorted((name, manager.get_object_pddl_type(name)) for name in manager.object_map)
    known = {name for name, kind in objects}
    missing = {v for fact in facts for v in fact[1:] if v not in known}
    if missing:
        raise ValueError(f'Scene predicates reference undeclared objects: {sorted(missing)}')
    domain = sexpr(domain_path.read_text(encoding='utf-8'))
    type_tokens = next(x[1:] for x in domain if isinstance(x, list) and x[0] == ':types')
    parents, pending = {}, []
    i = 0
    while i < len(type_tokens):
        if type_tokens[i] == '-':
            parents.update({x: type_tokens[i + 1] for x in pending})
            pending = []
            i += 2
        else:
            pending.append(type_tokens[i])
            i += 1
    parents.update({x: 'object' for x in pending})

    def compatible(actual, expected):
        seen = set()
        while actual and actual not in seen:
            if actual == expected:
                return True
            seen.add(actual)
            actual = parents.get(actual)
        return False

    types = dict(objects)
    filtered = []
    for fact in facts:
        expected = manager.pddl_parser.predicates.get(fact[0])
        good = (
            all(re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]*', v) for v in fact[1:])
            and expected is not None and len(expected) == len(fact) - 1
            and all(compatible(types[v], t) for v, t in zip(fact[1:], expected.values()))
        )
        if good:
            filtered.append(fact)
        elif dropped is not None:
            dropped.append(list(fact))
    object_text = '\n'.join(f'{name} - {kind}' for name, kind in objects if re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]*', name))
    fact_text = '\n'.join('(' + ' '.join(f) + ')' for f in filtered)
    domain_name = next(x[1] for x in domain if isinstance(x, list) and x[0] == 'domain')
    return f'(define (problem review) (:domain {domain_name}) (:objects {object_text}) (:init {fact_text}) (:goal (and)))'


def simulate(problem: str, plan: list[str], actions: dict[str, Any]) -> list[list[str]]:
    """Apply simultaneous delete/add sets. VAL checks preconditions separately."""
    initial = next(x[1:] for x in sexpr(problem) if isinstance(x, list) and x and x[0] == ':init')
    if any(any(isinstance(y, list) for y in x) for x in initial):
        raise ValueError('Unsupported non-atomic initial state')
    state = {tuple(x) for x in initial}
    for text in plan:
        action = sexpr(text)
        if not action or any(not isinstance(arg, str) for arg in action):
            raise ValueError(f'Malformed action: {text}')
        spec = actions[action[0]]
        parameters = list(spec['parameters'])
        if len(parameters) != len(action) - 1:
            raise ValueError(f'Wrong action arity: {text}')
        grounded = effects(spec['effect'], dict(zip(parameters, action[1:])))
        state.difference_update(atom for neg, atom in grounded if neg)
        state.update(atom for neg, atom in grounded if not neg)
    return [list(x) for x in sorted(state)]


def final_state(problem: str, plan: list[str], domain_path: Path) -> list[list[str]]:
    return simulate(problem, plan, PDDLDomainParser(domain_path.read_text(encoding='utf-8')).actions)
