# REPRODUCTION

Exact versions and commands used for the frozen C7 formal experiment.

## 1. Environment versions

| component | version |
|---|---|
| Python | 3.14.5 (Windows, project `.venv`; stdlib only) |
| WSL | Ubuntu 26.04.1 (WSL2), g++ 15.2.0 |
| Ganak | official v2.7.0 binary (repo HEAD e8f5184) |
| d4 | commit 333370cc1e843dd0749c1efe88516e72b5239174 (built from source) |
| Yosys | 0.52 (git sha1 fee39a3284c90249e1d9684cf6944ffbbcbb8f90) |
| VACSEM | commit b11ede7 (Circuit2Cnf built R5) |
| EvoApproxLib | commit ec28be83bfce1b8e8b92bd456be520d323a568b5 |

## 2. Environment setup (original machine, no sudo)

- Ganak binary: official v2.7.0 linux release in `<PROJECT_ROOT>/tools/cache/ganak_linux/`.
- d4 build (WSL): GMP/zlib headers+libs from official Ubuntu 26.04 .debs
  (`libgmp-dev`, `libgmpxx4ldbl`, `zlib1g-dev`) extracted via `dpkg -x` into
  `tools/cache/deps/aptroot`; boost 1.85 headers from `tools/cache/boost_1_85_0`:
  ```
  make -j32 CXX="g++ -std=c++17 -I<aptroot>/usr/include \
    -I<aptroot>/usr/include/x86_64-linux-gnu -I<boost>"
    LFLAGS="-L<aptroot>/usr/lib/x86_64-linux-gnu -lz -lgmpxx -lgmp patoh/libpatoh.a"
  ```
- Yosys: `yosys_0.52-2_amd64.deb` + `yosys-abc_0.52-2_amd64.deb` +
  `libtcl8.6_...amd64.deb` extracted into `tools/cache/deps/yosysroot`.
- The manifest generator (`src/c7_formal_manifest.py`) locates yosys at
  `<PROJECT_ROOT>/tools/cache/deps/yosysroot` by default; on other machines
  set the `YOSYS_ROOT` environment variable to the extracted yosys root.
- add12 exact/deviation Verilog converted with:
  ```
  LD_LIBRARY_PATH=<yosysroot>/usr/lib/x86_64-linux-gnu \
    <yosysroot>/usr/bin/yosys -p "read_verilog f.v; synth -top <top>; write_blif f.blif"
  ```

## 3. Exact solver invocations

- Ganak exact projected WMC (reference):
  ```
  ./ganak_linux/ganak --mode 1 --prob 0 <file>.wmc
  ```
- d4 d-DNNF compile (frozen backend):
  ```
  ./d4 -dDNNF <input.cnf> -out=<output.nnf>
  ```
- VACSEM ER miter:
  ```
  ./Circuit2Cnf/build/core/Circuit2Cnf.out -t ER -e <exact.blif> -a <approx.blif> -o <out>.cnf
  ```
- VACSEM MED miter (per-bit set generated from a base name):
  ```
  ./Circuit2Cnf/build/core/Circuit2Cnf.out -t MED -e <exact.blif> -a <approx.blif> \
    -d <width_N_absolute_error.blif> -o <out>_med.cnf
  ```

## 4. Formal run / resume / tables (from this repository root)

```
python src/c7_formal_manifest.py               # (one-time manifest)
python src/c7_formal_campaign.py               # formal run (auto-resume)
python src/c7_formal_campaign.py --resume      # resume
python src/c7_formal_campaign.py --rollup      # rollup CSVs
python src/c7_clean_tables.py                  # case/supplementary/fig data
```

(The original machine invoked the same scripts as
`.venv\Scripts\python.exe src\python\<name>.py`; the code is layout-independent
as long as the script directory is on `sys.path`.)

## 5. Pre-freeze verification scripts (frozen)

```
python src/c5_ground_truth.py    # exhaustive == Ganak (10 small circuits, corrected D0-D5)
python src/c5_ranking.py         # family-wise Kendall tau-b
python src/c7_pre_freeze_regression.py
python src/c7_med_backend_probe.py
python src/c7_pre_freeze_timing.py
```

## 6. Plotting (no solvers)

```
python figures/plotting_scripts/make_plots.py
```

Reads only `results/` + `figures/plotting_data/` inside this repository.

## 7. Table generation

All paper tables are in `results/` (formal_*.csv, case_level_summary.csv) and
`supplementary/`. They are regenerable from the raw per-task results via
`c7_formal_campaign.py --rollup` and `c7_clean_tables.py`.
