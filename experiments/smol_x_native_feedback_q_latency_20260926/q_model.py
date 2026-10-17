"""Random widened Q with native-feature preprocessing; no training."""
def make_q(torch, checkpoint_state, width, seed):
    """Five original MLPs at a new width, retaining each member's preprocessing."""
    from corrector.critic import observed_features
    nn = torch.nn

    class WideQ(nn.Module):
        def __init__(self):
            super().__init__()
            keys = ['norm_mean', 'norm_std', 'residual_scale'] + [
                f'{name}_{suffix}' for name in ('visual', 'language')
                for suffix in ('center', 'basis', 'scale')]
            for key in keys:
                self.register_buffer(key, checkpoint_state[key].detach().cpu().float().clone())
            state_dim = self.visual_basis.shape[1] + self.language_basis.shape[1] + 37
            def mlp(a, b, c, last_activation=True):
                return nn.Sequential(nn.Linear(a, b), nn.SiLU(), nn.Linear(b, c),
                                     *([nn.SiLU()] if last_activation else []))
            self.state = mlp(state_dim, 2 * width, width)
            self.action = mlp(40, width, width)
            self.residual = mlp(40, width, width)
            self.head = mlp(2 * width, 2 * width, 1, False)
            self.advantage = mlp(3 * width, 2 * width, 1, False)

        def features(self, arrays):
            visual, language, other = observed_features(arrays, self.norm_mean, self.norm_std)
            parts = []
            for name, values in (('visual', visual), ('language', language)):
                parts.append((((values - getattr(self, name + '_center')) @
                    getattr(self, name + '_basis')) / getattr(self, name + '_scale')).clamp(-8, 8))
            return torch.cat([*parts, other], -1)

        def forward(self, features, actions):
            n, k, _, _ = actions.shape
            base = actions[:, 0].repeat_interleave(k, 0)
            shared = torch.cat([self.state(features).repeat_interleave(k, 0),
                                self.action(base.flatten(1))], -1)
            delta = ((actions.flatten(0, 1) - base) / self.residual_scale).flatten(1)
            actual = self.advantage(torch.cat([shared, self.residual(delta)], -1))
            zero = self.advantage(torch.cat([shared, self.residual(torch.zeros_like(delta))], -1))
            return (self.head(shared) + actual - zero).reshape(n, k)

    # Startup-only CPU RNG scope. Concurrent inference never touches global RNG.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        model = WideQ()
    return model.eval().requires_grad_(False)

