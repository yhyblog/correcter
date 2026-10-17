"""Read-only JSON publication check. Passing never grants compute permission.

Reads only the supplied small JSON metadata and this package's small manifests;
does not follow input/code/external manifest entries or run the real launcher.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE/'code'))
from core.contracts import CAMPAIGN, TASK, RELEASE, ContractError, validate_metadata
from core.handoff import HANDOFF_SPEC

MAX_JSON_BYTES = 1024 * 1024

def small_json(path):
    path = Path(path)
    if path.suffix != '.json':
        raise ContractError('Only small JSON metadata may be read')
    with path.open('rb') as f:
        raw = f.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ContractError('Metadata exceeds the 1 MiB read limit')
    return json.loads(raw), hashlib.sha256(raw).hexdigest(), len(raw)

def check(control_path, board_path, release_json, release_path, hostname):
    expected_release = CAMPAIGN/'releases'/(RELEASE+'.json')
    if Path(release_path).resolve() != expected_release:
        raise ContractError('Only designated V3 release path accepted')
    closure_path = expected_release.with_name(RELEASE+'_CLOSED.json')
    if closure_path.exists():
        raise ContractError('Release closure exists')
    proposal, proposal_sha, _ = small_json(PACKAGE/'proposal/PROPOSAL.json')
    manifests = {}
    for key, relative in {
        'config':'config/CONFIG.json', 'input_manifest':'INPUT_MANIFEST.json',
        'external_sources':'EXTERNAL_SOURCE_MANIFEST.json',
        'code_manifest':'code/CODE_MANIFEST.json', 'authorization_identity':'proposal/IDENTITY.json',
    }.items():
        expected = PACKAGE/relative
        row = proposal[key]
        if Path(row['path']).resolve() != expected:
            raise ContractError('Metadata reference path mismatch: '+key)
        value, actual_sha, size = small_json(expected)
        if row['sha256'] != actual_sha or row['size_bytes'] != size:
            raise ContractError('Small metadata manifest identity mismatch: '+key)
        manifests[key] = value
    identity = manifests['authorization_identity']
    if proposal['task_id'] != TASK or proposal['task_revision'] != 1 or identity['task_id'] != TASK or identity['release_id'] != RELEASE:
        raise ContractError('V3 proposal identity mismatch')
    if proposal['required_release_path'] != str(expected_release):
        raise ContractError('Proposal release path mismatch')
    cfg = manifests['config']
    for key in ('device','cuda_environment','timeout_seconds','kill_grace_seconds'):
        if proposal[key] != cfg[key]:
            raise ContractError('Proposal/config mismatch: '+key)
    if proposal.get('occupancy_handoff') != HANDOFF_SPEC or cfg.get('occupancy_handoff') != HANDOFF_SPEC:
        raise ContractError('V3 handoff config/proposal mismatch')
    for name in ('input_manifest','external_sources'):
        rows = [x for x in manifests[name]['files'] if x['path'] == HANDOFF_SPEC['guard_path']]
        if (len(rows) != 1 or rows[0]['sha256'] != HANDOFF_SPEC['guard_expected_sha256']
                or rows[0]['size_bytes'] != HANDOFF_SPEC['guard_expected_size_bytes']):
            raise ContractError('Future installed guard manifest mismatch: '+name)
    control, _, _ = small_json(control_path)
    board, _, _ = small_json(board_path)
    release, _, _ = small_json(release_json)
    proposal['_sha256'] = proposal_sha
    validate_metadata(control, board, release, proposal, expected_release, hostname)
    row = next(t for t in board['tasks'] if t.get('id') == TASK)
    for key in ('run_id','wave_id','shard_id'):
        if row.get(key) != release[key] or release[key] != identity[key]:
            raise ContractError('Prepared V3 publication identity mismatch: '+key)
    if release.get('real_command') != [identity['command_path'], identity['release_path']]:
        raise ContractError('Published command metadata mismatch')
    return dict(status='PASS_METADATA_ONLY_NOT_AUTHORIZATION', task_id=TASK, release_id=RELEASE,
        board_status=row['status'], release_status=release['status'], proposal_sha256=proposal_sha,
        manifest_entries_followed=False, hardware_identity_verified=False,
        real_launcher_invocations=0, compute_release_claims=0, holder_operations=0,
        large_weight_hashes=0, publication_is_authorization=False)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--control', required=True)
    p.add_argument('--board', required=True)
    p.add_argument('--release-json', required=True, help='Staged candidate or separately issued real release JSON')
    p.add_argument('--release-path', default=str(CAMPAIGN/'releases'/(RELEASE+'.json')), help='Intended canonical release path, independent of staged JSON file')
    p.add_argument('--host', default=platform.node(), help='Declared A hostname; does not query GPU hardware')
    args = p.parse_args()
    try:
        result = check(args.control, args.board, args.release_json, args.release_path, args.host)
    except (ContractError, KeyError, ValueError, OSError, TypeError, StopIteration) as error:
        print(json.dumps(dict(status='REJECTED_METADATA_ONLY', error_type=type(error).__name__, error=str(error), real_launcher_invocations=0, compute_release_claims=0), indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0

if __name__ == '__main__':
    sys.exit(main())
