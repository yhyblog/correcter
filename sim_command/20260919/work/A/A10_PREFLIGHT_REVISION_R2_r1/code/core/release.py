"""Fail closed against this campaign's exact release, before any heavy import."""
from pathlib import Path
import json
import platform
import re
import subprocess
from .resume import sha
from .validation import ContractError
from .accounting import RESOURCE_KEYS
from .initialization import EXPECTED_CAPS, CONTROL_MINIMUM_LIMITS


def verify_device(release, query=None):
    """Read actual NVML identity after authorization, before model initialization."""
    output = query if query is not None else subprocess.run(
        ['nvidia-smi', '--query-gpu=index,uuid,name,driver_version', '--format=csv,noheader'],
        check=True, capture_output=True, text=True, timeout=15).stdout
    found = []
    for line in output.splitlines():
        fields = [x.strip() for x in line.split(',')]
        if len(fields) == 4 and fields[1] == release['gpu_uuid']:
            found.append(fields)
    expected = [str(release['gpu_index']), release['gpu_uuid'], release['gpu_model'], release['driver']]
    if found != [expected]:
        raise ContractError('Current GPU/driver identity differs from the finite release')
    return expected


def authorize(control, release, proposal, *, hostname=None):
    hostname = hostname or platform.node()
    if control.get('campaign_id') != 'corrector-sim-20260919' or release.get('campaign_id') != control['campaign_id']:
        raise ContractError('Wrong campaign')
    if control.get('stop_requested') or control.get('formal_gpu_runs_enabled') is not True:
        raise ContractError('Formal compute is not released by current CONTROL')
    if control.get('mode') not in ('preflight', 'run'):
        raise ContractError('Preparation cannot authorize physical work')
    if release.get('release_id') != control.get('active_compute_release_id'):
        raise ContractError('Release is not the active explicit compute release')
    if release.get('task_id') not in control.get('allowed_task_ids', []) or release.get('task_id') != proposal['task_id']:
        raise ContractError('Task not authorized')
    if release.get('owner_host') != hostname or release.get('node_role') != 'A':
        raise ContractError('Release assigned to another host')
    if release.get('task_revision') != proposal['task_revision'] or release.get('proposal_sha256') != proposal['_sha256']:
        raise ContractError('Proposal identity differs from release')
    if release.get('status') != 'released' or release.get('max_retries') != 0 or proposal['max_retries'] != 0:
        raise ContractError('Explicit release and zero retry required')
    if release.get('resource_caps') != proposal['resource_caps']:
        raise ContractError('Frozen finite resource caps differ')
    caps = release['resource_caps']
    if set(caps) != set(RESOURCE_KEYS) or any(type(v) is not int or v < 0 for v in caps.values()):
        raise ContractError('Every resource cap must be an explicit nonnegative integer')
    limits = control.get('current_compute_limits', {})
    if caps['vla_sampling_calls'] > limits.get('model_gpu_inference_calls', 0) or caps['simulator_attempts'] > limits.get('simulator_attempts', 0) or caps['optimizer_updates'] > limits.get('training_updates', 0):
        raise ContractError('Proposal exceeds current global CONTROL caps')
    for field in ('release_id', 'wave_id', 'shard_id', 'run_id', 'gpu_uuid', 'driver', 'runtime', 'gpu_model'):
        if not isinstance(release.get(field), str) or not release[field].strip():
            raise ContractError(f'Missing concrete runtime identity: {field}')
    for field in ('release_id', 'wave_id', 'shard_id', 'run_id'):
        if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', release[field]) is None:
            raise ContractError('Unsafe runtime identity: ' + field)
    if type(release.get('gpu_index')) is not int or release['gpu_index'] < 0:
        raise ContractError('Missing concrete GPU index')
    if release.get('timeout_seconds') != proposal['timeout_seconds']:
        raise ContractError('Timeout differs from finite proposal')
    if release.get('wave_participants') != ['A']:
        raise ContractError('This one-node diagnostic launcher requires an A-only wave')
    if (proposal.get('initialization_caps') != EXPECTED_CAPS or release.get('initialization_caps') != proposal['initialization_caps']
            or any(type(v) is not int for v in release['initialization_caps'].values())):
        raise ContractError('Explicit audited initialization caps required')
    if proposal.get('control_minimum_limits') != CONTROL_MINIMUM_LIMITS:
        raise ContractError('Proposal lacks the audited global minimum budgets')
    for key, value in CONTROL_MINIMUM_LIMITS.items():
        if type(limits.get(key)) is not int or limits[key] < value:
            raise ContractError('Current global CONTROL lacks initialization/compute budget: ' + key)
    for field in ('kill_grace_seconds', 'timeout_scope', 'external_source_manifest_sha256'):
        if release.get(field) != proposal.get(field) or field not in release:
            raise ContractError('Release must freeze ' + field)
    if proposal['timeout_seconds'] != 1800 or proposal['kill_grace_seconds'] != 30:
        raise ContractError('Only the frozen 1800+30 diagnostic process timeout is proposed')
    return caps


def check_task_board(campaign, release, proposal, release_path):
    rows = json.loads((Path(campaign) / 'TASK_BOARD.json').read_text())['tasks']
    matches = [r for r in rows if r['id'] == release['task_id']]
    if len(matches) != 1:
        raise ContractError('Exact diagnostic task absent or ambiguous in TASK_BOARD')
    row = matches[0]
    if row.get('revision') != proposal['task_revision'] or row.get('owner') != 'A' or row.get('status') not in ('ready', 'released', 'in_progress', 'running'):
        raise ContractError('Diagnostic task is not currently released to A')
    if not row.get('release') or (Path(campaign) / row['release']).resolve() != Path(release_path).resolve():
        raise ContractError('TASK_BOARD does not bind this exact compute release')


def load_authorization(campaign, release_path, proposal_path):
    campaign = Path(campaign).resolve()
    release_path = Path(release_path).resolve()
    if not release_path.is_relative_to(campaign / 'releases'):
        raise ContractError('Only a new release in this campaign can authorize work')
    proposal = json.loads(Path(proposal_path).read_text())
    proposal['_sha256'] = sha(proposal_path)
    control = json.loads((campaign / 'CONTROL.json').read_text())
    release = json.loads(release_path.read_text())
    authorize(control, release, proposal)
    check_task_board(campaign, release, proposal, release_path)
    for ref in proposal['required_inputs']:
        if sha(ref['path']) != ref['sha256']:
            raise ContractError(f"Frozen input changed: {ref['path']}")
    if release.get('code_manifest_sha256') != sha(proposal['code_manifest_path']):
        raise ContractError('Release does not bind this code snapshot')
    manifest = json.loads(Path(proposal['code_manifest_path']).read_text())
    root = Path(proposal['code_manifest_path']).parent
    if root.resolve() != Path(__file__).resolve().parents[1]:
        raise ContractError('Executing code is not the bound snapshot')
    for ref in manifest['files']:
        path = (root / ref['path']).resolve()
        if not path.is_relative_to(root) or sha(path) != ref['sha256']:
            raise ContractError('Code snapshot changed')
    external = Path(proposal['external_source_manifest_path'])
    if sha(external) != proposal['external_source_manifest_sha256']:
        raise ContractError('External initialization source manifest changed')
    for ref in json.loads(external.read_text())['files']:
        if str(Path(ref['path']).resolve()) != ref['realpath'] or sha(ref['path']) != ref['sha256']:
            raise ContractError('Installed initialization source changed: ' + ref['path'])
    release['_sha256'] = sha(release_path)
    return control, release, proposal


def check_current_authorization(campaign, release_path, release, proposal):
    if sha(release_path) != release['_sha256']:
        raise ContractError('Active release contents changed during execution')
    current = json.loads((Path(campaign) / 'CONTROL.json').read_text())
    authorize(current, release, proposal)
    check_task_board(campaign, release, proposal, release_path)
