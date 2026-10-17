"""Copy audited historical implementation; do not import or execute it."""
import ast
import hashlib
from pathlib import Path
from campaign_io import WORK, atomic, heartbeat

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')


def main():
    heartbeat('freezing source identity; no historical imports or computation')
    paths = [
        'Corrector/experiments/standalone_ablation_20260918/candidates.py',
        'Corrector/experiments/standalone_ablation_20260918/engine.py',
        'Corrector/experiments/native10_training_20260916/commands.py',
        'Corrector/src/corrector/candidates.py',
        'Corrector/src/corrector/guidance.py',
        'Corrector/src/corrector/actions.py',
        'Corrector/src/corrector/critic.py',
        'ACT-RECAP/src/ac_tmil/collection/metaworld_pi05.py',
        'ACT-RECAP/src/ac_tmil/idea3/metaworld_runtime.py',
    ]
    manifest = []
    for relative in paths:
        source = ROOT / relative
        target = WORK / 'legacy_basis' / relative
        if target.exists():
            raise RuntimeError('Refusing to overwrite frozen source')
        target.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        target.write_bytes(data)
        manifest.append({'source': str(source), 'snapshot_relative': str(target.relative_to(WORK)),
                         'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    original = (ROOT / paths[0]).read_text()
    imported = original.replace('from experiments.native10_training_20260916.commands import preserve_raw_anchor\nfrom corrector.candidates import radii',
                                'from .vendor_dependencies import preserve_raw_anchor, radii')
    (WORK / 'core/vendor_solo.py').write_text(imported)
    pieces = ['"""Exact extracted numpy helpers; see basis_manifest.json."""\nimport numpy as np\n']
    extracts = []
    for relative, name in [(paths[2], 'preserve_raw_anchor'), (paths[3], 'radii')]:
        source = (ROOT / relative).read_text()
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
        fragment = ast.get_source_segment(source, node)
        pieces.append(fragment + '\n')
        extracts.append({'source': relative, 'function': name, 'start_line': node.lineno,
                         'source_fragment_sha256': hashlib.sha256(fragment.encode()).hexdigest()})
    (WORK / 'core/vendor_dependencies.py').write_text('\n\n'.join(pieces))
    atomic(WORK / 'basis_manifest.json', {'files': manifest, 'exact_function_extractions': extracts,
        'candidate_change': 'Only two dependency import statements replaced by isolated numpy helper imports',
        'historical_engine': 'reference only; never imports historical protocol/release gates or executes old runs'})


if __name__ == '__main__':
    main()
