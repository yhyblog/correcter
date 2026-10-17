"""Current stage authority plus the independent first-eight activation gate."""
import hashlib
import json
import copy
import re
import socket
from pathlib import Path
from qio import PACKAGE, QUEUE, CAMPAIGN, read, ref, sha, verify, under
from qoccupancy import policy as effective_occupancy_policy

AUTH_SHA = 'd73448042b71ecb06940e8d891caf0ef8bef005018f155ee2743903981992928'
FIRST_RELEASE = 'P11_A_COMMON_POOL_QUEUE8_FIRST_V1'
FIRST_TASK = 'A11_COMMON_POOL_QUEUE8_FIRST_V1'


class AuthorityFault(RuntimeError):
    pass


class AwaitingRelease(AuthorityFault):
    pass


def current(node, *, host=None, admission=True):
    host = socket.gethostname() if host is None else host
    control = read(QUEUE/'CONTROL.json')
    effective_occupancy_policy(control,node)
    row = control['authorization']
    if row != dict(path='persistent_queue/AUTHORIZATION_V2.json', sha256=AUTH_SHA):
        raise AuthorityFault('authority changed; old V1/new unknown authority cannot dispatch')
    auth = read(verify(row))
    if admission:
        for item in auth['plan'].values():verify(item)
    if auth['hosts'].get(node) != host:
        raise AuthorityFault('node host identity mismatch')
    if control.get('global_stop'):
        raise AuthorityFault('explicit global stop')
    if not control['nodes'].get(node, {}).get('enabled'):
        raise AuthorityFault('node disabled')
    if admission and (QUEUE/'nodes'/node/'STOP.json').exists():
        raise AuthorityFault('node admission stop requested')
    if node=='A' and admission:
        legacy=control['nodes']['A'].get('legacy_exit_gate',{})
        if legacy.get('satisfied') is not True:raise AwaitingRelease('legacy complete exit/publication gate not satisfied')
        verify(legacy['closure']);verify(legacy['acceptance'])
    if auth['training_or_formal_evaluation_authorized'] or auth['deletion_authorized']:
        raise AuthorityFault('unexpected scientific scope; explicit new implementation required')
    return auth, control


def verify_manifest(row, *, payloads=False, seen=None):
    path = verify(row)
    document = read(path)
    if not payloads:
        return document
    seen = set() if seen is None else seen
    if str(path) in seen:
        return document
    seen.add(str(path))
    for item in document.get('files', []):
        verify(item)
    for item in document.get('inherited_manifests', []):
        verify_manifest(item, payloads=True, seen=seen)
    return document


def package_ready():
    ready = read(QUEUE/'package/READY.json')
    if ready['package_root'] != str(PACKAGE) or ready['authorization_sha256'] != AUTH_SHA:
        raise AuthorityFault('package READY identity mismatch')
    manifest = verify_manifest(ready['manifest'], payloads=True)
    if ready['status'] != 'READY' or ready['scientific_compute_performed_during_preparation'] != 0:
        raise AuthorityFault('package not frozen/CPU checked')
    return ready


def first_grant(*, required=True):
    path = CAMPAIGN/'releases'/(FIRST_RELEASE+'.json')
    if not path.exists():
        if required:
            raise AwaitingRelease('independent first8 release not yet published')
        return None
    release = read(path)
    if release.get('status') != 'released' or release.get('release_id') != FIRST_RELEASE:
        raise AuthorityFault('first8 release is not released')
    if release.get('task_id') != FIRST_TASK or release.get('task_revision') != 1:
        raise AuthorityFault('first8 task identity')
    if release.get('authorization_sha256') != AUTH_SHA or release.get('owner') != 'A':
        raise AuthorityFault('first8 stage/node authority')
    if release.get('owner_host') != socket.gethostname():
        raise AuthorityFault('first8 host identity')
    if release.get('formal_parent_concurrency') != 8 or release.get('max_commands') != 1 or release.get('max_claims') != 1 or release.get('max_retries') != 0:
        raise AuthorityFault('first8 exact concurrency/one-shot caps')
    for key in ('proposal', 'runtime_manifest', 'resource_admission','control_plane_aux'):
        verify(release[key])
    if release['control_plane_aux']!=ref(PACKAGE/'CONTROL_PLANE_AUX.json'):
        raise AuthorityFault('explicit control-plane monitoring/FD/storage budget binding required')
    if release['proposal']['path'] != str(PACKAGE/'proposal/first8/PROPOSAL.json'):
        raise AuthorityFault('first8 proposal path')
    proposal = read(release['proposal']['path'])
    if release['resource_caps'] != proposal['resource_caps'] or release['source_keys'] != proposal['source_keys']:
        raise AuthorityFault('first8 source/vector mismatch')
    if release['runtime_manifest'] != proposal['package_manifest']:
        raise AuthorityFault('first8 code binding mismatch')
    if release['runtime_manifest'] != read(QUEUE/'package/READY.json')['runtime_manifest']:
        raise AuthorityFault('first8 differs from published immutable runtime')
    if release.get('resource_admission_decision') != 'accept_requested8_with_declared_unknowns':
        raise AuthorityFault('explicit8 resource decision required; never fall back to2')
    # SHA-bound operational override supersedes the frozen legacy holder clause.
    # It cannot change this release's scientific scope, sources or caps.
    effective_occupancy_policy(node='A')
    entries = [x for x in read(CAMPAIGN/'TASK_BOARD.json')['tasks'] if x.get('id') == FIRST_TASK]
    if len(entries) != 1 or entries[0].get('status') not in ('ready', 'running') or entries[0].get('owner') != 'A':
        raise AuthorityFault('first8 board must be unique ready/running A task')
    if entries[0].get('revision') != 1 or entries[0].get('release') != 'releases/'+FIRST_RELEASE+'.json':
        raise AuthorityFault('first8 board binding')
    return release, ref(path)


def collection_gate(*, sequence, admission=True):
    auth, control = current('A', admission=admission)
    if control.get('remaining_common_pool_collection_enabled') is False:
        raise AuthorityFault('legacy475 collection superseded/disabled; occupancy override cannot reopen it')
    if auth['collection_source_limits_by_node']['A'] != 475 or auth['max_collection_parallel_parents_by_node']['A'] != 8:
        raise AuthorityFault('collection stage limits drift')
    if sequence == 1:
        release, release_ref = first_grant()
        if (CAMPAIGN/'releases'/(FIRST_RELEASE+'_CLOSED.json')).exists():
            raise AuthorityFault('first command closed; opportunity not reusable')
        return release_ref
    grant_path = QUEUE/'nodes/A/CONTINUATION_GRANT.json'
    if not grant_path.exists():
        raise AwaitingRelease('first8 machine validation/automatic continuation grant absent')
    grant = read(grant_path)
    if grant['authorization_sha256'] != AUTH_SHA or grant['automatic_continuation'] is not True:
        raise AuthorityFault('continuation authority mismatch')
    verify(grant['first_release']); verify(grant['first_validation']); verify(grant['runtime_manifest'])
    if grant['runtime_manifest']['path'] != str(PACKAGE/'RUNTIME_MANIFEST.json'):
        raise AuthorityFault('continuation code version mismatch')
    return ref(grant_path)


def validate_proposal(p, *, full=False):
    if p.get('synthetic') is not False or p.get('node') != 'A' or p.get('status') not in ('ready', 'running'):
        raise AuthorityFault('production rejects synthetic or wrong node/state')
    current('A', admission=False)
    if p['owner_host'] != socket.gethostname() or p['concurrency'] != 8:
        raise AuthorityFault('production host/explicit8 mismatch')
    if not re.fullmatch(r'A_pool_v2_b[0-9]{3}', p['job_id']) or type(p['sequence']) is not int or not 1 <= p['sequence'] <= 60:
        raise AuthorityFault('invalid bounded deterministic job identity')
    if p['job_id'] != 'A_pool_v2_b%03d' % p['sequence']:
        raise AuthorityFault('sequence/job mismatch')
    expected_paths = dict(output=str(CAMPAIGN/'results/A/PERSISTENT_QUEUE_RUNS'/p['job_id']),
        cache=str(CAMPAIGN/'work/A/PERSISTENT_QUEUE_CACHE'/p['job_id']),
        claim=str(QUEUE/'claims/A'/(p['job_id']+'.json')),
        command_record=str(QUEUE/'commands/A'/(p['job_id']+'.json')))
    if p['paths'] != expected_paths or p['one_parent_per_GPU'] is not True or p['source_retry'] is not False:
        raise AuthorityFault('immutable runtime path/retry identity')
    from qplan import resource_vector, auxiliary
    plan = read(verify(p['source_plan']))
    frozen = {r['source_key']:r for r in plan['sources']}
    budgets = read(verify(p['source_budgets']))['rows']
    if not 1 <= len(p['parents']) <= 8 or len(set(p['source_keys'])) != len(p['parents']):
        raise AuthorityFault('parent cardinality or duplicate source')
    if len({r['device']['gpu_uuid'] for r in p['parents']}) != len(p['parents']):
        raise AuthorityFault('one parent per unique fixed GPU')
    devices = [r['device'] for r in read(QUEUE/'plan/NEXT8_FORMAL_CONCURRENCY_V1.json')['parents']]
    base = read(PACKAGE/'config/BASE_PARENT_A.json')
    for slot, parent in enumerate(p['parents']):
        row = frozen[parent['source_key']]
        if row['owner'] != 'A' or row['initial_state'] != 'pending':
            raise AuthorityFault('terminal/reserved/wrong-owner source')
        if any(parent['source'].get(k) != v for k,v in row['source'].items()):
            raise AuthorityFault('source identity/split/seed changed')
        if parent['device'] != devices[slot] or parent['resource_caps'] != budgets[row['source']['task']]['resource_caps']:
            raise AuthorityFault('device or per-task initialization budget changed')
        for key in ('config', 'source_ref', 'initialization_ref'):
            verify(parent[key])
        cfg = read(parent['config']['path'])
        normalized = copy.deepcopy(cfg)
        for key in ('source','device','source_signature','source_manifest_ref','initialization_source_manifest'):
            normalized[key] = base[key]
        normalized['native']['device'] = base['native']['device']
        normalized['control']['cut'] = base['control']['cut']
        if normalized != base:
            raise AuthorityFault('science or runtime configuration changed outside exact source/device bindings')
        if cfg['source'] != parent['source'] or read(parent['source_ref']['path']) != parent['source']:
            raise AuthorityFault('source manifest/config mismatch')
        if cfg['device'] != parent['device'] or cfg['native']['device'] != parent['device']:
            raise AuthorityFault('native/policy physical identity mismatch')
        sig = hashlib.sha256(json.dumps(cfg['source'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if cfg['source_signature'] != sig:
            raise AuthorityFault('source signature mismatch')
        if cfg['source_manifest_ref']['path'] != parent['source_ref']['path'] or cfg['source_manifest_ref']['sha256'] != parent['source_ref']['sha256'] or cfg['initialization_source_manifest'] != parent['initialization_ref']['path']:
            raise AuthorityFault('configuration source/initialization references differ')
        from task_profiles import validate_config
        from observation_phase import validate_observation_config
        validate_config(cfg); validate_observation_config(cfg)
        for key in ('output', 'cache'):
            if Path(parent['paths'][key]) != Path(p['paths'][key])/parent['parent_key']:
                raise AuthorityFault('parent path isolation mismatch')
    if p['resource_caps'] != resource_vector(p['parents']):
        raise AuthorityFault('aggregate vector mismatch')
    expected = auxiliary(len(p['parents']),8,read(PACKAGE/'config/LEGACY_PROPOSAL.json')['storage'])
    if (p['timeouts'],p['scheduler_caps'],p['storage']) != expected:
        raise AuthorityFault('auxiliary/time/storage caps drift')
    under(p['paths']['output'], CAMPAIGN/'results/A/PERSISTENT_QUEUE_RUNS')
    under(p['paths']['cache'], CAMPAIGN/'work/A/PERSISTENT_QUEUE_CACHE')
    for key in ('package_manifest','code_manifest','input_manifest','external_manifest','inherited_package_manifest','closure','sidecar_ready'):
        verify(p[key])
    if full:
        seen=set()
        for key in ('package_manifest','code_manifest','input_manifest','external_manifest','inherited_package_manifest'):
            verify_manifest(p[key], payloads=True, seen=seen)
        for parent in p['parents']:
            verify_manifest(parent['initialization_ref'], payloads=True, seen=seen)
    return p
