"""Official pi05 LIBERO policy; own-domain frozen features and tiny Post head."""
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
    from native_head import Head, FEATURE_DIM, dev_candidate
    started = time.monotonic()
    jax.config.update('jax_compilation_cache_dir', str(d.ROOT/'embodied-ai-workspace/cache/jax/pi05-server'))
    policy = policy_config.create_trained_policy(config.get_config('pi05_libero'), Path(cfg['checkpoint']),
                                               sample_kwargs={'num_steps': cfg['NFE']})
    embed = nnx_utils.module_jit(policy._model.embed_prefix)
    spec = cfg['adaptation']
    stats = d.load(cfg['norm_stats'])['norm_stats']
    state_mid = (np.asarray(stats['state']['q99']) + np.asarray(stats['state']['q01'])) / 2
    state_scale = (np.asarray(stats['state']['q99']) - np.asarray(stats['state']['q01'])) / 2
    rng = np.random.Generator(np.random.PCG64(spec['feature_projection_seed']))
    projection = rng.normal(0, 1/np.sqrt(2048), size=(2048, 128)).astype(np.float32)
    head = None

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
        return feature

    class NativePolicy:
        def infer(self, observation):
            nonlocal head
            d.authorize()
            observation = dict(observation)
            seed = observation.pop('d24_policy_seed', None)
            control = observation.pop('d24_post', None)
            if seed is not None:
                policy._rng = jax.random.key(int(seed))
            result = policy.infer(observation)
            if control is None:
                return result
            tick = time.monotonic()
            feature = features(observation, int(control['step']))
            reference = np.asarray(result['actions'], dtype=np.float32).copy()
            if reference.shape != (10,7) or not np.isfinite(reference).all():
                raise ValueError('Expected finite native H10 action7')
            if control['mode'] == 'development':
                candidate = dev_candidate(reference, int(control['candidate_id']), int(control['candidate_seed']), spec)
                info = dict(mode='development', applied=bool(np.any(candidate != reference)))
            elif control['mode'] == 'Post':
                if head is None:
                    ready = d.load(Path(cfg['pipeline_output'])/'MODEL_READY.json')
                    head = Head(ready['model_path'])
                candidate, info = head.correct(feature, reference, spec)
                info['mode'] = 'Post-operator-transfer-native-LIBERO'
            else:
                raise ValueError('Unknown intervention mode')
            result.update(actions=candidate, d24_feature=feature, d24_reference=reference,
                          d24_post_info=info, d24_corrector_seconds=time.monotonic()-tick)
            return result

    metadata = dict(model='pi05', config='pi05_libero', checkpoint=cfg['checkpoint'], H=10, NFE=10,
        policy_rng='fixed per source, reset before first query; feature extraction consumes no policy RNG',
        load_seconds=time.monotonic()-started, job_id=cfg['job_id'],
        openpi_commit='215abfb217dbac7d5f1273282331b9b1866c0479',
        feature_version=spec['feature_version'], feature_dim=FEATURE_DIM,
        method='Post-operator-transfer-native-LIBERO; no D/G0; no base SFT')
    d.atomic(Path(cfg['output'])/'SERVER_READY.json', metadata)
    WebsocketPolicyServer(NativePolicy(), host='127.0.0.1', port=cfg['port'], metadata=metadata).serve_forever()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    p=argparse.ArgumentParser();p.add_argument('--config',required=True)
    main(p.parse_args().config)
