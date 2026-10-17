"""CPU planning only: frozen matrix/call upper bounds with no runtime authorization."""
from dataclasses import asdict
from math import ceil
from campaign_io import RESULTS, atomic, heartbeat
from core.scheduling import Protocol, legal_cuts
from core.resume import core_cells


def main():
    heartbeat('preparing exact 16-cell core matrix and conditional sampling bounds')
    configurations = []
    for cell in core_cells([10, 20, 30, 40, 50]):
        H, method = cell['H'], cell['method']
        normal = ceil(300 / H)
        cuts = legal_cuts(H)
        if method == 'N':
            bound = normal
        else:
            entry = 2 if method == 'Velocity' else 1
            bound = max([normal] + [ceil(t / H) + entry + ceil((300-t-10)/H) for t in cuts])
        configurations.append({**cell, 'protocol': asdict(Protocol(H=H)),
            'no_alarm_sampling_upper_bound': normal, 'sampling_upper_bound_per_physical_episode': bound,
            'env_steps_upper_bound': 300, 'legal_cut_count_without_intervention': len(cuts),
            'last_legal_cut': max(cuts), 'new_test_sources': None,
            'missing_reason': 'Analysis freezes actual source identities and repeats in P20; no compute authorized',
            'model_binding': 'MT50 D/G0/Q pending A12; existing five-task weights are a distinct identity'})
    directory = RESULTS / 'configs_v1'
    atomic(directory / 'core_eval_matrix.json', {'status': 'CPU_prepared_not_released', 'cell_count': len(configurations),
        'cells': configurations, 'all_16_cells_sampling_upper_bound_per_source_repeat': sum(r['sampling_upper_bound_per_physical_episode'] for r in configurations),
        'scope': 'sampling-only bound for independent full episodes; shared collection savings are actual-ledger observations, never deployment amortization',
        'flow_critic_backward_caps': None, 'missing_reason': 'Measure real backend low-level calls; no method-name-derived accounting or unbounded formal release',
        'wave_rule': 'Analysis assigns entire source package to one host; all participating hosts retain lifecycle reservation through the joint compute-exited barrier'})
    atomic(directory / 'E1_training_shape.json', {'status': 'CPU_prepared_for_B13_not_released',
        'training_data': 'existing five-task train600, no recollection',
        'losses': [{'name': f'L{a}{b}', 'BCE': 1., 'gain': float(a), 'pair': .5*b}
                   for a,b in [(0,0),(1,0),(0,1),(1,1)]],
        'operators': ['Post', 'Velocity'], 'complete_training_seed_slots': ['seed_slot_0', 'seed_slot_1', 'seed_slot_2'],
        'complete_training_fits_if_three_seeds_released': 12, 'operator_evaluation_cells_if_three_seeds_released': 24,
        'ensemble_members_are_training_seeds': False,
        'optimizer_updates_per_fit': None, 'actual_training_seeds': None, 'initialization_binding': None,
        'missing_reasons': {'optimizer_updates_per_fit': 'P10/B13 must freeze equal budgets',
                            'actual_training_seeds': 'analysis assigns exact integers before training',
                            'initialization_binding': 'B13 supplies common initialization/architecture/preprocessing identity'},
        'training_owner': 'B13; A10 supplies data/interface, no optimizer launcher authorized'})
    print({'core_cells': len(configurations), 'sampling_upper_bounds': [(r['H'],r['method'],r['sampling_upper_bound_per_physical_episode']) for r in configurations]})


if __name__ == '__main__':
    main()
