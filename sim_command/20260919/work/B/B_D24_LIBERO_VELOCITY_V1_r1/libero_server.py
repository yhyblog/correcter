"""Official LIBERO base stream and one same-noise native Velocity correction."""
import argparse
import logging
from pathlib import Path
import time
import d24_common as d


def main(config_path):
    cfg = d.load(config_path)
    d.authorize(admission=True)
    import jax
    import jax.numpy as jnp
    import numpy as np
    from openpi.policies import policy_config
    from openpi.training import config
    from openpi.serving.websocket_policy_server import WebsocketPolicyServer
    from openpi.models import model as model_types
    from openpi.shared import nnx_utils
    from native_head import Head, FEATURE_DIM
    from velocity_flow import NativeVelocitySampler
    started = time.monotonic()
    jax.config.update('jax_compilation_cache_dir', str(d.ROOT/'embodied-ai-workspace/cache/jax/pi05-server'))
    policy = policy_config.create_trained_policy(config.get_config('pi05_libero'), Path(cfg['checkpoint']),
                                               sample_kwargs={'num_steps': cfg['NFE']})
    if jax.config.jax_enable_x64 or policy._model.action_horizon != 10 or policy._model.action_dim != 32:
        raise ValueError('Unexpected base sampling dtype/horizon/action space')
    embed = nnx_utils.module_jit(policy._model.embed_prefix)
    guided_sample = nnx_utils.module_jit(NativeVelocitySampler(policy._model).sample)
    spec = cfg['adaptation']
    stats = d.load(cfg['norm_stats'])['norm_stats']
    state_mid = (np.asarray(stats['state']['q99']) + np.asarray(stats['state']['q01'])) / 2
    state_scale = (np.asarray(stats['state']['q99']) - np.asarray(stats['state']['q01'])) / 2
    rng = np.random.Generator(np.random.PCG64(spec['feature_projection_seed']))
    projection = rng.normal(0, 1/np.sqrt(2048), size=(2048, 128)).astype(np.float32)
    ready = d.load(cfg['frozen_head_ready'])
    head = Head(ready['model_path'])
    if head.members != 4:
        raise ValueError('Expected four frozen native small-head members')
    weights = {k:jnp.asarray(v, dtype=jnp.float32) for k,v in head.a.items() if k != 'members'}
    # Exact official output transform, including its fixed quantile epsilon.
    q0 = np.asarray(stats['actions']['q01'], dtype=np.float64)
    q1 = np.asarray(stats['actions']['q99'], dtype=np.float64)
    model_scale = jnp.asarray((q1-q0+1e-6)/2, dtype=jnp.float32)
    model_mid = jnp.asarray((q1+q0+1e-6)/2, dtype=jnp.float32)

    def features(observation, step):
        inputs = policy._input_transform(jax.tree.map(lambda x:x, observation))
        inputs = jax.tree.map(lambda x: jnp.asarray(x)[np.newaxis, ...], inputs)
        native = model_types.Observation.from_dict(inputs)
        native = model_types.preprocess_observation(None, native, train=False)
        keys = list(native.images)
        if keys != ['base_0_rgb','left_wrist_0_rgb','right_wrist_0_rgb']:
            raise ValueError('Unexpected native camera order: '+repr(keys))
        tokens, mask, _ = embed(native)
        tokens, mask = np.asarray(tokens[0], dtype=np.float32), np.asarray(mask[0], dtype=bool)
        if tokens.shape[1] != 2048 or tokens.shape[0] <= 768:
            raise ValueError('Unexpected LIBERO native prefix shape: '+str(tokens.shape))
        values = []
        for i in range(3):
            block, valid = tokens[i*256:(i+1)*256], mask[i*256:(i+1)*256]
            pooled = block[valid].mean(axis=0) if valid.any() else np.zeros(2048, dtype=np.float32)
            values.append(pooled @ projection[:, :64])
        text, valid = tokens[768:], mask[768:]
        if not valid.any():
            raise ValueError('Empty LIBERO language/state prompt')
        values.extend([text[valid].mean(axis=0) @ projection,
                       (np.asarray(observation['observation/state']) - state_mid) / state_scale,
                       np.asarray([1-float(step)/cfg['max_steps']])])
        feature = np.concatenate(values).astype(np.float32)
        if feature.shape != (FEATURE_DIM,) or not np.isfinite(feature).all():
            raise ValueError('Invalid native LIBERO feature vector')
        return feature, native, inputs['state']

    class NativePolicy:
        def infer(self, observation):
            d.authorize()
            observation = dict(observation)
            seed = observation.pop('d24_policy_seed', None)
            control = observation.pop('d24_post', None)
            if seed is not None:
                policy._rng = jax.random.key(int(seed))
            before_rng = policy._rng
            result = policy.infer(observation)
            if control is None:
                return result
            tick = time.monotonic()
            feature, native, transformed_state = features(observation, int(control['step']))
            reference = np.asarray(result['actions'], dtype=np.float32).copy()
            if reference.shape != (10,7) or not np.isfinite(reference).all():
                raise ValueError('Expected finite native H10 action7')
            if control['mode'] != 'Velocity':
                raise ValueError('Unknown intervention mode')
            next_rng, sample_rng = jax.random.split(before_rng)
            if not np.array_equal(jax.random.key_data(next_rng), jax.random.key_data(policy._rng)):
                raise ValueError('Native base random stream changed')
            # policy.infer generated its base noise from exactly this key/shape/dtype.
            noise = jax.random.normal(sample_rng, (1,10,32), dtype=jnp.float32)
            raw, steps, flow_log = guided_sample(native, noise, jnp.asarray(feature),
                jnp.asarray(reference[:5]), weights, model_mid, model_scale, jnp.asarray(10., jnp.float32))
            raw, flow_log = np.asarray(raw[0]), np.asarray(flow_log)
            if int(steps) != 10 or not np.allclose(flow_log[:,0], np.arange(10,0,-1)/10, atol=1e-6):
                raise ValueError('Unexpected native flow schedule')
            if int(flow_log[:,1].sum()) != 3 or not np.isfinite(raw).all() or not np.isfinite(flow_log).all():
                raise ValueError('Invalid late Velocity injection')
            guided_raw = np.asarray(policy._output_transform(dict(state=np.asarray(transformed_state[0]), actions=raw))['actions'], dtype=np.float32)
            # Native direction only; final radii/mask/bounds identical to frozen LIBERO Post.
            direction = np.clip(guided_raw[:5],-1,1).astype(np.float64)-np.clip(reference[:5],-1,1).astype(np.float64)
            candidate, info = head.project(feature, reference, direction, spec)
            info.update(mode='Velocity-operator-transfer-native-LIBERO', guided_flow_steps=3, guided_policy_calls=1,
                same_noise_source='same saved base sample_rng; official float32 normal(1,10,32)',
                times=flow_log[flow_log[:,1]>0,0].tolist(),alpha=10.,
                velocity_delta_l2=flow_log[flow_log[:,1]>0,5].tolist(),
                rotations_unchanged=True,tail_unchanged=True)
            result.update(actions=candidate, d24_feature=feature, d24_reference=reference,
                          d24_post_info=info, d24_corrector_seconds=time.monotonic()-tick,
                          d24_guided_raw=guided_raw,d24_flow_log=flow_log)
            return result

    metadata = dict(model='pi05', config='pi05_libero', checkpoint=cfg['checkpoint'], H=10, NFE=10,
        policy_rng='original source stream; guided cut reuses exact base noise key without advancing natural stream',
        load_seconds=time.monotonic()-started, job_id=cfg['job_id'],
        openpi_commit='215abfb217dbac7d5f1273282331b9b1866c0479',
        feature_version=spec['feature_version'], feature_dim=FEATURE_DIM,
        method='Velocity-operator-transfer-native-LIBERO; no D/G0; no base SFT',
        frozen_head=ready['model_path'],frozen_head_sha256=ready['model_sha256'],new_optimizer_updates=0,
        flow_rule='v +10*dQ/dv at tau .3/.2/.1, clean=x-tau*v, true native command clamp; fixed5-command XYZ/gripper projection')
    d.atomic(Path(cfg['output'])/'SERVER_READY.json', metadata)
    WebsocketPolicyServer(NativePolicy(), host='127.0.0.1', port=cfg['port'], metadata=metadata).serve_forever()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    p=argparse.ArgumentParser();p.add_argument('--config',required=True)
    main(p.parse_args().config)
