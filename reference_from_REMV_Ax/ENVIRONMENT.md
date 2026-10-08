# ENVIRONMENT

Recorded without personal/private paths; use `<PROJECT_ROOT>` for the project
location.

| item | value |
|---|---|
| OS | Windows 11 |
| Python | 3.14.5 (`<PROJECT_ROOT>/.venv`; stdlib only — no numpy/matplotlib required for tables) |
| CPU / RAM | 32 cores (WSL), 7.6 GiB RAM (WSL) |
| WSL | Ubuntu 26.04.1 (WSL2), user-space only (no sudo used) |
| Compiler | g++ 15.2.0 (WSL) |
| Ganak | official v2.7.0 binary (repo HEAD e8f5184) |
| d4 | official crillab/d4 commit 333370cc1e843dd0749c1efe88516e72b5239174 |
| Yosys | 0.52 (git sha1 fee39a3284c90249e1d9684cf6944ffbbcbb8f90) |
| VACSEM | commit b11ede7 |
| EvoApproxLib | commit ec28be83bfce1b8e8b92bd456be520d323a568b5 |
| Boost | 1.85 (headers, local) |
| GMP / zlib | official Ubuntu 26.04 debs, extracted locally (no sudo) |
| Timeout | 180 s per single compile / exact probe (never changed during the campaign) |
| K values | 16, 64 |
| Random seed | 42 (one frozen stream per PI width) |
| Probability pool | {1/8, 1/4, 1/2, 3/4, 7/8} |
| Experiment date | 2026-10-03 (manifest+pre-freeze) / 2026-10-04 (packaging) |
| Project root | `<PROJECT_ROOT>` (originally D:\paper_project_3) |
| Campaign version | C7_FORMAL_v1 |
| Manifest hash | 68051b9f8e18006a5b9cf97eedaa1c06b609f72033507e3e7fae1e890e2f4109 |

No credentials, tokens, SSH keys, or personal files are contained in this
bundle.
