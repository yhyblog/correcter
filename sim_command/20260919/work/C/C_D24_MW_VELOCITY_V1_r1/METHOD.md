# C Smol/X native Velocity adaptation

Frozen settings: Smol050000 H50, X030000 H30, K10, NFE10, G0 > 0.05,
at most one causal intervention, C10, alpha10, last three native times
0.3/0.2/0.1. Each method regenerates a0 and guided sampling from the same
candidate seed/noise, separate from the natural RNG stream. Own-radius
projection uses only that method's direction. No Q acceptance, reranking,
random fallback, base SFT, small-head fitting, or test-based tuning.

Smol's unmodified native sampler descends from1 to0 with Euler dt=-0.1.
At the last three calls, clean u=x_tau-tau*v is detached; differentiate
only the first10 physical4 actions through the saved native mean/std inverse
normalizer and real clamp. Return v_guided=v-10*tau*grad_u. All32 model
channels remain present, with zero direct gradient on padding/tail.

X is a clean-prediction flow model, **not an Euler velocity-head sampler**.
Its native loop remixes the same initial Gaussian noise with the previous
clean prediction at descending times1..0.1. The private hook defines
v=(x_tau-u)/tau, applies v_guided=v-10*tau*grad_u, then maps back exactly to
u_guided=u+10*tau^2*grad_u. The original native fixed-noise remixer consumes
this clean prediction. This is native-flow velocity reparameterization;
the remixer is not claimed equivalent to Smol/pi05's negative-dt Euler.
Native auto action space retains20 model channels and trims to4. Gradient
is taken through X's own saved inverse normalizer and true clamp. The
guided clean output retains the original output dtype. All base parameters
are frozen; no network Jacobian or cross-step differentiation is used.

Both use the exact B external pi05 image/language features/PCA/D/G0/Q,
whose training coverage is the historical five tasks. Native Smol/X
embeddings are never substituted into pi05 projection. The frozen Q
anchor is clipped a0[:10] throughout all three updates. The final direction
is clip(native_guided[:10])-clip(a0[:10]), then the accepted project_solo
pure function applies own symmetric feasible radii; raw tail stays exact.
After10 executed corrected commands, the unexecuted tail is discarded.

## Actual inherited environment protocol

The onboarding prose says30Hz/.015, but B's frozen native Smol/X code and
both saved Post episode D24_MW_t00_e00 RESULT.json record timestep0.0025,
frame_skip5, action_scale0.01: **actual control80Hz, physics400Hz**.
C preserves that B native protocol, its Mesa llvmpipe EGL renderer,
corner2 camera,480x480 observations, source/env/policy seeds and300-step
terminal rule. C asserts those actual values at every episode entry.
This discrepancy is disclosed rather than silently changing C's protocol
and attributing the resulting difference to Velocity. It also means the
transferred pi05 features/heads retain their existing temporal-domain gap.

## Readiness and cost

MINIMUM_CPU_CHECKS.json records action-coordinate derivatives, clamp-zero
regions, inert padding/tail gradients, late-step signs and unguided identity.
These are CPU checks with saved small normalizers, not a GPU model preflight.
First actual planned episodes check loading, valid observations and native
sampling. A natural trigger is needed before claiming real guided GPU
execution; a no-trigger terminal proves only that episode's natural path.

C runs four resident workers per base on eight observed H10080GB GPUs.
One full-node reservation stops all holders before loading and preserves
that state through all jobs/gaps. Restore after all formal descendants exit.
Per-GPU sampled utilization and process identity are saved. Episode/inference
times are not a controlled cross-host speed comparison. Inference time
includes synchronous gradient RPC, so it overlaps reported corrector time.
Optional statistics are saved after the authoritative core terminal.

No automatic replay after disconnect or restart. Durable scientific unit
claims prevent duplicate base/source/Velocity/repeat0 entries. Failed units
require diagnosis before the one authorized corrected retry. The finite
queue automatically advances normal sources, with no additional approval.
