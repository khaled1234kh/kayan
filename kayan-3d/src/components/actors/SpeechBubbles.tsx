import { useEffect, useState } from 'react';
import { Html } from '@react-three/drei';
import type { Actor } from '../../types';
import type { AgentMessage } from '../../agents/agentMessages';
import type { CollaborationState } from '../../state/eventReducer';
import { tileToWorld } from '../office/Office';

/**
 * Speech bubbles.
 *
 * When a message is delivered (`agent_message_received`), a small bubble floats
 * above the SENDER's head with the message text. Cues are derived in the reducer
 * (`collaboration.recent`) and never invented here: an event without a matching,
 * seated sender renders nothing. The bubble fades in (200ms), holds (6s) and
 * fades out (400ms) as a plain HTML overlay — not 3D text.
 */

const FADE_IN_MS = 200;
const HOLD_MS = 6000;
const FADE_OUT_MS = 400;
const LIFETIME_MS = FADE_IN_MS + HOLD_MS + FADE_OUT_MS;
const MAX_TEXT = 40;
/** Height above the floor where bubbles float, clear of the state ring. */
const BUBBLE_Y = 2.7;

function truncate(text: string, max: number): string {
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`;
}

function bubbleText(message: AgentMessage): string {
  return truncate(message.instructions ?? message.subject, MAX_TEXT);
}

interface BubbleCue {
  message: AgentMessage;
  actor: Actor;
  deliveredAt: number;
}

function resolveCues(collaboration: CollaborationState, actors: Actor[]): BubbleCue[] {
  const messagesById = new Map(collaboration.messages.map((m) => [m.id, m]));
  const actorsById = new Map(actors.map((a) => [a.id, a]));
  const cues: BubbleCue[] = [];
  for (const rec of collaboration.recent) {
    const message = messagesById.get(rec.messageId);
    if (!message) continue;
    const actor = actorsById.get(message.fromAgentId);
    if (!actor) continue; // external senders have no seat to speak from
    cues.push({ message, actor, deliveredAt: rec.deliveredAt });
  }
  return cues;
}

/** Ticks only while at least one bubble is still on screen, then stops. */
function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(id);
  }, [active]);
  return now;
}

function Bubble({ x, z, age, text }: { x: number; z: number; age: number; text: string }) {
  const [entered, setEntered] = useState(false);

  // Mount at opacity 0, then flip to the visible class next frame so the CSS
  // transition actually animates the fade-in from zero.
  useEffect(() => {
    const raf = requestAnimationFrame(() => setEntered(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  const fadingOut = age > FADE_IN_MS + HOLD_MS;
  const className = `speech-bubble${entered ? ' is-in' : ''}${fadingOut ? ' is-out' : ''}`;

  return (
    <Html position={[x, BUBBLE_Y, z]} center zIndexRange={[40, 0]} style={{ pointerEvents: 'none' }}>
      <div className={className}>{text}</div>
    </Html>
  );
}

export function SpeechBubbles({
  collaboration,
  actors,
}: {
  collaboration: CollaborationState;
  actors: Actor[];
}) {
  const cues = resolveCues(collaboration, actors);
  const active = cues.some((c) => Date.now() - c.deliveredAt < LIFETIME_MS);
  const now = useNow(active);

  return (
    <>
      {cues.map((cue) => {
        const age = now - cue.deliveredAt;
        if (age > LIFETIME_MS) return null;
        const [wx, wz] = tileToWorld(cue.actor.gridPosition.x, cue.actor.gridPosition.z);
        return (
          <Bubble key={cue.message.id} x={wx} z={wz} age={age} text={bubbleText(cue.message)} />
        );
      })}
    </>
  );
}