"""Bound an existing trainer without changing its numerical optimization loop."""
import json
import os
from pathlib import Path
import sys
import time

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
import d24_common as d

_active = None
CUTOFF = 1790164800.0
REASONS = {0: None, 1: 'six_hour_window', 2: 'campaign_cutoff', 3: 'CONTROL_stop', 4: 'resource_floor'}

def time_stop_reason(now, deadline, step):
    if step >= 30000:
        return 1
    if now >= CUTOFF:
        return 2
    if now >= deadline:
        return 1
    return 0

def verify_saved_checkpoint(path, step):
    path = Path(path)
    required = ['pretrained_model/model.safetensors', 'pretrained_model/config.json',
                'pretrained_model/train_config.json', 'training_state/optimizer_state.safetensors',
                'training_state/optimizer_param_groups.json', 'training_state/rng_state.safetensors',
                'training_state/scheduler_state.json', 'training_state/training_step.json']
    for name in required:
        p = path / name
        if not p.is_file() or p.stat().st_size == 0:
            raise RuntimeError('Incomplete checkpoint: ' + name)
    if d.load(path / 'training_state/training_step.json')['step'] != step:
        raise RuntimeError('Checkpoint step mismatch')
    # Processor metadata/state is needed to preserve the trained action normalization.
    pre = path / 'pretrained_model'
    for prefix in ('policy_preprocessor', 'policy_postprocessor'):
        if not list(pre.glob(prefix + '*.json')) or not list(pre.glob(prefix + '*.safetensors')):
            raise RuntimeError('Missing checkpoint processor: ' + prefix)

def save_complete_checkpoint(upstream):
    def save(**kwargs):
        target = Path(kwargs['checkpoint_dir'])
        staging = target.with_name(target.name + '.incomplete')
        if target.exists() or staging.exists():
            raise RuntimeError('Checkpoint path already consumed; no overwrite')
        if _active is not None and _active.saved_count >= 20:
            raise RuntimeError('Finite checkpoint cap reached')
        params = dict(kwargs, checkpoint_dir=staging)
        upstream(**params)
        verify_saved_checkpoint(staging, kwargs['step'])
        d.atomic(staging / 'COMPLETE.json', dict(status='complete', step=kwargs['step'], at_utc=d.utc(),
                                               selection='last complete checkpoint, never test-best'))
        os.replace(str(staging), str(target))
        if _active is not None:
            _active.record_checkpoint(kwargs['step'], target)
    return save

class Deadline:
    def __init__(self, cfg, accelerator):
        global _active
        import torch
        self.torch = torch
        self.accelerator = accelerator
        self.main = accelerator.is_main_process
        self.output = Path(os.environ['D24_XVLA_OUTPUT'])
        self.config = d.load(os.environ['D24_XVLA_CONFIG'])
        self.saved_count = 0
        self.last_saved = 0
        self.last_checkpoint = None
        self.stop_code = 0
        self.started = time.time()
        clock = torch.tensor([self.started], dtype=torch.float64, device=accelerator.device)
        if accelerator.num_processes > 1:
            torch.distributed.broadcast(clock, src=0)
        self.started = clock.item()
        self.deadline = self.started + self.config['maximum_wall_window_seconds']
        self.last_save_time = self.started
        if (accelerator.num_processes != 8 or cfg.batch_size != 8 or cfg.seed != 42
                or cfg.steps != 30000 or cfg.eval_freq != 0 or cfg.policy.chunk_size != 30):
            raise RuntimeError('Frozen X-VLA recipe drift')
        _active = self
        if self.main:
            d.authorize(admission=True)
            d.atomic(self.output / 'WINDOW.json', dict(start_unix=self.started, deadline_unix=self.deadline,
                     scope='from before dataset/model load; stop new updates at window end and save last complete update',
                     maximum_updates=30000, seed=42, global_batch=64, rank_count=8))
            self.progress(0, force=True, phase='loading_training_assets')

    def _broadcast_int(self, value):
        flag = self.torch.tensor([int(value)], dtype=self.torch.int32, device=self.accelerator.device)
        if self.accelerator.num_processes > 1:
            self.torch.distributed.broadcast(flag, src=0)
        return int(flag.item())

    def should_stop(self, step):
        code = 0
        if self.main:
            now = time.time()
            code = time_stop_reason(now, self.deadline, step)
            if not code:
                try:
                    d.authorize()
                except Exception:
                    code = 3
            if not code and step % 50 == 0:
                available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                                 if line.startswith('MemAvailable:'))
                if available < 64 * 1024 ** 3:
                    code = 4
        self.stop_code = self._broadcast_int(code)
        return self.stop_code != 0

    def checkpoint_due(self, step):
        due = self.main and (step % 5000 == 0 or step == 30000 or time.time() - self.last_save_time >= 1800)
        return bool(self._broadcast_int(due))

    def progress(self, step, force=False, phase='training'):
        if self.main and (force or step % 50 == 0):
            d.atomic(self.output / 'status.json', dict(status='running', phase=phase, job_id=self.config['job_id'],
                     optimizer_updates=step, maximum_updates=30000, rank_count=8, global_batch=64, seed=42,
                     last_complete_checkpoint=self.last_checkpoint, last_saved_step=self.last_saved,
                     elapsed_window_seconds=time.time() - self.started, at_utc=d.utc()))

    def record_checkpoint(self, step, path):
        self.saved_count += 1
        self.last_saved = step
        self.last_checkpoint = str(path)
        self.last_save_time = time.time()
        d.atomic(self.output / 'LAST_COMPLETE_CHECKPOINT.json', dict(step=step, checkpoint=str(path),
                 pretrained_model=str(path / 'pretrained_model'), selection='last complete checkpoint within fixed training window',
                 at_utc=d.utc(), test_results_used=False))
        self.progress(step, force=True, phase='checkpoint_saved')

    def finish(self, step, last_saved_step):
        if self.main:
            if step <= 0 or last_saved_step != step or self.last_saved != step:
                raise RuntimeError('No final complete saved update available')
            d.atomic(self.output / 'status.json', dict(status='complete' if self.stop_code in (0, 1, 2) else 'partial',
                     phase='finished', job_id=self.config['job_id'], optimizer_updates=step,
                     maximum_updates=30000, completion_reason=REASONS[self.stop_code] or 'maximum_updates',
                     seed=42, global_batch=64, rank_count=8, last_saved_step=self.last_saved,
                     last_complete_checkpoint=self.last_checkpoint, checkpoint_count=self.saved_count,
                     elapsed_window_seconds=time.time() - self.started, at_utc=d.utc(), test_results_used=False))
