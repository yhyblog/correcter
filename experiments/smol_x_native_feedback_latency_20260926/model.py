"""Native-backbone visual feedback; untrained D/G0 architecture timing only."""
import json
import math
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[2]


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    tmp.replace(path)


class ParallelModel:
    def __init__(self, cfg):
        import numpy as np
        import torch
        sys.path.insert(0, str(WORKSPACE / 'ACT-RECAP/src'))
        from ac_tmil.future_aware.models import WorldModel, BenefitModel
        self.np, self.torch, self.cfg = np, torch, cfg
        self.device = cfg.get('device', 'cuda:0')
        torch.set_num_threads(cfg.get('cpu_threads', 2))
        torch.backends.cuda.matmul.allow_tf32 = True
        started = time.perf_counter()
        if cfg['kind'] == 'smolvla':
            from smol_native import SmolNative
            self.native = SmolNative(cfg)
            self.channels = 960
        else:
            from x_native import XNative
            self.native = XNative(cfg)
            self.channels = 1024
        norm = dict(mean=[0.] * 4096, std=[1.] * 4096, delta_scale=[1.] * 4096)
        self.worlds, self.gates = [], []
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(20260926)
            # Same widths and member counts as the previously measured heads.
            for _ in range(2):
                self.worlds.append(WorldModel(norm, width=256).to(self.device).eval().requires_grad_(False))
                self.gates.append(BenefitModel(norm, width=128).to(self.device).eval().requires_grad_(False))
            matrix = torch.randn(self.channels, 256)
            self.projection = torch.linalg.qr(matrix, mode='reduced').Q.to(self.device)
        self.plan_stream = torch.cuda.Stream(device=self.device)
        self.feedback_stream = torch.cuda.Stream(device=self.device)
        initialized = torch.cuda.Event()
        initialized.record(torch.cuda.current_stream(self.device))
        self.plan_stream.wait_event(initialized)
        self.feedback_stream.wait_event(initialized)
        initialized.synchronize()
        self.language_cache = {}
        self.ready = dict(status='ready', pid=os.getpid(), kind=cfg['kind'],
            native=getattr(self.native, 'metadata', {}),
            D=[sum(p.numel() for p in m.parameters()) for m in self.worlds],
            G0=[sum(p.numel() for p in m.parameters()) for m in self.gates],
            heads_initialization='random; zero mean and unit scale; no old PI05 feature weights',
            visual_input=f'native {self.channels}-channel spatial tokens -> 4x4 pooling -> fixed random orthogonal channel projection to 256 -> 4096',
            language_input='native masked token embedding mean; zero padded to 2048; task cache',
            plan_cuda_stream=int(self.plan_stream.cuda_stream),
            feedback_cuda_stream=int(self.feedback_stream.cuda_stream),
            extra_PI05_model=False, extra_PI05_features=False, no_training=True, Q_included=False,
            load_seconds=time.perf_counter() - started)
        write(Path(cfg['output']) / 'MODEL_READY.json', self.ready)

    def prepare(self, record):
        np, torch = self.np, self.torch
        with np.load(record['snapshot_npz'], allow_pickle=False) as saved:
            ctx = dict(frames=saved['frames'].copy(), props=saved['props'].astype(np.float32),
                past_actions=np.clip(saved['prefix'][-4:].astype(np.float32), -1, 1),
                raw_plan=saved['raw'].astype(np.float32),
                currentobs=dict(pixels=saved['pixels'].copy(), agent_pos=saved['agent_pos'].astype(np.float32)),
                instruction=record['instruction'], step=int(record.get('cut', 5)), raw_age=int(record.get('age', 5)))
        if ctx['instruction'] not in self.language_cache:
            with torch.cuda.stream(self.feedback_stream), torch.no_grad():
                lang = self.native.language(ctx).reshape(-1).float()
                lang = torch.nn.functional.pad(lang, (0, 2048-lang.numel()))
                self.language_cache[ctx['instruction']] = lang
                self.feedback_stream.synchronize()
        ctx['language'] = self.language_cache[ctx['instruction']]
        return ctx

    def plan(self, ctx, seed):
        torch = self.torch
        with torch.cuda.device(self.device), torch.cuda.stream(self.plan_stream), torch.no_grad():
            raw = self.native.plan(ctx, seed)
            self.plan_stream.synchronize()
        return raw

    def monitor(self, ctx):
        torch, np = self.torch, self.np
        with torch.cuda.device(self.device), torch.cuda.stream(self.feedback_stream), torch.no_grad():
            tokens = self.native.encode_five(ctx).float()
            side = math.isqrt(tokens.shape[1])
            grid = tokens.transpose(1, 2).reshape(5, self.channels, side, side)
            cells = torch.nn.functional.adaptive_avg_pool2d(grid, (4, 4)).flatten(2).transpose(1, 2)
            history = (cells @ self.projection).flatten(1)[None]
            age = ctx['raw_age']
            batch = dict(history=history,
                history_mask=torch.ones((1, 5), device=self.device, dtype=torch.bool),
                proprio=torch.as_tensor(ctx['props'], device=self.device)[None],
                proprio_mask=torch.ones((1, 5), device=self.device, dtype=torch.bool),
                past_actions=torch.as_tensor(ctx['past_actions'], device=self.device)[None],
                language=ctx['language'][None],
                remaining=torch.tensor([(300-ctx['step'])/300], device=self.device),
                actions=torch.as_tensor(np.clip(ctx['raw_plan'][age:age+5], -1, 1), device=self.device)[None])
            values = []
            for world, gate in zip(self.worlds, self.gates):
                future, _ = world(batch)
                values.append(gate(batch, future))
            gates = torch.stack(values).reshape(-1).float().cpu().numpy()
            self.feedback_stream.synchronize()
        return dict(gate=float(gates.mean()), member_gates=gates.tolist())
