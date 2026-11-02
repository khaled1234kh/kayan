import type { Actor } from '../../types';
import { workstationRotation } from '../../data/actors';
import { Html } from '@react-three/drei';
import { MAPPING_BY_PENTEST_ROLE, ROLE_DESK_MAPPING, type PentestRole } from '../../data/roleMapping';
import { COLORS, STATE_COLOR } from '../../data/layout';
import { tileToWorld } from '../office/Office';
import ActorModel from './ActorModel';
import Chair from './Chair';
import { AttentionBeacon } from './AttentionBeacon';
import { DeskModel } from './DeskModel';
import { DeskInput } from './DeskInput';
import { DeskProps } from './DeskProps';
import { Monitor } from './Monitor';
import { StateMarker } from './StateMarker';
import { FEATURES } from '../../config/features';
import { useLabelOcclusionTargets } from '../scene/LabelOcclusion';
import { boundedLabelPosition } from './labelPosition';
import type { ActorRole } from './materials';

/**
 * Where the seated actor sits relative to the desk tile centre.
 *
 * The desk is now a real slab with legs rather than a solid block, so the figure
 * can sit at the front edge without the knees intersecting solid geometry. Reach
 * was measured: at z = -0.95 the shoulder-to-keyboard distance was 0.635 against
 * a 0.539 arm — genuinely unreachable, which is why the arms read as locked
 * straight. At -0.60 the reach is 0.290, giving the elbow room to bend.
 */
const ACTOR_Z = -0.6;

/**
 * The manager's platform raise was removed (Phase H Part 2).
 *
 * It existed to lift the manager's desk above the pods, but the Mixamo
 * sitting-typing clip is shared by all five actors, so a raised manager pushed
 * their hands 0.057 above everyone else's while the keyboard stayed on the
 * common desk plane. The reference shows the manager at an ordinary desk, so
 * the manager now sits on the same floor at the same height as everyone else.
 */
const MANAGER_RAISE = 0;

/** Map a domain actor onto an attire set. */
function roleFor(actor: Actor): ActorRole {
  const mapped = MAPPING_BY_PENTEST_ROLE[actor.role as PentestRole];
  if (mapped) return mapped.deskSlot === 'planner' ? 'ai-manager' : mapped.deskSlot;
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
 * Places one actor at their desk on the floor and attaches the state marker.
 *
 * Every part of the workstation — desk, mat, input, monitors, props — is a child
 * of this one group, which is positioned from the actor's gridPosition via
 * `tileToWorld`. No world coordinate is hardcoded anywhere below: moving an actor
 * in `data/actors.ts` moves the entire workstation with them.
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
  const labelOccluders = useLabelOcclusionTargets();
  const accent = STATE_COLOR[actor.state] ?? COLORS.muted;
  const [wx, wz] = tileToWorld(actor.gridPosition.x, actor.gridPosition.z);
  const role = roleFor(actor);
  const raise = MANAGER_RAISE;
  // Static role dressing never changes with task state or engagement IDs.
  const mapping = MAPPING_BY_PENTEST_ROLE[actor.role as PentestRole];
  const roleIndex = ROLE_DESK_MAPPING.findIndex((entry) => entry.pentestRole === actor.role);
  const variant = roleIndex >= 0 ? roleIndex : Math.round(actor.id.length + actor.gridPosition.x + actor.gridPosition.z);

  const needsAttention = actor.state === 'awaiting_approval' || actor.state === 'blocked';
  const isWorking = actor.state === 'working';

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
    <group position={[wx, raise, wz]} rotation={[0, workstationRotation(actor), 0]} onClick={select} onPointerOver={hoverOn} onPointerOut={hoverOff}>
      <Html position={[0, 1.6, ACTOR_Z]} center calculatePosition={boundedLabelPosition} occlude={labelOccluders} zIndexRange={[12, 1]}>
        <button tabIndex={-1} className="agent-name-tag" title={actor.name} style={{ borderLeftColor: mapping?.accentHex }} aria-label={`Inspect ${actor.name}`} aria-pressed={selected} onClick={(event) => { event.stopPropagation(); onSelect(actor.id); }}>{actor.name}</button>
      </Html>
      {/* D1/D2/D6 — desk */}
      <group
        onClick={select}
        onPointerOver={hoverOn}
        onPointerOut={hoverOff}
      >
        <DeskModel accentHex={mapping?.accentHex} />
      </group>

      {/* One display per workstation, facing its seated worker. */}
      <Monitor actor={actor} />

      {/* D4 — mat + keyboard + mouse */}
      <DeskInput />

      {/* D5 — plant, mug, notebook, pen holder, lamp. The lamp carries a real
          point light (Phase F3) so it reads as a working light source. */}
      <DeskProps variant={variant} lampLight accentHex={mapping?.accentHex} />

      {/* Ground disc: quiet, persistent state cue at the actor's feet */}
      {selected && <mesh position={[0, 0.03, ACTOR_Z - 0.35]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.42, 0.5, 32]} />
        <meshBasicMaterial color={accent} transparent opacity={0.65} />
      </mesh>}

      {/* Figure, facing +Z toward the desk and the room. */}
      <group
        position={[0, 0, ACTOR_Z]}
        onClick={select}
        onPointerOver={hoverOn}
        onPointerOut={hoverOff}
      >
        <Chair />
        <ActorModel role={role} active={isWorking} />
        {needsAttention && FEATURES.attentionBeacon && <AttentionBeacon />}
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
