import type { ActorRole } from './materials';
import { BODY, LOOKS, MAT, type RoleLook } from './materials';

/**
 * Actor body — placeholder-quality humanoid built only from R3F primitives.
 *
 * Reads at the operating camera distance (15–25 units): correct adult
 * proportions first (~6.8 heads), then silhouette, then role colour. No face
 * detail — a single dark visor band replaces eyes. No hair on AI agents.
 *
 * The group origin is at the actor's feet, facing +Z.
 */

/** One arm, pivoted at the shoulder and splayed slightly outward. */
function Arm({ side, look }: { side: 1 | -1; look: RoleLook }) {
  return (
    <group
      position={[side * BODY.armX, BODY.shoulderY, 0]}
      rotation={[0, 0, side * BODY.armTilt]}
    >
      {/* shoulder */}
      <mesh position={[0, 0, 0]} material={look.garment}>
        <sphereGeometry args={[BODY.shoulderR, 12, 10]} />
      </mesh>
      {/* upper arm */}
      <mesh position={[0, -BODY.upperArmH / 2, 0]} material={look.garment}>
        <cylinderGeometry args={[BODY.upperArmR, BODY.lowerArmR, BODY.upperArmH, 8]} />
      </mesh>
      {/* lower arm */}
      <mesh
        position={[0, -BODY.upperArmH - BODY.lowerArmH / 2, 0]}
        material={look.garment}
      >
        <cylinderGeometry args={[BODY.lowerArmR, BODY.lowerArmR * 0.92, BODY.lowerArmH, 8]} />
      </mesh>
      {/* hand */}
      <mesh
        position={[0, -BODY.upperArmH - BODY.lowerArmH - BODY.handR, 0]}
        material={MAT.skin}
      >
        <sphereGeometry args={[BODY.handR, 10, 8]} />
      </mesh>
    </group>
  );
}

/** One leg, hips down to the floor. */
function Leg({ side, look }: { side: 1 | -1; look: RoleLook }) {
  return (
    <group position={[side * BODY.legX, 0, 0]}>
      <mesh position={[0, BODY.upperLegY, 0]} material={look.trousers}>
        <cylinderGeometry args={[BODY.upperLegR, BODY.lowerLegR, BODY.upperLegH, 8]} />
      </mesh>
      <mesh position={[0, BODY.lowerLegY, 0]} material={look.trousers}>
        <cylinderGeometry args={[BODY.lowerLegR, BODY.lowerLegR * 0.94, BODY.lowerLegH, 8]} />
      </mesh>
      <mesh position={[0, 0.025, 0.03]} material={MAT.shoe}>
        <boxGeometry args={[0.12, 0.05, 0.22]} />
      </mesh>
    </group>
  );
}

/** Head with a minimal visor band. No eyes, mouth, nose or brows. */
function Head({ hair }: { hair: RoleLook['hair'] }) {
  return (
    <group>
      <mesh position={[0, BODY.headY, 0]} material={MAT.skin} castShadow>
        <sphereGeometry args={[BODY.headR, 16, 12]} />
      </mesh>

      {/* visor band across the eye line */}
      <mesh position={[0, BODY.headY + 0.005, BODY.headR - 0.015]} material={MAT.visor}>
        <boxGeometry args={[0.17, 0.036, 0.03]} />
      </mesh>

      {hair === 'cap' && (
        <mesh position={[0, BODY.headY + 0.03, -0.005]} scale={[1, 0.78, 1]} material={MAT.hair}>
          <sphereGeometry args={[BODY.headR + 0.012, 14, 10, 0, Math.PI * 2, 0, Math.PI * 0.62]} />
        </mesh>
      )}
      {hair === 'bun' && (
        <>
          <mesh position={[0, BODY.headY + 0.035, -0.004]} scale={[1, 0.72, 1]} material={MAT.hair}>
            <sphereGeometry args={[BODY.headR + 0.012, 14, 10, 0, Math.PI * 2, 0, Math.PI * 0.55]} />
          </mesh>
          <mesh position={[0, BODY.headY + 0.055, -BODY.headR - 0.02]} material={MAT.hair}>
            <sphereGeometry args={[0.055, 10, 8]} />
          </mesh>
        </>
      )}
    </group>
  );
}

export default function ActorBody({ role }: { role: ActorRole }) {
  const look = LOOKS[role];
  return (
    <group>
      {/* torso: low-poly tapered cylinder, flattened in Z for human proportions */}
      <mesh
        position={[0, BODY.torsoY, 0]}
        scale={[1, 1, 0.62]}
        material={look.garment}
        castShadow
      >
        <cylinderGeometry
          args={[BODY.shoulderTop, BODY.waistBottom, BODY.torsoH, 8, 1]}
        />
      </mesh>

      {/* hips */}
      <mesh position={[0, BODY.hipY, 0]} material={look.trousers} castShadow>
        <boxGeometry args={[0.36, 0.12, 0.2]} />
      </mesh>

      {/* contrasting front panel (CEO shirt). Sits proud of the torso surface:
          the tapered torso is 0.21 * 0.62 = 0.13 deep at the shoulders, so the
          panel must clear z = 0.13 or it renders inside the torso. */}
      {look.shirtFront && (
        <mesh position={[0, BODY.torsoY - 0.02, 0.142]} material={look.shirtFront}>
          <boxGeometry args={[0.17, 0.34, 0.02]} />
        </mesh>
      )}

      {/* Collar trim — the role identifier. Sits just above the torso top edge
          (torso top = torsoY + torsoH/2 = 1.21) so it is never swallowed. */}
      <mesh
        position={[0, BODY.neckY - BODY.neckH / 2 + 0.02, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        material={look.collar}
      >
        <torusGeometry args={[0.082, 0.023, 8, 20]} />
      </mesh>

      {/* neck */}
      <mesh position={[0, BODY.neckY, 0]} material={MAT.skin}>
        <cylinderGeometry args={[BODY.neckR, BODY.neckR, BODY.neckH, 8]} />
      </mesh>

      <Head hair={look.hair} />

      <Arm side={-1} look={look} />
      <Arm side={1} look={look} />
      <Leg side={-1} look={look} />
      <Leg side={1} look={look} />
    </group>
  );
}