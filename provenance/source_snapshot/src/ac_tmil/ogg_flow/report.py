"""Reproducible Chinese flow-mechanism report and source-bootstrap figures.

This module does not collect data, tune settings, or select a deployable winner.
Invoke only after the separate development evaluation has completed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from .common import ROOT, DOC, REPO, METHODS, MATCHED, read, file_sha256


LABELS = {
    "replan": "仅重规划 a0",
    "velocity_matched": "原 velocity，最终幅度匹配",
    "direct_matched": "QGF 式直接注入，最终幅度匹配",
    "post_matched": "采样后梯度修正，最终幅度匹配",
    "reverse_matched": "直接注入的反向命令对照",
    "random_matched": "结构化随机命令对照",
    "velocity_native": "原 velocity，原生输出",
    "direct_native": "QGF 式直接注入，原生输出",
}
PLOT_LABELS = {
    "replan": "Replan a0",
    "velocity_matched": "Velocity / matched",
    "direct_matched": "Direct / matched",
    "post_matched": "Post-sampling / matched",
    "reverse_matched": "Reverse / matched",
    "random_matched": "Random / matched",
    "velocity_native": "Velocity / native",
    "direct_native": "Direct / native",
}


def _p(value):
    return "未记录" if value is None else f"{100*value:.2f}%"


def _pp(value):
    return "未记录" if value is None else f"{100*value:+.2f}"


def _ci(metric):
    if metric["mean"] is None or metric["interval"] is None:
        return "未估计"
    lo, hi = metric["interval"]
    return f"{_pp(metric['mean'])} [{_pp(lo)}, {_pp(hi)}]"


def _n(value, places=4):
    return "未记录" if value is None else f"{value:.{places}f}"


def _range(summary, places=4):
    if not summary["n"]:
        return "无记录"
    return f"{_n(summary['mean'], places)} [{_n(summary['min'], places)}, {_n(summary['max'], places)}]"


def _comparison(result, method, reference):
    return next(item for item in result["registered_comparisons"]
                if item["method"] == method and item["reference"] == reference)


def interpretations(result):
    """Conditional wording fixed in code before new development outcomes exist."""
    methods = result["methods"]
    direct = methods["direct_matched"]["gain"]
    post = methods["post_matched"]["gain"]
    reverse = _comparison(result, "direct_matched", "reverse_matched")["gain"]
    random = _comparison(result, "direct_matched", "random_matched")["gain"]
    velocity = _comparison(result, "direct_matched", "velocity_matched")["gain"]
    versus_post = _comparison(result, "direct_matched", "post_matched")["gain"]
    post_minus_reverse = post["mean"]-methods["reverse_matched"]["gain"]["mean"]
    post_minus_random = post["mean"]-methods["random_matched"]["gain"]["mean"]
    lines = [
        f"QGF 式直接注入相对 a0 的真实配对收益为 **{_ci(direct)} 个百分点**；采样后梯度修正为 **{_ci(post)} 个百分点**。以下判断同时看幅度匹配的方向对照和区间，不以 Q 是否上升代替真实收益。",
        f"终点梯度修正、反向、随机的实际成功率分别为 {_p(methods['post_matched']['success']['mean'])}、{_p(methods['reverse_matched']['success']['mean'])}、{_p(methods['random_matched']['success']['mean'])}；终点修正减反向/随机的点差为 {_pp(post_minus_reverse)}/{_pp(post_minus_random)} 个百分点。这两项是描述性补充，不冒充六项预登记比较。不能因为几种引导都相对 a0 为负，就跳过这些控制并把原因判为评分方向。",
    ]
    if reverse["interval"][0] > 0 and random["interval"][0] > 0:
        lines.append("评分方向：直接引导相对同幅反向、随机两项名义区间下界均大于零，支持当前直接引导产生的命令方向具有比较优势。该证据仅对应这组新开发状态、半径和随机对照分布，不证明所有连续邻域的梯度都可靠。")
    elif reverse["mean"] <= 0 and random["mean"] <= 0:
        lines.append("评分方向：直接引导点估计同时没有优于同幅反向和随机，当前直接flow路径所产生的最终命令方向缺少比较优势。这个结论不自动覆盖终点动作梯度；还须结合终点修正相对a0及两个控制的成绩。若相应区间跨零，结论是证据不足，不能把小样本未检出差异写成梯度在所有状态都无效。")
    else:
        lines.append("评分方向：直接引导未在同幅反向和随机两个比较中同时得到区间下界为正的支持。局部方向性尚未建立；点估计的局部优势仍需要新源复核。")
    if post["interval"][0] > 0 and post_minus_reverse > 0 and post_minus_random > 0:
        lines.append("终点修正相对a0的区间下界为正，且点估计优于反向和随机，说明不能将问题一概归为评价器没有可用方向。由于终点与两个控制的差值这里只作描述，仍不把这种排序当成独立确认。")
    elif post_minus_reverse <= 0 and post_minus_random <= 0:
        lines.append("终点修正点估计也没有优于反向和随机；在当前半径与命令投影下，评分导数的方向性证据仍不足。该判断依赖控制比较，不是由所有方法均为负这一事实单独推出。反向是direct命令的反向，并非post梯度的精确反向，仍不能据此证明全部局部导数失效。")
    else:
        lines.append("终点修正与两个控制没有形成一致的点估计优势或劣势；评分方向和flow注入的责任不能在这组结果中简单二选一。反向控制对应direct最终命令，不是post梯度的精确负方向。")
    if post["interval"][0] > 0 and versus_post["interval"][1] < 0:
        lines.append("梯度进入 flow 的方式：终点动作修正得到正收益，且直接 flow 引导显著弱于终点修正；这支持继续检查引导时点、后续采样作用和 Jacobian。当前试验没有分别干预这些细节，不能指定其中某一个就是原因。")
    elif post["mean"] > 0 and direct["mean"] <= 0:
        lines.append("梯度进入 flow 的方式：点估计呈现终点修正为正、flow 直接引导非正的模式，提示注入及后续采样可能影响效果；是否有可靠差别应以 direct−post 的配对区间判断，目前不能仅凭一正一负认定机制已经定位。")
    elif direct["interval"][0] > 0 and versus_post["interval"][0] > 0:
        lines.append("梯度进入 flow 的方式：直接 flow 引导具有正收益，并优于终点修正，支持该 flow 内路径在本配置下增加价值。不能将这一开发优势推广到其他半径、注入时间或评价器。")
    else:
        lines.append("梯度进入 flow 的方式：终点与 flow 内方法的当前对照不能把失败单独归因于注入方式。二者共享同一个冻结评分目标；评分误差、局部导数及采样路径仍可能共同限制收益。")
    if velocity["interval"][0] > 0:
        lines.append("直接注入相对原 velocity 参数化的配对区间下界为正，支持本轮直接注入配置的比较优势；这不等价于证明只去掉 τ 因子就能普遍改善策略。")
    elif velocity["interval"][1] < 0:
        lines.append("直接注入相对原 velocity 参数化的配对区间上界小于零，本轮不支持用直接注入替换原参数化。")
    else:
        lines.append("直接注入与原 velocity 参数化的配对区间跨零，尚未分辨出稳定差异。")
    q = result["diagnostics"]["predictions"]
    q_up_no_real = [method for method in ("velocity_matched", "direct_matched", "post_matched")
                    if q[method]["predicted_gain"]["mean"] is not None
                    and q[method]["predicted_gain"]["mean"] > 0 and methods[method]["gain"]["mean"] <= 0]
    if q_up_no_real:
        lines.append("以下方法平均预测收益为正、完整源真实净收益非正：" + "、".join(LABELS[method] for method in q_up_no_real) + "。这直接说明 Q 改善不能在本批状态下当作纠偏有效的替代指标；预测均值只统计报警源，完整源结局仍保留未报警源。")
    improvements = [method for method in ("velocity_matched", "direct_matched", "post_matched", "velocity_native", "direct_native")
                    if methods[method]["gain"]["mean"] >= .05]
    if improvements:
        lines.append("达到约 +5 点开发点估计的方法为：" + "、".join(LABELS[method] for method in improvements) + "。这些是同一开发集多方法比较，不构成独立验证成功；需固定候选版本及新保留源方案后另行确认。")
    else:
        lines.append("本轮评分驱动的纠偏方法没有达到相对 a0 约 +5 个百分点的开发点估计目标。反向和随机为机制对照，不能因其偶然最高就作为已验证的纠偏算法发布。")
    return lines


def figure(result):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none", "savefig.facecolor": "white"})
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 5.7), sharey=True,
                             gridspec_kw={"width_ratios": [1, 1.15], "wspace": .23})
    palette = {"replan": "#5B6573", "velocity_matched": "#3D7EAA", "direct_matched": "#007C78",
               "post_matched": "#7351A1", "reverse_matched": "#BF7428", "random_matched": "#7E817E",
               "velocity_native": "#7DAAC7", "direct_native": "#76B4AB"}
    for index, method in enumerate(METHODS):
        for axis, metric_name in zip(axes, ("success", "gain")):
            metric = result["methods"][method][metric_name]
            center = 100*metric["mean"]
            lower, upper = np.asarray(metric["interval"])*100
            axis.errorbar(center, index, xerr=np.maximum(0, [[center-lower], [upper-center]]),
                          color=palette[method], fmt="o", markersize=6, capsize=3, elinewidth=1.5)
    axes[0].set_yticks(np.arange(len(METHODS)), [PLOT_LABELS[method] for method in METHODS])
    axes[0].invert_yaxis()
    axes[0].set_xlim(-3, 103)
    axes[0].set_xlabel("Task success (%)")
    axes[0].set_title("Actual paired outcomes", loc="left", fontsize=11, fontweight="bold")
    axes[1].axvline(0, color="#333333", lw=1)
    axes[1].axvline(5, color="#A76C26", lw=1, linestyle="--", label="+5 pp target")
    axes[1].set_xlabel("Gain over same-source a0 (percentage points)")
    axes[1].set_title("Gain and nominal 95% source interval", loc="left", fontsize=11, fontweight="bold")
    for axis in axes:
        axis.grid(axis="x", color="#D7DDE1", alpha=.6, linewidth=.7)
        axis.set_axisbelow(True)
        axis.set_ylim(len(METHODS)-.45, -.6)
    fig.suptitle("Frozen v3 critic: flow guidance development screen", x=.02, ha="left", fontsize=15, fontweight="bold")
    fig.text(.02, .91, f"{result['planned_sources']} planned sources · {result['paired_suffixes_per_source']} paired suffixes · ten-step prefix / fixed10 continuation", fontsize=10, color="#4B5563")
    fig.text(.02, .025, "Task-stratified source bootstrap. Dashed line: +5 pp. Native and matched arms are separate. Development, not independent validation.", fontsize=8.6, color="#4B5563")
    fig.subplots_adjust(left=.23, right=.985, bottom=.14, top=.83)
    return fig


def render(result, cfg, preflight, frozen):
    methods = result["methods"]
    diagnostic = result["diagnostics"]
    audit = result["audit"]
    counts = audit["counts"]
    budget = audit["budget"]
    lines = ["# 固定 v3 评价器的 Flow Guidance 机制实验结果", "", "日期：2026-09-16。", "",
             "本报告由封存参数、逐源真实结局及审计自动生成。实验用途是分辨评分方向与 flow 注入机制；全部方法共用冻结 v3 critic、VLA、D、G0，没有重训。", ""]
    lines.extend([paragraph + "\n" for paragraph in interpretations(result)])
    lines.extend([
        "**本轮是开发机制筛查，开发集最好成绩不称独立验证成功。** 八次后缀是同源配对重复，独立统计单位为源。", "",
        "## 范围、分母与冻结", "",
        f"预定开发源 {result['planned_sources']} 个，五任务各6源；实际报警 {result['alarm_sources']}、未报警 {result['no_alarm_sources']}。每臂每源八次配对后缀，成功率分母均为 {result['denominator']}。未报警源将共同真实结局广播到各臂，没有删除不利源。", "",
        f"预算日志累计 {budget['attempts']} 次计费尝试，上限 {budget['hard_maximum']}，余量 {budget['remaining']}。预检、并发复现、失败/未完成重试均保留计数；源捕获也保守加计。开发完整分支 {counts.get('completed_branches', 0)}，预检完整分支 {preflight['counts'].get('completed_branches', 0)}，核验通过的并发复现 {len(audit['concurrency_reproductions'])}。", "",
        "| 计费类型 | 次数 |", "| --- | ---: |",
    ])
    for kind, count in sorted(budget["by_kind"].items()):
        lines.append(f"| {kind} | {count} |")
    lines.extend([
        "", f"正式冻结记录证明开发源捕获前配置与比较规则已经固定：`development_sources_absent={frozen['development_sources_absent']}`，`preflight_outcomes_used_for_settings={frozen['preflight_outcomes_used_for_settings']}`。正式 config SHA256：`{result['config_sha256']}`；freeze SHA256：`{result['formal_freeze_sha256']}`。", "",
        f"晚报警源（cut>290）{counts.get('late_alarm_sources_cut_gt_290', 0)}，因总预算截短前缀的源 {counts.get('budget_truncated_prefix_sources', 0)}，因提前终止截短前缀的分支 {counts.get('terminal_shortened_prefix_branches', 0)}。这些源全部保留；候选按十步评分，实际执行可因成功、终止或总预算提前结束。", "",
        "## 真实成功率、救回与损害", "",
        "区间为按任务分层、完整源重采样的名义95% bootstrap区间；单位为百分点，未作多重比较校正。救回和损害均要求同源同后缀配对。", "",
        "| 方法 | 成功率 | 相对 a0 收益 [95%区间] | 救回/损害 | 正/负/零收益源 |",
        "| --- | ---: | --- | ---: | ---: |",
    ])
    for method in METHODS:
        row = methods[method]
        lines.append(f"| {LABELS[method]} | {_p(row['success']['mean'])} | {_ci(row['gain'])} | {row['rescues']}/{row['harms']} | {row['positive_sources']}/{row['negative_sources']}/{row['zero_sources']} |")
    lines.extend(["", "![八臂真实成功率和配对收益区间](docs/ogg_flow_20260916/success_comparison.png)", "",
                  "救回贡献为救回次数/完整配对分母，损害贡献为负的损害次数/完整配对分母；两者相加等于净收益。逐源逐候选八次结局见 [CSV](docs/ogg_flow_20260916/per_source.csv) 和 [JSON](docs/ogg_flow_20260916/per_source.json)。", "",
                  "## 六项预登记机制比较", "",
                  "| 方法 − 参照 | 配对收益 [95%区间]（百分点） | 配对救回/损害 |", "| --- | --- | ---: |"])
    for item in result["registered_comparisons"]:
        lines.append(f"| {LABELS[item['method']]} − {LABELS[item['reference']]} | {_ci(item['gain'])} | {item['rescues']}/{item['harms']} |")
    lines.extend(["", "同幅直接−反向/随机检验方向性；direct−velocity控制实际命令半径、比较注入方式；direct−post检验采样路径相对终点修正的附加作用。点估计不同而区间跨零不能证明机制差异。", "",
                  "## 按任务分层", "", "每任务只有6个独立源。下表用于描述，不能据此事后启用任务专属策略。每格为相对 a0 收益及95%区间（百分点）。", "",
                  "| 任务 | a0 成功率 | velocity匹配 | direct匹配 | post匹配 |", "| --- | ---: | --- | --- | --- |"])
    for task, item in result["per_task"].items():
        m = item["methods"]
        lines.append(f"| {task} | {_p(m['replan']['success']['mean'])} | {_ci(m['velocity_matched']['gain'])} | {_ci(m['direct_matched']['gain'])} | {_ci(m['post_matched']['gain'])} |")
    lines.extend(["", "| 任务 | reverse匹配 | random匹配 | velocity原生 | direct原生 |", "| --- | --- | --- | --- | --- |"])
    for task, item in result["per_task"].items():
        m = item["methods"]
        lines.append(f"| {task} | {_ci(m['reverse_matched']['gain'])} | {_ci(m['random_matched']['gain'])} | {_ci(m['velocity_native']['gain'])} | {_ci(m['direct_native']['gain'])} |")
    lines.extend(["", "## 参数、实际命令半径及回退", "",
        f"引导最大化 `R(a)=mean_i[Q_i(s,a;a0)−Q_i(s,a0;a0)]`，四成员sigmoid概率先平均；固定状态和槽0的指定a0，只对槽1候选求导。原 velocity 使用 `v'=v−alpha*tau*g`，直接使用 `v'=v−alpha*g`，alpha={cfg['guidance']['alpha']:g}，时点={cfg['guidance']['times']}。采样时间1→0、Euler步长−0.1，两组共用T与真实clamp导数。", "",
        f"只固定一组匹配目标：XYZ RMS≤{cfg['matching']['xyz_rms']:g}、夹爪 RMS≤{cfg['matching']['gripper_rms']:g}；Linf上限分别为{cfg['matching']['xyz_linf']:g}/{cfg['matching']['gripper_linf']:g}。共同边界mask为`1−abs(a0)>={cfg['matching']['boundary_clearance']:g}`，执行后幅度差容差{cfg['matching']['tolerance']:g}。这些量是[-1,1]环境命令单位，不是米。", "",
        "匹配对最终反归一化及裁剪后的前10×4命令实施，可能放大原生扰动；表中的匹配臂与原生臂因此分别命名。后采样方向为`S² grad_a R`，S为反归一化斜率；随机方向使用每维三节点平滑插值，反向是direct匹配命令差的负值。", "",
        "**命令归一化的解释限制：** XYZ与夹爪分组归一化会显著放大某些很小的原生夹爪方向，并改变XYZ/夹爪的相对比例。匹配臂是带额外最终命令投影的实验对象，不能称为原生QGF性能。原生velocity/direct另列；其实际幅度不同，不能据原生臂之间的收益差直接作同幅机制归因。", "",
        "**局部性的范围：** 最终命令相对a0的半径约束不约束中间干净动作估计或critic查询路径。较大alpha可以在中间更新产生明显变化，即使最后命令落在小半径内。因此本轮仅保证最终执行扰动受限，不声称整个生成链或中间评价查询都处于局部邻域；中间查询超出训练支持仍是评分可靠性的一个限制。", "",
        "| 方法 | XYZ RMS：均值 [最小,最大] | 夹爪 RMS：均值 [最小,最大] | XYZ Linf均值 | 夹爪 Linf均值 |",
        "| --- | --- | --- | ---: | ---: |",
    ])
    for method in METHODS:
        amp = diagnostic["amplitudes"][method]
        lines.append(f"| {LABELS[method]} | {_range(amp['xyz_rms'])} | {_range(amp['gripper_rms'])} | {_n(amp['xyz_linf']['mean'])} | {_n(amp['gripper_linf']['mean'])} |")
    matching = diagnostic["matching"]
    lines.extend(["", f"共同mask移除坐标比例：{_range(matching['masked_fraction'])}。统计分母为{matching['sources']}个实际报警源。", "",
                  "| 动作组 | 整组零方向共同回退源 | 共同半径回缩源 | 达到半径：均值 [最小,最大] |", "| --- | ---: | ---: | --- |"])
    for group, item in matching["groups"].items():
        lines.append(f"| {group} | {item['zero_group_sources']} | {item['shrunk_sources']} | {_range(item['achieved_target'])} |")
    for mode in ("velocity", "direct"):
        item = diagnostic["guidance"][mode]
        lines.extend(["", f"{mode}生成异常回退：{item['fallback_sources']}/{item['sources']} 源；原因计数`{json.dumps(item['fallback_reasons'], ensure_ascii=False, sort_keys=True)}`。回退仍使用同seed a0并保留源。"])
    lines.extend(["", "## 预测收益与真实收益", "",
        "下表只统计实际报警源；完整总体成功率仍以上表全部30源为准。收益MSE是预测相对最终成功概率与八次配对后缀经验相对成功率之差的平方均值，不是D的视觉预测误差。", "",
        "| 方法 | 预测收益均值（点） | 实际收益均值（点） | 收益MSE | Q预测正/实际负源 |", "| --- | ---: | ---: | ---: | ---: |",
    ])
    for method in METHODS:
        item = diagnostic["predictions"][method]
        lines.append(f"| {LABELS[method]} | {_pp(item['predicted_gain']['mean'])} | {_pp(item['actual_gain']['mean'])} | {_n(item['gain_mse'], 6)} | {item['predicted_positive_but_actual_negative']} |")
    lines.extend(["", "## 各flow时点的梯度与clamp", "",
        "以下为当次更新记录的源均值；梯度norm是内部干净动作变量前10×4的L2，XYZ/夹爪列为对应RMS。clip比例表示反归一化后裁剪前已越界坐标，零梯度比例是实际链式导数为零的坐标比例。失败回退可能使某时点样本数减少，不补造记录。", "",
        "| 模式 | τ | 记录数 | 干净梯度L2 | XYZ梯度RMS | 夹爪梯度RMS | 注入梯度L2 | clip比例 | 零梯度比例 | 干净估计距a0 XYZ RMS |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for mode in ("velocity", "direct"):
        for tau in cfg["guidance"]["times"]:
            item = diagnostic["guidance"][mode]["per_time"][str(tau)]
            lines.append(f"| {mode} | {tau:g} | {item['gradient_norm']['n']} | {_n(item['gradient_norm']['mean'], 6)} | {_n(item['gradient_xyz_rms']['mean'], 6)} | {_n(item['gradient_grip_rms']['mean'], 6)} | {_n(item['injection_gradient_norm']['mean'], 6)} | {_p(item['clipping_fraction']['mean'])} | {_p(item['zero_gradient_fraction']['mean'])} | {_n(item['clean_a0_xyz_rms']['mean'])} |")
    cost = diagnostic["cost"]
    lines.extend(["", "## 计算成本", "",
        "下列耗时是各源/worker累计负担，不等于并行波次经过的自然时间。匹配臂、原生臂及反向对照共享生成结果，不能将同一次VLA生成重复记作多次。GPU数值为每worker的PyTorch峰值统计，不是整机NVML总显存。回放、环境和VLA计时有不同范围，不能机械相加。", "",
        "| 候选生成 | VLA调用 | 累计秒 | 目标前向 | 目标反向 | 峰值已分配MiB：均值 [最小,最大] | 增量峰值MiB：均值 [最小,最大] |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ])
    for mode, item in cost["candidate_generation"].items():
        total, memory = item["totals"], item["memory_mib"]
        lines.append(f"| {mode} | {total['policy_calls']:.0f} | {total['seconds']:.2f} | {total['objective_forward_calls']:.0f} | {total['backward_calls']:.0f} | {_range(memory['peak_cuda_allocated_mib'], 1)} | {_range(memory['incremental_peak_cuda_allocated_mib'], 1)} |")
    objective = cost["objective_totals"]
    source_calls = sum(item.get("policy_calls", 0) for item in cost["source_capture"])
    source_seconds = sum(item.get("policy_seconds", 0) for item in cost["source_capture"])
    lines.extend(["", f"含终点梯度及最终候选打分的critic总成本：目标前向{objective['objective_forward_calls']:.0f}次（成员前向{objective['critic_member_forward_calls']:.0f}），目标反向{objective['objective_backward_calls']:.0f}次（成员反向{objective['critic_member_backward_calls']:.0f}）；记录前向耗时{objective['critic_forward_seconds']:.3f}秒。这些合计包含上表中的flow目标调用，不再相加。反向没有独立计时，其开销包含在生成或终点梯度wall中；终点梯度单源耗时{_range(cost['post_gradient_seconds'], 4)}秒。", "",
        f"源捕获VLA调用{source_calls:.0f}次、累计{source_seconds:.2f}秒。候选生成整体单源wall为{_range(cost['generation_wall_seconds'], 2)}秒。各分支正式fixed10后缀成本如下，含重复后缀但不含源捕获或candidate生成。", "",
        "| 执行方法 | 后缀VLA调用 | 后缀VLA秒 | 回放秒 | 环境秒 | 分支wall秒 |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for method in METHODS:
        item = cost["branches_by_method"][method]
        lines.append(f"| {LABELS[method]} | {item['suffix_policy_calls']:.0f} | {item['suffix_policy_seconds']:.2f} | {item['replay_seconds']:.2f} | {item['environment_seconds']:.2f} | {item['wall_seconds']:.2f} |")
    lines.extend(["", "预检额外的零强度与两个解析目标sampler调用各占每报警源3次VLA生成；其单独时间未保存，已包含在预检generation整体wall中。预检/复现预算与正式收益分母分开，上述主成本表针对正式开发阶段。", "",
        "## 已证实的实现性质、机制证据与边界", "",
        f"已证实的实现性质：预检审计状态`{preflight['status']}`，正式审计状态`{audit['status']}`；固定a0槽与状态、R(a0)=0、冻结权重SHA、同初始噪声、零强度逐位还原、真实sampler解析目标符号、无额外环境步、命令重建和float32幅度匹配均已检查。原始source物理回放容差{audit['replay_physics_atol']:g}，同候选重复前缀物理和图像逐位一致；后缀实际生成时刻和随机seed按决策序号核对。", "",
        "机制支持以开头的配对比较为准。旧v3同步诊断另见[只读复核](docs/ogg_flow_20260916/legacy_diagnosis.md)：它解释旧离散选择器的lift误选、a0切片低估、四成员共同偏差及margin=0的scale抵消，不承担本轮新方法的效果验证。", "",
        "尚未解决：30源规模对约+5点可能缺乏功效；评价器训练来自离散动作银行，连续局部导数未被训练标签充分约束；未对Jacobian、全链反传、更换critic、不同注入时点或第二组半径作结局驱动追加；没有真实机器人迁移证据。若本轮出现正的开发候选，下一步须先固定该版本与独立新源验证方案。", "",
        "本轮为QGF式直接干净动作注入适配，保留本地T的真实clamp导数以隔离主因素；没有同时复现官方裁剪后重建求导变量的路径。推导、论文与作者代码核对见[方法审查](docs/ogg_flow_20260916/method_review.md)，其中包括[QGF官方实现](https://github.com/zhouzypaul/qgf/blob/main/agents/qgf.py)。", "",
        "## 交付与复现", "",
        "- [冻结参数与种子](docs/ogg_flow_20260916/parameters.json)、[正式冻结身份](outputs/act_recap_ogg_flow_20260916/formal_freeze.json)。",
        "- [完整评估JSON](outputs/act_recap_ogg_flow_20260916/evaluation.json)、[开发审计](outputs/act_recap_ogg_flow_20260916/audits/development.json)、[预算日志](outputs/act_recap_ogg_flow_20260916/budget/attempts.jsonl)。",
        "- [引导实现](src/ac_tmil/ogg_flow/guidance.py)、[实际命令匹配](src/ac_tmil/ogg_flow/candidates.py)、[真实采集](src/ac_tmil/ogg_flow/collection.py)、[统计审计](src/ac_tmil/ogg_flow/evaluation.py)、[报告生成](src/ac_tmil/ogg_flow/report.py)。",
        "- [SVG图](docs/ogg_flow_20260916/success_comparison.svg)。旧代码、旧权重和旧封存产物保留。", "",
        "CPU审计与报告复现：", "", "```bash",
        "cd /mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP",
        "export CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2",
        "export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src MPLCONFIGDIR=/tmp/ogg_flow_mpl XDG_CACHE_HOME=/tmp/ogg_flow_report_cache",
        "/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python -m ac_tmil.ogg_flow.evaluation evaluate",
        "/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python -m ac_tmil.ogg_flow.report",
        "```", "",
        "GPU新采集须先按冻结配置生成wave spec，再统一经生命周期脚本执行；已有完整case会跳过，但不要将本轮已曝光源重跑称为新验证：", "", "```bash",
        "bash scripts/run_recap_ogg_flow.sh common launch --stage development",
        "/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_lifecycle.sh run -- /usr/bin/python scripts/run_recap_gpu_wave.py --spec /ABSOLUTE/PATH/PRINTED_BY_LAUNCH.json",
        "/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_lifecycle.sh status",
        "```", "",
        "正式波次期间所有占卡holder均停算，波次完成或失败后由guard恢复；最终运行状态以交付审计的GPU恢复记录为准。", "",
    ])
    return "\n".join(lines)


def main():
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/ogg_flow_mpl")
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/ogg_flow_report_cache")
    result = json.loads((ROOT / "evaluation.json").read_text())
    cfg = read(ROOT / "config.json")
    frozen = read(ROOT / "formal_freeze.json")
    preflight = json.loads((ROOT / "audits/preflight.json").read_text())
    assert result["status"] == "complete" and result["stage"] == "development"
    assert result["config_sha256"] == file_sha256(ROOT / "config.json")
    assert result["formal_freeze_sha256"] == file_sha256(ROOT / "formal_freeze.json")
    assert result["audit"]["status"] == preflight["status"] == "passed"
    DOC.mkdir(parents=True, exist_ok=True)
    fig = figure(result)
    fig.savefig(DOC / "success_comparison.png", dpi=180)
    fig.savefig(DOC / "success_comparison.svg")
    import matplotlib.pyplot as plt
    plt.close(fig)
    output = REPO / "ACT_RECAP_FLOW_GUIDANCE_RESULTS_20260916.md"
    output.write_text(render(result, cfg, preflight, frozen))
    print(json.dumps(dict(report=str(output), figure=str(DOC / "success_comparison.png"),
                         planned_sources=result["planned_sources"], independent_validation_success=False)), flush=True)


if __name__ == "__main__":
    main()
