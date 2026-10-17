"""Exact extracted feature functions; no D, G0 or environment construction."""
import math
import numpy as np
import torch
import einops
from torch import Tensor
from lerobot.utils.constants import OBS_IMAGE, OBS_IMAGES, OBS_ENV_STATE, OBS_STATE, OBS_STR

def preprocess_observation(observations: dict[str, np.ndarray]) -> dict[str, Tensor]:
    # TODO(jadechoghari, imstevenpmwork): refactor this to use features from the environment (no hardcoding)
    """Convert environment observation to LeRobot format observation.
    Args:
        observation: Dictionary of observation batches from a Gym vector environment.
    Returns:
        Dictionary of observation batches with keys renamed to LeRobot format and values as tensors.
    """
    # map to expected inputs for the policy
    return_observations = {}
    if "pixels" in observations:
        if isinstance(observations["pixels"], dict):
            imgs = {f"{OBS_IMAGES}.{key}": img for key, img in observations["pixels"].items()}
        else:
            imgs = {OBS_IMAGE: observations["pixels"]}

        for imgkey, img in imgs.items():
            # TODO(aliberts, rcadene): use transforms.ToTensor()?
            img_tensor = torch.from_numpy(img)

            # When preprocessing observations in a non-vectorized environment, we need to add a batch dimension.
            # This is the case for human-in-the-loop RL where there is only one environment.
            if img_tensor.ndim == 3:
                img_tensor = img_tensor.unsqueeze(0)
            # sanity check that images are channel last
            _, h, w, c = img_tensor.shape
            assert c < h and c < w, f"expect channel last images, but instead got {img_tensor.shape=}"

            # sanity check that images are uint8
            assert img_tensor.dtype == torch.uint8, f"expect torch.uint8, but instead {img_tensor.dtype=}"

            # convert to channel first of type float32 in range [0,1]
            img_tensor = einops.rearrange(img_tensor, "b h w c -> b c h w").contiguous()
            img_tensor = img_tensor.type(torch.float32)
            img_tensor /= 255

            return_observations[imgkey] = img_tensor

    if "environment_state" in observations:
        env_state = torch.from_numpy(observations["environment_state"]).float()
        if env_state.dim() == 1:
            env_state = env_state.unsqueeze(0)

        return_observations[OBS_ENV_STATE] = env_state

    if "agent_pos" in observations:
        agent_pos = torch.from_numpy(observations["agent_pos"]).float()
        if agent_pos.dim() == 1:
            agent_pos = agent_pos.unsqueeze(0)
        return_observations[OBS_STATE] = agent_pos

    if "robot_state" in observations:
        return_observations[f"{OBS_STR}.robot_state"] = _convert_nested_dict(observations["robot_state"])

    # Handle IsaacLab Arena format: observations have 'policy' and 'camera_obs' keys
    if "policy" in observations:
        return_observations[f"{OBS_STR}.policy"] = observations["policy"]

    if "camera_obs" in observations:
        return_observations[f"{OBS_STR}.camera_obs"] = observations["camera_obs"]

    return return_observations

def canonical_decode(visual):
    scale=(visual.float().abs().amax(dim=-1,keepdim=True)/127).clamp_min(torch.finfo(torch.float16).tiny)
    scale=scale.to(torch.float16).float()
    return ((visual.float()/scale).round().clamp(-127,127)*scale).to(torch.bfloat16)

def spatial_tokens(visual, projection):
    """16x16 row-major patches -> 4x4 fixed cells -> fixed channel projection."""
    if visual.shape[-3:] != (1,256,2048):
        raise ValueError(f'expected one 16x16 patch camera: {visual.shape}')
    n = len(visual)
    cells = visual.float().reshape(n,4,4,4,4,2048).mean(dim=(2,4))
    return cells.reshape(n,16,2048) @ projection

def cpu_batch(spatial,proprio,past,language,step,device='cuda:0'):
    import torch
    n=len(spatial);z=np.zeros((5,4096),np.float32);z[-n:]=spatial
    q=np.zeros((5,4),np.float32);q[-n:]=proprio
    a=np.zeros((4,4),np.float32)
    if n>1:a[-(n-1):]=np.asarray(past)[-(n-1):]
    values=dict(history=z,history_mask=np.arange(5)>=5-n,proprio=q,proprio_mask=np.arange(5)>=5-n,
                past_actions=a,language=np.asarray(language),remaining=np.float32((300-step)/300))
    return {k:torch.as_tensor(v,device=device)[None] for k,v in values.items()}

from typing import Any, Mapping, Sequence

class OfflineFeatures:
    def _policy_batch(self, observation: Mapping[str, Any], instruction: str) -> dict[str, Any]:
        batch = self._preprocess_observation(dict(observation))
        batch["task"] = [instruction]
        return self.preprocessor(batch)

    @torch.inference_mode()
    def encode_visual_batch(
        self,
        observations: Sequence[Mapping[str, Any]],
        *,
        batch_size: int,
    ) -> np.ndarray:
        """Encode control observations in bounded batches with the frozen vision tower.

        This path intentionally does not call ``policy.select_action`` or the
        PaliGemma language/reasoning transformer.  It only materializes the
        same frozen image patch embeddings used by the legacy collector.
        """

        if self._instruction is None:
            raise RuntimeError("reset_episode must be called before visual encoding")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if not observations:
            raise ValueError("observations must not be empty")
        self._visual_encoder_calls += math.ceil(len(observations) / batch_size)
        self._visual_observations_encoded += len(observations)

        encoded_rows: list[torch.Tensor] = []
        for start in range(0, len(observations), batch_size):
            image_rows: list[torch.Tensor] = []
            for observation in observations[start : start + batch_size]:
                policy_batch = self._policy_batch(observation, self._instruction)
                images, image_masks = self.policy._preprocess_images(policy_batch)
                real_images = [
                    image
                    for image, mask in zip(images, image_masks, strict=True)
                    if bool(mask[0].item())
                ]
                if len(real_images) != 1:
                    raise RuntimeError(
                        "Meta-World SFT collection expects one real camera, "
                        f"got {len(real_images)}"
                    )
                image_rows.append(real_images[0])
            image_batch = torch.cat(image_rows, dim=0)
            encoded = self.policy.model.paligemma_with_expert.embed_image(image_batch)
            encoded_rows.append(encoded.to(dtype=torch.float32, device="cpu"))
        # Preserve the collector's [time,camera,patch,feature] convention.
        return torch.cat(encoded_rows, dim=0).unsqueeze(1).numpy()

    @torch.inference_mode()
    def encode_instruction(self, instruction: str) -> np.ndarray:
        cleaned = instruction.strip().replace("_", " ").replace("\n", " ")
        tokenized = self.tokenizer(
            [cleaned],
            max_length=int(self.policy_config.tokenizer_max_length),
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        tokens = tokenized["input_ids"].to(self.device)
        mask = tokenized["attention_mask"].to(self.device, dtype=torch.bool)
        embedded = self.policy.model.paligemma_with_expert.embed_language_tokens(tokens)
        embedding_dim = embedded.shape[-1]
        embedded = embedded * math.sqrt(embedding_dim)
        weights = mask.unsqueeze(-1).to(dtype=embedded.dtype)
        pooled = (embedded * weights).sum(dim=1) / weights.sum(dim=1).clamp_min(1)
        return pooled[0].to(dtype=torch.float32, device="cpu").numpy()
