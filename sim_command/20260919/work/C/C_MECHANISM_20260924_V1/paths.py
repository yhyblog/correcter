"""Private supplemental experiment; never writes old dispatch or results."""
import sys
from pathlib import Path
WORKSPACE=Path('/mnt/bn/arnold-recommend/yaohaoyang')
CAMPAIGN=WORKSPACE/'Corrector/sim_command/20260919'
CODE=Path(__file__).resolve().parent
ROOT=CAMPAIGN/'results/C/C_MECHANISM_20260924_V1'
ACCEPTED=CAMPAIGN/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
LEGACY=CAMPAIGN/'results/C/C_D24_L11_RENDER_RECOVERY_V1'
TRAIN_ROOT=WORKSPACE/'ACT-RECAP/outputs/act_recap_future_aware_20260914'
QROOT=CAMPAIGN/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/ensembles'
for p in (WORKSPACE/'Corrector',WORKSPACE/'Corrector/src',WORKSPACE/'ACT-RECAP/src',ACCEPTED,ACCEPTED/'vendor_vla/src',CODE/'vendor',CODE):
    sys.path.insert(0,str(p))

