import copy
from paths import CONFIG
import gates
def locked_selection():return gates.selection()
def engine_config(job):
 s=locked_selection();e=s['ensemble'];cfg=copy.deepcopy(CONFIG)
 cfg.update(critic_assets=e['assets'],selected_model=dict(member_hashes=e['member_hashes'],ensemble=e),loss=e['loss'],fit_seed=9101)
 return cfg
