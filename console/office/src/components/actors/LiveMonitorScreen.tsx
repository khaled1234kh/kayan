import { useEffect, useMemo } from 'react';
import { CanvasTexture, LinearFilter, SRGBColorSpace } from 'three';
import type { Actor } from '../../types';
import { DISPLAY_SIDE, DISPLAY_SIZE } from './monitorGeometry';
import { monitorTextLines } from './monitorText';

/** GPU depth-tested, front-facing display. The monitor back is solid casing. */
export { DISPLAY_SIDE } from './monitorGeometry';

function wrap(context: CanvasRenderingContext2D, text: string, x: number, y: number, width: number, maxLines: number) {
  monitorTextLines(text, value => context.measureText(value).width, width, maxLines)
    .forEach((line, row) => context.fillText(line, x, y + row * 34));
}

export function LiveMonitorScreen({ actor }: { actor: Actor }) {
  const texture = useMemo(() => {
    const canvas = document.createElement('canvas'); canvas.width = 560; canvas.height = 330;
    const result = new CanvasTexture(canvas); result.colorSpace = SRGBColorSpace;
    result.minFilter = LinearFilter; result.magFilter = LinearFilter; result.generateMipmaps = false;
    return result;
  }, []);
  useEffect(() => {
    const canvas = texture.image as HTMLCanvasElement;
    const context = canvas.getContext('2d'); if (!context) return;
    const hasSession = Boolean(actor.backendAgentId);
    context.fillStyle = '#071018'; context.fillRect(0, 0, 560, 330);
    context.fillStyle = '#E8EFE9'; context.font = '600 27px system-ui';
    wrap(context, actor.name, 22, 44, 378, 1);
    context.strokeStyle = '#5C6F65'; context.strokeRect(422, 16, 112, 38);
    context.font = '22px system-ui'; context.fillText('Tier ' + (actor.modelTier ?? '—'), 436, 43);
    context.fillStyle = actor.state === 'working' ? '#3FAE7A' : actor.state === 'blocked' ? '#D9544F' : '#8FA399';
    context.beginPath(); context.arc(31, 89, 7, 0, Math.PI * 2); context.fill();
    context.font = '22px system-ui'; context.fillText(hasSession ? actor.state.toUpperCase() : 'IDLE · NO LIVE SESSION', 50, 96);
    context.strokeStyle = '#28372F'; context.beginPath(); context.moveTo(22, 115); context.lineTo(538, 115); context.stroke();
    context.fillStyle = '#E8EFE9'; context.font = '600 29px system-ui';
    wrap(context, hasSession ? actor.currentTask ?? 'No active task' : 'Waiting for engagement', 22, 158, 516, 2);
    context.fillStyle = '#8FA399'; context.font = '21px system-ui';
    wrap(context, hasSession ? actor.activity : 'No activity received', 22, 248, 516, 2);
    texture.needsUpdate = true;
  }, [texture, actor.name, actor.modelTier, actor.state, actor.backendAgentId, actor.currentTask, actor.activity]);
  useEffect(() => () => texture.dispose(), [texture]);
  return <mesh name="monitor-display" position={[0, 0, 0.001]}>
    <planeGeometry args={[...DISPLAY_SIZE]} />
    <meshBasicMaterial map={texture} side={DISPLAY_SIDE} toneMapped={false} depthTest depthWrite />
  </mesh>;
}
