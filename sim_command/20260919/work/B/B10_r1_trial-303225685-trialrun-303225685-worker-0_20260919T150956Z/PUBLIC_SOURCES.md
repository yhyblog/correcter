# Public method identity

[GAF paper v1](https://arxiv.org/html/2607.02092v1), arXiv2607.02092v1,2 July2026, sections III-D–G and IV-B, reviewed19 September2026. It defines discounted success-to-go/MSE, detached clean-action gradients and ensemble disagreement gating. The reported multi-task setting uses three critics, width768/depth4, beta2, clip1, uncertainty scale10 and minimum gate0.1.

[Public code](https://github.com/ylhaichen/guided-action-flow/tree/ee67a70e576dc7f02a00cff86c9dd97f868c896f) is pinned separately from the paper. Association as the authors’ official repository was not independently established; do not call it official. `upstream_lock.json` records every tracked file SHA. CPU parity uses the actual pinned guidance function.

Our changes are pi05/MetaWorld state/action/task-feature mapping, actual ten-step chunk, parent-episode split and finite training budget proposal. No claim of reproducing the paper’s scores or matching its complete training history. No QGF-v3/IQL baseline is added.
