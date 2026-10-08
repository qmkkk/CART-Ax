"""Clean-release table generation: case-level summary, supplementary tables,
and figures/plotting data, all derived ONLY from experiments/formal/ results.
No historical/legacy data is read.
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

F = Path("experiments/formal")


def wcsv(path, rows_, cols_):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols_)
        w.writeheader()
        w.writerows(rows_)


def load_rows():
    rows = {}
    with open(F / "formal_ledger.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rows[r["task_id"]] = r
    return rows


def res(tid):
    p = F / "results" / f"{tid}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main():
    m = json.load(open(F / "formal_manifest.json", encoding="utf-8"))
    rows = load_rows()
    er = list(csv.DictReader(open(F / "formal_er_results.csv", encoding="utf-8")))
    med = list(csv.DictReader(open(F / "formal_med_results.csv", encoding="utf-8")))
    tim = list(csv.DictReader(open(F / "formal_timing.csv", encoding="utf-8")))
    scal = list(csv.DictReader(open(F / "formal_scalability.csv", encoding="utf-8")))
    fail = list(csv.DictReader(open(F / "formal_failures.csv", encoding="utf-8")))

    er_by = defaultdict(list)
    med_by = defaultdict(list)
    tim_by = defaultdict(list)
    for r in er:
        er_by[r["case_id"]].append(r)
    for r in med:
        med_by[r["case_id"]].append(r)
    for r in tim:
        tim_by[r["case_id"]].append(r)

    # ---------------- case_level_summary.csv ----------------
    rows_out = []
    for c in m["cases"]:
        cid = c["case_id"]
        w = c["width"]

        def task(kind):
            return rows.get(f"width{w}__{cid}__{kind}", {})

        cer = task("compile_ER")
        cmed = task("compile_MED")
        ers = er_by.get(cid, [])
        meds = med_by.get(cid, [])
        tims = tim_by.get(cid, [])
        er_match = sum(1 for r in ers if r["match"] == "True")
        er_nf = sum(1 for r in ers if r["d4_nnf_missing"] == "True")
        med_ok = sum(1 for r in meds if r["total_match"] == "True")
        med_incomplete = sum(1 for r in meds if r["d4_total_complete"] == "False")
        ganak_ref = sum(1 for r in ers if r["ganak_value"] not in ("", "None"))
        t16 = next((r for r in tims if r["K"] == "16"), {})
        t64 = next((r for r in tims if r["K"] == "64"), {})
        cer_res = res(f"width{w}__{cid}__compile_ER")
        cer_time = cer_res.get("compile_wall_s") if cer_res else None
        nnf_er = cer_res.get("nnf_bytes") if cer_res else None
        cmed_res = res(f"width{w}__{cid}__compile_MED")
        cmed_time = None
        nnf_med = None
        if cmed_res and cmed_res.get("bits"):
            cmed_time = sum(float(b.get("compile_wall_s", 0) or 0)
                            for b in cmed_res["bits"].values())
            nnf_med = sum(int(b.get("nnf_bytes", 0) or 0)
                          for b in cmed_res["bits"].values()
                          if b.get("kind") == "compiled")
        tcount = sum(1 for r in rows.values()
                     if r["case_id"] == cid and r["status"] == "TIMEOUT")
        scount = sum(1 for r in rows.values()
                     if r["case_id"] == cid and r["status"] == "SKIPPED_DEPENDENCY")
        er_success = len(ers) > 0 and er_match == len(ers) and er_nf == 0
        med_success = len(meds) > 0 and med_ok == len(meds) and med_incomplete == 0
        er_cv = ("FULL" if er_success else ("PARTIAL" if len(ers) > 0 else "NO_D4"))
        med_cv = ("FULL" if med_success else
                  ("PARTIAL" if len(meds) > 0 and med_ok > 0 else "NONE"))
        rows_out.append({
            "width": w, "case_id": cid, "family": c["family"], "eligible": True,
            "compile_ER_status": cer.get("status", "NEW"),
            "compile_MED_status": cmed.get("status", "NEW"),
            "ER_cross_validation_status": er_cv,
            "MED_cross_validation_status": med_cv,
            "timing_status": "PASS" if (t16 or t64) else "NA",
            "ER_success": er_success, "MED_success": med_success,
            "ganak_reference_available": ganak_ref > 0,
            "compile_ER_time_s": round(float(cer_time), 3) if cer_time else None,
            "compile_MED_total_time_s": round(cmed_time, 2) if cmed_time else None,
            "NNF_ER_size_bytes": nnf_er,
            "NNF_MED_total_size_bytes": nnf_med,
            "K16_warm_s": t16.get("warm_s"), "K16_cold_s": t16.get("cold_s"),
            "K16_ganak_e2e_s": t16.get("ganak_e2e_s"),
            "K16_amortized": t16.get("amortized_cold"),
            "K64_warm_s": t64.get("warm_s"), "K64_cold_s": t64.get("cold_s"),
            "K64_ganak_e2e_s": t64.get("ganak_e2e_s"),
            "K64_amortized": t64.get("amortized_cold"),
            "timeout_count": tcount, "skipped_dependency_count": scount,
            "notes": ("256 supplementary stress probe" if w == 256 else ""),
        })
    cols = list(rows_out[0].keys())
    wcsv(F / "case_level_summary.csv", rows_out, cols)
    print("case_level_summary.csv:", len(rows_out), "rows")

    # ---------------- supplementary tables ----------------
    cc = []
    for r in rows_out:
        c = next(x for x in m["cases"] if x["case_id"] == r["case_id"])
        cc.append({**r, "selection_rule": c["selection_rule"],
                   "eligible_pool_size": c["eligible_pool_size"]})
    wcsv(F / "supplementary_complete_case_table.csv", cc, list(cc[0].keys()))

    ev = [{"width": r["width"], "case_id": r["case_id"],
           "ER_rows": len(er_by[r["case_id"]]),
           "ER_match": sum(1 for x in er_by[r["case_id"]] if x["match"] == "True"),
           "ER_d4_missing": sum(1 for x in er_by[r["case_id"]]
                                if x["d4_nnf_missing"] == "True"),
           "MED_rows": len(med_by[r["case_id"]]),
           "MED_total_match": sum(1 for x in med_by[r["case_id"]]
                                  if x["total_match"] == "True"),
           "MED_d4_incomplete": sum(1 for x in med_by[r["case_id"]]
                                    if x["d4_total_complete"] == "False")}
          for r in rows_out]
    wcsv(F / "supplementary_exactness_validation.csv", ev, list(ev[0].keys()))

    td = [{"width": r["width"], "case_id": r["case_id"],
           "task": r["task_id"].split("__")[-1], "elapsed_s": r["elapsed_s"]}
          for r in fail if r["status"] == "TIMEOUT"]
    wcsv(F / "supplementary_timeout_details.csv", td,
         ["width", "case_id", "task", "elapsed_s"])

    sk = [{"width": r["width"], "case_id": r["case_id"],
           "task": r["task_id"].split("__")[-1],
           "reason": "compile_MED timeout (180s)"}
          for tid, r in rows.items() if r["status"] == "SKIPPED_DEPENDENCY"]
    wcsv(F / "supplementary_skipped_dependency_details.csv", sk,
         ["width", "case_id", "task", "reason"])

    br = [{"width": r["width"], "case_id": r["case_id"],
           "compile_ER_status": r["compile_ER_status"],
           "compile_MED_status": r["compile_MED_status"],
           "ER_cross_validation_status": r["ER_cross_validation_status"],
           "supplementary_stress_probe": r["width"] == 256}
          for r in rows_out if r["width"] in (128, 192, 256)]
    wcsv(F / "supplementary_boundary_results.csv", br, list(br[0].keys()))

    rk = list(csv.DictReader(open(F / "formal_ranking.csv", encoding="utf-8")))
    neg = [{"type": "no_ranking_shift", "metric": r["metric"], "width": r["width"],
            "distribution": r["distribution"], "tau_b": r["kendall_tau_b_vs_D0"],
            "inversions": r["strict_inversions"]}
           for r in rk if r["strict_inversions"] == "0"]
    neg += [{"type": "timeout", "width": r["width"], "case_id": r["case_id"],
             "task": r["task_id"].split("__")[-1], "elapsed_s": r["elapsed_s"]}
            for r in fail]
    neg += [{"type": "skipped_dependency", "width": r["width"],
             "case_id": r["case_id"], "task": r["task_id"].split("__")[-1]}
            for tid, r in rows.items() if r["status"] == "SKIPPED_DEPENDENCY"]
    neg += [{"type": "never_amortized_cold_by_K64", "width": r["width"],
             "case_id": r["case_id"]}
            for r in rows_out if r["K64_amortized"] == "False"]
    _cols = sorted({k for r in neg for k in r})
    wcsv(F / "supplementary_negative_results.csv", neg, _cols)
    print("supplementary tables written")

    # ---------------- figures/plotting_data ----------------
    PD = F / "plotting_data"
    PD.mkdir(exist_ok=True)

    fr = [{"width": r["width"], "metric": r["metric"],
           "distribution": r["distribution"], "tau_b": r["kendall_tau_b_vs_D0"],
           "strict_inversions": r["strict_inversions"], "n_designs": r["n_designs"]}
          for r in rk]
    wcsv(PD / "fig_ranking.csv", fr, list(fr[0].keys()))

    be = list(csv.DictReader(open(F / "formal_break_even.csv", encoding="utf-8")))
    wcsv(PD / "fig_break_even.csv", be, list(be[0].keys()))

    agg = defaultdict(lambda: {"compiles": [], "nnf": []})
    for r in scal:
        if r["status"] == "PASS" and r["compile_wall_s"]:
            agg[r["width"]]["compiles"].append(float(r["compile_wall_s"]))
            agg[r["width"]]["nnf"].append(float(r["nnf_mb"]))
    fs = []
    for w in sorted(agg, key=int):
        c = sorted(agg[w]["compiles"])
        n = sorted(agg[w]["nnf"])
        fs.append({"width": w, "n_compiled": len(c),
                   "compile_med_s": statistics.median(c), "compile_max_s": c[-1],
                   "nnf_med_mb": statistics.median(n), "nnf_max_mb": n[-1],
                   "n_total": sum(1 for r in scal if int(r["width"]) == int(w))})
    wcsv(PD / "fig_scalability.csv", fs, list(fs[0].keys()))

    wcsv(PD / "fig_boundary_map.csv", br, list(br[0].keys()))

    es = [{"width": r["width"], "case_id": r["case_id"],
           "ER_rows": len(er_by[r["case_id"]]),
           "ER_match": sum(1 for x in er_by[r["case_id"]] if x["match"] == "True"),
           "MED_rows": len(med_by[r["case_id"]]),
           "MED_total_match": sum(1 for x in med_by[r["case_id"]]
                                  if x["total_match"] == "True")}
          for r in rows_out]
    wcsv(PD / "fig_exactness_summary.csv", es, list(es[0].keys()))
    print("plotting_data written")


if __name__ == "__main__":
    main()
