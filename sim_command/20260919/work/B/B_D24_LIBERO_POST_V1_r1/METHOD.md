# LIBERO Post operator transfer, frozen before development

Official pi05 LIBERO checkpoint and its own normalizer stay frozen. Native H10/K5, NFE10, action7/state8,
and the original four-suite random reset protocol are retained. No base SFT, MetaWorld features, D, or G0.

32 new development parents (8 tasks per suite) each execute five full rollouts: a0 and two antithetic
XYZ direction pairs, the second pair also uses opposite gripper commands. Intervention is at the natural
replan after 20 executed commands. Each candidate changes only the next five XYZ/gripper commands.
Environment/policy seeds are shared within each parent; all candidate attempts count. Development
perturbations explore a wider action interval than the small test-time correction. Labels are actual
terminal success; failed execution and episodes ending before the cut supply no training example.

Tasks 0-5 per suite train the heads; tasks 6-7 provide descriptive validation only. Parent-level separation
is fixed before collection. Four CPU MLP members fit for exactly 4000 updates each, with final checkpoints
used together. No validation checkpoint/threshold/radius selection, and no test outcomes enter fitting.
Insufficient real outcome contrast blocks test admission rather than fabricating a success critic.

Features use frozen native LIBERO prefix embeddings: per-view SigLIP token means, masked prompt-token
mean, native state8 and remaining-step fraction. Fixed Gaussian projection compresses embeddings;
feature standardization uses training parents only. Q consumes context and five-command candidate/reference.

At test time, one fixed intervention at command20 follows S^2 grad Q using LIBERO action quantiles.
The OSC XYZ scale is .05 metres per command unit. XYZ correction has .02 command RMS target (1mm)
and .06 component cap (3mm). Gripper uses .10 command RMS/.20 cap, without a physical-unit claim.
Symmetric action-bound margin .02 suppresses corrections at or outside the feasible boundary.
Rotations and chunk rows5-9 stay bit-identical. No extra base query or modified base RNG stream.

The fixed400 test sources match N. Valid394 N rows are reused only for comparison; missing N remains
missing. This is Post operator transfer with own-domain small-head adaptation, not the Full method.
All eight GPUs carry resident independent workers. The entire formal wave, including its CPU-fit barrier,
has no occupancy holders. Completion/failure drains owned descendants and restores the normal guard.
