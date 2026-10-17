"""Separate confirmed native-reset returns, full observations, and saved usable artifacts."""
import hashlib
import json
import os
from pathlib import Path


class ObservationAccounting:
    def __init__(self, path):
        self.path = Path(path)
        self.path.open('x').close()
        self.returned = 0
        self.usable = 0

    def record(self, row):
        with self.path.open('a') as f:
            f.write(json.dumps(row) + '\n'); f.flush(); os.fsync(f.fileno())

    def observation_returned(self):
        if self.returned: raise ValueError('Only one diagnostic observation may return')
        self.record({'phase': 'diagnostic_observation_returned'})
        self.returned = 1

    def artifact_written(self, path):
        if not self.returned or self.usable: raise ValueError('Invalid usable artifact order/count')
        path = Path(path)
        if not path.is_file() or path.stat().st_size == 0: raise ValueError('No saved usable artifact')
        self.record({'phase': 'usable_observation_artifact', 'path': str(path),
                     'size_bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        self.usable = 1

    def summary(self, initialization):
        return {'diagnostic_native_resets_returned': initialization.get('returned_operation_units', {}).get('diagnostic_reset_calls', 0),
                'diagnostic_observations_returned': self.returned,
                'usable_observation_artifacts': self.usable,
                'observation_counter_semantics': 'Confirmed return/write markers; raw native reset is not a full RGB observation; crash gaps stay unresolved'}
