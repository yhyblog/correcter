"""Untrained Q: forward inference only, on the existing CPU deployment."""
import json
import os
from pathlib import Path
import socket
import time
import torch
from torch import nn

ROOT = Path(__file__).resolve().parent
torch.set_num_threads(2)
torch.set_num_interop_threads(1)

class Q(nn.Module):
    def __init__(self, width):
        super().__init__()
        def mlp(a, b, c, activation=True):
            return nn.Sequential(nn.Linear(a,b), nn.SiLU(), nn.Linear(b,c),
                                 *([nn.SiLU()] if activation else []))
        self.state = mlp(61, 2*width, width)
        self.action = mlp(40, width, width)
        self.residual = mlp(40, width, width)
        self.head = mlp(2*width, 2*width, 1, False)
        self.advantage = mlp(3*width, 2*width, 1, False)
        self.register_buffer('residual_scale', torch.full((10,4), .05))
    def forward(self, features, actions):
        n,k,h,d = actions.shape
        base = actions[:,0].repeat_interleave(k,0)
        shared = torch.cat([self.state(features).repeat_interleave(k,0), self.action(base.flatten(1))],-1)
        delta = ((actions.flatten(0,1)-base)/self.residual_scale).flatten(1)
        actual = self.advantage(torch.cat([shared,self.residual(delta)],-1))
        zero = self.advantage(torch.cat([shared,self.residual(torch.zeros_like(delta))],-1))
        return (self.head(shared)+actual-zero).reshape(n,k).sigmoid()

torch.manual_seed(20260926)
models = {w: [Q(w).eval().requires_grad_(False) for _ in range(4)] for w in (16,512)}
features = torch.randn(1,61)
a0 = torch.randn(1,10,4).clamp(-1,1)
actions = torch.stack((a0,a0.clone()),dim=1)

def query(width, members):
    return torch.stack([model(features,actions) for model in models[width][:members]]).mean(0)

rows=[]
configs=[(16,1),(16,4),(512,1),(512,4)]
with torch.inference_mode():
    for w,m in configs:
        for _ in range(20):query(w,m)
    for rep in range(100):
        offset=rep%4
        for w,m in configs[offset:]+configs[:offset]:
            start=time.perf_counter()
            result=query(w,m)
            rows.append(dict(width=w,members=m,repetition=rep,seconds=time.perf_counter()-start))

summary=[]
for w,m in configs:
    times=sorted(row['seconds'] for row in rows if row['width']==w and row['members']==m)
    pos=(len(times)-1)*.95; lower=int(pos)
    p95=times[lower]+(times[min(lower+1,len(times)-1)]-times[lower])*(pos-lower)
    summary.append(dict(width=w,members=m,parameters_per_member=sum(p.numel() for p in models[w][0].parameters()),
                        n=len(times),mean_ms=1000*sum(times)/len(times),p95_ms=1000*p95))
cpu=sorted(set(line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')))
metadata=dict(status='complete',host=socket.gethostname(),cpu=cpu,device='CPU',dtype='float32',threads=2,
              batch_size=1,action_slots=2,torch_version=torch.__version__,initialization='random, untrained',
              scope='preprocessed 61D state -> anchored Q probabilities; forward only; ensemble mean',
              warmups_per_configuration=20,timed_queries_per_configuration=100,training_updates=0,
              gradient_calls=0,time=time.time(),results=summary)
(ROOT/'timings.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
(ROOT/'RESULT.json').write_text(json.dumps(metadata,indent=2))
report=['# 宽度512 Q：仅前向推理测速','',f"设备：CPU（{', '.join(cpu)}），FP32，2线程，batch1。随机初始化，无训练。",'',
        '保持既有Q的五个MLP、锚点/候选两槽、零差优势校正和四成员平均概率。状态61维，动作10×4；预处理后的固定输入。每种配置预热20次、计时100次。只包含前向推理，不包含梯度、哈希、投影、D/G0、VLA或通信。','',
        '| 宽度 | 成员数 | 单成员参数 | 均值ms | P95 ms | 次数 |','|---:|---:|---:|---:|---:|---:|']
for row in summary:
    report.append(f"| {row['width']} | {row['members']} | {row['parameters_per_member']:,} | {row['mean_ms']:.3f} | {row['p95_ms']:.3f} | {row['n']} |")
report += ['','此前约10ms是Q上下文构造、动作梯度与投影的合计，本表仅测前向，计量范围不同。','',
           '[逐次计时](timings.jsonl) · [机器可读结果](RESULT.json) · [测速代码](benchmark.py)']
(ROOT/'REPORT.md').write_text('\n'.join(report)+'\n')
print(json.dumps(metadata,ensure_ascii=False),flush=True)
