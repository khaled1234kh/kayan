import * as THREE from 'three';

/**
 * Shared material objects.
 *
 * Every actor part reuses these instances — materials are created once at module
 * load, never per mesh. That keeps shader programs and draw-call state low, and
 * makes the attire palette a single source of truth.
 */

const std = (color: string, roughness = 0.75, metalness = 0.03): THREE.MeshStandardMaterial =>
  new THREE.MeshStandardMaterial({ color, roughness, metalness });

/** Matte, non-shiny surface language. roughness 0.6–0.85, metalness ≤ 0.1. */
export const MAT = {
  /** Neutral mannequin tone — deliberately desaturated, not a skin tone. */
  skin: std('#BEB2A6', 0.82, 0.0),
  /** CEO suit + both actors' trousers. */
  navy: std('#1A2C45', 0.75, 0.05),
  /** CEO shirt front and collar. */
  cream: std('#F5F0E6', 0.7, 0.02),
  /** Employee sweater. */
  sweater: std('#2E8B78', 0.8, 0.0),
  /** Shared torso/limb colour for all three AI agents. */
  charcoal: std('#2B3A45', 0.7, 0.06),
  collarTeal: std('#1FB8C4', 0.65, 0.05),
  collarOrange: std('#F5A623', 0.65, 0.05),
  collarMint: std('#8FD4B8', 0.65, 0.05),
  hair: std('#141C26', 0.85, 0.02),
  /** Visor band. No eyes, mouth, nose or brows. */
  visor: std('#0E141C', 0.6, 0.1),
  shoe: std('#161B23', 0.8, 0.03),
} as const;

export type ActorRole = 'ceo' | 'human' | 'ai-manager' | 'ai-sales' | 'ai-ops';

export interface RoleLook {
  /** Torso + upper/lower arms. */
  garment: THREE.Material;
  trousers: THREE.Material;
  /** Collar trim — the primary role identifier at a glance. */
  collar: THREE.Material;
  /** Accent hex for the role's monitor screen, drawn from its palette. */
  accent: string;
  /** Optional contrasting front panel (CEO shirt). */
  shirtFront?: THREE.Material;
  hair: 'bun' | 'cap' | null;
}

/**
 * Attire differentiation. Humans get hair and clothing; AI agents get a uniform
 * charcoal body, no hair, and a single coloured collar — so kind is readable
 * from the overview camera without inspecting detail.
 */
export const LOOKS: Record<ActorRole, RoleLook> = {
  ceo: {
    garment: MAT.navy,
    trousers: MAT.navy,
    collar: MAT.cream,
    accent: '#F5A623',
    shirtFront: MAT.cream,
    hair: 'bun',
  },
  human: {
    garment: MAT.sweater,
    trousers: MAT.navy,
    collar: MAT.sweater,
    accent: '#1FB8C4',
    hair: 'cap',
  },
  'ai-manager': {
    garment: MAT.charcoal,
    trousers: MAT.charcoal,
    collar: MAT.collarTeal,
    accent: '#1FB8C4',
    hair: null,
  },
  'ai-sales': {
    garment: MAT.charcoal,
    trousers: MAT.charcoal,
    collar: MAT.collarOrange,
    accent: '#F5A623',
    hair: null,
  },
  'ai-ops': {
    garment: MAT.charcoal,
    trousers: MAT.charcoal,
    collar: MAT.collarMint,
    accent: '#8FD4B8',
    hair: null,
  },
};

/**
 * Monitor surfaces.
 *
 * Screens are emissive rather than lit: a UI panel lit only by the room key
 * reads as a dark rectangle at the operating camera distance. Instances are
 * shared across every desk; the accent is resolved per role so a screen echoes
 * its owner's collar colour.
 */
const glow = (
  color: string,
  emissive: string,
  emissiveIntensity: number,
): THREE.MeshStandardMaterial =>
  new THREE.MeshStandardMaterial({
    color,
    emissive,
    emissiveIntensity,
    roughness: 0.42,
    metalness: 0.0,
  });

export const SCREEN = {
  /** Panel background — dark, faintly self-lit so it never reads as a hole. */
  glass: glow('#07121B', '#0B3B48', 0.4),
  /** Window/table header bar. */
  chrome: glow('#0E3C46', '#1FB8C4', 0.3),
  /** Filled content cell. */
  ink: glow('#12414C', '#1FB8C4', 0.45),
  /** Empty cell / separator — deliberately near-invisible. */
  inkDim: glow('#0B2630', '#0E3A46', 0.25),
} as const;

/**
 * Accent materials are cached per hex. Roles draw their accents from the collar
 * palette, so the cache holds at most four entries for the whole office.
 */
const accentCache = new Map<string, THREE.MeshStandardMaterial>();

export function screenAccentMaterial(hex: string): THREE.MeshStandardMaterial {
  let m = accentCache.get(hex);
  if (!m) {
    m = new THREE.MeshStandardMaterial({
      color: hex,
      emissive: hex,
      emissiveIntensity: 0.9,
      roughness: 0.42,
      metalness: 0.0,
    });
    accentCache.set(hex, m);
  }
  return m;
}

/**
 * Ring materials are cached per (colour, slot). Outer and inner rings must be
 * separate instances because the inner ring animates opacity/scale on its own.
 */
const outerCache = new Map<string, THREE.MeshStandardMaterial>();
const innerCache = new Map<string, THREE.MeshStandardMaterial>();

export function outerRingMaterial(hex: string): THREE.MeshStandardMaterial {
  let m = outerCache.get(hex);
  if (!m) {
    m = new THREE.MeshStandardMaterial({
      color: hex, emissive: hex, emissiveIntensity: 0.75, roughness: 0.45, metalness: 0.1,
    });
    outerCache.set(hex, m);
  }
  return m;
}

export function innerRingMaterial(hex: string): THREE.MeshStandardMaterial {
  let m = innerCache.get(hex);
  if (!m) {
    m = new THREE.MeshStandardMaterial({
      color: hex, emissive: hex, emissiveIntensity: 1.0, roughness: 0.45, metalness: 0.1,
      transparent: true, opacity: 0.9,
    });
    innerCache.set(hex, m);
  }
  return m;
}

/**
 * Attention beacon material, cached per hex. Emissive so the sphere reads in the
 * low office light; capped intensity so it never outshines the state ring.
 */
const beaconCache = new Map<string, THREE.MeshStandardMaterial>();

export function beaconMaterial(hex: string): THREE.MeshStandardMaterial {
  let m = beaconCache.get(hex);
  if (!m) {
    m = new THREE.MeshStandardMaterial({
      color: hex, emissive: hex, emissiveIntensity: 1.1, roughness: 0.5, metalness: 0.05,
    });
    beaconCache.set(hex, m);
  }
  return m;
}

/** Body metrics. 1.5 units tall, head 0.22 → ~6.8 heads, per the spec. */
export const BODY = {
  headR: 0.11,
  headY: 1.39,
  neckR: 0.03,
  neckH: 0.07,
  neckY: 1.245,
  torsoH: 0.5,
  torsoY: 0.96,
  shoulderTop: 0.21,
  waistBottom: 0.17,
  shoulderR: 0.07,
  shoulderX: 0.185,
  shoulderY: 1.18,
  upperArmR: 0.04,
  upperArmH: 0.26,
  lowerArmR: 0.035,
  lowerArmH: 0.24,
  armX: 0.195,
  armTilt: 0.087, // ~5° outward — the single biggest silhouette cue
  handR: 0.033,
  hipY: 0.65,
  legX: 0.085,
  upperLegR: 0.05,
  upperLegH: 0.32,
  upperLegY: 0.43,
  lowerLegR: 0.045,
  lowerLegH: 0.3,
  lowerLegY: 0.12,
  /**
   * Ring sits above the head; chip 0.4 above the ring.
   * Actors are normalised to TARGET_HEIGHT (1.65) by ActorModel, so this is
   * that height plus 0.35 of clearance. Was tuned at 1.95 for the old 1.5-unit
   * primitive body.
   */
  ringY: 2.0,
  chipY: 2.35,
} as const;