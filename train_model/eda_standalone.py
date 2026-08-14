"""
EDA Cells - Standalone (no model, no dependencies, no emoji crash)
================================================================
3 hàm:
  - list_kaggle_checkpoints(output_root)   : Scan cấu trúc checkpoint
  - build_adapter_dict(sorted_ckpts)        : Build {agent: path}
  - eda_training_loss(history_json_path)    : Plot training loss

Tất cả:
  - KHÔNG load model
  - KHÔNG cần GPU
  - KHÔNG pip install thêm (chỉ cần os, json, numpy, matplotlib)
  - KHÔNG import từ file khác → không bị crash do setup_environment()
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend (no plt.show() block)
import matplotlib.pyplot as plt
plt.ion()  # Enable interactive mode off


# ════════════════════════════════════════════════════════════════
# CELL 0A: list_kaggle_checkpoints
# ════════════════════════════════════════════════════════════════

def list_kaggle_checkpoints(output_root):
    """
    Liệt kê cấu trúc checkpoint dưới `output_root/<agent_id>/<ckpt_name>/`.
    Trả về dict {agent_id: [(ckpt_basename, ckpt_full_path), ...]}.
    KHÔNG load model, KHÔNG filter theo adapter_config — chỉ in ra hết.
    """
    print("\n" + "=" * 70)
    print("  SCAN: " + str(output_root))
    print("=" * 70)

    if not os.path.exists(output_root):
        print("  ERROR: Path not found: " + str(output_root))
        return {}

    # Step 1: top-level
    print("\n  [TOP-LEVEL]")
    try:
        top_entries = sorted(os.listdir(output_root))
    except Exception as e:
        print("  ERROR: Cannot listdir: " + str(e))
        return {}

    for entry in top_entries:
        full = os.path.join(output_root, entry)
        if os.path.isdir(full):
            try:
                n_sub = len(os.listdir(full))
                print("    [DIR]  " + entry + "/  (" + str(n_sub) + " entries)")
            except Exception:
                print("    [DIR]  " + entry + "/")
        else:
            size = os.path.getsize(full)
            print("    [FILE] " + entry + "  (" + str(size) + " bytes)")

    # Step 2: group per agent
    print("\n  [PER-AGENT]")
    agents_found = {}
    for entry in top_entries:
        full = os.path.join(output_root, entry)
        if not os.path.isdir(full):
            continue

        entry_lower = entry.lower()
        matched_agent = None
        for aid in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
            if aid in entry_lower:
                matched_agent = aid
                break

        if matched_agent is None:
            print("    SKIP (not agent folder): " + entry + "/")
            continue

        # List sub-checkpoints
        ckpts = []
        try:
            for sub in sorted(os.listdir(full)):
                sub_full = os.path.join(full, sub)
                if os.path.isdir(sub_full):
                    try:
                        sub_files = sorted(os.listdir(sub_full))
                    except Exception:
                        sub_files = []
                    ckpts.append((sub, sub_full, sub_files))
        except Exception as e:
            print("    ERROR: Cannot listdir " + full + ": " + str(e))

        agents_found[matched_agent] = ckpts
        print("    " + matched_agent + ": " + str(len(ckpts)) + " sub-folder(s)")
        for i, (bn, bfull, bfiles) in enumerate(ckpts):
            has_adapter = "adapter_config.json" in bfiles
            has_weights = any(f.endswith((".safetensors", ".bin")) for f in bfiles)
            flag = "[OK]" if (has_adapter and has_weights) else "[!!]"
            print("       " + str(i+1) + ". " + flag + " " + bn + "/  "
                  + "[adapter=" + ("Y" if has_adapter else "N")
                  + ", weights=" + ("Y" if has_weights else "N")
                  + ", files=" + str(len(bfiles)) + "]")

    # Step 3: sort by priority (final > checkpoint-N highest)
    print("\n  [SORTED - final > highest checkpoint-N]")
    sorted_out = {}
    for aid in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
        if aid not in agents_found:
            sorted_out[aid] = []
            continue

        def _key(item):
            bn = item[0]
            if bn == "final":
                return (0, 0)
            try:
                n = int(bn.split("-")[-1])
                return (1, -n)
            except Exception:
                return (2, 0)

        ckpts_sorted = sorted(agents_found[aid], key=_key)
        sorted_out[aid] = [(bn, bfull) for bn, bfull, _ in ckpts_sorted]

        print("    " + aid + ":")
        for i, item in enumerate(ckpts_sorted):
            bn = item[0]
            star = " [BEST]" if i == 0 else ""
            print("       " + str(i+1) + ". " + bn + star)

    # Step 4: summary
    print("\n  [SUMMARY]")
    total_ckpt = sum(len(v) for v in sorted_out.values())
    n_agents_with_ckpt = sum(1 for v in sorted_out.values() if v)
    print("    Total: " + str(total_ckpt) + " checkpoint(s) across "
          + str(n_agents_with_ckpt) + " agent(s)")

    multi = [a for a, v in sorted_out.items() if len(v) > 1]
    if multi:
        print("    Agents with multiple checkpoints: " + ", ".join(multi))
        print("    -> Can probe each to pick the best")
    elif n_agents_with_ckpt > 0:
        print("    Each agent has only 1 checkpoint -> use it directly")

    print("\n" + "=" * 70)
    return sorted_out


def build_adapter_dict(sorted_ckpts, agent_ids=None):
    """
    Từ output của list_kaggle_checkpoints() → dict {agent_id: ckpt_path}
    cho auto_pick_best_checkpoints() và pipeline inference.
    """
    if agent_ids is None:
        agent_ids = ["agent1", "agent2", "agent3", "agent4", "agent5"]

    print("\n  [BUILD ADAPTER DICT]")
    print("  " + "-" * 70)

    out = {}
    for aid in agent_ids:
        ckpts = sorted_ckpts.get(aid, [])
        if not ckpts:
            print("    [WARN] " + aid + ": no checkpoint")
            continue
        bn, full = ckpts[0]
        out[aid] = full
        print("    " + aid + " -> " + bn)
        print("        path: " + full)

    print("  " + "-" * 70)
    return out


# ════════════════════════════════════════════════════════════════
# CELL 0B: eda_training_loss
# ════════════════════════════════════════════════════════════════

def eda_training_loss(history_json_path, plots_dir="plots"):
    """
    Phân tích training_history.json từ Kaggle training pipeline.
    Vẽ 2 chart: overview + per-agent.
    """
    print("\n" + "=" * 70)
    print("  TRAINING LOSS ANALYSIS")
    print("=" * 70)

    if not os.path.exists(history_json_path):
        print("  ERROR: File not found: " + str(history_json_path))
        return None

    with open(history_json_path) as f:
        history = json.load(f)

    os.makedirs(plots_dir, exist_ok=True)

    agents = sorted(history.keys())
    if not agents:
        print("  ERROR: history.json is empty or wrong format")
        return None

    # Summary table
    print("\n  " + "Agent".ljust(10) + "Final Train".rjust(15)
          + "Final Eval".rjust(15) + "Best Train".rjust(15)
          + "Best Eval".rjust(15) + "Steps".rjust(8))
    print("  " + "-" * 80)

    summary_rows = []
    for aid in agents:
        h = history[aid]
        train_losses = h.get("train_loss", [])
        eval_losses  = h.get("eval_loss", [])
        final_train  = train_losses[-1] if train_losses else None
        final_eval   = eval_losses[-1]  if eval_losses  else None
        best_train   = min(train_losses) if train_losses else None
        best_eval    = min(eval_losses)  if eval_losses  else None
        steps        = len(train_losses)

        summary_rows.append({
            "agent": aid,
            "final_train": final_train,
            "final_eval": final_eval,
            "best_train": best_train,
            "best_eval": best_eval,
            "steps": steps,
            "train_loss_list": train_losses,
            "eval_loss_list": eval_losses,
        })

        ft_s = ("{:.6f}".format(final_train) if final_train is not None else "N/A")
        fe_s = ("{:.6f}".format(final_eval)  if final_eval  is not None else "N/A")
        bt_s = ("{:.6f}".format(best_train)  if best_train  is not None else "N/A")
        be_s = ("{:.6f}".format(best_eval)   if best_eval    is not None else "N/A")
        print("  " + aid.ljust(10) + ft_s.rjust(15) + fe_s.rjust(15)
              + bt_s.rjust(15) + be_s.rjust(15) + str(steps).rjust(8))

    # Diagnosis
    print("\n  " + "-" * 80)
    print("  DIAGNOSIS:")
    print("  " + "-" * 80)

    for row in summary_rows:
        aid   = row["agent"]
        tl    = row["train_loss_list"]
        el    = row["eval_loss_list"]

        issues = []
        if len(tl) < 3:
            issues.append("Too few steps (<3) — training too short")
        elif tl:
            first_10 = tl[:min(10, len(tl))]
            last_10  = tl[-min(10, len(tl)):]
            if np.mean(last_10) >= np.mean(first_10) * 1.05:
                issues.append("Loss NOT decreasing (overfitting or divergence)")
            if len(tl) > 5:
                diffs = [abs(tl[i+1]-tl[i]) for i in range(len(tl)-1)]
                if np.mean(diffs) > 0.5:
                    issues.append("Loss oscillating strongly (avg_delta="
                                  + "{:.3f}".format(np.mean(diffs)) + ")")
            if el and tl:
                if el[-1] > tl[-1] * 2:
                    issues.append("Eval >> Train (clear overfitting)")
            if len(el) > 3:
                if el[-1] > el[0]:
                    issues.append("Eval loss increasing (overfitting)")
            if tl and tl[-1] > 3.0:
                issues.append("Final train loss HIGH ("
                              + "{:.2f}".format(tl[-1])
                              + ") — model didn't learn")
            if tl and tl[-1] < 0.1:
                issues.append("Final train loss VERY LOW ("
                              + "{:.4f}".format(tl[-1])
                              + ") — possible complete overfit")

        if issues:
            print("\n  [" + aid + "]")
            for iss in issues:
                print("     - " + iss)
        else:
            print("  [" + aid + "] Loss decreasing steadily, no major overfitting")

    # Plot 1: overview (train + eval all agents)
    n_agents = len(agents)
    colors = plt.cm.tab10(np.linspace(0, 1, max(n_agents, 1)))

    fig1, axes1 = plt.subplots(1, 2, figsize=(14, 5))
    fig1.suptitle("Training Loss - Overview (all agents)",
                  fontsize=14, fontweight="bold")

    ax = axes1[0]
    for i, aid in enumerate(agents):
        tl = summary_rows[i]["train_loss_list"]
        if tl:
            steps_ = range(1, len(tl)+1)
            ax.plot(steps_, tl, label=aid, color=colors[i], linewidth=1.5)
    ax.set_xlabel("Step")
    ax.set_ylabel("Train Loss")
    ax.set_title("Train Loss - All Agents")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    ax = axes1[1]
    has_eval = False
    for i, aid in enumerate(agents):
        el = summary_rows[i]["eval_loss_list"]
        if el:
            has_eval = True
            steps_ = range(1, len(el)+1)
            ax.plot(steps_, el, label=aid, color=colors[i],
                    linewidth=1.5, marker="o", markersize=3)
    if has_eval:
        ax.set_xlabel("Eval Step")
        ax.set_ylabel("Eval Loss")
        ax.set_title("Eval Loss - All Agents")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
    else:
        ax.text(0.5, 0.5, "No eval loss\nin history.json",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Eval Loss - (no data)")

    fig1.tight_layout()
    fig1_path = os.path.join(plots_dir, "05a_overview_loss.png")
    fig1.savefig(fig1_path, bbox_inches="tight", facecolor="white")
    plt.close(fig1)

    # Plot 2: per-agent grid (n_rows x 2 cols, max n_agents slots)
    n_rows = (n_agents + 1) // 2
    fig2, axes2 = plt.subplots(n_rows, 2, figsize=(14, 4 * n_rows))
    fig2.suptitle("Per-Agent Loss Curves (train + eval)",
                  fontsize=14, fontweight="bold")

    if n_rows == 1:
        axes_flat = [axes2[0], axes2[1]]
    else:
        axes_flat = list(axes2.flat)

    n_slots = len(axes_flat)
    for idx in range(n_slots):
        ax = axes_flat[idx]
        if idx < n_agents:
            aid = agents[idx]
            tl = summary_rows[idx]["train_loss_list"]
            el = summary_rows[idx]["eval_loss_list"]
            c  = colors[idx]

            if tl:
                ax.plot(range(1, len(tl)+1), tl, label="train",
                        color=c, linewidth=1.2)
            if el:
                ax.plot(range(1, len(el)+1), el, label="eval",
                        color=c, linewidth=1.2, linestyle="--",
                        marker="o", markersize=2)
            ax.set_title(aid, fontsize=11, fontweight="bold")
            ax.set_xlabel("Step")
            ax.set_ylabel("Loss")
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)

            if tl:
                ax.axhline(tl[-1], color=c, linestyle=":", alpha=0.4)
                ax.text(0.02, 0.05, "final train: " + "{:.4f}".format(tl[-1]),
                        transform=ax.transAxes, fontsize=8,
                        bbox=dict(boxstyle="round,pad=0.3",
                                  facecolor="white", alpha=0.8))
        else:
            ax.set_visible(False)

    fig2.tight_layout()
    fig2_path = os.path.join(plots_dir, "05b_per_agent_loss.png")
    fig2.savefig(fig2_path, bbox_inches="tight", facecolor="white")
    plt.close(fig2)
    print("  Saved: " + fig2_path)

    # Ranking
    print("\n  " + "-" * 80)
    print("  RANKING by Final Eval Loss (lower = better):")
    print("  " + "-" * 80)
    ranked = [(r["agent"], r["final_eval"], r["best_eval"])
              for r in summary_rows if r["final_eval"] is not None]
    ranked.sort(key=lambda x: x[1])
    if ranked:
        for rank, (aid, fe, be) in enumerate(ranked, 1):
            delta = ((fe - be) / be * 100) if be else 0
            print("     " + str(rank) + ". " + aid.ljust(10)
                  + " final=" + "{:.6f}".format(fe)
                  + "  best=" + "{:.6f}".format(be)
                  + "  (+" + "{:.1f}".format(delta) + "% gap)")
    else:
        print("     (No eval loss — ranking by train loss only)")
        ranked_train = [(r["agent"], r["final_train"])
                        for r in summary_rows if r["final_train"] is not None]
        ranked_train.sort(key=lambda x: x[1])
        for rank, (aid, ft) in enumerate(ranked_train, 1):
            print("     " + str(rank) + ". " + aid.ljust(10)
                  + " final_train=" + "{:.6f}".format(ft))

    print("\n" + "=" * 70)
    return summary_rows