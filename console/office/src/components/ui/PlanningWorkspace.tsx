import { lazy, Suspense } from 'react';

// Load the planning journey only when requested; live-office startup stays bounded.
const PlanningPanel=lazy(()=>import('./PlanningPanel').then(module=>({default:module.PlanningPanel})));
export function PlanningWorkspace({onClose}:{onClose:()=>void}) {
  return <Suspense fallback={<div className="workspace-loading" role="status">Opening planning workspace…</div>}><PlanningPanel onClose={onClose}/></Suspense>;
}
