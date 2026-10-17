"""Sealed, cross-protocol canonical inputs; no PCA, model or simulator imports.

create_bundle writes only a NEW ROOT/input_bundles/<version>. Its three source
specifications contain dataset_binding (the original five-field binding),
collection (config_path/config_sha256/freeze_path/freeze_sha256), bank_version;
round2_train additionally requires completion_audit from the independent wave
audit. Child protocol identities are never rewritten into the bundle identity.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re

import numpy as np

from . import storage
from .dataset import STATE_KEYS, STATE_SHAPES, PAIR_INDICES, load_saved_dataset
from .candidates13 import CANDIDATE_ORDER
from .protocol import TASKS, canonical_hash, protocol_digest, validate_manifest

SCHEMA = 'native10_final_input_bundle_v1'
ROLES = ('round1_train', 'round2_train', 'development')
CHECKS = ('manifest_registration', 'source_seals', 'bank_seals', 'branch_seals',
          'budget_attempts', 'raw_command_mapping', 'suffix_pairing', 'alias_equivalence',
          'complete_labels', 'no_future_split_access', 'scene_identity', 'replacement_chain')
BINDING_KEYS = {'path', 'seal_sha256', 'input_audit_path', 'input_audit_sha256', 'input_protocol_sha256'}
CONTRACT_SHA = 'bceeccecbe2f5a41a27f05e8245ee8b9e68c525e8cb3d653a3460f275fab54a0'


class BundleError(ValueError):
    pass


def _read(path):
    return json.loads(Path(path).read_text())


def _checked(path, digest):
    path = Path(path).resolve()
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest) or storage.sha256(path) != digest:
        raise BundleError('Bound file SHA changed: '+str(path))
    return path


def _inside(path, kind=None):
    path = Path(path).resolve()
    root = (storage.ROOT/kind if kind else storage.ROOT).resolve()
    if not path.is_relative_to(root):
        raise BundleError('Artifact escapes its workflow directory: '+str(path))
    return path


def _seal(directory, expected):
    directory = _inside(directory)
    complete = _checked(directory/'complete.json', expected)
    record = _read(complete)
    actual = {str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file() and p != complete}
    if record.get('status') != 'complete' or set(record.get('files', {})) != actual:
        raise BundleError('Incomplete or changed sealed file set')
    for name, digest in record['files'].items():
        path = (directory/name).resolve()
        if not path.is_relative_to(directory):
            raise BundleError('Sealed file escapes directory')
        _checked(path, digest)
    return record


def _collection(binding):
    cpath = _inside(_checked(binding['config_path'], binding['config_sha256']), 'main_protocols')
    fpath = _inside(_checked(binding['freeze_path'], binding['freeze_sha256']), 'main_protocols')
    config, frozen = _read(cpath), _read(fpath)
    if (frozen.get('files', {}).get(str(cpath)) != binding['config_sha256']
            or frozen.get('config_sha256') != binding['config_sha256']):
        raise BundleError('Collection freeze does not bind its actual config')
    if config.get('status') != 'frozen' or config.get('analysis_approval', {}).get('status') != 'approved':
        raise BundleError('An independently frozen collection is required')
    if config['analysis_approval'].get('protocol_sha256') != protocol_digest(config):
        raise BundleError('Collection input protocol is not its actual frozen digest')
    validate_manifest(config['episode_manifest'])
    return config, frozen


def canonical_feature_contract(collection):
    """Derive comparable raw feature/action identities from a collection freeze.

    Only JSON and file hashes are read; quantile tensors and model weights are
    never deserialized. Critic PCA projections deliberately are not equated.
    """
    config, frozen = _collection(collection)
    files = frozen['files']
    suffixes = ('ac_tmil/evaluation/metaworld_vla_features.py', 'ac_tmil/vla_features.py',
                'ac_tmil/ogg/common.py', 'ac_tmil/ogg_research/experiment.py',
                'native10_training_20260916/engine.py')
    feature_files = {}
    for suffix in suffixes:
        matches = [p for p in files if p.endswith(suffix)]
        if len(matches) != 1:
            raise BundleError('Canonical feature extractor binding missing/ambiguous: '+suffix)
        p = matches[0]; _checked(p, files[p]); feature_files[p] = files[p]
    def unique(suffix):
        paths = [p for p in files if p.endswith(suffix)]
        if len(paths) != 1:
            raise BundleError('ActionTransform binding missing/ambiguous: '+suffix)
        p = paths[0]; _checked(p, files[p]); return p
    implementation = unique('src/corrector/actions.py')
    post = unique('/policy_postprocessor.json')
    step = _read(post)['steps'][0]
    state = str((Path(post).parent/step['state_file']).resolve())
    if step['config']['norm_map']['ACTION'] != 'QUANTILES' or state not in files:
        raise BundleError('ActionTransform requires the frozen quantile metadata and state')
    _checked(state, files[state])
    groups = config.get('model_dependency_groups', {})
    if not isinstance(groups.get('vla'), str):
        raise BundleError('Canonical feature model identity is missing')
    return dict(schema='native10_canonical_features_actions_v1',
        canonical_space='vision4096_language2048_before_critic_projection',
        state_shapes={k:list(v) for k,v in STATE_SHAPES.items()},
        state_order=list(STATE_KEYS), floating_dtype='float32', masks_dtype='bool',
        temporal_order='frozen cpu_batch oldest_to_newest; mask identifies available history',
        remaining='(300-cut_step)/300', feature_extractor=feature_files, vla_sha256=groups['vla'],
        action_transform=dict(files={p:files[p] for p in (implementation, post, state)},
            config=step['config'], action_order=['x', 'y', 'z', 'gripper'],
            raw_units='native MetaWorld commands', critic_mapping='C(raw)=clip(raw,-1,1)',
            clean_to_raw='(clean+1)*(q99-q01)/2+q01; zero range uses recorded eps',
            prefix_horizon=10, a0_slot=0, normal_control_separate=True),
        execution={k:deepcopy(config[k]) for k in ('seed_namespace','source_horizon','prefix_horizon',
            'suffix_horizon','control_budget','guidance','matching','command_semantics')},
        candidate_order=list(CANDIDATE_ORDER), repeats=4,
        sampling='uniform effective whole source; no round/teacher/Q/benefit weighting')


def _critic(config, frozen, bank):
    directory = Path(config['critic_assets']).resolve()
    ranking_path, configuration = directory/'ranking.json', directory/'config.json'
    files = frozen['files']; selected = {}
    for path in (ranking_path, configuration):
        if str(path) not in files:
            raise BundleError('Generation critic preprocessing/ranking not frozen')
        _checked(path, files[str(path)]); selected[str(path)] = files[str(path)]
    ranking = _read(ranking_path); members = ranking.get('model_hashes', {})
    if len(members) != 4 or bank['critic_member_hashes'] != members:
        raise BundleError('Generation critic must bind its original four members')
    for member, digest in members.items():
        path = directory/f'models/refit/member_{member}/selected.pt'
        if files.get(str(path)) != digest or bank['model_hashes'].get('critic_'+member) != digest:
            raise BundleError('Generation checkpoint/model provenance differs')
        _checked(path, digest); selected[str(path)] = digest
    return dict(directory=str(directory), members=members, files=selected,
                preprocessing='original config plus preprocessing buffers in each SHA-bound checkpoint',
                projected_coordinates_are_not_training_inputs=True)


def _arrays(packed):
    a, rows = packed['arrays'], packed['rows']; n = len(rows)
    for key, shape in STATE_SHAPES.items():
        dtype = np.bool_ if key.endswith('_mask') else np.float32
        if a[key].shape != (n,*shape) or a[key].dtype != dtype or not np.isfinite(a[key]).all():
            raise BundleError('Noncanonical state feature shape/dtype: '+key)
    if not np.allclose(a['remaining'], (300-a['cut_step'])/300, atol=1e-7, rtol=0):
        raise BundleError('Canonical remaining feature is not the saved cut budget')
    if not a['control_valid'].all():
        raise BundleError('Complete bundle requires the separate four normal controls')
    if a['pair_indices'].shape != (n,5,2) or not np.array_equal(a['pair_indices'], np.broadcast_to(PAIR_INDICES,(n,5,2))):
        raise BundleError('Registered positive/negative candidate pairing changed')
    for index in range(n):
        raw = a['raw_actions'][index]; first = {}; aliases = []
        for slot, value in enumerate(raw):
            aliases.append(first.setdefault(value.tobytes(),slot))
        alias = np.asarray(aliases, np.int64); counts = Counter(aliases)
        weights = np.asarray([1/counts[x] for x in aliases],np.float32)
        gain = weights.copy(); gain[alias == 0] = 0
        keys = [tuple(sorted((aliases[x],aliases[y]))) for x,y in PAIR_INDICES]
        multiplicity = Counter(key for key in keys if key[0] != key[1])
        pairs = np.asarray([0 if x==y else 1/multiplicity[(x,y)] for x,y in keys],np.float32)
        for name, expected in (('alias_indices',alias),('group_ids',alias),('candidate_weights',weights),
                               ('gain_weights',gain),('pair_weights',pairs)):
            if not np.array_equal(a[name][index], expected):
                raise BundleError('Source-uniform within-loss deduplication changed: '+name)
        for group in set(aliases):
            if not np.all(a['outcomes'][index,alias==group] == a['outcomes'][index,group]):
                raise BundleError('Identical raw candidates have inconsistent paired labels')


def _round2_completion(source, binding, collection):
    spec = source.get('completion_audit')
    if not isinstance(spec, dict):
        raise BundleError('Round2 requires the independent complete-wave/ledger audit')
    directory = _inside(spec['path']); _seal(directory,spec['seal_sha256'])
    result = _read(_checked(directory/'result.json',spec['result_sha256']))
    expected = dict(collection,bank_version=source['bank_version'],protocol_sha256=binding['input_protocol_sha256'])
    gate, ledger = result.get('wave_gate',{}),result.get('ledger',{})
    config,_ = _collection(collection)
    ids=[r['episode_id'] for r in config['episode_manifest'] if not r.get('replacement_of') and r['split']=='train' and r.get('round')==2]
    if (result.get('schema') != 'native10_round2_dataset_completion_audit_v1' or result.get('status') != 'passed'
            or result.get('dataset_binding') != binding or result.get('collection') != expected
            or gate.get('all_300_disposed') is not True or gate.get('loaded_workers') != 32
            or gate.get('wave_exited') is not True or gate.get('planned_slot_ids') != ids or gate.get('missing_slot_ids') != []
            or ledger.get('all_attempts_charged') is not True
            or ledger.get('new_optimizer_updates') != 0
            or result.get('coverage',{}).get('planned_slot_count') != 300
            or result['coverage'].get('complete_planned_selection_evidence') is not True
            or result['coverage'].get('unresolved_or_exhausted_slot_ids') != []):
        raise BundleError('Round2 completion/ledger evidence is incomplete or mismatched')
    contract=result.get('contract',{})
    if contract.get('sha256') != CONTRACT_SHA:
        raise BundleError('Round2 completion audit lacks the approved final-input contract')
    _checked(contract['path'],CONTRACT_SHA)
    _checked(directory/'budget_snapshot.jsonl',ledger['snapshot_sha256'])
    evidence=_read(directory/'evidence.json')
    if not evidence:raise BundleError('Round2 complete-wave evidence cannot be empty')
    for path,digest in evidence.items():_checked(path,digest)
    critic=result.get('generation_critic',{})
    if (critic.get('member_hashes') != config['main_collection']['banks'][source['bank_version']]['critic_member_hashes']
            or Path(critic.get('assets','')).resolve() != Path(config['critic_assets']).resolve()):
        raise BundleError('Round2 wave loaded generation critic differs from collection identity')
    return deepcopy(spec)


def _source(role, source):
    purpose, generation = ('development',1) if role == 'development' else ('train',int(role[5]))
    binding = source['dataset_binding']
    if set(binding) != BINDING_KEYS:
        raise BundleError('Use the original five-field dataset binding without protocol rewriting')
    config, frozen = _collection(source['collection'])
    bank = config['main_collection']['banks'][source['bank_version']]
    protocol = config['analysis_approval']['protocol_sha256']
    bank_protocol = bank.get('bank_protocol_sha256',protocol)
    if (binding['input_protocol_sha256'] != protocol or bank_protocol != protocol
            or bank.get('generation_round') != generation or bank.get('kind') != 'labels13'):
        raise BundleError('Child collection, input audit and actual bank protocol/round disagree')
    manifest = config['episode_manifest']; registry = validate_manifest(manifest)
    planned = [r for r in manifest if not r.get('replacement_of') and r['split']==purpose
               and (purpose=='development' or r.get('round')==generation)]
    ids = [r['episode_id'] for r in planned]
    if len(ids) != (100 if purpose=='development' else 300) or not set(ids) <= set(bank['episode_ids']):
        raise BundleError('Child does not cover its original full planned split/round')
    if Counter(r['task'] for r in planned) != Counter({t:20 if purpose=='development' else 60 for t in TASKS}):
        raise BundleError('Original task balance changed')
    directory = _inside(binding['path'],'datasets');_seal(directory,binding['seal_sha256'])
    audit_path = _inside(_checked(binding['input_audit_path'],binding['input_audit_sha256']))
    audit = _read(audit_path)
    if (audit.get('schema') != 'native10_input_artifact_audit_v1' or audit.get('status') != 'passed'
            or audit.get('purpose') != purpose or audit.get('protocol_sha256') != protocol
            or audit.get('dataset_seal_sha256') != binding['seal_sha256']
            or audit.get('manifest_sha256') != canonical_hash(manifest) or audit.get('episode_ids') != ids
            or audit.get('bank_versions') != [source['bank_version']]
            or audit.get('missing_artifacts') or any(audit.get('checks',{}).get(k) is not True for k in CHECKS)
            or type(audit.get('completed_collections_only')) is not bool
            or role != 'round2_train' and audit['completed_collections_only']
            or audit['completed_collections_only'] and audit.get('completed_collection_slot_ids') != ids):
        raise BundleError('Complete unfiltered independently audited child data required')
    artifacts = audit.get('artifacts',[]); amap = {}
    allowed_cases=set(ids)|{key for key,row in registry.items() if row.get('replacement_of') in ids}
    for item in artifacts:
        path = _inside(item['path']);parts=path.relative_to(storage.ROOT.resolve()).parts
        allowed=(parts[0]=='sources' and len(parts)>2 and parts[1] in allowed_cases
            or parts[0]=='banks' and len(parts)>3 and parts[1]==source['bank_version'] and parts[2] in allowed_cases
            or parts[0] in ('rollouts','collections') and len(parts)>4 and parts[1]==bank['stage'] and parts[2]==source['bank_version'] and parts[3] in allowed_cases
            or path.parent==audit_path.parent and path.name in ('budget_snapshot.jsonl','scene_registry_snapshot.jsonl'))
        if not allowed:raise BundleError('Input audit attempts to read another split/round artifact')
        _checked(path,item['sha256'])
        if str(path) in amap or item.get('role') not in ('source','bank','branch','budget_snapshot'):
            raise BundleError('Ambiguous input-artifact evidence')
        amap[str(path)] = item
    ledger_paths = [Path(p) for p,v in amap.items() if v['role']=='budget_snapshot']
    if len(ledger_paths) != 1 or storage.sha256(ledger_paths[0]) != audit['ledger_snapshot_sha256']:
        raise BundleError('Immutable physical ledger snapshot is required')
    ledger_rows = [json.loads(x) for x in ledger_paths[0].read_text().splitlines()]
    ledger = {r['number']:r for r in ledger_rows}
    if len(ledger) != len(ledger_rows) or len(set(audit['referenced_attempts'])) != len(audit['referenced_attempts']):
        raise BundleError('Duplicate physical attempt identifiers')
    for number in audit['referenced_attempts']:
        if number not in ledger or ledger[number]['resource'] != 'simulator_attempts' or ledger[number]['protocol_sha256'] != protocol:
            raise BundleError('Physical attempt lost its true source protocol')
    packed = load_saved_dataset(directory,purpose,canonical_hash(manifest))
    meta = packed['metadata']; records = meta['records']
    if (meta.get('complete_planned_selection_evidence') is not True or meta['planned_episode_count'] != len(ids)
            or [r['planned_slot_id'] for r in records] != ids or meta.get('repeats') != 4
            or meta.get('candidate_order') != list(CANDIDATE_ORDER) or meta.get('a0_slot') != 0
            or meta.get('normal_control_is_separate') is not True):
        raise BundleError('Planned denominator/canonical candidates incomplete')
    resolutions = {r['planned_slot_id']:r for r in audit['slot_resolutions']}
    if set(resolutions) != set(ids) or len(resolutions) != len(audit['slot_resolutions']):
        raise BundleError('Complete original-slot resolution evidence is required')
    row_lookup = {r['episode_id']:r for r in packed['rows']}; provenance=[]
    for rec in records:
        actual, slot = rec['episode_id'],rec['planned_slot_id']; registered = registry.get(actual)
        if registered is None or registered['split'] != purpose or registered.get('replacement_of',actual) != slot:
            raise BundleError('Actual episode/whole-episode split is not registered')
        summary = rec['source_summary']; resolution = resolutions[slot]
        if summary.get('case') != registered or resolution['resolved_episode_id'] != actual:
            raise BundleError('Resolved episode differs from source or original registry')
        chain=[slot]+config['main_collection'].get('replacement_candidates',{}).get(slot,[])
        if actual not in chain or [r['episode_id'] for r in resolution['preceding_rejections']] != chain[:chain.index(actual)]:
            raise BundleError('Actual source does not preserve the original ordered replacement chain')
        if rec['status']=='no_cut':
            if rec.get('critic_eligible') or rec.get('full_episode_outcome_available') is not True or type(rec.get('native10_outcome')) is not bool or actual in row_lookup:
                raise BundleError('No-cut requires known full outcome without fabricated critic row')
        elif rec['status']=='complete' and rec.get('critic_eligible') is True and rec.get('control_complete') is True:
            if actual not in row_lookup or {k:v for k,v in row_lookup[actual].items() if k!='planned_slot_id'} != registered:
                raise BundleError('Effective critic row lost original episode registration')
        else:
            raise BundleError('Technical missing/failed labels cannot claim complete bundle')
        source_path = str((storage.ROOT/'sources'/actual/'complete.json').resolve())
        source_evidence = amap.get(source_path)
        if source_evidence is None or summary.get('protocol_sha256') != protocol:
            raise BundleError('Source seal/original protocol binding is missing')
        attempt = summary['budget_attempt']
        if attempt not in audit['referenced_attempts'] or ledger[attempt]['kind'] != 'source_capture' or ledger[attempt]['identity'] != registered['case_id']:
            raise BundleError('Source capture physical attempt identity mismatch')
        fingerprint = summary.get('scene_fingerprint'); exact = summary.get('exact_state_sha256')
        if not all(isinstance(x,str) and re.fullmatch('[0-9a-f]{64}',x) for x in (fingerprint,exact)):
            raise BundleError('Actual physical scene identity missing')
        bank_hash = None
        if rec.get('critic_eligible'):
            p = rec['provenance']; bank_path = str((storage.ROOT/'banks'/source['bank_version']/actual/f"cut{rec['cut_step']:03d}"/'complete.json').resolve())
            bank_evidence = amap.get(bank_path)
            if (p['protocol_sha256'] != bank_protocol or p['model_hashes'] != bank['model_hashes']
                    or p['source_seal_sha256'] != source_evidence['sha256'] or bank_evidence is None
                    or p['candidate_bank_sha256'] != bank_evidence['sha256']):
                raise BundleError('Candidate provenance does not preserve true bank/generation identity')
            bank_hash = p['candidate_bank_sha256']
            if any(n not in audit['referenced_attempts'] for n in rec['physical_attempt_ids']):
                raise BundleError('Candidate/control physical attempt absent from audited ledger')
        provenance.append(dict(planned_slot_id=slot,episode_id=actual,task=rec['task'],split=purpose,round=registered.get('round'),
            status=rec['status'],source=role,bank_version=source['bank_version'],bank_protocol_sha256=bank_protocol,
            generation_round=generation,generation_critic=deepcopy(bank['critic_member_hashes']),
            source_seal_sha256=source_evidence['sha256'],candidate_bank_sha256=bank_hash,
            scene_fingerprint=fingerprint,exact_state_sha256=exact,source_attempt=attempt,
            physical_attempt_ids=rec.get('physical_attempt_ids',[]),resolution=deepcopy(resolution)))
    _arrays(packed)
    completion = _round2_completion(source,binding,source['collection']) if role=='round2_train' else None
    identity = dict(pipeline_binding=deepcopy(binding),collection=deepcopy(source['collection']),
        bank_version=source['bank_version'],bank_protocol_sha256=bank_protocol,generation_round=generation,
        generation_critic=_critic(config,frozen,bank),completion_audit=completion,
        referenced_attempts=audit['referenced_attempts'],planned_episode_ids=ids)
    packed['pipeline_binding']=deepcopy(binding)
    return dict(packed=packed,identity=identity,manifest=manifest,provenance=provenance,
                features=canonical_feature_contract(source['collection']))


def _assemble(sources, feature_contract, analysis_sources):
    if set(sources) != set(ROLES):
        raise BundleError('Exactly two training rounds and original development are required')
    analysis = dict(analysis_sources)
    names = {Path(p).name for p in analysis}
    if 'NATIVE10_FINAL_INPUT_CONTRACT.md' not in names:
        raise BundleError('Final input contract provenance is required')
    contract_refs=[h for p,h in analysis.items() if Path(p).name=='NATIVE10_FINAL_INPUT_CONTRACT.md']
    if contract_refs != [CONTRACT_SHA]:
        raise BundleError('Final input contract must retain its exact approved SHA')
    for p,h in analysis.items():_checked(p,h)
    # Fail before opening any round2 dataset/outcome evidence while its wave is
    # incomplete. A passing source self-seal does not grant this full-wave gate.
    _round2_completion(sources['round2_train'],sources['round2_train']['dataset_binding'],sources['round2_train']['collection'])
    loaded={role:_source(role,sources[role]) for role in ROLES}
    manifest=loaded['round1_train']['manifest']
    if any(x['manifest'] != manifest for x in loaded.values()):
        raise BundleError('All child packs must retain the original complete registration')
    features=loaded['round1_train']['features']
    if any(x['features'] != features for x in loaded.values()) or feature_contract is not None and feature_contract != features:
        raise BundleError('Canonical extractor/ActionTransform contracts differ; never concatenate PCA coordinates')
    if loaded['development']['identity']['bank_protocol_sha256'] != loaded['round1_train']['identity']['bank_protocol_sha256']:
        raise BundleError('Development must remain in its original round1 collection')
    if loaded['round2_train']['identity']['bank_protocol_sha256'] == loaded['round1_train']['identity']['bank_protocol_sha256']:
        raise BundleError('Two actual collection protocols must remain distinguishable')
    all_provenance=[p for role in ROLES for p in loaded[role]['provenance']]
    if len({p['episode_id'] for p in all_provenance}) != 700 or len({(p['task'],p['scene_fingerprint'])for p in all_provenance}) != 700:
        raise BundleError('Actual episode/physical scene leakage across train rounds or development')
    all_attempts=[n for role in ROLES for n in loaded[role]['identity']['referenced_attempts']]
    if len(set(all_attempts)) != len(all_attempts):
        raise BundleError('Physical attempts reused across independent child datasets')
    packs={}
    for purpose,roles in (('train',ROLES[:2]),('development',ROLES[2:])):
        selected=[loaded[r]['packed']for r in roles];keys=set(selected[0]['arrays'])
        if any(set(p['arrays']) != keys for p in selected):raise BundleError('Canonical array schemas differ')
        arrays={key:np.concatenate([p['arrays'][key]for p in selected],axis=0)for key in keys}
        arrays['raw_deltas']=arrays['raw_actions']-arrays['raw_actions'][:,0:1]
        records=[deepcopy(r)for p in selected for r in p['metadata']['records']]
        rows=[deepcopy(r)for p in selected for r in p['rows']]
        expected=[r['episode_id']for r in manifest if not r.get('replacement_of')and r['split']==purpose]
        if [r['planned_slot_id']for r in records] != expected:
            raise BundleError('Combined planned source order differs from original registration')
        meta=deepcopy(selected[0]['metadata']);meta.update(purpose=purpose,selected_rounds=[1,2]if purpose=='train'else None,
            planned_episode_count=len(records),complete_critic_groups=len(rows),records=records,
            status_counts=dict(Counter(r['status']for r in records)),analysis_sources=analysis,
            complete_planned_selection_evidence=True,logical_critic_labels=len(rows)*52,
            physical_attempts_referenced=sum(len(r.get('physical_attempt_ids',[])) for r in records),
            all_simulator_attempts_referenced=sum(len(loaded[r]['identity']['referenced_attempts'])for r in roles),
            input_bundle_schema=SCHEMA,source_bindings={r:loaded[r]['identity']['pipeline_binding']for r in roles})
        packs[purpose]=dict(rows=rows,arrays=arrays,metadata=meta)
    coverage=[]
    for role in ROLES:
        for task in TASKS:
            records=[r for r in loaded[role]['packed']['metadata']['records']if r['task']==task]
            coverage.append(dict(source=role,task=task,planned=len(records),actual_initial_states=len(records),
                effective_cut=sum(r['critic_eligible']for r in records),
                no_cut=sum(r['status']=='no_cut'for r in records),
                missing_reasons=dict(Counter(r['missing_reason']for r in records if r.get('missing_reason')))))
    summary=dict(train_planned=600,train_effective=len(packs['train']['rows']),development_planned=100,
        development_effective=len(packs['development']['rows']),coverage=coverage,
        complete_planned_disposition=True,canonical_features_only=True,source_uniform=True,
        no_future_split_outcomes=True,model_calls=0,simulator_calls=0,optimizer_updates=0,pca_fits=0)
    return dict(manifest=manifest,packs=packs,source_identities={r:loaded[r]['identity']for r in ROLES},
                provenance=all_provenance,features=features,summary=summary)


def create_bundle(version, *, round1_train, round2_train, development, feature_contract=None, analysis_sources):
    """Audit completed inputs, then exclusively publish a new canonical bundle."""
    if not isinstance(version,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',version):
        raise BundleError('Use a safe NEW explicit bundle version')
    sources=deepcopy(dict(round1_train=round1_train,round2_train=round2_train,development=development))
    built=_assemble(sources,feature_contract,analysis_sources)
    dest=_inside(storage.ROOT/'input_bundles'/version,'input_bundles');dest.mkdir(parents=True,exist_ok=False)
    files={}
    for purpose,pack in built['packs'].items():
        folder=dest/purpose;folder.mkdir()
        storage.arrays(folder/'arrays.npz',**pack['arrays']);storage.dump(folder/'rows.json',pack['rows'])
        storage.dump(folder/'metadata.json',pack['metadata'])
        files.update({str(p.relative_to(dest)):storage.sha256(p)for p in folder.iterdir()})
    record=dict(schema=SCHEMA,version=version,status='complete',registered_manifest=built['manifest'],
        manifest_sha256=canonical_hash(built['manifest']),sources=sources,source_identities=built['source_identities'],
        feature_contract=built['features'],planned_provenance=built['provenance'],summary=built['summary'],
        analysis_sources=dict(analysis_sources),implementation={str(p.resolve()):storage.sha256(p)
            for p in [Path(__file__)]+[Path(__file__).parent/name for name in ('dataset.py','protocol.py','storage.py','candidates13.py')]},
        derived_files=files,child_protocols_preserved=True)
    identity=canonical_hash(record)
    storage.dump(dest/'manifest.json',record)
    storage.seal(dest,schema=SCHEMA,input_bundle_sha256=identity)
    return dict(path=str(dest),seal_sha256=storage.sha256(dest/'complete.json'),input_bundle_sha256=identity)


def load_bundle(bundle_path, expected_sha256=None):
    """Recheck child provenance and derived canonical arrays; never fit a model."""
    binding=deepcopy(bundle_path)if isinstance(bundle_path,dict)else dict(path=str(bundle_path))
    directory=_inside(binding['path'],'input_bundles')
    seal=_seal(directory,binding.get('seal_sha256',storage.sha256(directory/'complete.json')))
    record=_read(directory/'manifest.json');identity=canonical_hash(record)
    expected=expected_sha256 or binding.get('input_bundle_sha256')
    if record.get('schema') != SCHEMA or seal.get('schema') != SCHEMA or seal.get('input_bundle_sha256') != identity or expected is not None and expected != identity:
        raise BundleError('Independent aggregate input_bundle_sha256 changed')
    for p,h in record['implementation'].items():_checked(p,h)
    built=_assemble(record['sources'],record['feature_contract'],record['analysis_sources'])
    for name,value in (('registered_manifest',built['manifest']),('source_identities',built['source_identities']),
                       ('planned_provenance',built['provenance']),('summary',built['summary'])):
        if record[name] != value:raise BundleError('Derived bundle identity/provenance changed: '+name)
    for purpose,pack in built['packs'].items():
        folder=directory/purpose
        if _read(folder/'rows.json') != pack['rows'] or _read(folder/'metadata.json') != pack['metadata']:
            raise BundleError('Derived rows/coverage differ from the exact original subpacks')
        with np.load(folder/'arrays.npz',allow_pickle=False)as archive:
            if set(archive.files) != set(pack['arrays']):raise BundleError('Derived canonical array fields changed')
            for key,value in pack['arrays'].items():
                saved=archive[key]
                if saved.dtype != value.dtype or saved.shape != value.shape or saved.tobytes() != value.tobytes():
                    raise BundleError('Derived canonical array differs from source bytes: '+key)
    for p,h in record['derived_files'].items():_checked(directory/p,h)
    verification=dict(status='passed',bundle_identity=dict(path=str(directory),seal_sha256=storage.sha256(directory/'complete.json'),input_bundle_sha256=identity),
        source_bindings=deepcopy(record['source_identities']),child_protocols_preserved=True,
        canonical_arrays_verified=True,model_calls=0,simulator_calls=0,optimizer_updates=0)
    return dict(train=built['packs']['train'],development=built['packs']['development'],manifest=built['manifest'],
        bundle_manifest=record,metadata=dict(schema=SCHEMA,sources=record['source_identities']),
        summary=built['summary'],input_bundle_sha256=identity,verification=verification)


def validate_bundle(bundle_path, expected_sha256=None):
    result=load_bundle(bundle_path,expected_sha256)
    return dict(result['verification'],summary=result['summary'])
