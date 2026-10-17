"""Frozen model adapter; old runtime/core imports are read-only dependencies.

Construction is deliberately gated by a frozen analysis protocol. CPU preparation
never calls create_engine. Proposal math is unchanged; the actual policy queue
capacity is now ten even though the sampler returns a fifty-command plan.
"""
from __future__ import annotations


def create_engine(config, stage):
    from .protocol import require_stage_budget
    require_stage_budget(config, stage)
    import time
    import numpy as np
    import torch
    from ac_tmil.ogg.experiment import Engine
    from ac_tmil.ogg_research.experiment import ResearchEngine
    from ac_tmil.ogg.common import ROOT as OGG, cpu_batch
    from corrector.actions import ActionTransform, GuidanceError
    from corrector.critic import FrozenSelector
    from corrector.guidance import FrozenObjective, FlowHook
    from corrector.candidates import construct
    from .protocol import candidate_seed, seed_for

    class Native10Engine(Engine):
        spatial = ResearchEngine.spatial

        def __init__(self):
            # Existing config must exist, preventing the legacy loader's fallback
            # registration path from ever writing into the archived experiment.
            if not (OGG / 'config.json').is_file():
                raise FileNotFoundError('Frozen OGG config required')
            super().__init__(OGG, with_c=False)
            self.study = config
            self.selector = FrozenSelector(config.get('critic_assets'))
            self.hook.close()
            self.transform = ActionTransform(self.transform.q01, self.transform.q99, self.transform.eps)
            self.hook = FlowHook(self.runtime.backend.policy.model, self.transform,
                                 dict(config['guidance'], mode='velocity'))
            self.runtime.clear_policy(10)

        def propose(self, seed, loss=None):
            runtime = self.runtime
            runtime.clear_policy(10)
            before = runtime.fingerprint()
            self.hook.begin(loss)
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
            allocated_start = torch.cuda.memory_allocated()
            begin = time.perf_counter()
            fallback = None
            attempts = 1
            failed_forwards = failed_backwards = 0
            try:
                first_action, plan, _ = runtime.native_action(seed)
            except GuidanceError as error:
                fallback = str(error)
                logs = list(self.hook.logs)
                failed_forwards = self.hook.objective_calls
                failed_backwards = self.hook.failed_backward_calls
                self.hook.begin(None)
                runtime.clear_policy(10)
                first_action, plan, _ = runtime.native_action(seed)
                attempts = 2
            else:
                logs = list(self.hook.logs)
            torch.cuda.synchronize()
            seconds = time.perf_counter() - begin
            times = list(self.hook.times)
            objective_calls = failed_forwards + self.hook.objective_calls
            noise_sha256 = self.hook.last_noise_sha
            self.hook.begin(None)
            if len(times) != 10 or not np.allclose(times, np.arange(10, 0, -1)/10, atol=1e-6):
                raise ValueError('Unexpected flow schedule')
            if runtime.fingerprint() != before:
                raise ValueError('Proposal changed environment')
            if plan.shape != (50, 4) or not np.isfinite(plan).all():
                raise ValueError('Invalid raw generated plan')
            np.testing.assert_array_equal(np.asarray(first_action, dtype=np.float32), plan[0])
            return plan, dict(seconds=seconds, policy_calls=attempts, fallback=fallback,
                updates=logs, times=times, noise_sha256=noise_sha256,
                execution_horizon=10, generated_horizon=50, first_action_exact=True,
                peak_cuda_allocated_mib=torch.cuda.max_memory_allocated()/2**20,
                peak_cuda_reserved_mib=torch.cuda.max_memory_reserved()/2**20,
                incremental_peak_cuda_allocated_mib=(torch.cuda.max_memory_allocated()-allocated_start)/2**20,
                objective_forward_calls=objective_calls,
                backward_calls=failed_backwards+sum(x['backward_calls'] for x in logs))

        @torch.no_grad()
        def context(self, frames, proprio, past, language, step):
            return cpu_batch(self.spatial(list(frames), proprio), proprio, past, language, step)

        @torch.no_grad()
        def monitor(self, observed, next_five):
            batch = dict(observed, actions=torch.as_tensor(next_five, device='cuda:0')[None])
            benefits = {}
            for member, world in self.worlds.items():
                future, _ = world(batch)
                benefits[str(member)] = float(self.gates[member](batch, future))
            return dict(gate=float(np.mean(list(benefits.values()))), member_benefits=benefits,
                        trigger_metric='frozen G0 mean benefit; no D-error trigger')

        def make_bank(self, observed, case, cut):
            start = time.perf_counter()
            before = self.runtime.fingerprint()
            seed = candidate_seed(case, cut, namespace=config['seed_namespace'])
            raw_base, base_stats = self.propose(seed)
            base = np.clip(raw_base, -1, 1).astype(np.float32)
            objective = FrozenObjective(observed, base, selector=self.selector)
            generated, stats = {}, {}
            noise_hashes = {'replan': base_stats['noise_sha256']}
            for mode in ('velocity', 'direct'):
                self.hook.settings['mode'] = mode
                generated[mode], stats[mode] = self.propose(seed, objective)
                generated[mode] = np.clip(generated[mode], -1, 1).astype(np.float32)
                noise_hashes[mode] = stats[mode]['noise_sha256']
            if len(set(noise_hashes.values())) != 1 or noise_hashes['replan'] is None:
                raise ValueError('Guidance candidate noise mismatch')
            tick = time.perf_counter()
            gradient, gradient_stats = objective.gradient()
            slopes = ((self.transform.q99-self.transform.q01)/2).detach().cpu().numpy()
            post_direction = gradient.numpy()*slopes[None]**2
            gradient_stats['seconds'] = time.perf_counter()-tick
            plans, matching = construct(base, generated['velocity'], generated['direct'], post_direction,
                seed_for('matching_random', case['task'], case['env_seed'], cut, namespace=config['seed_namespace']),
                config['matching'])
            predictions = {name: objective.evaluate(plan[:10]) for name, plan in plans.items()}
            # Preserve the native raw a0 at every coordinate. Matching masks
            # saturated coordinates, so only bounded, feasible deltas change.
            # This removes an extra replan-only clamp from the interruption test.
            from .commands import preserve_raw_anchor
            plans = {name: preserve_raw_anchor(raw_base, base, plan)
                     for name, plan in plans.items() if name not in ('velocity_native', 'direct_native')}
            from .bank_audit import audit_raw_bank
            raw_audit = audit_raw_bank(raw_base, plans, config['matching'])
            if predictions['replan']['mean_gain'] != 0:
                raise ValueError('a0 anchor moved')
            objective.verify()
            self.verify()
            if self.runtime.fingerprint() != before:
                raise ValueError('Candidate bank changed environment')
            return plans, dict(base_seed=seed, base_generation=base_stats, guidance=stats,
                post_gradient=gradient_stats, matching=matching, predictions=predictions,
                raw_bank_audit=raw_audit, noise_hashes=noise_hashes, candidate_bank_seconds=time.perf_counter()-start,
                objective_stats=objective.stats(), same_noise=True, a0_slot=0,
                saved_before_any_branch=True, command_semantics='raw a0 plus matched feasible delta',
                critic_action_representation='bounded proxy T; raw saturated coordinates remain unchanged in all arms'), dict(raw_a0=raw_base, critic_a0=base,
                    mask=(1-np.abs(base[:10].astype(float))>=config['matching']['boundary_clearance']),
                    **{name+'_actual_delta':plan[:10].astype(float)-raw_base[:10] for name,plan in plans.items()},
                    **{name+'_critic_commands':np.clip(plan[:10],-1,1) for name,plan in plans.items()},
                    post_command_gradient=gradient.numpy(), post_internal_metric_direction=post_direction)

        def verify(self):
            super().verify()
            if hasattr(self, 'selector'):
                self.selector.verify()

    return Native10Engine()
