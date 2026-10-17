"""Native JAX reverse-time velocity injection for the frozen LIBERO head.

Only the candidate velocity is differentiated, never the VLA parameters.
The final native command projection stays outside the sampler.
"""
import jax
import jax.numpy as jnp
from flax import nnx
from openpi.models import model as model_types
from openpi.models.pi0 import make_attn_mask


@jax.custom_jvp
def clipped_command(value):
    return jnp.clip(value, -1., 1.)


@clipped_command.defjvp
def clipped_command_jvp(primals, tangents):
    value, = primals
    tangent, = tangents
    # Same inclusive-boundary derivative convention as the historical torch clamp.
    return clipped_command(value), jnp.where((value >= -1.) & (value <= 1.), tangent, 0.)


@jax.custom_jvp
def stable_sigmoid(value):
    return jax.nn.sigmoid(value)


@stable_sigmoid.defjvp
def stable_sigmoid_jvp(primals, tangents):
    value, = primals
    tangent, = tangents
    small = jnp.exp(-jnp.abs(value))
    # Avoid float32 cancellation of (1-sigmoid) near a confident success logit.
    return stable_sigmoid(value), tangent * small / (1. + small) ** 2


def q_probability(weights, feature, candidate, reference):
    x = jnp.concatenate(((feature - weights['feature_mean']) / weights['feature_std'],
        ((candidate - weights['action_mid']) / weights['action_scale']).reshape(-1),
        ((reference - weights['action_mid']) / weights['action_scale']).reshape(-1)))
    probabilities = []
    for member in range(4):
        key = 'm%d_' % member
        a = jax.nn.relu(weights[key+'w0'] @ x + weights[key+'b0'])
        a = jax.nn.relu(weights[key+'w1'] @ a + weights[key+'b1'])
        probabilities.append(stable_sigmoid((weights[key+'w2'] @ a + weights[key+'b2'])[0]))
    return jnp.mean(jnp.stack(probabilities))


def inject_velocity(x, velocity, tau, feature, reference, weights, model_mid, model_scale, alpha):
    fixed_x = jax.lax.stop_gradient(x).astype(jnp.float32)
    fixed_v = jax.lax.stop_gradient(velocity).astype(jnp.float32)
    def objective(candidate_velocity):
        clean = fixed_x - tau * candidate_velocity
        physical = clean[0, :5, :7] * model_scale + model_mid
        return q_probability(weights, feature, clipped_command(physical), reference)
    before, derivative = jax.value_and_grad(objective)(fixed_v)
    mask = jnp.zeros_like(derivative).at[:, :5, :3].set(1.).at[:, :5, 6].set(1.)
    derivative = derivative * mask
    updated = fixed_v + alpha * derivative
    after = objective(updated)
    # tau, used, Q before/after, derivative L2, velocity delta L2.
    log = jnp.stack((tau, jnp.asarray(1., jnp.float32), before, after,
                     jnp.linalg.norm(derivative), jnp.linalg.norm(updated-fixed_v)))
    return updated.astype(velocity.dtype), log


class NativeVelocitySampler(nnx.Module):
    def __init__(self, model):
        self.model = model

    def sample(self, observation, noise, feature, reference, weights, model_mid, model_scale, alpha):
        model = self.model
        observation = model_types.preprocess_observation(None, observation, train=False)
        batch_size = observation.state.shape[0]
        assert batch_size == 1 and noise.shape == (1, 10, 32)
        dt = -.1
        prefix_tokens, prefix_mask, prefix_ar_mask = model.embed_prefix(observation)
        prefix_attn_mask = make_attn_mask(prefix_mask, prefix_ar_mask)
        positions = jnp.cumsum(prefix_mask, axis=1) - 1
        _, kv_cache = model.PaliGemma.llm([prefix_tokens, None], mask=prefix_attn_mask, positions=positions)

        def step(carry):
            x_t, tau, index, logs = carry
            suffix_tokens, suffix_mask, suffix_ar_mask, adarms_cond = model.embed_suffix(
                observation, x_t, jnp.broadcast_to(tau, batch_size))
            suffix_attn_mask = make_attn_mask(suffix_mask, suffix_ar_mask)
            prefix_attn_mask = jnp.broadcast_to(prefix_mask[:, None, :],
                (batch_size, suffix_tokens.shape[1], prefix_tokens.shape[1]))
            full_attn_mask = jnp.concatenate([prefix_attn_mask, suffix_attn_mask], axis=-1)
            positions = jnp.sum(prefix_mask, axis=-1)[:, None] + jnp.cumsum(suffix_mask, axis=-1) - 1
            (prefix_out, suffix_out), _ = model.PaliGemma.llm([None, suffix_tokens],
                mask=full_attn_mask, positions=positions, kv_cache=kv_cache, adarms_cond=[None, adarms_cond])
            assert prefix_out is None
            velocity = model.action_out_proj(suffix_out[:, -model.action_horizon:])
            # Frozen historical times .3/.2/.1; no backtracking or adaptive gains.
            selected = jnp.any(jnp.abs(tau-jnp.asarray([.3,.2,.1], jnp.float32)) < 1e-6)
            def guided(v):
                return inject_velocity(x_t, v, tau, feature, reference, weights, model_mid, model_scale, alpha)
            def unchanged(v):
                return v, jnp.zeros((6,), jnp.float32).at[0].set(tau)
            velocity, row = jax.lax.cond(selected & (alpha > 0), guided, unchanged, velocity)
            return x_t + dt * velocity, tau + dt, index + 1, logs.at[index].set(row)

        def cond(carry):
            return carry[1] >= -dt/2

        actions, _, steps, logs = jax.lax.while_loop(cond, step,
            (noise, 1., jnp.asarray(0, jnp.int32), jnp.zeros((10,6), jnp.float32)))
        return actions, steps, logs
