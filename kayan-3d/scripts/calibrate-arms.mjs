/**
 * Arm-pose calibration (Phase H2).
 *
 * Measures the live rig instead of guessing: locates the keyboard by its
 * 70-instance key mesh, reads its true world transform, captures each arm bone's
 * rest quaternion, then runs coordinate descent over the six Euler offsets to
 * put both hands on the home row.
 *
 * This is OFFLINE calibration. It produces static Euler numbers which are then
 * hard-coded into ActorModel.tsx. The shipped scene runs no IK and no per-frame
 * solver — it multiplies fixed offsets after the mixer, exactly as before.
 *
 * Run: node scripts/calibrate-arms.mjs
 */
import { spawn } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

async function waitForServer(url, timeoutMs) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    try {
      const r = await fetch(url);
      if (r.ok) return true;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

let server = null;
if (!(await waitForServer('http://localhost:5173/', 3000))) {
  server = spawn('npx', ['vite', '--port', '5173', '--strictPort'], {
    cwd: ROOT,
    shell: true,
    stdio: 'ignore',
  });
  if (!(await waitForServer('http://localhost:5173/', 90000))) {
    console.error('FAIL: dev server never came up');
    process.exit(1);
  }
}

const browser = await puppeteer.launch({
  headless: true,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox'],
});
const page = await browser.newPage();
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle2', timeout: 120000 });
await page.waitForFunction('window.__setCamera !== undefined', { timeout: 60000 });
for (let i = 0; i < 90; i++) {
  const s = await page.evaluate(() => window.__sceneStats());
  if (s.skinned > 0) break;
  await new Promise((r) => setTimeout(r, 1000));
}
await new Promise((r) => setTimeout(r, 2500));

const out = await page.evaluate(() => {
  const THREE = window.__camera.constructor.prototype.constructor;
  const scene = window.__camera.parent;
  const V = window.__camera.position.constructor;

  // --- locate the keyboard: 5 rows x 14 cols = 70 key instances -------------
  let keys = null;
  scene.traverse((o) => {
    if (!keys && o.isInstancedMesh && o.count === 70) keys = o;
  });
  if (!keys) return { error: 'keyboard key mesh not found' };
  const kbGroup = keys.parent; // keyboard group
  const matGroup = kbGroup.parent; // DeskInput group
  kbGroup.updateMatrixWorld(true);
  const kbPos = kbGroup.getWorldPosition(new V());

  // key local geometry: base top + key half height
  const KEY = 0.026, BASE_H = 0.02, PITCH = 0.03, ROWS = 5, COLS = 14;
  const keyCentreY = kbPos.y + BASE_H / 2 + KEY / 2;
  const keyTopY = keyCentreY + KEY / 4;

  // --- locate one actor's arm bones ---------------------------------------
  const SUF = ['LeftArm', 'LeftForeArm', 'LeftHand', 'RightArm', 'RightForeArm', 'RightHand'];
  let skelRoot = null;
  scene.traverse((o) => {
    if (skelRoot || !o.isBone || !/LeftArm$/.test(o.name)) return;
    let r = o;
    while (r.parent && r.parent.isBone) r = r.parent;
    skelRoot = r;
  });
  if (!skelRoot) return { error: 'skeleton not found' };

  const bones = {};
  skelRoot.traverse((o) => {
    if (!o.isBone) return;
    const m = /(Left|Right)(Arm|ForeArm|Hand)$/.exec(o.name);
    if (m) bones[`${m[1]}${m[2]}`] = o;
  });
  const missing = SUF.filter((s) => !bones[s]);
  if (missing.length) return { error: `missing bones: ${missing.join(',')}` };

  // --- capture rest quaternions --------------------------------------------
  // ActorModel now strips the arm tracks from the clip before the mixer sees
  // them, so the arms stay at their BIND pose and no stale offset is applied.
  // What is on screen now IS the rest pose, so it is captured directly.
  const rest = {};
  for (const s of SUF) rest[s] = bones[s].quaternion.clone();

  // --- measure reach: bone lengths along the chain -------------------------
  const boneLen = (a, b) => a.getWorldPosition(new V()).distanceTo(b.getWorldPosition(new V()));
  const shoulder = (side) => {
    let s = null;
    skelRoot.traverse((o) => {
      if (!s && o.isBone && o.name.endsWith(`${side}Shoulder`)) s = o;
    });
    return s;
  };
  const reach = {};
  for (const side of ['Left', 'Right']) {
    const sh = shoulder(side);
    reach[side] = {
      upperArm: +boneLen(sh, bones[`${side}Arm`]).toFixed(4),
      forearm: +boneLen(bones[`${side}Arm`], bones[`${side}ForeArm`]).toFixed(4),
      hand: +boneLen(bones[`${side}ForeArm`], bones[`${side}Hand`]).toFixed(4),
    };
    reach[side].shoulderToWrist =
      +(reach[side].upperArm + reach[side].forearm).toFixed(4);
    reach[side].shoulderToHand =
      +(reach[side].upperArm + reach[side].forearm + reach[side].hand).toFixed(4);
  }

  const chainInfo = SUF.map((s) => ({
    name: bones[s].name,
    parent: bones[s].parent?.name ?? '(none)',
    localEuler: [bones[s].rotation.x, bones[s].rotation.y, bones[s].rotation.z].map(
      (v) => +v.toFixed(4),
    ),
  }));

  // --- targets -------------------------------------------------------------
  // LEFT hand sits on the actor's LEFT, which is +X (characters face +Z). The
  // right hand sits on -X. Both wrists target the keyboard's NEAR edge at the
  // same Z so the forearms run parallel instead of crossing.
  //
  // SIGN NOTE: the brief said "keyboard_center_z + 0.05 (near edge)", but +Z is
  // AWAY from the actor — ActorSeat places the figure at desk z = -0.6 while the
  // keyboard sits at desk z = -0.01, so the actor is at LOWER z. The near edge
  // is therefore kbPos.z - 0.08 (BASE_D 0.16, half = 0.08). Targeting +0.05
  // would put the wrist past the FAR edge, which is also unreachable: the
  // measured shoulder->wrist reach is 0.576 against a 0.641 requirement.
  // Using the near edge, as the word "near" requires.
  //
  // Y sits just above the key surface. Measured reach forces the WRIST to rest
  // behind the keys with the fingers extending forward onto them.
  const HALF = 0.1;
  const NEAR_EDGE = 0.08;
  const WRIST_UP = 0.02;
  const target = {
    LeftHand: { x: kbPos.x + HALF, y: keyTopY + WRIST_UP, z: kbPos.z - NEAR_EDGE },
    RightHand: { x: kbPos.x - HALF, y: keyTopY + WRIST_UP, z: kbPos.z - NEAR_EDGE },
  };
  const targetVec = {
    LeftHand: new V(target.LeftHand.x, target.LeftHand.y, target.LeftHand.z),
    RightHand: new V(target.RightHand.x, target.RightHand.y, target.RightHand.z),
  };

  const EulerCtor = window.__camera.rotation.constructor;
  const QuatCtor = bones.LeftArm.quaternion.constructor;

  const apply = (e) => {
    for (const s of SUF) {
      const b = bones[s];
      b.quaternion.copy(rest[s]);
      const q = new (b.quaternion.constructor)().setFromEuler(
        new (window.__camera.rotation.constructor)(e[s][0], e[s][1], e[s][2], 'XYZ'),
      );
      b.quaternion.multiply(q);
    }
    skelRoot.updateMatrixWorld(true);
  };

  const err = (e) => {
    apply(e);
    let sum = 0;
    for (const s of ['LeftHand', 'RightHand']) {
      const p = bones[s].getWorldPosition(new V());
      sum += p.distanceTo(targetVec[s]);
    }
    return sum;
  };

  // --- coordinate descent -------------------------------------------------
  // The two arms are INDEPENDENT chains: LeftArm/ForeArm/Hand cannot move the
  // right hand. Solving them jointly let one side thrash the shared objective
  // (observed: right converged to 0.004 while left stalled 7 cm short). Each
  // side is therefore solved on its own, against its own wrist target.
  const names = SUF;
  const rand = (a, b) => a + Math.random() * (b - a);

  // Finger direction: wrist -> fingertip. The fingertip is the DESCENDANT of the
  // wrist bone that sits furthest from it — reliable regardless of how the rig
  // names its digits. (Matching on a name suffix picked the wrist itself, which
  // silently disabled the orientation term.)
  const fingertips = {};
  for (const side of ['Left', 'Right']) {
    const wrist = bones[`${side}Hand`];
    const wp = wrist.getWorldPosition(new V());
    let bestBone = null;
    let bestD = 0;
    wrist.traverse((o) => {
      if (!o.isBone || o === wrist) return;
      const d = o.getWorldPosition(new V()).distanceTo(wp);
      if (d > bestD) {
        bestD = d;
        bestBone = o;
      }
    });
    fingertips[side] = bestBone;
  }

  // Want the fingers pointing forward (+Z) and slightly down toward the keys.
  const wantDir = new V(0, -0.34, 0.94).normalize();

  const sideErr = (bonesForSide, values, restAll) => {
    const side = bonesForSide[0].startsWith('Left') ? 'Left' : 'Right';
    for (const s of bonesForSide) {
      const b = bones[s];
      b.quaternion.copy(restAll[s]);
      b.quaternion.multiply(
        new QuatCtor().setFromEuler(new EulerCtor(...values[s], 'XYZ')),
      );
    }
    skelRoot.updateMatrixWorld(true);

    const wristName = `${side}Hand`;
    const p = bones[wristName].getWorldPosition(new V());
    let e = p.distanceTo(targetVec[wristName]);

    // Orientation term: align the wrist->fingertip vector with wantDir.
    if (fingertips[side]) {
      const tip = fingertips[side].getWorldPosition(new V());
      const dir = tip.clone().sub(p);
      if (dir.lengthSq() > 1e-9) {
        dir.normalize();
        e += 1.5 * (1 - dir.dot(wantDir));
      }
    }

    // Keep the pose natural: penalise large joint rotations.
    for (const s of bonesForSide) {
      const v = values[s];
      e += 0.015 * (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    }
    return e;
  };

  const solveSide = (chain) => {
    let bestLocal = null;
    for (let start = 0; start < 60; start++) {
      let cur = {};
      for (const s of chain) {
        cur[s] =
          start === 0 ? [0, 0, 0] : [rand(-1.4, 1.4), rand(-1.4, 1.4), rand(-1.4, 1.4)];
      }
      let bestE = sideErr(chain, cur, rest);
      let step = 0.4;
      for (let pass = 0; pass < 900 && step > 0.002; pass++) {
        let improved = false;
        for (const s of chain) {
          for (let axis = 0; axis < 3; axis++) {
            for (const dirn of [step, -step]) {
              const trial = { ...cur, [s]: [...cur[s]] };
              trial[s][axis] += dirn;
              const e = sideErr(chain, trial, rest);
              if (e < bestE - 1e-10) {
                bestE = e;
                cur = trial;
                improved = true;
              }
            }
          }
        }
        if (!improved) step /= 2;
      }
      if (!bestLocal || bestE < bestLocal.err - 1e-10) bestLocal = { e: cur, err: bestE };
    }
    return bestLocal;
  };

  const left = solveSide(['LeftArm', 'LeftForeArm', 'LeftHand']);
  const right = solveSide(['RightArm', 'RightForeArm', 'RightHand']);
  const cur = { ...left.e, ...right.e };
  const bestErr = left.err + right.err;

  // Report the resolved geometry: where each wrist landed, and which way the
  // fingers point relative to the keycaps.
  apply(cur);
  const handGeom = {};
  for (const side of ['Left', 'Right']) {
    const wrist = bones[`${side}Hand`].getWorldPosition(new V());
    const tip = fingertips[side] ? fingertips[side].getWorldPosition(new V()) : null;
    const dir = tip ? tip.clone().sub(wrist).normalize() : null;
    handGeom[side] = {
      wrist: { x: +wrist.x.toFixed(4), y: +wrist.y.toFixed(4), z: +wrist.z.toFixed(4) },
      fingertip: tip ? { x: +tip.x.toFixed(4), y: +tip.y.toFixed(4), z: +tip.z.toFixed(4) } : null,
      fingerDir: dir ? { x: +dir.x.toFixed(3), y: +dir.y.toFixed(3), z: +dir.z.toFixed(3) } : null,
      // Is the fingertip actually over the key surface?
      fingertipOnKeys: tip ? Math.abs(tip.x - kbPos.x) < 0.25 && tip.z > kbPos.z - 0.09 && tip.z < kbPos.z + 0.09 && tip.y > keyTopY - 0.05 && tip.y < keyTopY + 0.12 : null,
      kbSpanZ: [+(kbPos.z - 0.08).toFixed(3), +(kbPos.z + 0.08).toFixed(3)],
      keyTopY: +keyTopY.toFixed(4),
    };
  }

  // --- final measurement ---------------------------------------------------
  apply(cur);
  const final = {};
  for (const s of ['LeftHand', 'RightHand']) {
    const p = bones[s].getWorldPosition(new V());
    final[s] = { x: +p.x.toFixed(4), y: +p.y.toFixed(4), z: +p.z.toFixed(4) };
  }
  // shoulders, for the report
  const shoulders = {};
  skelRoot.traverse((o) => {
    if (o.isBone && /(Left|Right)Shoulder$/.test(o.name)) {
      const p = o.getWorldPosition(new V());
      shoulders[o.name.replace(/^.*(Left|Right)Shoulder$/, '$1')] = {
        x: +p.x.toFixed(4),
        y: +p.y.toFixed(4),
        z: +p.z.toFixed(4),
      };
    }
  });

  return {
    kbPos: { x: +kbPos.x.toFixed(4), y: +kbPos.y.toFixed(4), z: +kbPos.z.toFixed(4) },
    keyCentreY: +keyCentreY.toFixed(4),
    keyTopY: +keyTopY.toFixed(4),
    target,
    reach,
    shouldersAtRest: (() => {
      const r = {};
      for (const side of ['Left', 'Right']) {
        const p = shoulder(side).getWorldPosition(new V());
        r[side] = { x: +p.x.toFixed(4), y: +p.y.toFixed(4), z: +p.z.toFixed(4) };
      }
      return r;
    })(),
    requiredReach: (() => {
      const r = {};
      for (const side of ['Left', 'Right']) {
        const sp = shoulder(side).getWorldPosition(new V());
        const t = targetVec[`${side}Hand`];
        r[side] = +sp.distanceTo(t).toFixed(4);
      }
      return r;
    })(),
    chainInfo,
    eulers: Object.fromEntries(names.map((s) => [s, cur[s].map((v) => +v.toFixed(4))])),
    handGeom,
    leftErr: +left.err.toFixed(4),
    rightErr: +right.err.toFixed(4),
    final,
    finalErr: +bestErr.toFixed(4),
  };
});

console.log(JSON.stringify(out, null, 2));
await browser.close();
if (server) server.kill();