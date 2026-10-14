"""Verbatim paper prompts used by AHAT's GPT-6.1-sol review."""
from pathlib import Path


PROMPT_VERSION = 'paper-rubric-2602.12244v2'
PROMPT_DIR = Path(__file__).parent / 'paper_rubric'
NAMES = {
    'D1': 'Goal_Achievement',
    'D2': 'Intent_Understanding',
    'D3': 'Completeness',
    'D4': 'Execution_Quality',
}
PROMPTS = {key: (PROMPT_DIR / (name + '.txt')).read_text(encoding='utf-8') for key, name in NAMES.items()}
