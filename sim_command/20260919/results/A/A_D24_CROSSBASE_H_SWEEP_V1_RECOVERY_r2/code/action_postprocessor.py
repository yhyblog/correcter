"""Preserve the saved action transform while keeping its cached stats autograd-safe."""


def autograd_safe_postprocessor(processor):
    import torch

    def post(actions):
        # The saved normalizer lazily moves its statistics to the action dtype/device.
        # Those cached tensors must remain ordinary tensors even for native inference.
        # Do not detach actions: Post/Velocity require the unchanged action Jacobian.
        with torch.inference_mode(False):
            return processor(actions)

    return post
