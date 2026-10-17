"""Isolated standalone generation with the original frozen sampler and objective.

Production never imports the joint reference generator. Each invocation samples
its own a0 and only its own direction. Model construction follows the NEW gate.
"""
from __future__ import annotations

import hashlib
import time
import numpy as np

from .candidates import METHODS, project_solo, audit_solo, array_sha
from experiments.native10_training_20260916.protocol import candidate_seed


def _failure_json_value(value):
    """Preserve failure diagnostics in strict JSON, including explicit NaN/Inf."""
    if isinstance(value,np.ndarray):return _failure_json_value(value.tolist())
    if isinstance(value,np.generic):return _failure_json_value(value.item())
    if isinstance(value,float) and not np.isfinite(value):
        return dict(nonfinite='nan' if np.isnan(value) else ('positive_infinity' if value>0 else 'negative_infinity'))
    if isinstance(value,dict):return {str(key):_failure_json_value(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):return [_failure_json_value(item) for item in value]
    if value is None or isinstance(value,(str,bool,int,float)):return value
    return dict(diagnostic_type=type(value).__module__+'.'+type(value).__qualname__,representation=repr(value))


class SoloGenerationError(RuntimeError):
    """A failed entry retains actual completed proposal/cost evidence."""
    def __init__(self,message,evidence):
        super().__init__(message)
        self.evidence=_failure_json_value(evidence)


class ProposalGuidanceError(RuntimeError):
    """A single interrupted sampler invocation; no output or retry is usable."""
    def __init__(self,message,evidence):
        super().__init__(message)
        self.evidence=_failure_json_value(evidence)


def context_sha(observed):
    digest=hashlib.sha256()
    for name in sorted(observed):
        value=np.ascontiguousarray(observed[name])
        if not np.isfinite(value).all():raise ValueError('Nonfinite frozen source context')
        digest.update(name.encode());digest.update(str(value.dtype).encode())
        digest.update(str(value.shape).encode());digest.update(value.tobytes())
    return digest.hexdigest()


def _objective(observed,base,selector):
    from corrector.guidance import FrozenObjective
    return FrozenObjective(observed,base,selector=selector)


def generate_solo(engine,observed,case,cut,method):
    """Return raw50, complete entry metadata and this method's numeric arrays."""
    started=time.perf_counter()
    from .protocol import require_stage_budget
    require_stage_budget(engine.study,engine.stage)
    if method not in METHODS:raise ValueError('Only a registered solo method is accepted')
    config=engine.study;components={'authorization_seconds':time.perf_counter()-started};proposals=[]
    before=engine.runtime.fingerprint();observed_sha=context_sha(observed)
    seed=candidate_seed(case,cut,namespace=config['seed_namespace'])
    mode=method.removeprefix('solo_');old_mode=engine.hook.settings['mode']
    expected=1 if mode=='post' else 2

    def propose(purpose,objective=None):
        tick=time.perf_counter()
        try:
            plan,stats=engine.propose(seed,objective)
        except Exception as error:
            components[purpose+'_wall_seconds']=time.perf_counter()-tick
            failure=getattr(error,'evidence',None)
            stats=dict(failure) if isinstance(failure,dict) else dict(policy_calls=None,
                policy_call_count_known=False,error_type=type(error).__name__,error=str(error))
            proposals.append(dict(purpose=purpose,mode=None if objective is None else mode,
                seed=seed,returned_successfully=False,stats=stats))
            raise
        components[purpose+'_wall_seconds']=time.perf_counter()-tick
        proposals.append(dict(purpose=purpose,mode=None if objective is None else mode,
            seed=seed,returned_successfully=True,stats=stats))
        if stats.get('fallback') is not None or stats.get('policy_calls')!=1:
            raise ValueError('Guidance fallback or extra sampler call is a technical solo failure')
        if plan.shape!=(50,4) or plan.dtype!=np.dtype('float32') or not np.isfinite(plan).all():
            raise ValueError('Invalid independently generated raw plan')
        return plan,stats

    try:
        raw,base_stats=propose('base')
        base=np.clip(raw,-1,1).astype(np.float32)
        tick=time.perf_counter();objective=_objective(observed,base,engine.selector)
        components['objective_setup_seconds']=time.perf_counter()-tick
        native_stats=None;gradient_stats=None;extras={}
        if mode=='post':
            tick=time.perf_counter();gradient,gradient_stats=objective.gradient()
            slopes=((engine.transform.q99-engine.transform.q01)/2).detach().cpu().numpy()
            direction=gradient.numpy()*slopes[None]**2
            gradient_stats['seconds']=time.perf_counter()-tick
            components['post_gradient_seconds']=gradient_stats['seconds']
            extras=dict(post_command_gradient=gradient.numpy(),post_internal_metric_direction=direction,
                        transform_slopes=slopes)
            if gradient_stats.get('value')!=0:raise ValueError('Post gradient moved the fixed a0 anchor')
        else:
            engine.hook.settings['mode']=mode
            native,native_stats=propose(mode,objective)
            if native_stats.get('noise_sha256')!=base_stats.get('noise_sha256'):
                raise ValueError('Own guided sampler did not reuse the designated a0 initial noise')
            clipped=np.clip(native,-1,1).astype(np.float32)
            direction=clipped[:10].astype(float)-base[:10].astype(float)
            extras=dict(own_native_raw=native.copy(),own_native_clipped=clipped)
        if base_stats.get('noise_sha256') is None:raise ValueError('Missing actual initial noise SHA')
        tick=time.perf_counter();plan,matching,arrays=project_solo(raw,direction,config['matching'])
        components['matching_seconds']=time.perf_counter()-tick
        tick=time.perf_counter()
        predictions=dict(replan=objective.evaluate(base[:10]))
        predictions[method]=objective.evaluate(np.clip(plan[:10],-1,1))
        components['diagnostic_score_seconds']=time.perf_counter()-tick
        if predictions['replan']['mean_gain']!=0:raise ValueError('Designated a0 anchor changed')
        tick=time.perf_counter();proof=audit_solo(raw,plan,direction,config['matching'])
        objective.verify();engine.verify()
        if context_sha(observed)!=observed_sha or engine.runtime.fingerprint()!=before:
            raise ValueError('Standalone generation changed source context or physical state')
        components['verification_seconds']=time.perf_counter()-tick
        count=sum(row['stats']['policy_calls'] for row in proposals)
        if count!=expected:raise ValueError('Standalone entry sampled more than its own 1/2/2 contract')
        arrays.update(extras)
        elapsed=time.perf_counter()-started
        metadata=dict(schema='standalone_generation_v1',status='complete',method=method,base_seed=seed,
            base_generation=base_stats,own_generation=native_stats,post_gradient=gradient_stats,
            matching=matching,predictions=predictions,objective_stats=objective.stats(),projection_audit=proof,
            actual_policy_calls=count,expected_policy_calls=expected,proposal_records=proposals,
            native_direction=mode,other_direction_calls=0,random_calls=0,joint_bank_calls=0,cached_a0_used=False,
            context_sha256=observed_sha,raw_a0_sha256=array_sha(raw),noise_sha256=base_stats['noise_sha256'],
            same_noise=True,a0_slot=0,saved_before_any_branch=True,environment_unchanged=True,
            full_entry_seconds=elapsed,candidate_generation_seconds=elapsed,component_seconds=components,
            diagnostic_scoring_included=True,includes_own_a0_generation=True,restore_included=False,
            model_loading_included=False,component_sampler_stats_overlap_with_entry_timers=True,
            command_semantics='raw a0 plus own matched feasible delta',
            critic_action_representation='bounded proxy C(raw)',new_acceptance_or_selection_rule=False)
        return plan,metadata,arrays
    except Exception as error:
        def known_calls(row):
            count=row['stats'].get('policy_calls')
            return isinstance(count,int) and not isinstance(count,bool) and count>=0
        calls_known=all(known_calls(row) for row in proposals)
        known_count=sum(row['stats']['policy_calls'] for row in proposals if known_calls(row))
        failed_proposals=[row for row in proposals if not row['returned_successfully']]
        failed_count=(sum(row['stats']['policy_calls'] for row in failed_proposals)
            if all(known_calls(row) for row in failed_proposals) else None)
        observed_retry=any((known_calls(row) and row['stats']['policy_calls']>1)
            or row['stats'].get('automatic_retry') is True
            or row['stats'].get('sampler_retry_performed') is True for row in proposals)
        sampler_retry=observed_retry if observed_retry or calls_known else None
        evidence=dict(status='failed',method=method,base_seed=seed,proposal_records=proposals,
            completed_proposal_policy_calls=sum(row['stats']['policy_calls'] for row in proposals
                if row['returned_successfully'] and known_calls(row)),
            failed_proposal_policy_calls=failed_count,
            actual_policy_calls=known_count if calls_known else None,
            known_policy_calls=known_count,policy_call_count_known=calls_known,
            expected_policy_calls=expected,full_entry_seconds=time.perf_counter()-started,
            component_seconds=components,error_type=type(error).__name__,error=str(error),
            output_is_usable=False,successful_generation=False,
            entry_automatic_retry=False,sampler_retry_performed=sampler_retry,
            automatic_retry=sampler_retry)
        raise SoloGenerationError('Standalone generation failed: '+str(error),evidence) from error
    finally:
        engine.hook.begin(None)
        engine.hook.settings['mode']=old_mode


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
    from experiments.native10_training_20260916.protocol import candidate_seed, seed_for

    class Native10Engine(Engine):
        spatial = ResearchEngine.spatial

        def __init__(self):
            # Existing config must exist, preventing the legacy loader's fallback
            # registration path from ever writing into the archived experiment.
            if not (OGG / 'config.json').is_file():
                raise FileNotFoundError('Frozen OGG config required')
            super().__init__(OGG, with_c=False)
            self.study = config
            self.stage = stage
            self.selector = FrozenSelector(config.get('critic_assets'))
            self.hook.close()
            self.transform = ActionTransform(self.transform.q01, self.transform.q99, self.transform.eps)
            self.hook = FlowHook(self.runtime.backend.policy.model, self.transform,
                                 dict(config['guidance'], mode='velocity'))
            self.runtime.clear_policy(10)
            self.selector.verify(check_files=True)
            from pathlib import Path
            selected=config['selected_model']
            if (Path(self.selector.assets_dir).resolve()!=Path(selected['path']).resolve()
                    or self.selector.ranking['model_hashes']!=selected['member_hashes']
                    or selected['selection']!={'path':'A','step':4000}
                    or [str(Path(p).resolve()) for p in self.selector.model_paths]!=[
                        str(Path(selected['path']).resolve()/f'models/refit/member_{m}/selected.pt') for m in range(4)]):
                raise ValueError('Actually loaded standalone critic differs from the frozen A4000 binding')
            self.loaded_identity = dict(status='passed', stage=stage,
                selected_assets=str(Path(self.selector.assets_dir).resolve()),
                selected_seal_sha256=selected['seal_sha256'],
                model_paths=[str(Path(p).resolve()) for p in self.selector.model_paths],
                member_hashes=dict(self.selector.ranking['model_hashes']),
                selection=dict(path='A', step=4000), optimizer_updates=0,
                actual_selector_paths=True, checkpoint_file_sha=True,
                frozen_parameter_buffer_versions=True, eval_cpu_no_parameter_grad=True,
                generation_only=True, world_checkpoint_hashes=dict(self.identities))

        def generate_solo(self, observed, case, cut, method):
            return generate_solo(self, observed, case, cut, method)

        def make_bank(self, *args, **kwargs):
            raise RuntimeError('Joint bank generation is forbidden on the standalone production engine')

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
                torch.cuda.synchronize()
                logs = list(self.hook.logs)
                evidence = dict(status='failed', error_type=type(error).__name__, error=str(error),
                    seconds=time.perf_counter()-begin, policy_calls=1, policy_call_count_known=True,
                    output_is_usable=False, successful_generation=False, partial_sampler=True,
                    fallback=None, fallback_performed=False, automatic_retry=False,
                    sampler_retry_performed=False, updates=logs, times=list(self.hook.times),
                    noise_sha256=self.hook.last_noise_sha,
                    execution_horizon=10, generated_horizon=50,
                    peak_cuda_allocated_mib=torch.cuda.max_memory_allocated()/2**20,
                    peak_cuda_reserved_mib=torch.cuda.max_memory_reserved()/2**20,
                    incremental_peak_cuda_allocated_mib=(torch.cuda.max_memory_allocated()-allocated_start)/2**20,
                    objective_forward_calls=self.hook.objective_calls,
                    failed_backward_calls=self.hook.failed_backward_calls,
                    backward_calls=self.hook.failed_backward_calls+sum(x['backward_calls'] for x in logs),
                    environment_unchanged=runtime.fingerprint()==before)
                self.hook.begin(None)
                raise ProposalGuidanceError('Guided sampler stopped without fallback: '+str(error), evidence) from error
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

        def verify(self):
            super().verify()
            if hasattr(self, 'selector'):
                self.selector.verify()

    return Native10Engine()
