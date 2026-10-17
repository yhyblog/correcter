"""Official checkpoint and normalizer, with per-episode frozen RNG seeds."""
import argparse
import logging
from pathlib import Path
import time
import d24_common as d

def main(config_path):
    cfg = d.load(config_path)
    d.authorize(admission=True)
    import jax
    from openpi.policies import policy_config
    from openpi.training import config
    from openpi.serving.websocket_policy_server import WebsocketPolicyServer
    started = time.monotonic()
    jax.config.update('jax_compilation_cache_dir', str(d.ROOT / 'embodied-ai-workspace/cache/jax/pi05-server'))
    policy = policy_config.create_trained_policy(config.get_config('pi05_libero'), Path(cfg['checkpoint']),
                                               sample_kwargs={'num_steps': cfg['NFE']})
    class SeededPolicy:
        def infer(self, observation):
            d.authorize()
            seed = observation.pop('d24_policy_seed', None)
            if seed is not None:
                policy._rng = jax.random.key(int(seed))
            return policy.infer(observation)
    metadata = dict(model='pi05', config='pi05_libero', checkpoint=cfg['checkpoint'], H=10, NFE=10,
                    policy_rng='fixed per source, reset before first query', load_seconds=time.monotonic() - started,
                    job_id=cfg['job_id'], openpi_commit='215abfb217dbac7d5f1273282331b9b1866c0479')
    d.atomic(Path(cfg['output']) / 'SERVER_READY.json', metadata)
    WebsocketPolicyServer(SeededPolicy(), host='127.0.0.1', port=cfg['port'], metadata=metadata).serve_forever()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True)
    main(p.parse_args().config)
