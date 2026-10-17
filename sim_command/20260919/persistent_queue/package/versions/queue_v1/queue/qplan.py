"""Deterministic metadata factory; never imports model/environment packages."""
import copy
import hashlib
import math
from pathlib import Path
from qio import PACKAGE, QUEUE, CAMPAIGN, canonical, read, ref, new_json


def ordered_pending(rows, claimed=()):
    claimed = set(claimed)
    candidates = [r for r in rows if r['initial_state'] == 'pending' and
                  r['owner'] == 'A' and r['source_key'] not in claimed]
    return sorted(candidates, key=lambda r: (0 if r['source']['split'] == 'train' else 1,
                                            r['source']['ordinal'], r['source']['task']))


def resource_vector(parents):
    names = set().union(*(x['resource_caps'] for x in parents))
    return {k: sum(p['resource_caps'].get(k, 0) for p in parents) for k in sorted(names)}


def auxiliary(parent_count, concurrency, base_storage):
    if type(parent_count) is not int or not 1 <= parent_count <= 8:
        raise ValueError('one to eight actual parents required; no padding')
    if type(concurrency) is not int or not 1 <= concurrency <= 8:
        raise ValueError('invalid concurrency')
    waves = math.ceil(parent_count / concurrency)
    timeouts = dict(preparation_seconds=900, lock_wait_seconds=None, handoff_seconds=300,
                    child_seconds=1800, child_grace_seconds=30,
                    reserved_wave_seconds=waves * 27900 + 300, reserved_wave_grace_seconds=30,
                    drain_TERM_seconds=30, drain_poll_seconds=.2,
                    restoration_observation_seconds=120, end_to_end_hard_bound_seconds=None,
                    technical_validation_seconds=1800,
                    GPU_compute_seconds_cap=None, parent_seconds=27900, publication_seconds=300,
                    branch_seconds=1800, branch_grace_seconds=30, scheduler_poll_seconds=.2)
    polls = 5 * (timeouts['reserved_wave_seconds'] + 30) + 10
    scheduler = dict(parent_admissions=parent_count, branch_process_starts=15 * parent_count,
                     parent_publications=parent_count, reservation_requests=0,
                     restoration_observations=0, poll_iterations=polls,
                     ownership_scans=(1 + concurrency) * polls,
                     publication_group_scans=parent_count, maximum_active_parents=concurrency,
                     maximum_physical_GPU_assignments=parent_count)
    storage = copy.deepcopy(base_storage)
    storage.update(mode='bounded_queue_stage_v2', parent_count=parent_count,
                   admission_bytes=parent_count * 11609841664 + 536870912,
                   minimum_remaining_space_bytes=536870912,
                   minimum_available_inodes=parent_count * 70000 + 4096,
                   concurrent_parent_limit=concurrency, RAM_planning_bytes=concurrency * 64 * 1024**3,
                   monitor_max_polls=(300 + timeouts['reserved_wave_seconds'] + 30 + 30 + 4)//5 + 4)
    return timeouts, scheduler, storage


def build_metadata(rows, destination, *, job_id, sequence, package_manifest_ref,
                   code_manifest_ref, authorization_ref, concurrency=8, synthetic=False):
    """Writes only the requested metadata directory. Runtime directories stay absent."""
    destination = Path(destination).absolute()
    if not rows or len(rows) > 8 or len({r['source_key'] for r in rows}) != len(rows):
        raise ValueError('invalid frozen source selection')
    legacy = read(PACKAGE/'config/LEGACY_PROPOSAL.json')
    base = read(PACKAGE/'config/BASE_PARENT_A.json')
    table = read(PACKAGE/'config/MT50_TASK_TABLE.json')
    profiles = {r['task']: r for r in table['rows']}
    budgets = read(QUEUE/'plan/PER_TASK_PARENT_BUDGETS_V1.json')['rows']
    devices = [x['device'] for x in read(QUEUE/'plan/NEXT8_FORMAL_CONCURRENCY_V1.json')['parents']]
    if any(r['initial_state'] != 'pending' or r['owner'] != 'A' for r in rows):
        raise ValueError('not an A pending plan source')
    destination.mkdir(parents=True, exist_ok=False)
    task = 'A11_COMMON_POOL_QUEUE8_FIRST_V1' if sequence == 1 else 'A_COMMON_POOL_AUTOMATIC_BATCH'
    run = job_id
    release_id = 'P11_A_COMMON_POOL_QUEUE8_FIRST_V1' if sequence == 1 else 'QUEUE_DERIVED_' + job_id
    identity = dict(node_role='A', release_id=release_id, run_id=run, shard_id=run+'_shard',
                    task_id=task, wave_id=run+'_wave')
    paths = dict(output=str(CAMPAIGN/'results/A/PERSISTENT_QUEUE_RUNS'/run),
                 cache=str(CAMPAIGN/'work/A/PERSISTENT_QUEUE_CACHE'/run),
                 claim=str(QUEUE/'claims/A'/(job_id+'.json')),
                 command_record=str(QUEUE/'commands/A'/(job_id+'.json')))
    parents = []
    for slot, row in enumerate(rows):
        frozen = row['source']; task_name = frozen['task']; profile = profiles[task_name]
        if profile['static_cap_status'] != 'known':
            raise ValueError('retain source, block unknown cap: '+row['source_key'])
        source = copy.deepcopy(base['source']); source.update(frozen)
        source.update(instruction=profile['instruction'], purpose='frozen475 independent A collection',
                      selection='SOURCES_V2 fixed train/development, ordinal, ASCII order',
                      status='FROZEN_QUEUE_SOURCE')
        sfile = destination/('SOURCE_%d.json' % slot); new_json(sfile, source)
        init = read(PACKAGE/'config/BASE_INITIALIZATION.json')
        init['files'] = init['files'][:-1] + [profile['source_ref']]
        init['source_hooks']['native_class'] = profile['source_ref']['path']
        init['task'] = task_name; init['static_task_table'] = ref(PACKAGE/'config/MT50_TASK_TABLE.json')
        ifile = destination/('INITIALIZATION_%d.json' % slot); new_json(ifile, init)
        cfg = copy.deepcopy(base); cfg['source'] = source; cfg['device'] = copy.deepcopy(devices[slot])
        cfg['control']['cut'] = source['cut']; cfg['native']['device'] = copy.deepcopy(devices[slot])
        cfg['source_signature'] = hashlib.sha256(canonical(source).rstrip(b'\n')).hexdigest()
        cfg['source_manifest_ref'] = dict(path=str(sfile), sha256=ref(sfile)['sha256'], format='json')
        cfg['initialization_source_manifest'] = str(ifile)
        cfile = destination/('PARENT_%d.json' % slot); new_json(cfile, cfg)
        key = 'p%02d_%s_%s%04d_cut%d' % (slot,task_name[:-3].replace('-','_'),source['split'],source['ordinal'],source['cut'])
        parents.append(dict(parent_key=key, source_key=row['source_key'], source=source,
                            source_ref=ref(sfile), config=ref(cfile), initialization_ref=ref(ifile),
                            device=devices[slot], identity=dict(identity,run_id=run+':'+key),
                            resource_caps=budgets[task_name]['resource_caps'],
                            paths={k:str(Path(paths[k])/key) for k in ('output','cache')}))
    timeouts, scheduler, storage = auxiliary(len(rows), concurrency, legacy['storage'])
    proposal = dict(schema='queue_derived_batch_v1', synthetic=synthetic, job_id=job_id,
                    sequence=sequence, task_id=task, task_revision=1, release_id=release_id,
                    campaign_id='corrector-sim-20260919', node='A', owner_host=read(QUEUE/'AUTHORIZATION_V2.json')['hosts']['A'],
                    status='ready', actual_compute_authorized=False,
                    authorization_identity=identity, authorization_ref=authorization_ref,
                    package_manifest=package_manifest_ref, code_manifest=code_manifest_ref,
                    parents=parents, source_keys=[r['source_key'] for r in rows], concurrency=concurrency,
                    one_parent_per_GPU=True, resource_caps=resource_vector(parents),
                    scheduler_caps=scheduler, storage=storage, timeouts=timeouts, paths=paths,
                    source_plan=ref(QUEUE/'plan/SOURCES_V2.json'),
                    source_budgets=ref(QUEUE/'plan/PER_TASK_PARENT_BUDGETS_V1.json'),
                    input_manifest=ref(PACKAGE/'config/INPUT_MANIFEST.json'),
                    external_manifest=ref(PACKAGE/'config/EXTERNAL_SOURCE_MANIFEST.json'),
                    inherited_package_manifest=ref(PACKAGE/'config/INHERITED_PACKAGE_MANIFEST.json'),
                    closure=ref(PACKAGE/'config/STATE_FIELD_CLOSURE.json'),
                    sidecar_ready=legacy['sidecar_ready'],
                    restoration='deferred_to_queue_until_no_runnable_jobs_and_exit_publication_barriers',
                    source_retry=False, training_evaluation_deletion_authorized=False)
    new_json(destination/'PROPOSAL.json', proposal)
    return proposal
