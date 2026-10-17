"""Resident frozen D/G0 with five-step predictions retained for causal scoring."""
import numpy as np
import torch
from base_numeric_engine import Engine as BaseEngine


class Engine(BaseEngine):
    def __init__(self, state, config, out):
        super().__init__(state, config, out)
        self.feature_scale = np.stack([
            world.delta_scale.detach().float().cpu().numpy()
            for world in self.worlds.values()
        ])
        if self.feature_scale.shape != (2, 4096) or not np.isfinite(self.feature_scale).all() or not (self.feature_scale > 0).all():
            raise ValueError('Expected fixed positive train-only D delta scales')

    @staticmethod
    def actual_features(observed):
        return observed['history'][0].detach().float().cpu().numpy()

    @torch.no_grad()
    def forecast(self, observed, next_five):
        batch = dict(observed, actions=torch.as_tensor(next_five, device=self.device)[None])
        predictions, benefits = [], {}
        for key, world in self.worlds.items():
            self.counts['D_forward'] += 1
            future, _ = world(batch)
            predictions.append(future[0].detach().float().cpu().numpy())
            self.counts['G0_forward'] += 1
            benefits[str(key)] = float(self.gates[key](batch, future))
        prediction = np.stack(predictions)
        if prediction.shape != (2, 5, 4096) or not np.isfinite(prediction).all() or not np.isfinite(list(benefits.values())).all():
            raise ValueError('Invalid frozen D/G0 output')
        return dict(prediction=prediction, gate=float(np.mean(list(benefits.values()))), member_benefits=benefits)
