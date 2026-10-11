import type { Actor } from '../../types';
import { COLORS, STATE_COLOR } from '../../data/layout';
import { tileToWorld } from '../office/Office';
import ActorModel from './ActorModel';
import Chair from './Chair';
import Keyboard from './Keyboard';
import Mouse from './Mouse';
import { AttentionBeacon } from './AttentionBeacon';
import { MonitorScreen } from './MonitorScreen';
import { StateMarker } from './StateMarker';
import type { ActorRole } from './materials';

/**
 * Where the seated actor sits relative to the desk tile centre.
 *
 * Measured, not guessed. At z = -0.95 the shoulder-to-keyboard distance was
 * 0.635 against an arm length of 0.539 — genuinely unreachable, which is why
 * the arms read as locked straight. At -0.60 the reach is 0.290 against the
 * same 0.539 arm, so the elbow has room to bend into a typing pose.
 *
 * Known trade-off: the seated character's knees reach z ≈ -0.22, which is inside
 * the desk's footprint (the desk is a solid block spanning z -0.45..0.45). That
 * interpenetration already existed at -0.70; moving forward makes it slightly
 * deeper. The proper fix is to rebuild the desk as a top plus legs rather than a
 * solid block.
 */
const ACTOR_Z = -0.6;

/** Map a domain actor onto an attire set. */
function roleFor(actor: Actor): ActorRole {
  if (actor.kind === 'human') {
    // "Chief Executive Officer" does not contain the substring "CEO".
    const r = actor.role.toLowerCase();
    return r.includes('chief') || r.includes('ceo') ? 'ceo' : 'human';
  }
  const r = actor.role.toLowerCase();
  if (r.includes('sales')) return 'ai-sales';
  if (r.includes('operations')) return 'ai-ops';
  return 'ai-manager';
}

/**
 * Wrapper: places one actor at their desk on the floor and attaches the state
 * marker. Desk, monitor and ground disc are unchanged from the foundation build;
 * the figure now stands beside the desk (base at floor level, facing +Z) instead
 * of perching on the desktop.
 */
export function ActorSeat({
  actor,
  selected,
  onSelect,
}: {
  actor: Actor;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const accent = STATE_COLOR[actor.state] ?? COLORS.muted;
  const [wx, wz] = tileToWorld(actor.gridPosition.x, actor.gridPosition.z);
  const role = roleFor(actor);

  // Attention states carry a beacon so a blocked or approval-waiting actor is
  // visible from the overview camera; the N shortcut cycles between them.
  const needsAttention = actor.state === 'awaiting_approval' || actor.state === 'blocked';

  const select = (e: { stopPropagation: () => void }) => {
    e.stopPropagation();
    onSelect(actor.id);
  };
  const hoverOn = (e: { stopPropagation: () => void }) => {
    e.stopPropagation();
    document.body.style.cursor = 'pointer';
  };
  const hoverOff = () => {
    document.body.style.cursor = 'default';
  };

  return (
    <group position={[wx, 0, wz]}>
      {/* Desk */}
      <mesh
        position={[0, 0.4, 0]}
        castShadow
        receiveShadow
        onClick={select}
        onPointerOver={hoverOn}
        onPointerOut={hoverOff}
      >
        <boxGeometry args={[1.4, 0.8, 0.9]} />
        <meshStandardMaterial
          color={COLORS.deskTop}
          emissive={selected ? COLORS.teal : '#000000'}
          emissiveIntensity={selected ? 0.3 : 0}
          roughness={0.85}
          metalness={0.06}
        />
      </mesh>

      {/* Monitor: bezel + an abstract UI face (task graph / inventory grid /
          quotation table). Rotated 180° about Y so the screen faces the actor,
          who stands at local z = -0.95 and faces +Z — without this the actors
          see the back of the casing. The screen stays 0.0005 proud of the
          bezel's now-forward face (z = -0.2 - 0.0355) so it cannot z-fight. */}
      <group position={[0, 0.98, -0.2]} rotation={[0, Math.PI, 0]}>
        <mesh castShadow>
          <boxGeometry args={[0.66, 0.42, 0.07]} />
          <meshStandardMaterial
            color={COLORS.monitor}
            emissive={COLORS.teal}
            emissiveIntensity={selected ? 0.4 : 0.18}
            roughness={0.6}
          />
        </mesh>
        <group position={[0, 0, 0.0355]}>
          <MonitorScreen role={role} />
        </group>
      </group>

      {/* Keyboard: on the desk between the actor (z = -0.95) and the monitor
          (z = -0.2). Desk top is y = 0.8, so the base rests on it. */}
      <group position={[0, 0.8, -0.35]}>
        <Keyboard />
        <Mouse />
      </group>

      {/* Ground disc: quiet, persistent state cue at the actor's feet */}
      <mesh position={[0, 0.03, -0.95]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.42, 0.5, 32]} />
        <meshBasicMaterial color={accent} transparent opacity={0.65} />
      </mesh>

      {/* Figure. Actor sits at z = -0.70: the desk front edge is z = -0.45, and at
          the original -0.95 the keyboard was 0.59 away, which forced the arms
          to full extension. -0.70 puts the keyboard within natural reach. */}
      <group
        position={[0, 0, ACTOR_Z]}
        onClick={select}
        onPointerOver={hoverOn}
        onPointerOut={hoverOff}
      >
        <Chair />
        <ActorModel role={role} />
        {needsAttention && <AttentionBeacon />}
      </group>

      <StateMarker actor={actor} />
    </group>
  );
}

/** Renders every actor from the store snapshot. */
export function ActorLayer({
  actors,
  selectedId,
  onSelect,
}: {
  actors: Actor[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <>
      {actors.map((actor) => (
        <ActorSeat key={actor.id} actor={actor} selected={selectedId === actor.id} onSelect={onSelect} />
      ))}
    </>
  );
}