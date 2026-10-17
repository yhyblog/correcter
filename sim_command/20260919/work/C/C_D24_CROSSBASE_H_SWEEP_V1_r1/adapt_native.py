from pathlib import Path
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
R=B/'results/C/C_D24_CROSSBASE_H_SWEEP_V1'
s=(B/'results/C/C_D24_L11_RENDER_RECOVERY_V1/xcode/native_client.py').read_text()
s=s[:s.index('    def evaluate_source(')]
s=s.replace('Resident X native H30/K10 G0-multi evaluation, with a separate encoder.','Resident X raw30, natural H20/H30 and corrective C10 evaluation.')
s=s.replace('from paths import ROOT,WORKSPACE','from paths import ROOT,WORKSPACE,CONFIG')
s=s.replace('from common import claim_attempt,claim_work,boundary,AdmissionStop,episode_deadline,remaining_seconds','from common import boundary,AdmissionStop\nfrom admission import claim_unit\nfrom horizon_queue import HorizonQueue')
s=s.replace("connection=Client(cfg['socket_path'],family='AF_UNIX',authkey=bytes.fromhex(cfg['ipc_auth']))", "connection=Client(cfg['socket_path'],family='AF_UNIX',authkey=bytes.fromhex(cfg['ipc_auth'])) if cfg['encoder_required'] else None")
s=s.replace("if stopping:raise AdmissionStop('owned native worker stop')", "if stopping or time.time()>=CONFIG['absolute_wall_deadline_unix']-90:raise AdmissionStop('owned native worker stop or finite deadline')")
s=s.replace("        connection.send(dict(kind=kind,**fields))", "        if connection is None:raise RuntimeError('N must never use auxiliary RPC')\n        counters['encoder_RPC_entered']+=1\n        connection.send(dict(kind=kind,**fields))")
s=s.replace("        bridge.begin(gradient)", "        counters['policy_queries_entered']+=1\n        bridge.begin(gradient)")
a=s.index('    with torch.inference_mode(False),torch.enable_grad():');b=s.index("    atomic_json(out/'MODEL_READY.json'",a)
s=s[:a]+'''    native_slopes=None
    if cfg['methods'][0] in ('Post','Velocity'):
        with torch.inference_mode(False),torch.enable_grad():
            leaf=torch.zeros((10,4),device='cuda',requires_grad=True)
            physical=post(leaf);native_slopes=torch.autograd.grad(physical.sum(),leaf)[0].detach().cpu().numpy()
        if not np.isfinite(native_slopes).all() or np.any(native_slopes==0):raise ValueError('native inverse action transform invalid')
'''+s[b:]
s=s.replace("base='X-VLA030000',raw_H=30,native_K=10,NFE=10", "base='X-VLA030000',raw_plan_length=30,normal_H=[20,30],commitment_C=10,base_n_action_steps_metadata=10,NFE=10")
s=s.replace('native_action_slopes=native_slopes[0].tolist()', 'native_action_slopes=native_slopes[0].tolist() if native_slopes is not None else None,encoder_required=cfg[\'encoder_required\']')
(R/'xcode/native_client.py').write_text(s)
