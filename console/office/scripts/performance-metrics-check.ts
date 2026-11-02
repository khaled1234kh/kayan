import assert from 'node:assert/strict';
import { summarizeFrames } from '../src/devtools/performanceMetrics';
const sample = summarizeFrames([100, 200, 300], 400, true);
assert.equal(sample.valid, true);
if (sample.valid) { assert.equal(sample.rendered_fps, 7.5); assert.equal(sample.frame_gap_max_ms, 100); }
assert.equal(summarizeFrames([100], 1000, false).valid, false);
assert.equal(summarizeFrames([200, 100], 1000, true).valid, false);
assert.equal(summarizeFrames([NaN], 1000, true).valid, false);
const demandIdle = summarizeFrames([], 10000, true);
assert.equal(demandIdle.valid && demandIdle.rendered_fps, 0);
console.log('Synthetic metric calculations passed. No real browser FPS was measured by this check.');
