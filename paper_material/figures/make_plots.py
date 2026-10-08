"""C7 clean-bundle postprocessing/overview plots.
Reads only results/ in this bundle; invokes no solver.
Produces corrected CSV/text summaries plus vector PDF/SVG overview.
"""
from __future__ import annotations
import csv, statistics
from pathlib import Path
HERE = Path(__file__).resolve().parents[2]
RESULTS = HERE / "results"
OUT = HERE / "figures"
OUT.mkdir(exist_ok=True)

def read(name):
    with open(RESULTS / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def main():
    er=read("formal_er_results.csv"); med=read("formal_med_results.csv")
    byw={}
    for r in er:
        w=int(r["width"]); d=byw.setdefault(w,{"er":0,"er_m":0,"er_nf":0,"med":0,"med_m":0})
        d["er"]+=1; d["er_m"]+=r["match"]=="True"; d["er_nf"]+=r["d4_nnf_missing"]=="True"
    for r in med:
        w=int(r["width"]); d=byw.setdefault(w,{"er":0,"er_m":0,"er_nf":0,"med":0,"med_m":0})
        d["med"]+=1; d["med_m"]+=r["total_match"]=="True"
    lines=["width,ER_rows,ER_match,ER_d4_missing,MED_rows,MED_total_match"]
    for w in sorted(byw):
        d=byw[w]; lines.append(f"{w},{d['er']},{d['er_m']},{d['er_nf']},{d['med']},{d['med_m']}")
    (OUT/"summary_exactness_by_width.csv").write_text("\n".join(lines)+"\n",encoding="utf-8")

    rk=read("formal_ranking.csv")
    txt=["Ranking sensitivity vs D0 (corrected D0-D5; Kendall tau-b / strict inversions):",""]
    for metric in ("ER","MED"):
        txt.append(metric+":")
        for r in rk:
            if r["metric"]==metric and r["distribution"]!="D0" and int(r["strict_inversions"])>0:
                txt.append(f"  width {r['width']} {r['distribution']}: tau_b={r['kendall_tau_b_vs_D0']} inv={r['strict_inversions']}")
        txt.append("")
    (OUT/"summary_ranking_sensitivity.txt").write_text("\n".join(txt).rstrip()+"\n",encoding="utf-8")

    sc=read("formal_scalability.csv"); agg={}
    for r in sc:
        if r["status"]=="PASS" and r["compile_wall_s"]:
            agg.setdefault(int(r["width"]),[]).append(float(r["compile_wall_s"]))
    lines=["width,n_compiled,compile_med_s,compile_max_s"]
    for w in sorted(agg):
        v=agg[w]; lines.append(f"{w},{len(v)},{statistics.median(v):.2f},{max(v):.2f}")
    (OUT/"summary_scalability.csv").write_text("\n".join(lines)+"\n",encoding="utf-8")

    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    fig,ax=plt.subplots(1,2,figsize=(7.16,2.5))
    w=sorted(agg); ax[0].plot(w,[statistics.median(agg[x]) for x in w],"o-")
    ax[0].set_xscale("log",base=2); ax[0].set_yscale("log"); ax[0].set_xlabel("width (bits)"); ax[0].set_ylabel("fresh compile time (s)")
    ww=sorted(byw); ax[1].bar([str(x) for x in ww],[byw[x]["er_m"]/max(1,byw[x]["er"]) for x in ww])
    ax[1].set_xlabel("width (bits)"); ax[1].set_ylabel("ER exact-match fraction")
    fig.tight_layout(); fig.savefig(OUT/"fig_overview.pdf"); fig.savefig(OUT/"fig_overview.svg"); plt.close(fig)

if __name__=="__main__": main()
