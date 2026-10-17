"""Narrow CPU regression checks for the observed A/C export schema mismatch."""
import csv
import json
import sys
from pathlib import Path

REPAIR = Path(__file__).resolve().parent
ROOT = REPAIR.parents[1]
sys.path.insert(0, str(ROOT / 'code'))
from merge_remote import normalize_row
from qio import new_json, ref, utc

CAMPAIGN = ROOT.parents[2]
C = CAMPAIGN / 'results/C/C_D24_PI05_SELECTED_H40_H50_V1/FINAL_CELLS.csv'
A = ROOT / 'MAIN_CELLS.csv'
with A.open(newline='') as f:
    a = next(csv.DictReader(f))
with C.open(newline='') as f:
    c = next(csv.DictReader(f))
selection = {'chosen_loss': 'L01'}
checks = []


def accepted(label, row, node, expected_complete):
    result = normalize_row(row, node, selection, C if node == 'C' else A)
    assert result['resolved_loss'] == 'L01'
    assert result['complete'] == str(expected_complete)
    checks.append({'name': label, 'pass': True})


def rejected(label, row, node='C'):
    try:
        normalize_row(row, node, selection, C)
    except ValueError:
        checks.append({'name': label, 'pass': True})
    else:
        raise AssertionError(label + ' was accepted')


accepted('saved_A_resolved_loss_and_complete', a, 'A', True)
accepted('saved_C_selected_loss_and_full_cell_complete', c, 'C', True)
rejected('conflicting_explicit_loss_not_masked', dict(c, resolved_loss='L11'))
rejected('wrong_fixed_fit', dict(c, fit_seed='9102'))
rejected('wrong_node_horizon', c, 'B')
rejected('incomplete_counts_cannot_be_complete', dict(c, valid='499', successes='324', success_rate=str(324/499)))
rejected('success_rate_count_conflict', dict(c, success_rate='0.9'))
rejected('conflicting_complete_flags', dict(c, complete='False'))
partial = dict(c)
partial.pop('full_cell_complete')
accepted('transferred_complete_alone_is_not_full_cell_complete', partial, 'C', False)
accepted('Velocity_uses_same_selection_without_paper_inclusion', dict(c, method='Velocity'), 'C', True)
assert not any(name in sys.modules for name in ('torch', 'mujoco', 'metaworld'))
result = dict(utc=utc(), status='PASS', scientific_compute=0, tests=checks,
              actual_small_inputs=[ref(A), ref(C)], modules_not_imported=['torch', 'mujoco', 'metaworld'])
new_json(REPAIR / 'CPU_CHECK.json', result)
print(json.dumps({'status': 'PASS', 'checks': len(checks), 'scientific_compute': 0}))
