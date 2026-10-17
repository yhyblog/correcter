from paths import ROOT
from qio import read
def consumed_selection():return dict(own_assets=read(ROOT/'ASSETS.json')['X-VLA']['assets'],chosen_loss='L11',fixed_fit_seed=9101)
def engine_config(job=None):return read(ROOT/'config/PI_ENGINE.json')
