#!/usr/bin/env python3
"""Render report figures directly from the checked-in experimental evidence.

Run from any directory with Python 3.10+ and requirements-figures.txt installed:
    python scripts/plot_results.py

Only docs/figures/ (or --output-dir) is written. The research evidence is read-only.
The companion plot-data.json records source hashes, extracted fields, and derived
values. Error bars are observed minima/maxima, not confidence intervals.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
BLUE = "#0072B2"
ORANGE = "#D55E00"
GRAY = "#70777D"
INK = "#202A35"
SOURCES: dict[str, dict] = {}


def read_json(relative: str):
    raw = (ROOT / relative).read_bytes()
    SOURCES[relative] = {"sha256": hashlib.sha256(raw).hexdigest()}
    return json.loads(raw)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def workflow_data():
    rows = []
    for jobs in range(2, 7):
        source = f"experiments/workflow/historical/n{jobs}-record-measurement.json"
        evidence = read_json(source)
        row = {
            "jobs": jobs,
            "source": source,
            "recording_date": "2026-09-11" if jobs == 6 else "2026-09-10",
            "date_source": "experiments/workflow/README.md",
            "full_rebuild_input_states": evidence["full_rebuild_input_states"],
            "reuse_rebuild_input_states": evidence["reuse_rebuild_input_states"],
            "full_record_path_product_visits": evidence["new_record_items"]["path_product_visits"],
            "reused_record_path_product_visits": evidence["recreated_record_path_product_visits"],
            "all_boundary_ports_checked": evidence["all_boundary_ports_checked"],
            "boundary_product_visits": evidence["boundary_product_visits"],
            "timing": {},
        }
        require(evidence["full_record_equality"], f"Record disagreement in {source}")
        require(all(evidence["three_guarantees"].values()), f"Guarantee failure in {source}")
        for method in ("full", "reuse"):
            samples = [sample["total_ms"] for sample in evidence["samples"][method]]
            require(len(samples) == 7, f"Expected seven timing samples in {source}")
            calculated = {"median": statistics.median(samples), "min": min(samples), "max": max(samples)}
            require(calculated == evidence["timing_summary"][method]["total_ms"],
                    f"Archived timing summary disagrees with raw samples in {source}")
            row["timing"][method] = {"unit": "ms", "samples": samples, **calculated}
        rows.append(row)
    context = ROOT / "experiments/workflow/README.md"
    SOURCES[str(context.relative_to(ROOT))] = {
        "sha256": hashlib.sha256(context.read_bytes()).hexdigest(),
        "purpose": "Recording-date and measurement-scope context; numerical values come from JSON.",
    }
    return rows


def http_data():
    base = "experiments/async-interface-contracts/evidence/http-20260908"
    records = read_json(f"{base}/results.json")
    summary = read_json(f"{base}/summary.json")
    rows = []
    for policy in ("release_on_terminal", "release_on_2xx", "confirm_status"):
        conditions = [row for row in records if row["policy"] == policy]
        counts = Counter()
        for row in conditions:
            if row["status"] == "complete":
                counts["complete_with_forbidden_overlap" if row["unsafe"]
                       else "complete_without_forbidden_overlap"] += 1
            elif row["status"] == "stalled" and not row["unsafe"]:
                counts["stalled_without_forbidden_overlap"] += 1
            else:
                raise ValueError(f"Unrepresented HTTP outcome for {policy}: {row['status']}")
        require(len(conditions) == summary["inputs"] == 36, f"Unexpected HTTP condition count for {policy}")
        require(len({row["input"] for row in conditions}) == 36, f"Duplicate HTTP input for {policy}")
        require(sum(counts.values()) == 36, f"Outcome categories do not partition {policy}")
        unsafe = sum(bool(row["unsafe"]) for row in conditions)
        complete = sum(row["status"] == "complete" for row in conditions)
        stalled = sum(row["status"] == "stalled" for row in conditions)
        retained = sum(row["heldAtEnd"] > 0 for row in conditions)
        complete_nonoverlapping_retained = sum(
            row["status"] == "complete" and not row["unsafe"] and row["heldAtEnd"] > 0
            for row in conditions
        )
        for key, value in (("unsafe", unsafe), ("complete", complete), ("stalled", stalled),
                           ("retainedReservations", retained)):
            require(summary["policies"][policy][key] == value, f"HTTP summary mismatch: {policy}/{key}")
        rows.append({"policy": policy, "conditions": len(conditions),
                     **{key: counts[key] for key in ("complete_without_forbidden_overlap",
                                                    "complete_with_forbidden_overlap",
                                                    "stalled_without_forbidden_overlap")},
                     "conditions_with_retained_reservations": retained,
                     "complete_nonoverlapping_conditions_with_retained_reservations": complete_nonoverlapping_retained})
    require(sum(row["conditions"] for row in rows) == summary["conditions"] == 108,
            "Expected 108 historical HTTP conditions")
    return rows


def search_data():
    source = "results/record_policy_search_results.json"
    evidence = read_json(source)
    totals = evidence["totals"]
    require(totals["distinct_final_records"] == totals["independently_checked_representatives"],
            "Not all final record representatives were independently checked")
    require(totals["exhaustive_global_policies"] == evidence["cases"] * 64,
            "Unexpected bounded-policy count")
    return {"source": source, "games": evidence["cases"], "totals": totals,
            "derived_final_compositions": totals["record_compositions"] - totals["first_compositions"],
            "derived_final_compositions_formula": "record_compositions - first_compositions",
            "interpretation": "Different object counts; not execution times or search-work ratios."}


def style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11,
        "axes.labelsize": 11, "axes.titlesize": 12, "axes.titleweight": "bold",
        "axes.edgecolor": "#808890", "axes.labelcolor": INK,
        "text.color": INK, "xtick.color": INK, "ytick.color": INK,
        "axes.spines.top": False, "axes.spines.right": False,
        "figure.facecolor": "white", "axes.facecolor": "white",
        "legend.frameon": False, "legend.fontsize": 11,
        "svg.fonttype": "none", "svg.hashsalt": "progress-certificate-reuse",
        "savefig.facecolor": "white", "lines.linewidth": 2,
    })


def prepare_axis(ax):
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#E3E7EA", linewidth=0.8)
    ax.tick_params(length=3)


def save(fig, output, name):
    for suffix in ("png", "svg"):
        metadata = {"Creator": "scripts/plot_results.py"}
        if suffix == "svg":
            metadata["Date"] = None
        fig.savefig(output / f"{name}.{suffix}", dpi=180, metadata=metadata)
        if suffix == "svg":
            path = output / f"{name}.{suffix}"
            path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    plt.close(fig)


def workflow_workload(rows, output):
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 6.0))
    fig.subplots_adjust(left=0.08, right=0.97, bottom=0.23, top=0.78, wspace=0.26)
    fig.suptitle("Workflow: record reconstruction workload", x=0.08, y=0.965,
                 ha="left", fontsize=17, fontweight="bold")
    fig.text(0.08, 0.895, "The changed second stage stays small as concurrent first-stage work grows.", fontsize=11)
    jobs = [row["jobs"] for row in rows]
    specifications = [
        ("A  States read for reconstruction", "Input states (log scale)",
         "full_rebuild_input_states", "reuse_rebuild_input_states", [5, 10, 50, 100, 500, 1000]),
        ("B  Visits while constructing records", "Path-product visits (log scale)",
         "full_record_path_product_visits", "reused_record_path_product_visits", [10, 50, 100, 500, 1000, 2000]),
    ]
    for ax, (title, ylabel, full, reuse, ticks) in zip(axes, specifications):
        prepare_axis(ax)
        ax.set_title(title, loc="left", pad=13)
        for field, color, marker, linestyle, label in (
            (full, BLUE, "s", "-", "Rebuild all records"),
            (reuse, ORANGE, "o", "--", "Rebuild changed-stage record"),
        ):
            values = [row[field] for row in rows]
            ax.plot(jobs, values, color=color, marker=marker, linestyle=linestyle, label=label, markersize=6)
            for job, value in zip(jobs, values):
                ax.annotate(f"{value:,}", (job, value), xytext=(0, 10 if field == full else -17),
                            textcoords="offset points", ha="center", fontsize=11, color=color)
        ax.set_yscale("log")
        ax.set_ylim(ticks[0] * 0.45, ticks[-1] * 1.4)
        ax.yaxis.set_major_locator(FixedLocator(ticks))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
        ax.minorticks_off()
        ax.set_xticks(jobs)
        ax.set_xlabel("Concurrent first-stage jobs")
        ax.set_ylabel(ylabel)
        ax.set_xlim(1.7, 6.3)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower left", bbox_to_anchor=(0.065, 0.103), ncol=2)
    ports = sorted({row["all_boundary_ports_checked"] for row in rows})
    visits = sorted({row["boundary_product_visits"] for row in rows})
    require(len(ports) == len(visits) == 1, "Boundary-work annotation needs updating")
    fig.text(0.08, 0.055, f"Both methods still check all {ports[0]} boundary ports ({visits[0]} boundary-product visits per configuration).", fontsize=11)
    fig.text(0.08, 0.018, "Source: historical/n2–n6-record-measurement.json. State and visit counts are distinct measures, not timings.", fontsize=11, color=GRAY)
    save(fig, output, "workflow-workload")


def workflow_time(rows, output):
    fig, ax = plt.subplots(figsize=(11.8, 6.7))
    fig.subplots_adjust(left=0.10, right=0.95, bottom=0.29, top=0.78)
    fig.suptitle("Workflow: record processing time after model construction", x=0.08, y=0.965,
                 ha="left", fontsize=16, fontweight="bold")
    fig.text(0.08, 0.895, "Known changed stage; reconstruction + boundary check. Median and observed min–max over 7 repetitions.", fontsize=11)
    prepare_axis(ax)
    jobs = [row["jobs"] for row in rows]
    for method, color, marker, linestyle, label in (
        ("full", BLUE, "s", "-", "Rebuild all records + boundary check"),
        ("reuse", ORANGE, "o", "--", "Rebuild changed-stage record + boundary check"),
    ):
        medians = [row["timing"][method]["median"] for row in rows]
        low = [row["timing"][method]["median"] - row["timing"][method]["min"] for row in rows]
        high = [row["timing"][method]["max"] - row["timing"][method]["median"] for row in rows]
        ax.errorbar(jobs, medians, yerr=[low, high], color=color, marker=marker,
                    linestyle=linestyle, label=label, capsize=5, markersize=7, elinewidth=1.5)
        for job, value in zip(jobs, medians):
            ax.annotate(f"{value:.3f}", (job, value), xytext=(0, 14 if method == "full" else -22),
                        textcoords="offset points", ha="center", color=color, fontsize=11)
    ax.set_yscale("log")
    ax.set_ylim(0.043, 85)
    ax.yaxis.set_major_locator(FixedLocator([0.1, 0.3, 1, 3, 10, 30]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
    ax.minorticks_off()
    ax.set_xlim(1.65, 6.35)
    ax.set_xticks(jobs, [f"{row['jobs']}\nSep {row['recording_date'][-2:]}" for row in rows])
    ax.set_xlabel("Concurrent first-stage jobs / recording date (2026)")
    ax.set_ylabel("Reconstruction + boundary check (ms, log scale)")
    ax.legend(loc="upper left", fontsize=11)
    fig.text(0.08, 0.14, "Error bars show the observed range, not confidence intervals. The six-job run was recorded on a different day.", fontsize=11)
    fig.text(0.08, 0.093, "Excludes model/old-record construction, offline reuse validation, migration, search, and full-graph checks.", fontsize=11)
    fig.text(0.08, 0.048, "This measures record processing only; it does not establish end-to-end update speedup.", fontsize=11)
    fig.text(0.08, 0.012, "Source: historical/n2–n6-record-measurement.json, samples.{full,reuse}[].total_ms.", fontsize=11, color=GRAY)
    save(fig, output, "workflow-record-time")


def http_outcomes(rows, output):
    fig, ax = plt.subplots(figsize=(11.8, 6.5))
    fig.subplots_adjust(left=0.25, right=0.95, bottom=0.34, top=0.77)
    fig.suptitle("HTTP experiment: completion and forbidden overlap", x=0.08, y=0.965,
                 ha="left", fontsize=17, fontweight="bold")
    fig.text(0.08, 0.895, "36 artificial inputs per policy; the three outcome categories below are mutually exclusive.", fontsize=11)
    labels = ["Release on any\nHTTP terminal event", "Release on\nHTTP 2xx only", "Release after confirmed\noperation completion"]
    left = [0, 0, 0]
    definitions = (
        ("complete_without_forbidden_overlap", "Complete, no forbidden overlap", BLUE, ""),
        ("complete_with_forbidden_overlap", "Complete, forbidden overlap", ORANGE, "///"),
        ("stalled_without_forbidden_overlap", "Stalled, no forbidden overlap", GRAY, ".."),
    )
    for field, label, color, hatch in definitions:
        values = [row[field] for row in rows]
        ax.barh(range(3), values, left=left, color=color, hatch=hatch, edgecolor="white",
                linewidth=1.2, height=0.63, label=label)
        for index, value in enumerate(values):
            if value:
                ax.text(left[index] + value / 2, index, str(value), ha="center", va="center",
                        color="white", fontsize=13, fontweight="bold")
        left = [start + value for start, value in zip(left, values)]
    ax.set_yticks(range(3), labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 36)
    ax.set_xticks([0, 9, 18, 27, 36])
    ax.set_xlabel("Conditions (36 per policy)")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=10)
    fig.legend(*ax.get_legend_handles_labels(), loc="lower left", bbox_to_anchor=(0.065, 0.185), ncol=1, fontsize=11)
    fig.text(0.08, 0.123, "Complete: every job ended. Forbidden overlap: at least one prohibited pair was active simultaneously.", fontsize=11)
    retained_2xx = next(row for row in rows if row["policy"] == "release_on_2xx")["complete_nonoverlapping_conditions_with_retained_reservations"]
    fig.text(0.08, 0.077, f"Completion need not release every reservation: {retained_2xx} complete, non-overlapping 2xx-only conditions retain reservations.", fontsize=11)
    fig.text(0.08, 0.034, "Historical mock-server run, 2026-09-08. These are observed outcomes, not performance claims for arbitrary flows.", fontsize=11, color=GRAY)
    fig.text(0.08, 0.005, "Source: evidence/http-20260908/results.json; categories derived from each condition's status and unsafe fields.", fontsize=11, color=GRAY)
    save(fig, output, "http-outcomes")


def bounded_search(data, output):
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 6.2))
    fig.subplots_adjust(left=0.08, right=0.97, bottom=0.32, top=0.78, wspace=0.30)
    fig.suptitle("Bounded policy search: candidates and distinct records", x=0.08, y=0.965,
                 ha="left", fontsize=17, fontweight="bold")
    fig.text(0.08, 0.895, f"Aggregate counts across {data['games']} generated games with six binary memoryless choices per game.", fontsize=11)
    totals = data["totals"]
    panels = (
        ("A  First-stage composition (A + B)",
         ["Record-pair composition\noperations", "Distinct intermediate\nrecord pairs"],
         [totals["first_compositions"], totals["distinct_intermediate_records"]]),
        ("B  Complete policies and final records",
         ["Complete policies\n(reference enumeration)", "Distinct final\nrecord pairs"],
         [totals["exhaustive_global_policies"], totals["distinct_final_records"]]),
    )
    for ax, (title, labels, values) in zip(axes, panels):
        prepare_axis(ax)
        ax.set_title(title, loc="left", pad=13)
        bars = ax.bar([0, 1], values, color=[BLUE, ORANGE], width=0.55, edgecolor="white")
        bars[1].set_hatch("///")
        ax.set_xticks([0, 1], labels)
        ax.set_ylim(0, max(values) * 1.25)
        ax.set_ylabel("Count (object type shown under each bar)")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
        ax.bar_label(bars, labels=[f"{value:,}" for value in values], padding=7, fontsize=12, fontweight="bold")
    fig.text(0.08, 0.17, f"{totals['initial_local_candidates']:,} local candidates; {totals['record_compositions']:,} record-pair compositions in total; all {totals['distinct_final_records']:,} final representatives independently checked.", fontsize=11)
    fig.text(0.08, 0.119, f"Intermediate merging occurred in {totals['instances_with_intermediate_merging']} of {data['games']} games. Counts are aggregated within games, not deduplicated across games.", fontsize=11)
    fig.text(0.08, 0.068, "Bars count different objects. These are not timings or search-work ratios; the panels use different vertical ranges.", fontsize=11)
    fig.text(0.08, 0.022, "Source: results/record_policy_search_results.json, totals. No comparison with external synthesis tools is shown.", fontsize=11, color=GRAY)
    save(fig, output, "bounded-search-counts")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/figures")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    workflow = workflow_data()
    http = http_data()
    search = search_data()
    style()
    workflow_workload(workflow, output)
    workflow_time(workflow, output)
    http_outcomes(http, output)
    bounded_search(search, output)
    data = {
        "generator": "scripts/plot_results.py",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "matplotlib_version": matplotlib.__version__,
        "sources": SOURCES,
        "workflow": workflow,
        "workflow_timing_definition": "Seven observed samples of total_ms = record_ms + boundary_and_check_ms for a known changed stage; median and min/max recomputed from samples, checked against stored summaries. Excludes input reading, model and old-record construction, offline reuse validation, migration checks, candidate search, and the full-graph oracle. Not confidence intervals.",
        "http": http,
        "http_outcome_definitions": {
            "complete_without_forbidden_overlap": "status == complete and unsafe == false; reservations may remain",
            "complete_with_forbidden_overlap": "status == complete and unsafe == true",
            "stalled_without_forbidden_overlap": "status == stalled and unsafe == false",
            "conditions_with_retained_reservations": "count of conditions where heldAtEnd > 0, not count of held reservations",
        },
        "bounded_search": search,
    }
    (output / "plot-data.json").write_text(json.dumps(data, indent=2) + "\n")
    print(f"Wrote four PNG/SVG pairs and plot-data.json to {output}")
    print("Checked: raw timing samples against summaries; 108 HTTP conditions against summary; bounded-search totals.")


if __name__ == "__main__":
    main()
