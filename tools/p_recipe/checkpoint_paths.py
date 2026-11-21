"""Resolve exact evaluation checkpoints through a run's resume ancestry."""
import json
from pathlib import Path


def evaluation_checkpoint(configuration, samples):
    filename = f'samples_{samples}.pt'
    current = configuration
    while True:
        checkpoint = Path(current['output']) / filename
        if checkpoint.is_file():
            return checkpoint
        previous = current.get('resume_from_output')
        if not previous:
            raise FileNotFoundError(f'No exact {samples}-sample checkpoint in resume ancestry')
        current = json.loads((Path(previous) / 'configuration.json').read_text())
