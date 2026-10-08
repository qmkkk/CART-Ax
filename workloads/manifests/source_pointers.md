# Benchmark Source Pointers

All benchmark designs are public. Per frozen rule, eligibility = the ER miter
is not a constant (functionally identical designs are excluded with reason).

## VACSEM adder input sets (add8/16/32/64/128/192/256 + deviation functions)
- repo: https://github.com/ehw-fit/vacsem
- commit: b11ede7 (as recorded in run_report_5)
- local path on the original machine: tools/cache/VACSEM/Circuit2Cnf/input/
- used files: addW/*.blif (approx + exact), deviation-function/width_*_absolute_error.blif
- selection rule per width (frozen): stable filename sort; eligible >= 10 ->
  deterministic equal-interval 10 (indices floor(i*n/10)); 5-9 -> all; < 5 ->
  all (pool-limited noted). VACSEM BLIFs are NOT redistributed in this bundle;
  regenerate via the repo at the pinned commit.
- deviation functions width_13/193/257 are MISSING upstream; instantiated
  mechanically from the official parametric template
  (`abs_err = (a>b)?(a-b):(b-a)` over `_bit` bits) and synthesized with the
  frozen yosys 0.52 flow (tool-input gap, not a method change).

## EvoApproxLib add12 (only_required_local_sources/add12/)
- repo: https://github.com/ehw-fit/evoapproxlib
- commit: ec28be83bfce1b8e8b92bd456be520d323a568b5
- path: adders/12_unsigned/pareto_pwr_ep/*.v  (MIT license, redistributed with
  attribution; see each file header)
- exact counterpart add12exact.v = `assign O = A + B` (project-generated,
  same yosys flow)
- add12u_19A is EXCLUDED by the frozen eligibility rule (functionally equal to
  the exact adder, ER=0, miter const0) - recorded in the manifest
  `excluded_designs`.

## Excluded designs (frozen eligibility rule)
- add12u_19A (width 12): functionally_exact_ER0_degenerate
