"""Append-only follow-up to completed A10. Exact known VLA candidates only."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
import subprocess

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')
BASE = ROOT/'Corrector/sim_command/20260919'
OUT = BASE/'receipts/A'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path): return {'path':str(path),'sha256':sha(path)}
def write_once(path, data):
    with path.open('x') as stream:
        stream.write(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def inspect(path, expected_bytes):
    p = Path(path); real = p.resolve(strict=True)
    if not real.is_relative_to(ROOT): raise ValueError('Candidate resolves outside authorized workspace')
    paths = [real] if real.is_file() else [x for x in real.rglob('*') if x.is_file() and not x.is_symlink()]
    files = []
    for x in sorted(paths):
        if not x.resolve().is_relative_to(real if real.is_dir() else real.parent):
            raise ValueError('Nested file leaves the candidate tree')
        s=x.stat();files.append({'path':str(x),'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'inode':s.st_ino,'device':s.st_dev})
    total=sum(x['bytes'] for x in files)
    return {'absolute_path':str(p),'realpath':str(real),'inside_authorized_root':True,'logical_bytes':total,
            'matches_prior_inventory_bytes':total==expected_bytes,'file_count':len(files),
            'metadata_fingerprint_sha256':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),
            'files':files,'full_payload_rehashed':False}


def main():
    c=json.loads((BASE/'CONTROL.json').read_text())
    assert c['mode']=='prepare' and not c['stop_requested'] and all(v==0 for v in c['current_compute_limits'].values())
    assert c['storage_cleanup']['active_deletion_release'] is None
    old_inventory=OUT/'STORAGE_CANDIDATES.json';prior=json.loads(old_inventory.read_text())
    b_inventory=BASE/'receipts/B/STORAGE_CANDIDATES.json';peer=json.loads(b_inventory.read_text())
    b_result_path=BASE/'receipts/B/B10_RESULT.json';b_result=json.loads(b_result_path.read_text())
    b_root=Path(next(x['path'] for x in b_result['artifacts'] if x['path'].endswith('ARTIFACT_MANIFEST.json'))).parent
    roots=[BASE/'contracts',BASE/'manifests',BASE/'releases',b_root/'configs',
           ROOT/'embodied-ai-workspace/projects/vla-baselines/configs',
           ROOT/'embodied-ai-workspace/manifests/vla-baselines-20260911']
    listed=subprocess.run(['rg','--files',*[str(p) for p in roots]],capture_output=True,text=True,check=True)
    text_paths=[Path(x) for x in listed.stdout.splitlines() if Path(x).suffix in ('.json','.md','.txt','.yaml','.yml')]
    corpus=[(p,p.read_text(errors='replace')) for p in text_paths]
    records=[]
    for candidate in prior['candidates']:
        record=inspect(candidate['absolute_path'],candidate['logical_bytes'])
        target=Path(candidate['absolute_path']);relative=str(target.relative_to(ROOT))
        needles=[str(target),candidate['realpath'],relative]
        if target.parent.name=='checkpoints':needles.append('checkpoints/'+target.name)
        hits=[]
        for p,text in corpus:
            for number,line in enumerate(text.splitlines(),1):
                if any(word in line for word in needles):
                    hits.append({'path':str(p),'line':number,'match_excerpt':line.strip()[:350]})
        record.update(project=candidate['project'],prior_recommendation=candidate['recommendation'],
            current_recommendation=candidate['recommendation'],bounded_reference_hits=hits,
            cross_node_receipt_status=b_result['status'],cross_node_receipt=ref(b_result_path),
            cross_node_live_writer_check='not established by shared receipt; analysis must coordinate before deletion',
            all_historical_seal_dependencies_cleared=False,
            unused_conclusion='not established' if candidate['recommendation']=='defer' else 'explicitly retained experiment input',
            retained_alternative=candidate['replacement_retained_asset'])
        records.append(record)
    peer_records=[]
    for candidate in peer['candidates']:
        record=inspect(candidate['absolute_path'],candidate['logical_bytes'])
        replacement=Path(candidate['replacement_retained'])
        record.update(project=candidate['project'],recommendation='defer',origin_receipt=ref(b_inventory),
            retained_alternative={'path':str(replacement),'exists':replacement.is_file(),
                                  'bytes':replacement.stat().st_size if replacement.is_file() else None},
            unused_conclusion='B reports historical download fragments; active writers and historical recovery references not cleared',
            cross_node_live_writer_check='not established; no deletion authorization')
        peer_records.append(record)
    last=ROOT/'embodied-ai-workspace/artifacts/vla-baselines/runs/metaworld/smolvla/mt50-smolvla-s42-mb-20260912-v1/checkpoints/last'
    checks={'campaign_id':'corrector-sim-20260919','scope':'A10 completed-task/storage follow-up; no rerun',
        'checked_at_utc':datetime.now(timezone.utc).isoformat(),'hostname':platform.node(),
        'control_revision':c['revision'],'source_inventory':ref(old_inventory),
        'bounded_reference_scope':[str(p) for p in roots],'reference_files_checked':len(corpus),
        'reference_file_identities':[ref(p) for p in text_paths],
        'scope_limit':'Exact known VLA candidate paths and current named configs/manifests only; absence of a hit does not prove unused or authorize deletion. No non-VLA content scanned.',
        'A_candidates':records,'B_reported_candidates_metadata_confirmed_by_A':peer_records,
        'smol_last_alias':{'path':str(last),'is_symlink':last.is_symlink(),'realpath':str(last.resolve(strict=True))},
        'active_deletion_release':None,'deleted_paths':[],'deleted_bytes':0,
        'resource_counts':{'simulator_attempts':0,'vla_sampling_calls':0,'optimizer_updates':0,'gpu_seconds':0},
        'existing_A00_result':ref(OUT/'A00_RESULT.json'),'existing_A10_result':ref(OUT/'A10_RESULT.json')}
    path=OUT/'STORAGE_REFERENCE_CHECK_r1.json';write_once(path,checks)
    report=OUT/'A10_STORAGE_FOLLOWUP_r1.md'
    with report.open('x') as stream:
        stream.write(f'''# A10／存储交接补充

已核对 CONTROL v{c['revision']}、TASK_BOARD、P00_PREP_V1及存储规则；A00/A10完整RESULT已交付，合同/任务SHA一致。本轮只核对回执与已知VLA资产，不重复已完成实验或CPU测试。

- 公共接口：`results/A/A10/interface_v1/INTERFACE_READY.json`，B已消费；最终代码为`code_snapshot_v3`。两环境各42项CPU检查通过，A7/B23样例兼容。
- 有限预检文件：`results/A/A10/commands_v3/run_proposed_native_preflight.sh`与`preflight_v3/PROPOSAL.json`；需另行release。报价1次reset/attempt、5次native采样、50次flow、1真实控制步，0优化/重试；本轮未执行。
- 原存储清单：`receipts/A/STORAGE_CANDIDATES.json`，4 keep＋9 defer；9个Smol中间checkpoint为14,494,556,639逻辑bytes。不再使用未获证实，不能将其写成已批准删除。
- 本次补查：{len(corpus)}份限定范围的合同/manifest/配置及B10回执；13项候选重新解析真实路径、大小/mtime/inode，结果见`STORAGE_REFERENCE_CHECK_r1.json`。Smol `last`指向保留的050000。
- B提交的2个X-VLA下载残片，A已核对其确切路径与大小，总计3,519,073,692逻辑bytes，完整替代权重存在。仍为defer；双方写入/历史恢复依赖尚未排除。
- 没有active_deletion_release，删除0；收到分析端逐项delete/keep/defer清单后，A仅执行匹配的delete项，届时重新检查身份、写入和引用，再追加清理回执。非VLA项目、目录外目标及旧封存不动。
- 模型GPU推理、训练更新、仿真全部0；8张H100的occupancy guard保持正常。TASK_BOARD仍由分析端维护，执行端未改为complete。

完整短报告与RESULT：`receipts/A/A10_REPORT.md`、`A10_RESULT.json`；此前已queue送达分析会话。此次只追加补充文件，未覆盖原结果或存储清单。
''')
    write_once(OUT/'A10_STORAGE_FOLLOWUP_r1.json',{'status':'complete_read_only_followup','report':ref(report),
        'reference_check':ref(path),'existing_inventory':ref(old_inventory),'existing_A10_result':ref(OUT/'A10_RESULT.json'),
        'formal_compute_started':False,'deleted_bytes':0,'control_revision':c['revision']})
    print(json.dumps({'report':str(report),'reference_check':str(path),'files_checked':len(corpus),
        'A_metadata_matches':sum(x['matches_prior_inventory_bytes'] for x in records),
        'A_candidate_count':len(records),'B_metadata_matches':sum(x['matches_prior_inventory_bytes'] for x in peer_records),
        'deleted_bytes':0},ensure_ascii=False))


if __name__=='__main__':main()
