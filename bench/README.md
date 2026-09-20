# bench/ — same pack, same oracle, every implementation

`bench/run.sh <stage> <impl> <pack-dir>` (arrives with R04) runs
`stages/<stage>/<impl>/run` on a pack and copies its `result.json` to
`bench/results/<date>/<stage>-<impl>.json`. That directory is gitignored: numbers
are measured on the owner's 3090 and quoted from here, never typed from memory.

The point of the contract (`stages/CONTRACT.md`) is that `python-cuda` and `bend2`
implementations of `s1-fuse` are judged by the same file and the same metrics
(`wall_s`, `gpu_s`, plus PSNR/SSIM against the reference computed by `s4-score`).
Nothing in the MVP depends on Bend2; it plugs in here later (R09) without touching
the orchestrator.
