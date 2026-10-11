import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { useFBX } from '@react-three/drei';
import { SkeletonUtils } from 'three-stdlib';
import * as THREE from 'three';
import type { ActorRole } from './materials';

/**
 * Rigged Mixamo actor, business attire, playing a looping sitting-idle.
 *
 * Facts established by inspecting the source FBX files:
 *
 * - Each file carries one real clip, "mixamo.com" (53 tracks, 16.5 s), plus an
 *   empty "Take 001" placeholder with zero tracks. The placeholder is filtered
 *   out — playing it would silently leave the actor in its bind pose.
 * - Native height is ~176-179 units (centimetres), so each model is scaled to
 *   TARGET_HEIGHT. Measured from the loaded model rather than hard-coded, so a
 *   differently-sized model still lands correctly.
 * - The models are authored facing +Z, matching the seat orientation, so no
 *   rotation is applied.
 * - Feet sit at y ~ -0.04 natively, which is under 2 mm once scaled.
 * - Materials are MeshPhongMaterial with *embedded textures*. The conversion
 *   below must carry every map across or the characters lose their skin,
 *   hair and clothing detail and render as flat coloured blobs.
 */

const ROLE_MODEL: Record<ActorRole, string> = {
  ceo: '/models/CEO.fbx',
  human: '/models/Employee.fbx',
  'ai-manager': '/models/AIManager.fbx',
  'ai-sales': '/models/AISales.fbx',
  'ai-ops': '/models/AIOps.fbx',
};

/** Only these three read as AI; the two humans keep the model's own colours. */
const AI_ROLES: ReadonlySet<ActorRole> = new Set<ActorRole>([
  'ai-manager',
  'ai-sales',
  'ai-ops',
]);

/**
 * AI identity colour. Deliberately dim and desaturated: a bright emissive
 * reads as a glow from within, which the eye interprets as translucent. Kept
 * low enough that the actors still look solid, distinct enough to tell apart
 * from the two humans at overview distance.
 */
const AI_EMISSIVE = '#0A5C62';
const AI_EMISSIVE_INTENSITY = 0.1;
const TARGET_HEIGHT = 1.65;
const ROUGHNESS = 0.75;

/**
 * Skinned meshes at bent elbows and knees show gaps at the joint seams under
 * backface culling, so these draw double-sided. With five characters the extra
 * fill cost is irrelevant.
 */
const SIDE_RENDERING = THREE.DoubleSide;
const MAX_METALNESS = 0.1;
const MIN_ROUGHNESS = 0.6;

/**
 * Hair keeps its alpha-masked edge (strands, not a helmet) via alphaTest while
 * still rendering in the *opaque* pass.
 *
 * Note `transparent` stays false even for hair: alphaTest alone cuts the same
 * silhouette, and setting transparent=true would push hair back into the sorted
 * pass — which is exactly the depth-sorting artefact that made these characters
 * look see-through in the first place. Cutout belongs in the opaque pass.
 */
const HAIR_ALPHA_TEST = 0.5;
const isHairMaterial = (name: string) => /hair/i.test(name);

/** Warm every model before the first seat renders, so nobody pops in. */
for (const path of Object.values(ROLE_MODEL)) useFBX.preload(path);

/**
 * One source material → one fresh MeshStandardMaterial.
 *
 * Always returns a new instance: `useFBX` hands back a single cached object per
 * URL, so mutating a material in place would tint every actor sharing it.
 * Textures are shared by reference on purpose — they are immutable here and
 * cloning them per actor would multiply ~250 MB of GPU texture memory.
 */
function toStandardMaterial(source: THREE.Material, isAI: boolean): THREE.Material {
  const src = source as THREE.MeshPhongMaterial;

  const material = new THREE.MeshStandardMaterial({
    color: src.color ? src.color.clone() : new THREE.Color(0xffffff),
    // Maps must survive the conversion: these models are texture-driven.
    map: src.map ?? null,
    normalMap: src.normalMap ?? null,
    alphaMap: src.alphaMap ?? null,
    aoMap: src.aoMap ?? null,
    emissiveMap: src.emissiveMap ?? null,
    roughness: ROUGHNESS,
    metalness: 0.04,
    side: SIDE_RENDERING,
  });

  // The converted material must keep the source name, otherwise the hair
  // detection below has nothing to match on.
  material.name = src.name ?? '';

  // Several models carry vertex colours; the attribute is ignored unless set.
  material.vertexColors = src.vertexColors ?? false;
  if (src.normalScale) material.normalScale.copy(src.normalScale);

  // Opaque rendering. `transparent` was the defect: it moved these materials
  // into the sorted pass and let geometry behind show through.
  material.transparent = false;
  material.opacity = 1;
  material.depthWrite = true;
  material.depthTest = true;
  material.alphaTest = isHairMaterial(material.name) ? HAIR_ALPHA_TEST : 0;
  if (material.map) material.map.premultiplyAlpha = false;

  // Skin and fabric, not metal or glass.
  material.metalness = Math.min(material.metalness ?? 0, MAX_METALNESS);
  material.roughness = Math.max(material.roughness ?? 0.5, MIN_ROUGHNESS);

  if (isAI) {
    material.emissive = new THREE.Color(AI_EMISSIVE);
    material.emissiveIntensity = AI_EMISSIVE_INTENSITY;
  }

  material.needsUpdate = true;
  return material;
}

/**
 * Collapse the partial skeletons these FBX files ship with into one hierarchy.
 *
 * Each skinned mesh (Body, Hair, Suit, Tie, Belt, Pants, Shoes…) arrives with
 * its *own* Skeleton containing only the bones that mesh happens to use — CEO
 * has 9 meshes and 9 skeletons covering 8, 28, 5, 12, 8, 13, 58, 6 and 6 bones.
 * Because every subset uses identical bone *names*, AnimationMixer resolves a
 * track to the first object of that name and leaves the rest untouched: before
 * this, 93 of CEO's 144 bones never moved, so hair, suit, tie, belt and shoes
 * hung frozen in bind pose. That was the T-pose, the hollow limbs and the
 * floating hands.
 *
 * The fix is safe because the duplicate hierarchies are exact clones — every
 * same-named bone pair was measured to have an identical inverse bind matrix.
 * So we keep the most complete hierarchy, repoint every mesh at it by name, and
 * detach the duplicates outright (hiding them would leave duplicate names in the
 * graph, which is exactly what breaks track resolution in the first place).
 */
function mergeSkeletonsToPrimary(root: THREE.Object3D): void {
  const skinned: THREE.SkinnedMesh[] = [];
  root.traverse((obj) => {
    if ((obj as THREE.SkinnedMesh).isSkinnedMesh) skinned.push(obj as THREE.SkinnedMesh);
  });
  if (skinned.length <= 1) return;

  // The mesh whose skeleton covers the most bones names the hierarchy to keep.
  skinned.sort((a, b) => b.skeleton.bones.length - a.skeleton.bones.length);
  const primary = skinned[0];

  const keep = new Map<string, THREE.Bone>();
  const keepInverseBind = new Map<string, THREE.Matrix4>();
  let top: THREE.Bone = primary.skeleton.bones[0];
  while (top.parent && (top.parent as THREE.Bone).isBone) {
    top = top.parent as THREE.Bone;
  }
  const stack = [top];
  while (stack.length) {
    const bone = stack.pop() as THREE.Bone;
    if (!keep.has(bone.name)) {
      keep.set(bone.name, bone);
      keepInverseBind.set(
        bone.name,
        new THREE.Matrix4().copy(bone.matrixWorld).invert(),
      );
    }
    for (const child of bone.children) {
      const asBone = child as THREE.Bone;
      if (asBone.isBone) stack.push(asBone);
    }
  }

  for (const mesh of skinned) {
    const bones: THREE.Bone[] = [];
    const inverses: THREE.Matrix4[] = [];
    for (let i = 0; i < mesh.skeleton.bones.length; i++) {
      const match = keep.get(mesh.skeleton.bones[i].name);
      if (match) {
        bones.push(match);
        inverses.push(keepInverseBind.get(match.name) as THREE.Matrix4);
      } else {
        // Not present in the kept hierarchy — leave this reference untouched.
        bones.push(mesh.skeleton.bones[i]);
        inverses.push(mesh.skeleton.boneInverses[i]);
      }
    }
    mesh.skeleton.bones = bones;
    mesh.skeleton.boneInverses = inverses;
    mesh.bind(mesh.skeleton, mesh.bindMatrix);
  }

  const all: THREE.Bone[] = [];
  root.traverse((obj) => {
    if ((obj as THREE.Bone).isBone) all.push(obj as THREE.Bone);
  });
  const doomed = all.filter((bone) => keep.get(bone.name) !== bone);
  const doomedSet = new Set(doomed);
  doomed
    .filter((bone) => !doomedSet.has(bone.parent as THREE.Bone))
    .forEach((bone) => bone.removeFromParent());
}

/**
 * Resting-on-keys pose — deliberately NOT applied yet.
 *
 * Measured facts about this rig, for whoever picks this up:
 *
 * - The characters face +Z, so the LEFT hand sits on +X and the right on -X.
 *   (Verified: with no pose applied, LeftHand sits at x = +0.207 and RightHand
 *   at x = -0.248.) Targets must respect that or the hands cross.
 * - The sitting idle settles the hips at y ≈ 0.51, but the desk top is at
 *   y = 0.80. The desk therefore sits ~0.29 ABOVE the seat, which is backwards
 *   — a real desk is level with or below a seated hip. Reaching up to it from a
 *   seated posture needs shoulder angles no human arm can produce; a bounded
 *   solve still missed the target by 55 cm.
 * - The idle animates the arms with a ~22 cm swing, so any fixed offset or
 *   slerp blend decays over time and the hands slide off the keys.
 *
 * Fixing this properly needs either a lower desk (y ≈ 0.68) or world-space
 * two-bone IK aimed at the keycaps each frame. Both are outside the files this
 * change may touch, so the arms are left on the idle rather than shipping a
 * pose that measurably clips through the desk.
 */
const ARM_POSE: Record<string, THREE.Euler> = {};

const ARM_SUFFIXES = Object.keys(ARM_POSE) as Array<keyof typeof ARM_POSE>;

/** Bones are named per-rig, so match on the trailing name only. */
function findBoneBySuffix(root: THREE.Object3D, suffix: string): THREE.Bone | null {
  let found: THREE.Bone | null = null;
  root.traverse((obj) => {
    if (!found && (obj as THREE.Bone).isBone && obj.name.endsWith(suffix)) {
      found = obj as THREE.Bone;
    }
  });
  return found;
}

export function ActorModel({ role }: { role: ActorRole }) {
  const fbx = useFBX(ROLE_MODEL[role]);
  const group = useRef<THREE.Group>(null);
  const isAI = AI_ROLES.has(role);

  const { object, scale, mixer } = useMemo(() => {
    // SkeletonUtils.clone, not Object3D.clone — only the former rebinds the
    // bone inverses, so the rig survives into the copy.
    const clone = SkeletonUtils.clone(fbx) as THREE.Object3D;
    mergeSkeletonsToPrimary(clone);

    clone.traverse((child) => {
      if (!(child instanceof THREE.Mesh)) return;
      child.castShadow = true;
      child.receiveShadow = true;
      const mesh = child as THREE.Mesh;
      mesh.material = Array.isArray(mesh.material)
        ? mesh.material.map((m) => toStandardMaterial(m, isAI))
        : toStandardMaterial(mesh.material, isAI);
    });

    const box = new THREE.Box3().setFromObject(clone);
    const nativeHeight = box.max.y - box.min.y;
    const fitted = nativeHeight > 0 ? TARGET_HEIGHT / nativeHeight : 1;

    // One mixer, owned here rather than delegated to drei's useAnimations, so
    // the arm pose can be applied after the mixer has written the idle.
    const created = new THREE.AnimationMixer(clone);
    const clip = (fbx.animations ?? []).find((c) => c.tracks.length > 0);
    if (clip) {
      const action = created.clipAction(clip);
      action.reset();
      action.setLoop(THREE.LoopRepeat, Infinity);
      action.play();
    }

    // Capture the solved pose as absolute target quaternions, when a pose is
    // defined. Empty today (see ARM_POSE) — the arms stay on the idle.
    const bones = ARM_SUFFIXES.map((suffix) => ({
      suffix,
      bone: findBoneBySuffix(clone, suffix),
      offset: new THREE.Quaternion().setFromEuler(ARM_POSE[suffix]),
    })).filter((e): e is { suffix: keyof typeof ARM_POSE; bone: THREE.Bone; offset: THREE.Quaternion } =>
      e.bone !== null,
    );

    // Run the mixer forward before sampling any pose, so the figure has settled
    // into the sitting idle rather than the standing start frame.
    const WARMUP = 90;
    for (let i = 0; i < WARMUP; i++) created.update(1 / 60);
    for (const entry of bones) entry.bone.quaternion.multiply(entry.offset);

    return {
      object: clone,
      scale: fitted,
      mixer: created,
    };
  }, [fbx, isAI]);

  useFrame((_, delta) => {
    mixer.update(delta);
  });

  return (
    <group ref={group} scale={scale}>
      <primitive object={object} />
    </group>
  );
}

export default ActorModel;