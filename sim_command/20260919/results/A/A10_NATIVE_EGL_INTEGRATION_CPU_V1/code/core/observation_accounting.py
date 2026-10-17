"""Confirmed native reset, complete RGB observations and saved usable artifacts."""
import hashlib
import json
import os
from pathlib import Path


class ObservationAccounting:
    PHASES = ('diagnostic', 'post_control')

    def __init__(self, path):
        self.path = Path(path)
        self.path.open('x').close()
        self.returned, self.usable = [], []

    def record(self, row):
        with self.path.open('a') as f:
            f.write(json.dumps(row) + '\n'); f.flush(); os.fsync(f.fileno())

    def observation_returned(self, phase):
        if len(self.returned) >= 2 or phase != self.PHASES[len(self.returned)]:
            raise ValueError('Observation phase repeated or out of order')
        self.record({'phase': phase, 'event': 'complete_observation_returned'})
        self.returned.append(phase)

    def artifact_written(self, phase, path):
        if phase not in self.returned or phase in self.usable:
            raise ValueError('Invalid usable observation artifact order/count')
        path = Path(path)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('No saved usable artifact')
        self.record({'phase': phase, 'event': 'usable_observation_artifact', 'path': str(path),
                     'size_bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        self.usable.append(phase)

    def summary(self, initialization):
        missing = {p: ('complete observation did not return' if p not in self.returned else
                       'complete observation returned but no usable NPZ saved')
                   for p in self.PHASES if p not in self.usable}
        return {'diagnostic_native_resets_returned': initialization.get('returned_operation_units', {}).get('diagnostic_reset_calls', 0),
                'diagnostic_observations_returned': int('diagnostic' in self.returned),
                'post_control_observations_returned': int('post_control' in self.returned),
                'complete_observations_returned': len(self.returned),
                'usable_observation_artifacts': len(self.usable),
                'usable_observation_artifacts_by_phase': {p: int(p in self.usable) for p in self.PHASES},
                'missing_observation_reasons': missing,
                'observation_counter_semantics': 'Native reset return excludes RGB; complete observations count both phases; usable artifacts count one verified saved NPZ per phase, PPM views add zero; crash gaps remain unresolved'}
