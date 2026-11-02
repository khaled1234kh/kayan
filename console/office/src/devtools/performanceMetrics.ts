export function summarizeFrames(offsets: number[], durationMs: number, visible: boolean) {
  if (!visible || durationMs <= 0 || !Number.isFinite(durationMs) ||
    offsets.some((n, i) => !Number.isFinite(n) || n < 0 || n > durationMs || (i > 0 && n < offsets[i - 1]))) {
    return { valid: false as const, reason: 'Hidden tab or invalid frame timing; repeat the sample.' };
  }
  const bounds = [0, ...offsets, durationMs];
  const gaps = bounds.slice(1).map((n, i) => n - bounds[i]).sort((a, b) => a - b);
  return { valid: true as const, rendered_frames: offsets.length,
    rendered_fps: offsets.length * 1000 / durationMs,
    frame_gap_p95_ms: gaps[Math.max(0, Math.ceil(gaps.length * .95) - 1)],
    frame_gap_max_ms: gaps[gaps.length - 1],
    limit: 'Canvas render cadence, not GPU timing, browser visual acceptance or input latency. Demand-rendered idle can correctly have zero frames.' };
}
