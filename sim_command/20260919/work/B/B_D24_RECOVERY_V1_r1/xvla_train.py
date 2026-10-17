#!/usr/bin/env python3
"""Single-seed LeRobot launcher. Default is config-only; --execute is explicit.

Use accelerate launch for DDP; global batch is fixed at 64 for formal runs.
The upstream trainer owns optimization, scheduler, checkpoint and resume logic.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

WORKSPACE = Path('/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace')
PROJECT = WORKSPACE / 'projects/vla-baselines'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["xvla"])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--world-size", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Exactly two optimizer steps in preparation/smoke-runs")
    parser.add_argument("--resume-from", type=Path, help="Local checkpoint pretrained_model/train_config.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.resume_from or args.smoke:
        parser.error("New frozen X-VLA stage only; no smoke probe or old-run resume")
    args.output = args.output.resolve()
    if not args.output.is_relative_to(Path("/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B")):
        parser.error("B-owned output required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", args.run_id):
        parser.error("run-id must be a simple, non-path identifier")
    if args.world_size not in (1, 2, 4, 8):
        parser.error("world-size must be 1, 2, 4 or 8")
    recipes = json.loads((PROJECT / "configs/experiments.json").read_text())
    common, recipe = recipes["metaworld"], recipes["metaworld"][args.kind]
    from lerobot.configs.default import DatasetConfig, WandBConfig
    from lerobot.configs.policies import PreTrainedConfig
    from lerobot.configs.train import TrainPipelineConfig
    from lerobot.policies import factory  # register policy types

    if args.resume_from:
        config_path = args.resume_from.resolve(strict=True)
        allowed = (WORKSPACE / "artifacts/vla-baselines").resolve()
        if not config_path.is_relative_to(allowed) or config_path.name != "train_config.json":
            parser.error("resume must target this project's local train_config.json")
        cfg = TrainPipelineConfig.from_pretrained(config_path, local_files_only=True)
        cfg.resume = True
        if cfg.policy.type != args.kind or cfg.seed != 42 or cfg.job_name != args.run_id:
            parser.error("resume kind/seed differs from this single-seed recipe")
        if args.smoke != ("preparation/smoke-runs" in str(cfg.output_dir)):
            parser.error("Do not mix preparation and formal checkpoint streams")
        sys.argv = [sys.argv[0], "--config_path=" + str(config_path)]
    else:
        initial = WORKSPACE / recipe["init"]
        policy = PreTrainedConfig.from_pretrained(initial, local_files_only=True)
        policy.pretrained_path, policy.device, policy.push_to_hub = initial, "cuda", False
        policy.n_action_steps = recipe["K"]
        branch = "preparation/smoke-runs" if args.smoke else "runs/metaworld"
        destination = args.output
        cfg = TrainPipelineConfig(
            dataset=DatasetConfig(repo_id=common["dataset_repo"], root=str(WORKSPACE / common["dataset_root"]),
                revision=common["dataset_revision"], use_imagenet_stats=False),
            policy=policy, output_dir=destination, job_name=args.run_id, seed=42,
            batch_size=2 if args.smoke else common["global_batch_size"] // args.world_size,
            steps=2 if args.smoke else recipe["steps"], num_workers=2 if args.smoke else 4,
            eval_freq=0, log_freq=1 if args.smoke else 100,
            save_freq=1 if args.smoke else 5000, save_checkpoint=True,
            rename_map=common["rename_map"], wandb=WandBConfig(enable=False),
        )
        sys.argv = [sys.argv[0]]
    cfg.validate()
    assert set(cfg.policy.input_features) == {"observation.state", "observation.images.image"}
    assert cfg.policy.input_features["observation.state"].shape == (4,)
    assert cfg.policy.output_features["action"].shape == (4,)
    assert cfg.policy.chunk_size == recipe["H"]
    assert not cfg.dataset.image_transforms.enable and not cfg.use_rabc and cfg.peft is None
    resolved = {"scope": "smoke" if args.smoke else "formal", "execute": args.execute,
                "world_size": args.world_size, "effective_batch": cfg.batch_size * args.world_size,
                "mixed_precision": "bf16", "recipe_status": recipe["recipe_status"], "config": cfg.to_dict()}
    if int(os.environ.get("RANK", "0")) == 0:
        print(json.dumps(resolved, indent=2), flush=True)
    if not args.execute:
        return
    if int(os.environ.get("WORLD_SIZE", "1")) != args.world_size:
        raise RuntimeError("Launch world-size disagrees with the requested effective batch")
    os.environ["ACCELERATE_MIXED_PRECISION"] = "bf16"
    # CUDA/NCCL is initialized before upstream creates DataLoader workers.
    # Spawn avoids inheriting GPU communicator state through Linux fork.
    import torch.multiprocessing
    torch.multiprocessing.set_start_method("spawn", force=True)
    from train_xvla_bounded import train
    train(cfg)


if __name__ == "__main__":
    main()
