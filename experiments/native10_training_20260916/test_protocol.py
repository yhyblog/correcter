"""CPU-only protocol tests; no imports of torch, VLA, runtime or simulator."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from experiments.native10_training_20260916.protocol import (
    TASKS, ProtocolError, audit_records, candidate_seed, canonical_hash,
    episode_key, pending_protocol, protocol_digest, require_stage_budget,
    seed_for, source_seed, suffix_seed, validate_manifest, validate_protocol,
)


def episode(task=TASKS[0], env_seed=11, split="train"):
    return dict(episode_id=episode_key(task, env_seed), task=task,
                env_seed=env_seed, split=split)


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.document = Path(self.temp.name) / "ANALYSIS_TEST_PROTOCOL.md"
        self.document.write_text("Synthetic CPU-test approval fixture, no simulation authorization.\n")
        self.ready_path = Path(self.temp.name) / "NATIVE10_ANALYSIS_READY.json"

    def approved_fixture(self):
        cfg = pending_protocol()
        cfg.update(status="frozen", episode_manifest=[episode(task, i + 11) for i, task in enumerate(TASKS)],
                   replicates=2, cpu=dict(worker_threads=1, critic_threads=2),
                   budget=dict(hard_total=8, training_update_total=7, count_failures=True,
                               count_retries=True, stages={
                                   "p0": dict(simulator_attempts=2, training_updates=0),
                                   "collect": dict(simulator_attempts=6, training_updates=0),
                                   "fit": dict(simulator_attempts=0, training_updates=7)}))
        cfg["stage_release_scopes"] = {"p0": "p0_anchor_and_native10_diagnostics",
                                       "collect": "main_collection", "fit": "critic_training"}
        ready = dict(task_id="native10-training-20260916", status="approved",
                     task_document=str(self.document), protocol_review=str(self.document),
                     task_document_sha256=hashlib.sha256(self.document.read_bytes()).hexdigest(),
                     protocol_review_sha256=hashlib.sha256(self.document.read_bytes()).hexdigest(),
                     released_scope=list(cfg["stage_release_scopes"].values()),
                     new_simulator_attempts_hard_limit=8, p0_attempts_hard_limit=2)
        self.ready_path.write_text(json.dumps(ready))
        cfg["analysis_ready"] = dict(path=str(self.ready_path),
            sha256=hashlib.sha256(self.ready_path.read_bytes()).hexdigest())
        self.approve(cfg)
        return cfg

    def approve(self, cfg):
        cfg["analysis_approval"] = dict(status="approved", approved_by="analysis",
            protocol_sha256=protocol_digest(cfg), document_path=str(self.document),
            document_sha256=hashlib.sha256(self.document.read_bytes()).hexdigest())

    def test_pending_has_no_formal_counts_and_cannot_run_any_resource(self):
        cfg = pending_protocol()
        self.assertFalse(validate_protocol(cfg)["runnable"])
        self.assertEqual(cfg["episode_manifest"], [])
        self.assertIsNone(cfg["replicates"])
        self.assertIsNone(cfg["budget"])
        for resource in ("simulator_attempts", "training_updates"):
            with self.subTest(resource=resource), self.assertRaises(ProtocolError):
                require_stage_budget(cfg, "collect", resource=resource)

    def test_five_tasks_horizons_and_cpu_config_are_explicit(self):
        good = self.approved_fixture()
        self.assertTrue(validate_protocol(good, require_runnable=True)["runnable"])
        bad_values = [("tasks", list(TASKS[:-1])), ("tasks", [TASKS[0]] * 5),
                      ("source_horizon", 50), ("prefix_horizon", 5),
                      ("suffix_horizon", 50), ("replicates", 0),
                      ("cpu", {"worker_threads": 0, "critic_threads": 2})]
        for key, value in bad_values:
            cfg = deepcopy(good);cfg[key] = value;self.approve(cfg)
            with self.subTest(key=key, value=value), self.assertRaises(ProtocolError):
                validate_protocol(cfg)

    def test_episode_split_cannot_leak_through_cut_repeat_or_renamed_id(self):
        row = episode()
        for extra in [dict(row, split="held"), dict(row, cut=15), dict(row, repeat=7)]:
            with self.subTest(extra=extra), self.assertRaises(ProtocolError):
                validate_manifest([row, extra])
        with self.assertRaises(ProtocolError):
            validate_manifest([row, dict(row, episode_id="renamed_variation", split="held")])
        with self.assertRaises(ProtocolError):
            audit_records([row], [dict(row, split="held", cut=5)])

    def test_every_planned_outcome_type_is_retained_and_cannot_be_filtered(self):
        planned = [episode(env_seed=i) for i in range(4)]
        records = [dict(planned[0], success=True, no_alarm=True),
                   dict(planned[1], success=False, no_alarm=True),
                   dict(planned[2], status="failed", no_alarm=None),
                   dict(planned[3], success=False, no_alarm=False, cut=5),
                   dict(planned[3], success=True, no_alarm=False, cut=15, repeat=2)]
        result = audit_records(planned, records)
        self.assertEqual(result["planned_episodes"], 4)
        self.assertEqual(result["recorded_episodes"], 4)
        self.assertEqual(result["records"], 5)
        with self.assertRaises(ProtocolError):
            audit_records(planned, records[3:])
        partial = audit_records(planned, records[3:], require_all=False)
        self.assertEqual(len(partial["missing_episode_ids"]), 3)
        with self.assertRaises(ProtocolError):
            validate_manifest([dict(planned[0], success=True)])
        for key, value in [("retain_all_planned", False), ("no_outcome_filter", False),
                           ("manifest_filters", ["alarm_only"])]:
            cfg = pending_protocol();cfg[key] = value
            with self.subTest(key=key), self.assertRaises(ProtocolError):
                validate_protocol(cfg)

    def test_seed_domains_are_stable_typed_and_independent_of_split(self):
        row = episode()
        changed_split = dict(row, split="held")
        self.assertEqual(source_seed(row, 1), source_seed(changed_split, 1))
        self.assertEqual(source_seed(row, 1), source_seed(row["episode_id"], 1))
        self.assertNotEqual(seed_for(1), seed_for("1"))
        self.assertNotEqual(source_seed(row, 1), suffix_seed(row, 5, 0, 1))
        self.assertNotEqual(source_seed(row, 1), source_seed(row, 1, namespace="other"))
        self.assertEqual(canonical_hash({"x": 1, "y": 2}), canonical_hash({"y": 2, "x": 1}))
        with self.assertRaises(ProtocolError):
            canonical_hash({"nan": float("nan")})
        with self.assertRaises(ProtocolError):
            source_seed(row, True)

    def test_same_a0_all_methods_share_noise_and_no_method_seed_argument(self):
        row = episode()
        bank = {method: candidate_seed(row, 5, candidate_index=0, namespace="test")
                for method in ("replan", "velocity", "direct", "post")}
        self.assertEqual(len(set(bank.values())), 1)
        self.assertNotEqual(bank["replan"], candidate_seed(row, 5, 1, namespace="test"))
        with self.assertRaises(TypeError):
            candidate_seed(row, 5, method="direct")
        with self.assertRaises(TypeError):
            suffix_seed(row, 5, 0, 0, method="direct")

    def test_suffix_pairs_by_decision_index_across_different_control_times(self):
        row = episode()
        normal = {step: suffix_seed(row, 5, 0, i) for i, step in enumerate((10, 20, 30))}
        guided = {step: suffix_seed(row, 5, 0, i) for i, step in enumerate((15, 25, 35))}
        self.assertEqual(list(normal.values()), list(guided.values()))
        self.assertNotEqual(normal[20], guided[15])
        streams = {suffix_seed(row, 5, repeat, decision_index)
                   for repeat in range(8) for decision_index in range(12)}
        self.assertEqual(len(streams), 96)
        self.assertNotEqual(suffix_seed(row, 5, 0, 0), suffix_seed(row, 15, 0, 0))

    def test_missing_or_stale_analysis_approval_cannot_run(self):
        for mutate in [lambda c: c.update(analysis_approval=None),
                       lambda c: c["analysis_approval"].update(status="pending"),
                       lambda c: c["analysis_approval"].update(approved_by="executor"),
                       lambda c: c["analysis_approval"].update(document_sha256="0" * 64),
                       lambda c: c["analysis_approval"].update(document_path="relative.md"),
                       lambda c: c.update(replicates=3),
                       lambda c: c["budget"].update(hard_total=9),
                       lambda c: c["episode_manifest"][0].update(split="held")]:
            cfg = self.approved_fixture();mutate(cfg)
            with self.subTest(config=cfg), self.assertRaises(ProtocolError):
                require_stage_budget(cfg, "collect")
        cfg = self.approved_fixture()
        self.document.write_text("Changed after approval")
        with self.assertRaises(ProtocolError):
            validate_protocol(cfg, require_runnable=True)

    def test_budget_stage_and_global_limits_include_retry_and_training(self):
        cfg = self.approved_fixture()
        self.assertEqual(require_stage_budget(cfg, "collect", used=5, total_used=7)["remaining_after"], 0)
        for kwargs in [dict(stage="unknown"), dict(stage="collect", used=6, total_used=6),
                       dict(stage="collect", total_used=8), dict(stage="collect", used=2, total_used=1),
                       dict(stage="fit"), dict(stage="collect", requested=0)]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ProtocolError):
                require_stage_budget(cfg, **kwargs)
        self.assertEqual(require_stage_budget(cfg, "fit", used=6, total_used=6,
                                             resource="training_updates")["remaining_after"], 0)
        with self.assertRaises(ProtocolError):
            require_stage_budget(cfg, "fit", used=7, total_used=7, resource="training_updates")
        for key in ("count_failures", "count_retries"):
            bad = deepcopy(cfg);bad["budget"][key] = False;self.approve(bad)
            with self.subTest(key=key), self.assertRaises(ProtocolError):
                validate_protocol(bad)
        bad = deepcopy(cfg);bad["budget"]["stages"]["collect"]["simulator_attempts"] = 7;self.approve(bad)
        with self.assertRaises(ProtocolError):
            validate_protocol(bad)

    def test_p0_ready_does_not_release_registered_main_or_training_budgets(self):
        cfg = self.approved_fixture()
        ready = json.loads(self.ready_path.read_text())
        ready["released_scope"] = ["isolated_implementation", "cpu_protocol_checks",
                                   "p0_anchor_and_native10_diagnostics"]
        self.ready_path.write_text(json.dumps(ready))
        cfg["analysis_ready"]["sha256"] = hashlib.sha256(self.ready_path.read_bytes()).hexdigest()
        self.approve(cfg)
        self.assertEqual(require_stage_budget(cfg, "p0")["limit"], 2)
        for stage, resource in [("collect", "simulator_attempts"), ("fit", "training_updates")]:
            with self.subTest(stage=stage), self.assertRaises(ProtocolError):
                require_stage_budget(cfg, stage, resource=resource)

    def test_old_stale_ready_and_p0_overallocation_are_rejected(self):
        cfg = self.approved_fixture()
        old = self.ready_path.with_name("ANALYSIS_READY.json")
        old.write_bytes(self.ready_path.read_bytes())
        cfg["analysis_ready"]["path"] = str(old);self.approve(cfg)
        with self.assertRaises(ProtocolError):
            validate_protocol(cfg)

    def test_p0_and_cpu_scope_cannot_be_used_to_authorize_training_or_other_stages(self):
        for scope in ("p0_anchor_and_native10_diagnostics", "cpu_protocol_checks", "isolated_implementation"):
            cfg = self.approved_fixture()
            cfg["stage_release_scopes"]["fit"] = scope
            self.approve(cfg)
            with self.subTest(scope=scope), self.assertRaises(ProtocolError):
                require_stage_budget(cfg, "fit", resource="training_updates")
        cfg = self.approved_fixture()
        cfg["budget"]["stages"]["p0"]["training_updates"] = 1
        cfg["budget"]["training_update_total"] += 1
        self.approve(cfg)
        with self.assertRaises(ProtocolError):
            require_stage_budget(cfg, "p0", resource="training_updates")
        cfg = self.approved_fixture()
        ready = json.loads(self.ready_path.read_text());ready["status"] = "revoked"
        self.ready_path.write_text(json.dumps(ready))
        cfg["analysis_ready"]["sha256"] = hashlib.sha256(self.ready_path.read_bytes()).hexdigest()
        self.approve(cfg)
        with self.assertRaises(ProtocolError):
            validate_protocol(cfg)
        cfg = self.approved_fixture()
        self.ready_path.write_text(self.ready_path.read_text() + "\n")
        with self.assertRaises(ProtocolError):
            validate_protocol(cfg)
        cfg = self.approved_fixture()
        cfg["stage_release_scopes"]["collect"] = "p0_anchor_and_native10_diagnostics"
        self.approve(cfg)
        with self.assertRaises(ProtocolError):
            validate_protocol(cfg)


if __name__ == "__main__":
    unittest.main()
