"""Bounded copies of actual planned observations; no extra render or model call."""
from pathlib import Path
from qio import new_json, utc, process_identity


class ObservationEvidenceError(RuntimeError):
    pass


def save_frame(frame, proprio, step, unit, cfg, episode, device):
    import numpy as np
    from PIL import Image
    array = np.asarray(frame)
    valid = (array.shape == (480, 480, 3) and array.dtype == np.uint8
             and int(array.max()) > int(array.min())
             and bool(np.isfinite(proprio).all()))
    destination = Path(episode) / 'observation_evidence'
    destination.mkdir(exist_ok=True)
    image_path = destination / f'frame_step_{step:03d}.png'
    if array.shape == (480, 480, 3) and array.dtype == np.uint8:
        Image.fromarray(array).save(image_path)
    record = dict(utc=utc(),unit_id=unit['unit_id'],source_id=unit['source_id'],
                  task=unit['task'],env_seed=unit['env_seed'],policy_seed=unit['policy_seed'],
                  method=unit['method'],mode=unit['mode'],H=unit['H'],step=step,
                  process=process_identity(),branch_id=cfg['branch_id'],slot=cfg['slot'],
                  gpu_uuid=device['gpu_uuid'],rgb_path=str(image_path),shape=list(array.shape),
                  dtype=str(array.dtype),pixel_min=int(array.min()),pixel_max=int(array.max()),
                  proprio=np.asarray(proprio).tolist(),basic_observation_valid=valid,
                  origin='current physical environment observation before current step monitoring/Q',
                  first_possible_intervention_step=5,extra_render_calls=0,extra_model_calls=0,
                  environment_process_isolated=True,scientific_frame_unchanged=True)
    new_json(destination / f'frame_step_{step:03d}.json', record)
    if not valid:
        raise ObservationEvidenceError('invalid first planned RGB/proprio; see saved evidence')


def rendering_failure(exc):
    message = str(exc).lower()
    return isinstance(exc, ObservationEvidenceError) or any(
        token in message for token in ('0x506','gl_invalid_framebuffer',
                                      'framebuffer is not complete','framebuffer incomplete'))
