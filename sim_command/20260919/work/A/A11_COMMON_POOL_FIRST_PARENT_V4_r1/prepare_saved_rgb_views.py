"""Lossless CPU views of existing PPMs only; no new environment/render call."""
from pathlib import Path
import hashlib
import json
from PIL import Image

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W = B / 'work/A/A11_COMMON_POOL_FIRST_PARENT_V4_r1'
assert (W / 'OUTER_EXECUTION_RESULT.json').exists()
P = B / 'results/A/A11_COMMON_POOL_FIRST_PARENT_V4'
R = B / 'results/A/P11_COMMON_POOL_V4_runs/PROPOSED_A11_shelf_train0000_parent_V4'
D = P / 'saved_rgb_views'
D.mkdir(exist_ok=False)
choices = [('normal', 0), ('normal', 5), ('normal', 300), ('Q_a0_r0', 15),
           ('Q_local_plus_r0', 300), ('Q_local_minus_r0', 300), ('G0_old_r0', 10), ('G0_fresh2_r1', 300)]
for result_path in sorted(R.glob('*/BRANCH_RESULT.json')):
    result = json.loads(result_path.read_text())
    if result.get('outcome', {}).get('outcome_complete') and result.get('first_success_step') is not None:
        terminal = (result_path.parent.name, result['first_success_step'])
        if terminal not in choices:
            choices.append(terminal)
rows = []
for branch, step in choices:
    source = R / branch / 'observations' / f'step{step:03d}.ppm'
    if not source.exists():
        rows.append(dict(branch=branch, step=step, status='missing', reason='No saved source; never render or fill.'))
        continue
    target = D / f'{branch}_step{step:03d}.png'
    with Image.open(source) as img:
        assert img.mode == 'RGB' and img.size == (480, 480)
        raw = img.tobytes()
        img.save(target, format='PNG', optimize=False)
    with Image.open(target) as restored:
        assert restored.mode == 'RGB' and restored.size == (480, 480) and restored.tobytes() == raw
    rows.append(dict(branch=branch, step=step, status='LOSSLESS_CPU_COPY',
        source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        PNG=str(target), PNG_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        pixel_sha256=hashlib.sha256(raw).hexdigest(), pixel_bytes=len(raw), pixel_equal=True,
        size=[480, 480], visual_semantic_review='pending_direct_view'))
with (P / 'SAVED_RGB_CONVERSION_AUDIT.json').open('x') as f:
    json.dump(dict(real_render_calls=0, saved_pixels_only=True, entries=rows), f, indent=2)
    f.write('\n')
print(json.dumps(dict(saved_PNGs=sum(x['status']=='LOSSLESS_CPU_COPY' for x in rows), files=rows)))
