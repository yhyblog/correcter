"""Read-only main-bank/trajectory/ledger audit and new dataset publication.

No simulator or optimizer is imported or run. Main READY is checked before any
outcome path is opened. Explicit registered train/development bank versions are
the only discoverable inputs; calibration/heldout/P0 paths are never traversed.
"""
from __future__ import annotations

from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import re

import numpy as np

from . import storage
from .candidates13 import CANDIDATE_ORDER
from .dataset import (STATE_KEYS, CONTROL, DatasetError, audit_cut_selection,
                      build_dataset, raw_command_sha256, save_new_dataset)
from .protocol import canonical_hash, require_stage_budget, source_seed, validate_manifest
from .semantics import QueueSnapshot


AUDIT_SCHEMA = 'native10_input_artifact_audit_v1'
CHECK_NAMES = ('manifest_registration','source_seals','bank_seals','branch_seals',
               'budget_attempts','raw_command_mapping','suffix_pairing',
               'alias_equivalence','complete_labels','no_future_split_access','scene_identity','replacement_chain')


class ArtifactAuditError(DatasetError):
    """An existing artifact is inconsistent, not an observed unsuccessful branch."""


def _read(path):
    return json.loads(Path(path).read_text())


def _safe(path):
    path = Path(path).resolve()
    if not path.is_relative_to(storage.ROOT.resolve()):
        raise ArtifactAuditError('Input artifact escaped the new workflow root')
    return path


def _bit_equal(first, second):
    return first.shape == second.shape and first.dtype == second.dtype and first.tobytes() == second.tobytes()


def _npz(path):
    with np.load(path,allow_pickle=False) as archive:
        return {name:archive[name].copy() for name in archive.files}


def _sealed(folder, protocols, role, artifacts):
    folder = _safe(folder)
    seal = _read(folder/'complete.json')
    if seal.get('status') != 'complete' or seal.get('protocol_sha256') not in protocols:
        raise ArtifactAuditError('Artifact protocol is not explicitly registered: '+str(folder))
    actual = {str(path.relative_to(folder)) for path in folder.rglob('*')
              if path.is_file() and path != folder/'complete.json'}
    files = seal.get('files')
    if not isinstance(files,dict) or set(files) != actual:
        raise ArtifactAuditError('Sealed artifact file list changed: '+str(folder))
    for name,expected in files.items():
        path = _safe(folder/name)
        if not path.is_relative_to(folder) or storage.sha256(path) != expected:
            raise ArtifactAuditError('Sealed input SHA mismatch: '+str(path))
        artifacts[str(path)] = dict(path=str(path),sha256=expected,role=role,
                                    protocol_sha256=seal['protocol_sha256'])
    seal_path = folder/'complete.json'
    artifacts[str(seal_path)] = dict(path=str(seal_path),sha256=storage.sha256(seal_path),role=role,
                                     protocol_sha256=seal['protocol_sha256'])
    return seal


def _ledger_snapshot():
    # Reserve uses this same per-workflow /tmp mutex. The shared lock only reads
    # a complete JSONL prefix; no budget reservation or new compute occurs here.
    path = _safe(storage.ROOT/'budget/attempts.jsonl')
    with storage.LOCK_PATH.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_SH)
        raw = path.read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ArtifactAuditError('Attempt ledger has an incomplete record')
    rows = [json.loads(line) for line in raw.splitlines()]
    lookup = {}
    for row in rows:
        number = row.get('number')
        if type(number) is not int or number < 1 or number in lookup:
            raise ArtifactAuditError('Attempt ledger numbers must be unique positive integers')
        lookup[number] = row
    return raw,lookup


def _scene_registry_snapshot():
    from .scene_identity import LOCK
    with LOCK.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_SH)
        path = _safe(storage.ROOT/'scene_registry/entries.jsonl')
        raw = path.read_bytes() if path.exists() else b''
    if raw and not raw.endswith(b'\n'):
        raise ArtifactAuditError('Scene registry contains an incomplete record')
    rows = [json.loads(line) for line in raw.splitlines()]
    lookup,accepted = {},set()
    for row in rows:
        key = row['episode_id']
        if key in lookup:
            raise ArtifactAuditError('Scene registry repeated an episode identity')
        lookup[key] = row
        scene = (row['task'],row['scene_fingerprint'])
        if row['status'] == 'accepted':
            if scene in accepted:
                raise ArtifactAuditError('Accepted main scenes repeat across task-matched splits')
            accepted.add(scene)
    return raw,lookup


def _scene(case, source, summary, source_data, registry, protocol, artifacts):
    from .scene_identity import SCHEMA,PRECISION,canonical_scene,exact_arrays_hash
    folder = source/'initial_scene'
    _sealed(folder,[protocol],'source',artifacts)
    identity = _read(folder/'identity.json')
    raw = _npz(folder/'state.npz')
    canonical = canonical_scene(raw)
    expected = dict(schema=SCHEMA,precision=PRECISION,status='accepted',episode_id=case['episode_id'],
                    task=case['task'],split=case['split'],protocol_sha256=protocol,
                    budget_attempt=summary['budget_attempt'],before_first_policy_action=True,
                    privileged_critic_input=False,control_steps=0,scene_fields=canonical,
                    scene_fingerprint=canonical_hash(canonical),exact_state_sha256=exact_arrays_hash(raw),
                    state_file_sha256=storage.sha256(folder/'state.npz'))
    if any(identity.get(name) != value for name,value in expected.items()):
        raise ArtifactAuditError('Initial scene identity is not accepted canonical pre-action physics')
    if not _bit_equal(raw['runtime_physics_state'],source_data['physics_states'][0]):
        raise ArtifactAuditError('Initial scene exact state differs from the first recorded source state')
    if (summary.get('initial_scene') != identity or summary.get('scene_fingerprint') != expected['scene_fingerprint']
            or summary.get('exact_state_sha256') != expected['exact_state_sha256']
            or summary.get('initial_scene_seal_sha256') != storage.sha256(folder/'complete.json')):
        raise ArtifactAuditError('Source summary changed the sealed initial scene provenance')
    entry = registry.get(case['episode_id'])
    if not isinstance(entry,dict) or any(entry.get(name) != identity[name] for name in
        ('episode_id','task','split','scene_fingerprint','exact_state_sha256','status','budget_attempt','protocol_sha256')):
        raise ArtifactAuditError('Initial scene is absent or inconsistent in the accepted-scene registry')
    if (Path(entry['path']).resolve() != folder.resolve()
            or entry.get('seal_sha256') != storage.sha256(folder/'complete.json')):
        raise ArtifactAuditError('Scene registry path/seal differs from the accepted source')


def _attempt(folder, summary, ledger, *, kind, stage, protocol, identity):
    saved = _read(Path(folder)/'attempt.json')
    number = saved.get('number')
    if number not in ledger or saved != ledger[number]:
        raise ArtifactAuditError('Saved attempt does not match the frozen ledger snapshot')
    if (saved.get('kind') != kind or saved.get('stage') != stage or saved.get('identity') != identity
            or saved.get('protocol_sha256') != protocol or saved.get('resource') != 'simulator_attempts'
            or saved.get('amount') != 1 or summary.get('budget_attempt') != number):
        raise ArtifactAuditError('Attempt kind/stage/protocol/identity does not describe the artifact')
    return number


def _trajectory(data, *, terminal_required=False):
    needed = {'actions','physics_states','rewards','success_flags','done_flags','generated_plans',
              'generated_steps','actual_sampling_seeds','actual_sampling_steps'}
    if set(data) != needed:
        raise ArtifactAuditError('Trajectory fields differ from the registered Trace schema')
    n = len(data['actions'])
    if data['actions'].shape != (n,4) or data['actions'].dtype != np.float32 or n > 300:
        raise ArtifactAuditError('Invalid raw command trajectory shape/dtype/budget')
    for name in ('rewards','success_flags','done_flags'):
        if data[name].shape != (n,):
            raise ArtifactAuditError('Trajectory control/label count mismatch')
    if any(data[name].dtype != np.bool_ for name in ('success_flags','done_flags')):
        raise ArtifactAuditError('Trajectory success/done must be boolean')
    if data['physics_states'].ndim != 2 or len(data['physics_states']) != n+1:
        raise ArtifactAuditError('Trajectory must retain initial and every post-control physics state')
    if any(not np.isfinite(value).all() for value in data.values()):
        raise ArtifactAuditError('Nonfinite trajectory')
    if n and (data['done_flags'][:-1].any() or data['success_flags'][:-1].any()
              or bool(data['success_flags'][-1]) and not bool(data['done_flags'][-1])):
        raise ArtifactAuditError('Trajectory continued after success/termination')
    if terminal_required and (not n or not (data['done_flags'][-1] or n == 300)):
        raise ArtifactAuditError('Complete branch must reach success/termination or the original 300 cap')
    k = len(data['generated_plans'])
    if data['generated_plans'].shape != (k,50,4) or data['generated_plans'].dtype != np.float32:
        raise ArtifactAuditError('Recorded sampler plans must retain all fifty raw commands')
    for name in ('generated_steps','actual_sampling_seeds','actual_sampling_steps'):
        if data[name].shape != (k,) or data[name].dtype.kind not in 'iu':
            raise ArtifactAuditError('Generated plans must align with exact sampling identities')
    if not np.array_equal(data['generated_steps'],data['actual_sampling_steps']):
        raise ArtifactAuditError('Reported generation and actual sampling steps differ')
    return n


def _raw_suffix(data, first, expected_seeds):
    n = len(data['actions'])
    steps = data['generated_steps'].tolist()
    expected_steps = list(range(first,n,10))
    if steps != expected_steps or data['actual_sampling_seeds'].tolist() != expected_seeds:
        raise ArtifactAuditError('Actual sampler steps/seeds differ from the saved native10 suffix')
    for plan,step in zip(data['generated_plans'],steps):
        length = min(10,n-step)
        if not _bit_equal(data['actions'][step:step+length],plan[:length]):
            raise ArtifactAuditError('Suffix actions differ from the sampled raw first-ten queue')


def _source(case, path, registration, config, ledger, artifacts, scene_registry):
    current = registration.get('bank_protocol_sha256',config['analysis_approval']['protocol_sha256'])
    allowed = [current]+registration.get('allowed_source_protocol_sha256',[])
    sealed = _sealed(path,allowed,'source',artifacts)
    summary = _read(path/'summary.json')
    if (summary.get('case') != case or summary.get('cut_selection_policy') != 'analysis_lead_v1'
            or summary.get('planned_episode_retained') is not True or summary.get('outcome_filter_applied') is not False):
        raise ArtifactAuditError('Source registration/retention/fallback protocol changed')
    for name in ('vla','d','g0'):
        if summary.get('model_hashes',{}).get(name) != registration['model_hashes'].get(name):
            raise ArtifactAuditError('Source frozen model identity differs from the registered bank')
    if summary.get('protocol_sha256') != sealed['protocol_sha256']:
        raise ArtifactAuditError('Source summary protocol differs from source seal')
    source_attempt = _read(path/'attempt.json')
    expected_stage = (config['main_collection'].get('replacement_capture_stage','technical_reserve')
                      if case.get('replacement_of') else registration['stage'])
    number = _attempt(path,summary,ledger,kind='source_capture',stage=expected_stage,
                      protocol=sealed['protocol_sha256'],identity=case['case_id'])
    data = _npz(path/'trajectory.npz')
    n = _trajectory(data)
    _scene(case,path,summary,data,scene_registry,sealed['protocol_sha256'],artifacts)
    if summary.get('steps') != n or summary.get('success') != bool(data['success_flags'].any()):
        raise ArtifactAuditError('Source success/length summary differs from recorded trajectory')
    full = bool(n == 300 or n and data['done_flags'][-1])
    if summary.get('full_episode_outcome_available') != full:
        raise ArtifactAuditError('Source claims an unavailable full-episode outcome')
    namespace = summary.get('seed_namespace')
    if namespace != config['seed_namespace']:
        raise ArtifactAuditError('Source natural stream namespace changed')
    steps = data['generated_steps'].tolist()
    # A selected natural boundary is never an active cut, so there are no
    # additional generated-but-unexecuted plans at the final source step.
    _raw_suffix(data,0,[source_seed(case,i,namespace=namespace) for i in range(len(steps))])
    saved = sorted(int(item.name[3:]) for item in path.glob('cut[0-9][0-9][0-9]') if item.is_dir())
    if saved != summary.get('available_legal_cuts'):
        raise ArtifactAuditError('Available cut evidence differs from the saved source anchors')
    contexts, snapshots = {}, {}
    for cut in saved:
        anchor = _read(path/f'cut{cut:03d}'/'anchor.json')
        context = _npz(path/f'cut{cut:03d}'/'context.npz')
        snapshot = QueueSnapshot.from_dict(anchor['queue'],raw_plan=context['full_plan'])
        if (snapshot.step != cut or cut > n or cut % 10 != 5 or cut > 285
                or data['done_flags'][:cut].any() or data['success_flags'][:cut].any()
                or anchor.get('live_nonterminal') is not True
                or anchor.get('anchor_saved_without_outcome_selection') is not True):
            raise ArtifactAuditError('Saved source anchor was not a live legal midpoint')
        plan_index = snapshot.plan_start_step//10
        if (plan_index >= len(data['generated_plans']) or not _bit_equal(snapshot.raw_plan,data['generated_plans'][plan_index])):
            raise ArtifactAuditError('Saved normal queue differs from the actual source sampled plan')
        contexts[cut],snapshots[cut] = context,snapshot
    events = summary.get('events')
    if not isinstance(events,list):
        raise ArtifactAuditError('Source must retain causal G0 events')
    alarms = [event['step'] for event in events if event.get('alarm')]
    if summary.get('first_legal_alarm_step') != (min(alarms) if alarms else None):
        raise ArtifactAuditError('First alarm selection differs from recorded causal monitor events')
    audit_cut_selection(case,summary)
    return summary,data,contexts,snapshots,number


def _resolve(primary, registration, config, registry, ledger, artifacts, scene_registry):
    """First accepted source after only explicitly authorized pre-action rejects."""
    backups = config.get('main_collection',{}).get('replacement_candidates',{}).get(primary['episode_id'],[])
    if not isinstance(backups,list) or len(backups) != len(set(backups)):
        raise ArtifactAuditError('Replacement candidates must be a unique ordered registration')
    cases = [primary]
    for key in backups:
        if key not in registry or registry[key].get('replacement_of') != primary['episode_id']:
            raise ArtifactAuditError('Ordered replacement is not registered for this primary slot')
        backup = registry[key]
        if any(backup.get(name) != primary.get(name) for name in ('task','split','round','cut_rule','source_horizon')):
            raise ArtifactAuditError('Replacement changed task/split/round/cut registration')
        cases.append(backup)
    protocol = registration.get('bank_protocol_sha256',config['analysis_approval']['protocol_sha256'])
    allowed = [protocol]+registration.get('allowed_source_protocol_sha256',[])
    rejected,attempts = [],[]
    for case in cases:
        folder = _safe(storage.ROOT/'sources'/case['case_id'])
        if not (folder/'complete.json').exists():
            return case,folder,rejected,attempts
        seal = _sealed(folder,allowed,'source',artifacts)
        if not (folder/'rejection.json').exists():
            return case,folder,rejected,attempts
        record = _read(folder/'rejection.json')
        if (record.get('case') != case or record.get('episode_id') != case['episode_id']
                or record.get('planned_slot_id') != primary['episode_id']
                or record.get('reason') not in ('duplicate_initial_scene','initialization_failed')
                or record.get('before_first_action') is not True or record.get('outcome_not_observed') is not True
                or record.get('control_steps_executed') != 0 or record.get('success') is not None
                or (folder/'trajectory.npz').exists() or (folder/'summary.json').exists()):
            raise ArtifactAuditError('Replacement predecessor was not a valid pre-action rejection')
        expected_stage = (config['main_collection'].get('replacement_capture_stage','technical_reserve')
                          if case.get('replacement_of') else registration['stage'])
        attempts.append(_attempt(folder,record,ledger,kind='source_capture',stage=expected_stage,
                                  protocol=seal['protocol_sha256'],identity=case['case_id']))
        if record['reason']=='duplicate_initial_scene':
            from .scene_identity import canonical_scene,exact_arrays_hash
            initial=folder/'initial_scene'
            _sealed(initial,[seal['protocol_sha256']],'source',artifacts)
            identity=_read(initial/'identity.json')
            raw=_npz(initial/'state.npz')
            entry=scene_registry.get(case['episode_id'],{})
            duplicate=identity.get('duplicate_of') or {}
            previous=scene_registry.get(duplicate.get('episode_id'),{})
            fingerprint=canonical_hash(canonical_scene(raw))
            if (identity.get('status')!='duplicate' or identity.get('episode_id')!=case['episode_id']
                    or identity.get('scene_fingerprint')!=fingerprint
                    or identity.get('exact_state_sha256')!=exact_arrays_hash(raw)
                    or identity.get('budget_attempt')!=record['budget_attempt']
                    or identity.get('before_first_policy_action') is not True or identity.get('control_steps')!=0
                    or entry.get('status')!='duplicate' or entry.get('scene_fingerprint')!=fingerprint
                    or entry.get('seal_sha256')!=storage.sha256(initial/'complete.json')
                    or previous.get('status')!='accepted' or previous.get('task')!=case['task']
                    or previous.get('scene_fingerprint')!=fingerprint):
                raise ArtifactAuditError('Duplicate replacement lacks matching pre-action physical/registry evidence')
        rejected.append(dict(episode_id=case['episode_id'],reason=record['reason'],
                             budget_attempt=record['budget_attempt'],source_seal_sha256=storage.sha256(folder/'complete.json')))
    return None,None,rejected,attempts


def _branch_trajectory(summary, path, source_data, snapshot, plan):
    data = _npz(path/'trajectory.npz')
    n = _trajectory(data,terminal_required=True)
    cut = snapshot.step
    if n < cut or summary.get('terminal_step') != n or summary.get('success') != bool(data['success_flags'].any()):
        raise ArtifactAuditError('Branch terminal/success summary differs from trajectory')
    if not _bit_equal(data['actions'][:cut],source_data['actions'][:cut]):
        raise ArtifactAuditError('Branch restored commands differ from registered source prefix')
    for name,atol in (('physics_states',1e-10),('rewards',1e-8)):
        length = cut+1 if name == 'physics_states' else cut
        if not np.allclose(data[name][:length],source_data[name][:length],atol=atol,rtol=0):
            raise ArtifactAuditError('Branch restored state/reward differs from its sealed source')
    for name in ('success_flags','done_flags'):
        if not _bit_equal(data[name][:cut],source_data[name][:cut]):
            raise ArtifactAuditError('Branch restored flags differ from its sealed source')
    prefix = snapshot.remaining_commands if summary['method'] == CONTROL else plan[:10]
    requested = len(prefix)
    actual = min(requested,n-cut)
    if (summary.get('requested_prefix_steps') != requested or summary.get('actual_prefix_steps') != actual
            or not _bit_equal(data['actions'][cut:cut+actual],prefix[:actual])
            or summary.get('command_sha256') != hashlib.sha256(prefix.tobytes()).hexdigest()):
        raise ArtifactAuditError('Executed prefix/identity differs from the saved raw candidate or normal queue')
    suffix = summary.get('suffix_seeds')
    if not isinstance(suffix,list):
        raise ArtifactAuditError('Branch must save suffix identities')
    _raw_suffix(data,cut+requested,[row['seed'] for row in suffix])
    if data['generated_steps'].tolist() != [row['step'] for row in suffix]:
        raise ArtifactAuditError('Suffix summary differs from actual recorded sampling steps')


def load_artifact_dataset(config, bank_versions, *, purpose, rounds=None, analysis_sources=None,
                          completed_collections_only=False):
    """Audit registered actual artifacts and build a pack; no writes or compute.

    For final two-round fitting pass both registered bank versions. Each old
    version explicitly binds ``bank_protocol_sha256`` when it differs from the
    current aggregation protocol; no protocol drift is accepted implicitly.
    Missing/unsealed planned artifacts are retained as incomplete records. An
    existing sealed artifact with inconsistent evidence raises immediately.
    For a live smoke audit, completed_collections_only fixes the complete source
    collection set before the ledger snapshot. Newly finishing work is retained
    as missing until the next audit, avoiding concurrent ledger-prefix races.
    """
    if purpose not in ('train','development'):
        raise ArtifactAuditError('Calibration/heldout/P0 outcome access is forbidden')
    if type(completed_collections_only) is not bool:
        raise ArtifactAuditError('completed_collections_only must be boolean')
    if isinstance(bank_versions,str):
        bank_versions = [bank_versions]
    if not bank_versions or len(set(bank_versions)) != len(bank_versions):
        raise ArtifactAuditError('Explicit unique registered bank versions are required')
    if rounds is not None and (purpose != 'train' or not rounds
            or any(type(value) is not int or value not in (1,2) for value in rounds)):
        raise ArtifactAuditError('Only explicit train round IDs 1/2 may be selected')
    registry = validate_manifest(config['episode_manifest'])
    wanted_rounds = None if rounds is None else set(rounds)
    eligible = {key:row for key,row in registry.items() if row['split'] == purpose and not row.get('replacement_of')
                and (wanted_rounds is None or row.get('round') in wanted_rounds)}
    registered = {}
    for version in bank_versions:
        if not isinstance(version,str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',version) is None:
            raise ArtifactAuditError('Unsafe bank version')
        bank = config.get('main_collection',{}).get('banks',{}).get(version)
        if not isinstance(bank,dict) or bank.get('kind') != 'labels13':
            raise ArtifactAuditError('Training pack requires registered labels13 banks')
        stage = bank.get('stage')
        scope = config.get('stage_release_scopes',{}).get(stage)
        if stage == 'p0' or scope == 'p0_anchor_and_native10_diagnostics':
            raise ArtifactAuditError('Main input loader cannot use the P0 release')
        require_stage_budget(config,stage)  # Before opening any outcome or ledger.
        ids=bank.get('episode_ids',[])
        if not ids or len(ids)!=len(set(ids)) or bank.get('generation_round') not in (1,2):
            raise ArtifactAuditError('Bank selection requires unique primary slots and a generation round')
        for key in ids:
            row=registry.get(key)
            if (row is None or row.get('replacement_of') or row['split'] not in ('train','development')
                    or row['split']=='train' and row.get('round')!=bank['generation_round']):
                raise ArtifactAuditError('Bank selection crosses split/round or contains a nonprimary episode')
            # One local-label bank intentionally registers train and development
            # together. Validate all registration rows, but never open outcomes
            # outside the requested purpose/round.
            if key in eligible:
                if key in registered:
                    raise ArtifactAuditError('Bank selection duplicates an episode')
                registered[key] = (version,bank)
    if set(registered) != set(eligible):
        raise ArtifactAuditError('Selected banks must cover every planned episode in this dataset purpose/round')
    completed_paths={}
    if completed_collections_only:
        for key in eligible:
            version,bank=registered[key]
            candidates=[key]+config['main_collection'].get('replacement_candidates',{}).get(key,[])
            present=[]
            for candidate in candidates:
                if candidate not in registry or (candidate!=key and registry[candidate].get('replacement_of')!=key):
                    raise ArtifactAuditError('Invalid registered live-audit replacement identity')
                folder=_safe(storage.ROOT/'collections'/bank['stage']/version/registry[candidate]['case_id'])
                if (folder/'complete.json').exists():present.append(folder)
            if len(present)>1:
                raise ArtifactAuditError('More than one completed collection resolves a planned slot')
            if present:completed_paths[key]=present[0]
    ledger_raw,ledger = _ledger_snapshot()
    scene_raw,scene_registry = _scene_registry_snapshot()
    artifacts,groups,missing,used_attempts = {},[],[],[]
    checks = dict.fromkeys(CHECK_NAMES,True)
    protocol = config['analysis_approval']['protocol_sha256']
    resolutions=[]
    for key,primary in eligible.items():
        version,registration = registered[key]
        stage = registration['stage']
        bank_protocol = registration.get('bank_protocol_sha256',protocol)
        if completed_collections_only and key not in completed_paths:
            checks['complete_labels']=False
            missing.append(dict(episode_id=key,kind='collection_unsealed_at_snapshot'))
            resolutions.append(dict(planned_slot_id=key,resolved_episode_id=None,preceding_rejections=[]))
            groups.append(dict(episode=primary,source_summary=dict(
                **{name:primary[name] for name in ('episode_id','task','env_seed','split')},
                status='missing',error='collection_unsealed_at_snapshot')))
            continue
        case,source,rejected,rejection_attempts = _resolve(primary,registration,config,registry,ledger,artifacts,scene_registry)
        used_attempts.extend(rejection_attempts)
        resolutions.append(dict(planned_slot_id=key,resolved_episode_id=case['episode_id'] if case else None,
                                preceding_rejections=rejected))
        if case is None:
            checks['complete_labels']=False
            missing.append(dict(episode_id=key,kind='all_registered_initializations_rejected'))
            groups.append(dict(episode=primary,source_summary=dict(
                **{name:primary[name] for name in ('episode_id','task','env_seed','split')},
                status='failed',error='all_registered_initializations_rejected')))
            continue
        if completed_collections_only:
            folder=completed_paths[key]
            if folder.name!=case['case_id']:
                raise ArtifactAuditError('Completed collection differs from the registered replacement chain')
            _sealed(folder,[bank_protocol],'branch',artifacts)
            completion=_read(folder/'summary.json')
            if (completion.get('case')!=case or completion.get('planned_slot_id')!=key
                    or completion.get('model_hashes')!=registration['model_hashes']):
                raise ArtifactAuditError('Completed collection identity differs from the registered source')
        if not (source/'complete.json').exists():
            checks['source_seals'] = False
            missing.append(dict(episode_id=key,kind='source',path=str(source)))
            groups.append(dict(episode=case,source_summary=dict(
                **{name:case[name] for name in ('episode_id','task','env_seed','split')},
                status='failed' if source.exists() else 'missing',error='source_missing_or_unsealed')))
            continue
        summary,source_data,contexts,snapshots,attempt = _source(case,source,registration,config,ledger,artifacts,scene_registry)
        used_attempts.append(attempt)
        group = dict(episode=case,source_summary=summary)
        groups.append(group)
        if not summary['cuts']:
            continue
        cut = summary['cuts'][0]
        bank_path = _safe(storage.ROOT/'banks'/version/case['case_id']/f'cut{cut:03d}')
        if not (bank_path/'complete.json').exists():
            checks['bank_seals'] = False
            missing.append(dict(episode_id=key,kind='bank',path=str(bank_path)))
            continue
        _sealed(bank_path,[bank_protocol],'bank',artifacts)
        generation = _read(bank_path/'generation.json')
        bank_hash = storage.sha256(bank_path/'complete.json')
        identity = dict(source_seal_sha256=storage.sha256(source/'complete.json'),protocol_sha256=bank_protocol,
                        candidate_bank_sha256=bank_hash,model_hashes=registration['model_hashes'],
                        suffix_seed_namespace=config['seed_namespace'])
        for name,expected in identity.items():
            if name != 'candidate_bank_sha256' and generation.get(name) != expected:
                raise ArtifactAuditError('Bank generation provenance differs from registered source/models/protocol')
        if (generation.get('episode_id') != case['episode_id'] or generation.get('planned_slot_id') != key
                or generation.get('split') != purpose
                or generation.get('round') != case.get('round') or generation.get('cut_step') != cut
                or generation.get('candidate_bank_sha256') is not None):
            raise ArtifactAuditError('Bank generation episode/cut identity changed')
        attempt = _attempt(bank_path,generation,ledger,kind='candidate_restore',stage=stage,
                           protocol=bank_protocol,identity=str(bank_path.relative_to(storage.ROOT.resolve())))
        used_attempts.append(attempt)
        plans,metadata = _npz(bank_path/'plans.npz'),_read(bank_path/'metadata.json')
        rows = []
        for method in (*CANDIDATE_ORDER,CONTROL):
            for repeat in range(4):
                branch = _safe(storage.ROOT/'rollouts'/stage/version/case['case_id']/f'cut{cut:03d}'/method/f'repeat_{repeat}')
                if not (branch/'complete.json').exists():
                    checks['branch_seals'] = False
                    missing.append(dict(episode_id=key,kind='branch',method=method,repeat=repeat,path=str(branch)))
                    continue
                _sealed(branch,[bank_protocol],'branch',artifacts)
                row = _read(branch/'summary.json')
                if row.get('method') != method or row.get('repeat') != repeat or row.get('candidate_name') != method:
                    raise ArtifactAuditError('Branch path and logical candidate/repeat disagree')
                attempt = _attempt(branch,row,ledger,kind='branch_including_restore',stage=stage,
                    protocol=bank_protocol,identity=str(branch.relative_to(storage.ROOT.resolve())))
                used_attempts.append(attempt)
                _branch_trajectory(row,branch,source_data,snapshots[cut],None if method == CONTROL else plans[method])
                rows.append(row)
        group.update(observed={name:contexts[cut][name] for name in STATE_KEYS},candidate_plans=plans,
                     candidate_metadata=metadata,branch_summaries=rows,provenance=identity)
    if len(used_attempts) != len(set(used_attempts)):
        raise ArtifactAuditError('One ledger attempt was reassigned across independent source/bank/branch artifacts')
    bindings = config.get('analysis_documents',{}) if analysis_sources is None else analysis_sources
    for name,expected in bindings.items():
        if storage.sha256(name) != expected:
            raise ArtifactAuditError('Analysis input binding changed: '+str(name))
    packed = build_dataset(config['episode_manifest'],groups,purpose=purpose,rounds=rounds,analysis_sources=bindings)
    checks['complete_labels'] = packed['metadata']['complete_planned_selection_evidence']
    audit = dict(schema=AUDIT_SCHEMA,status='passed' if all(checks.values()) else 'incomplete',
                 dataset_seal_sha256=None,manifest_sha256=canonical_hash(config['episode_manifest']),purpose=purpose,
                 protocol_sha256=protocol,episode_ids=list(eligible),checks=checks,
                 bank_versions=list(bank_versions),artifacts=sorted(artifacts.values(),key=lambda row:row['path']),
                 slot_resolutions=resolutions,
                 missing_artifacts=missing,referenced_attempts=sorted(used_attempts),
                 ledger_snapshot_sha256=hashlib.sha256(ledger_raw).hexdigest(),
                 scene_registry_snapshot_sha256=hashlib.sha256(scene_raw).hexdigest(),
                 no_outcome_imputation=True,no_future_split_access=True,simulator_calls=0,training_updates=0)
    audit.update(completed_collections_only=completed_collections_only,
                 completed_collection_slot_ids=list(completed_paths))
    return dict(packed=packed,input_audit=audit,budget_snapshot=ledger_raw,scene_registry_snapshot=scene_raw)


def save_audited_dataset(version, audited):
    """Write one new dataset plus a frozen ledger/input audit in new paths only."""
    # save_new_dataset validates the version and latest analysis bindings first.
    packed = audited['packed']
    dataset_path = save_new_dataset(version,packed)
    folder = storage.ROOT/'dataset_audits'/version
    storage.destination(folder)
    folder.mkdir(exist_ok=False)
    snapshot = folder/'budget_snapshot.jsonl'
    with snapshot.open('xb') as stream:
        stream.write(audited['budget_snapshot'])
    audit = deepcopy(audited['input_audit'])
    if storage.sha256(snapshot) != audit['ledger_snapshot_sha256']:
        raise ArtifactAuditError('Ledger snapshot bytes changed while publishing audit')
    audit['dataset_seal_sha256'] = storage.sha256(dataset_path/'complete.json')
    audit['artifacts'].append(dict(path=str(snapshot.resolve()),sha256=storage.sha256(snapshot),role='budget_snapshot'))
    scene_snapshot=folder/'scene_registry_snapshot.jsonl'
    with scene_snapshot.open('xb') as stream:
        stream.write(audited['scene_registry_snapshot'])
    if storage.sha256(scene_snapshot) != audit['scene_registry_snapshot_sha256']:
        raise ArtifactAuditError('Scene registry snapshot changed while publishing audit')
    audit['artifacts'].append(dict(path=str(scene_snapshot.resolve()),sha256=storage.sha256(scene_snapshot),
                                  role='source',artifact_type='scene_registry_snapshot'))
    storage.dump(folder/'input_audit.json',audit)
    storage.seal(folder,schema=AUDIT_SCHEMA,dataset_seal_sha256=audit['dataset_seal_sha256'])
    return dict(path=str(dataset_path.resolve()),seal_sha256=audit['dataset_seal_sha256'],
                input_audit_path=str((folder/'input_audit.json').resolve()),
                input_audit_sha256=storage.sha256(folder/'input_audit.json'),
                input_protocol_sha256=audit['protocol_sha256'])
