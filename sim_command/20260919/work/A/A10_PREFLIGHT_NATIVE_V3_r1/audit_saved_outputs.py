"""Read saved arrays/JSON and encode lossless PNG; no model or environment."""
from pathlib import Path
import collections
import hashlib
import json
import sys


def forbidden(event, args):
    if event.startswith(('ctypes.dlopen', 'ctypes.dlsym')):
        raise RuntimeError('No driver/library calls in saved-output audit')
    if event == 'import' and args[0].split('.')[0] in {'torch', 'mujoco', 'metaworld', 'gymnasium', 'OpenGL', 'pynvml'}:
        raise RuntimeError('No model, environment or GPU imports')


sys.addaudithook(forbidden)
sys.dont_write_bytecode = True
import numpy as np
from PIL import Image

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W = B/'work/A/A10_PREFLIGHT_NATIVE_V3_r1'
RUN = B/'results/A/P10_launcher_runs/A10_PREFLIGHT_NATIVE_V3_r1_A_wave05'
P = B/'results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1'
sys.path.insert(0, str(P/'code'))
from core.validation import validate


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    path = Path(path)
    return dict(path=str(path), sha256=sha(path), size_bytes=path.stat().st_size)


D = Path(read(RUN/'diagnostic_link.json')['path'])
R = read(W/'inputs/releases__P10_A_NATIVE_PREFLIGHT_V3.json')
proposal = read(P/'proposal/PROPOSAL.json')
transition, checks, complete = [read(D/name) for name in ('transition.json', 'checks.json', 'COMPLETE.json')]
for item in complete['artifacts']:
    path = D/item['path']
    assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256']
schema = read(Path(proposal['interface_directory'])/'interface.schema.json')
validate(transition, schema)
assert transition['synthetic'] is False and transition['environment']['task'] == 'shelf-place-v3'
assert transition['source']['source_id'] == proposal['source']['source_id']
assert transition['seed'] == proposal['source']['env_seed'] and transition['suffix_seed'] == proposal['source']['suffix_seed']
for key in ('task_id', 'run_id', 'wave_id', 'shard_id', 'release_id'):
    assert transition['identity'][key] == R[key]
assert transition['identity']['code_sha256'] == R['code_manifest_sha256']
assert transition['identity']['config_sha256'] == R['proposal_sha256']
assert transition['H'] == 10 and transition['generated_length'] == 50 and transition['executed_prefix_length'] == 1
assert transition['step'] == 0 and transition['next_step'] == 1
assert transition['cut_reason'] == 'diagnostic_stop_after_one_step'
assert transition['terminal_success'] is None and len(transition['rewards']) == len(transition['successes']) == 1
for field in ('observation_ref', 'next_observation_ref', 'generated_chunk_ref'):
    item = transition[field]
    assert Path(item['path']).parent == D and sha(item['path']) == item['sha256']
plans = np.load(D/'raw_plans.npy', allow_pickle=False)
assert plans.shape == (5, 50, 4) and plans.dtype == np.float32 and np.isfinite(plans).all()
assert checks['status'] == 'passed' and checks['completed_rollouts'] == 0 and checks['actual_control_steps'] == 1
probes = checks['queue_probes']
assert [probe['H'] for probe in probes] == [10, 20, 30, 40, 50]
assert len({probe['noise_sha256'] for probe in probes}) == 1
for index, probe in enumerate(probes):
    assert probe['queue_after_first_pop'] == probe['H'] - 1
    assert probe['generated_length'] == 50 and probe['actual_flow_calls'] == 10
    assert hashlib.sha256(plans[index].tobytes()).hexdigest() == probe['plan_sha256']
    assert np.array_equal(plans[index], plans[0])
assert np.array_equal(np.array(transition['raw_actions'], dtype=np.float32), plans[0, :1])
events = [json.loads(line) for line in (D/'events.jsonl').read_text().splitlines()]
flow = collections.Counter(row['sampling_index'] for row in events if row['phase'] == 'entered' and row['resource_units']['flow_forward_calls'])
sample = collections.Counter(row['sampling_index'] for row in events if row['phase'] == 'entered' and row['resource_units']['vla_sampling_calls'])
assert flow == dict.fromkeys(range(5), 10) and sample == dict.fromkeys(range(5), 1)
provenance = read(D/'RGB_provenance.json')
assert provenance['extra_render_for_views'] == 0
views = W/'RGB_views'
views.mkdir(exist_ok=False)
frames, arrays = [], []
for index, phase in enumerate(('diagnostic', 'post_control')):
    path = D/f'observation_step{index}.npz'
    with np.load(path, allow_pickle=False) as saved:
        pixels = saved['pixels'].copy()
        proprio = saved['proprioception'].copy()
    assert pixels.shape == (480, 480, 3) and pixels.dtype == np.uint8
    assert np.isfinite(proprio).all()
    if index == 0:
        assert np.array_equal(proprio, np.array(transition['proprioception']))
    ppm = D/f'RGB_{phase}.ppm'
    ppm_bytes = ppm.read_bytes()
    header = b'P6\n480 480\n255\n'
    assert ppm_bytes.startswith(header) and ppm_bytes[len(header):] == pixels.tobytes()
    meta = provenance['frames'][index]
    assert meta['phase'] == phase and meta['camera'] == 'corner2'
    assert meta['pixels_sha256'] == hashlib.sha256(pixels.tobytes()).hexdigest()
    png = views/f'RGB_{phase}.png'
    Image.fromarray(pixels).save(png, format='PNG')
    with Image.open(png) as decoded:
        assert decoded.mode == 'RGB' and np.array_equal(np.asarray(decoded), pixels)
    frames.append(dict(phase=phase, NPZ=ref(path), PPM=ref(ppm), PNG=ref(png), shape=list(pixels.shape),
        pixels_sha256=meta['pixels_sha256'], NPZ_PPM_PNG_pixels_identical=True,
        saved_proprioception=proprio.tolist(), no_crop_flip_resize_or_color_change=True))
    arrays.append(pixels)
result = dict(status='saved_output_CPU_checks_passed', complete_manifest_artifacts_verified=len(complete['artifacts']),
    transition_schema_and_identity_valid=True, transition=ref(D/'transition.json'),
    raw_plans=dict(artifact=ref(D/'raw_plans.npy'), shape=list(plans.shape), dtype=str(plans.dtype),
        all_five_plans_bitwise_equal=True, paired_noise_sha256=probes[0]['noise_sha256'],
        all_five_measured_noise_hashes_equal=True, horizons=[p['H'] for p in probes],
        queue_lengths_after_first_pop=[p['queue_after_first_pop'] for p in probes],
        flow_calls_per_probe=dict(flow), samples_per_probe=dict(sample), actual_first_command=plans[0,0].tolist()),
    one_step_reward=transition['rewards'][0], one_step_success=transition['successes'][0],
    terminated=transition['terminated'], truncated=transition['truncated'], terminal_success=None,
    completed_rollouts=0, frames=frames,
    changed_RGB_pixels=int(np.any(arrays[0] != arrays[1], axis=2).sum()),
    PNG_encodings=2, extra_render_calls=0, extra_RGB_readbacks=0, GPU_calls=0,
    new_model_or_environment_imports=0, large_weight_hashes=0,
    visual_scene_review='Pending inspection of the saved PNG images; pixel equality alone is not scene validation')
with (W/'SAVED_OUTPUTS_AUDIT.json').open('x') as stream:
    stream.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
