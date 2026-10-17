#!/usr/bin/python
"""Atomic B11 CPU report publication after the prepared queue jobs pass."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from datetime import datetime, timezone
from consume import C, HERE, write, require


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def install_bytes(target, raw):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        require(target.read_bytes()==raw,'immutable published file differs: '+str(target));return
    tmp=target.with_name(target.name+'.tmp.'+str(os.getpid()))
    with tmp.open('xb') as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    os.link(tmp,target);tmp.unlink()


def publish(out, wave):
    summary=json.loads((out/'REAL_VIEW_SUMMARY.json').read_text());require(summary['status']=='PASS','integration did not pass')
    test=json.loads((wave/'01_tests.RESULT.json').read_text());require(test['exit_code']==0,'CPU tests did not pass')
    destination=C/'results/B/B11_COMMON_POOL_VIEWS_CPU_V1';destination.mkdir(parents=True,exist_ok=True)
    for p in out.rglob('*'):
        if p.is_file():
            target=destination/p.relative_to(out);target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():require(target.read_bytes()==p.read_bytes(),'published file differs')
            else:install_bytes(target,p.read_bytes())
    for name in ['views.py','consume.py','test_views.py','publish.py','CPU_INPUT_LOCK.json']:
        target=destination/'code'/name;install_bytes(target,(HERE/name).read_bytes())
    evidence=destination/'evidence';evidence.mkdir(exist_ok=True)
    for name in ['01_tests.log','01_tests.RESULT.json','02_consume.log','02_consume.RESULT.json','JOBS.json']:
        install_bytes(evidence/name,(wave/name).read_bytes())
    counts=summary['totals']
    contract={
        'kind':'internal_CPU_reference_view_contract_not_new_public_schema',
        'LVM':'normal demonstration; same physical original episode and continuous 11 frames; actual endpoint float32 [256,2048] tokens with encoder/preprocessing signature; original action_t [4] and normalizer. Terminal flags may remain null; no action clipping.',
        'D5':'same physical branch, actual five commands t..t+4 and arrived features s(t+1)..s(t+5). Causal history references use max(0,t-4)..t; no future context and no invented frames. Completeness of the terminal outcome is independent. Initial histories shorter than five remain explicit references, with no tensor padding/materialization here.',
        'GAF':'actual ten executed bounded commands; state is the existing four policy-side observation_bundle.proprio values matched to transition.proprioception; frozen 2048 language bytes. Preserve B10 wire action/normalizer binding. gamma=.99 per real control, target gamma**(first_success_result_state - window_start - 1), or zero only for a proven complete failure. Never raw50 tail or short-window padding.',
        'paired':'parent/source/split/cut/source signature/context/protocol common, frozen captured full-state closure checked before intervention, planned aligned repeats exactly [0,1]. No single-repeat paired mean. G0 C5 = mean3fresh(mean2repeat) - mean2old; Q C10 gain = candidate-a0; pair = plus-minus.',
        'BCE':'one group per parent/cut/protocol/raw C10; own complete repeats with explicit effective count; no inferred paired permission',
        'outcome':'s300 inclusive, early observed success valid; technical/quota/timeout/unknown TimeLimit remain null. No currently accepted MW absorbing-failure rule is invented.',
        'grouping':'canonical parent/source identity and physical branch only; exclude partial hardlink aliases; logical aggregates/reference roles add zero physical attempts; a0/fresh0 can share a plan but never Q/G0 physical outcomes.',
        'privileged_state':'restoration evidence is used only for CPU audit; model input whitelist contains public observations/features, executed actions and language references.',
        'validation_scope':'reference indices and targets, not tensor materialization, full feature-byte audit, new GPU execution, training or scientific acceptance',
        'lineage':{'existing_backbone':'2500 demonstrations previously seen, per frozen protocol; not re-read here',
                   'new_common_pool':'17 processed train parents, 16 paired; dev0, independent of historical initialization splits',
                   'old_initializations':'old five-task D/G0/Q and old LVM split lineage retained separately; no claim that every method used identical historical data'},
        'old_GPU_proposal':'sealed/unapproved; old 90-second handoff and 200 GPU/1600 reservation seconds not reused. Future genuine jobs use their own queue machine gates and scoped timeouts.'}
    write(destination/'VIEW_CONTRACT.json',contract)
    compatibility=dict(status='PASS_CPU_REFERENCE_COMPATIBILITY',task_id='B11_COMMON_POOL_VIEWS_CPU_V1',
        public_interface_v1_unchanged=True,sidecar_v1_unchanged=True,
        checks=['A READY/schema/examples SHA verified','each physical sidecar and public record independently checked',
                'shared BANK requested key and actual commitment phase','branch-local observation and SHA identity',
                'logical aggregate label_key/member references','both repeats and Q C10/G0 C5 namespaces',
                'raw C10 grouping and source inheritance','pre-outcome full-state closure evidence',
                'bounded command mapping and original raw plan index','G0_old is nonintervened old_queue_control',
                'short GAF windows rejected and s300 final state retained','public deployment cost missing preserved'],
        correctly_rejected=['all real rollout LVM positives: not demonstrations, no endpoint tokens',
                            'GAF missing ten executed commands','paired targets of normal-only pre-cut source',
                            'observable-only, missing/misaligned repeat, raw alias and technical cutoff fixtures'],
        counts=counts,synthetic_test_count=9,synthetic_samples_counted_as_real=False,
        limits=['No feature/token extraction or model/driver/environment/training calls',
                'Accepted file manifests bind all feature references; only two stored feature endpoints per branch are payload-checked',
                'No complete RGB/feature/MJB/weight-store rehash or new physics-equivalence claim'],
        queue_control_plane='Separate QUEUE_AUTONOMY_V2 detached CPU controller. No executable GPU job, so no formal reservation and no holder/driver operation under B revision2; future GPU stages use the gated shared service.')
    write(destination/'SIDECAR_COMPATIBILITY.json',compatibility)
    diff='''B11 adds an isolated stdlib metadata consumer and targeted tests. B10/R2 packages and model/loss code remain unchanged.

The previous general trajectory validator required terminal flags for LVM. The new independent LVM gate preserves unknown flags and checks only its own demonstrated endpoint/action identities. D5, GAF and paired Q/G0 retain their separate, stricter requirements. The consumer recomputes eligibility instead of trusting raw sidecar views=false or aggregate carriers. It uses accepted canonical physical records and shared BANK references with exact phase/key checks. No public schema or scientific numerical collector is changed.

Validation: 9 new CPU test methods plus the real accepted 17-parent reference integration. Existing 9/27-test suites, inventories, old GPU probes and historical held/storage candidates were not rerun or opened.
'''
    install_bytes(destination/'DIFF.md',diff.encode())
    normal=next(p for p in summary['by_parent'] if p['disposition']=='normal_complete_success_before_preplanned_cut')
    table=[('D5',counts['D5_eligible_windows'],counts['D5_rejected_windows']),
           ('GAF',counts['GAF_eligible_windows'],counts['GAF_rejected_windows']),
           ('LVM',0,counts['LVM_rejected_contiguous_11frame_windows']),
           ('Q BCE groups',counts['Q_BCE_groups'],'effective repeats explicit'),
           ('Q gain / pair',str(counts['Q_gain_targets'])+' / '+str(counts['Q_pair_targets']),'normal-only masked'),
           ('G0',counts['G0_targets'],'normal-only masked')]
    report='B11 已完成 CPU 引用视图适配；无模型、驱动、仿真或训练调用。\n\n'
    report+='| 视图 | 真实 train 可用数 | 拒绝或限制 |\n|---|---:|---|\n'
    report+='\n'.join('| '+str(a)+' | '+str(b)+' | '+str(d)+' |' for a,b,d in table)+'\n\n'
    report+=f"共 17 个已处理父源、16 个配对父源、{counts['physical_attempts']} 次既有物理尝试；development 为 0。{counts['logical_aggregates']} 个逻辑汇总及 partial 硬链接没有增加物理计数。所有数量来自真实既有元数据，9 项新 CPU 测试的合成数据另计。\n\n"
    report+=f"cut55 前 s48 成功的 normal-only 源保留 {normal['D5_eligible_windows']} 个 D5、{normal['GAF_eligible_windows']} 个 GAF 窗口，四项配对目标保持 null/mask=false。完整 Q 成功且承诺不足十步的案例共 {len(summary['Q_complete_short_commitment_cases'])} 个；cut 处缺十步的 GAF 窗口不补齐。box-close 的既有实际初始化计数单独引用在父源摘要。\n\n"
    report+='所有 normal rollout 都不是 LVM demonstration，未保存所需 token，因此没有真实 LVM 正例。Q/G0 按独立 C10/C5 域重算，旧队列 G0_old 不冒充在线纠偏。恢复特权状态只用于审计；公共成本引用仍缺失，不用私有整数账本拼造 UUID。\n\n'
    report+='这里只建立带 SHA 的窗口/目标引用索引。全部 JSON、语言小数组及每分支两个已保存特征端点经过读取核验，其余特征/RGB/MJB 引用沿用已验收 manifest；没有重 hash 整库。训练张量和模型训练尚未执行。已有 2500 示范底座、旧初始化沿革、新共同池保持分别披露。\n\n'
    report+='证据：REAL_VIEW_SUMMARY.json、INPUT_CHECK_MANIFEST.json、indices/、SIDECAR_COMPATIBILITY.json、VIEW_CONTRACT.json、evidence/01_tests.log。旧两 forward GPU 提案仍封存；新持久队列控制面与 B11 的零计算用量分列。\n'
    install_bytes(destination/'REPORT.md',report.encode())
    manifest=[dict(path=str(p),sha256=digest(p),size_bytes=p.stat().st_size) for p in sorted(destination.rglob('*')) if p.is_file() and p.name not in ('ARTIFACT_MANIFEST.json','RESULT.json')]
    write(destination/'ARTIFACT_MANIFEST.json',dict(files=manifest))
    ack=json.loads((C/'receipts/B/B11_COMMON_POOL_VIEWS_CPU_V1_ACK.json').read_text())
    result=dict(campaign_id='corrector-sim-20260919',task_id='B11_COMMON_POOL_VIEWS_CPU_V1',revision=1,role='B',
        hostname=os.uname().nodename,session_id=ack['executor_session_id'],status='complete',
        started_at_utc=ack['started_at_utc'],finished_at_utc=datetime.now(timezone.utc).isoformat(),
        input_identity=json.loads((HERE/'CPU_INPUT_LOCK.json').read_text()),
        artifacts={'report':str(destination/'REPORT.md'),'summary':str(destination/'REAL_VIEW_SUMMARY.json'),
                   'compatibility':str(destination/'SIDECAR_COMPATIBILITY.json'),'manifest':str(destination/'ARTIFACT_MANIFEST.json')},
        resource_counts=dict(simulator_attempts=0,completed_rollouts=0,vla_sampling_calls=0,optimizer_updates=0,
                             model_forward_calls=0,encoder_forward_calls=0,gpu_seconds=0,driver_queries=0,
                             scientific_compute_release_claims=0,torch_imports=0),
        existing_data_counts=counts,control_plane_accounting='B_QUEUE_JOIN_V1 revision2 separately owns the CPU queue; no formal reservation needed for CPU-only B preparation',
        failures_and_retries=[],findings=['Independent method eligibility implemented','16 paired plus one normal-only source consumed',
        'All paired targets independently recomputed with two aligned repeats','Real LVM positive unavailable, synthetic terminal-unknown case passes',
        'D5/GAF are reference indices, no feature extraction or training','Private restoration and cost evidence remains audit-only'],
        blockers=[],next_task_proposal='analysis review; persistent queue may run its separately authorized frozen collection after package/machine gates')
    write(destination/'RESULT.json',result)
    install_bytes(C/'receipts/B/B11_COMMON_POOL_VIEWS_CPU_V1_REPORT.md',report.encode())
    write(C/'receipts/B/B11_COMMON_POOL_VIEWS_CPU_V1_RESULT.json',result)
    print(json.dumps(dict(status='complete',result=str(destination/'RESULT.json'),counts=counts),indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--wave',type=Path,required=True);a=p.parse_args()
    publish(a.out,a.wave)
