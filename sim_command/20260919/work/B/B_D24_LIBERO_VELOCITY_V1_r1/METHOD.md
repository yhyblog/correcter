# Native LIBERO Velocity operator transfer

Same official pi05 LIBERO model/norm, H10/K5/NFE10, raw action7/state8 and original400 random-reset sources as N/Post.
Same native head from development160: no new collection, base or small-head training. No D/G0; not Full.
The fixed single intervention remains command20. Base reference comes from the original policy.infer call.
Guided sampling reuses its exact sample key and float32 normal(1,10,32) noise, without advancing the natural RNG.

The JAX sampler preserves the native prefix KV cache, suffix attention and ten Euler steps. At the historical
times .3/.2/.1 and alpha10, it differentiates Q with respect to a detached velocity leaf through clean=x-tau*v,
the official quantile output transform (including1e-6), and the true command clamp. Only first5 XYZ/gripper
velocity entries change. No VLA parameter derivative or update, intermediate trust projection or line search.
The stable sigmoid derivative avoids float32 cancellation at confident logits; frozen-head CPU comparisons use
only saved development rows. There is no separate GPU preflight or extra control rollout.

The guided clean command minus the same-noise base defines the native physical direction. The final XYZ/grip
projection is exactly the Post rule:1mm XYZ RMS target/3mm component cap, .10/.20 gripper command bounds,
same boundary margin. Original raw rotations and chunk tail remain unchanged even if internal guidance couples them.
Q quality is limited by5 negative training candidates and no negative validation candidate. All final-step members
stay fixed; Post/test success does not choose the sampler, head, gain, times, or projection radii.

Eight independent50-source jobs use one whole-wave reservation. All holders are off from loading through full
drain, including early-finished GPUs; the guard restores occupancy after terminal publication/cleanup.
The finite supervisor registers the same original B thread's completion trigger before model loading.
