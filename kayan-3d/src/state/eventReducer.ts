import type { Actor, ActorState, Task } from '../types';
import type { KayanEvent } from '../types/events';
import type { AgentMessage } from '../agents/agentMessages';
import type { AgentHandoff } from '../agents/handoffs';
import type { PolicyDecision, SecurityDecisionView } from '../security/policyTypes';
import { AGENT_IDS, isSeat } from '../agents/agentProfiles';
import { SEED_ACTORS } from '../data/actors';
import { useStore } from './useStore';

/**
 * Event reducer â€” the ONLY place business rules live.
 *
 * Actors and 3D components never decide a transition; they render whatever the
 * reducer returns for the events they receive. Because this is a pure function of
 * (state, event), the same event stream replayed from a WebSocket later produces
 * identical results.
 *
 * This file contains NO policy logic. Authorization decisions are made by the
 * TrustGate evaluator and arrive here already resolved inside a
 * `policy_denied` payload; the reducer merely projects them into state.
 *
 * Collaboration state (messages, handoffs, mailboxes) is rebuilt purely from the
 * event stream, so a replay reproduces inboxes and outboxes exactly.
 */

/** Per-agent collaboration state, derived from message events. */
export interface AgentMailboxView {
  /** Message ids received. */
  inbox: string[];
  /** Message ids sent. */
  outbox: string[];
  activeHandoffId: string | null;
  currentTaskId: string | null;
}

export interface CollaborationState {
  /** All agent messages, oldest first. */
  messages: AgentMessage[];
  /** All handoffs, oldest first. */
  handoffs: AgentHandoff[];
  mailboxes: Record<string, AgentMailboxView>;
  /** Speech-bubble cues, newest first; resolved to messages by id. */
  recent: Array<{ messageId: string; deliveredAt: number }>;
}

/** Kanban column for a company task on the task board. */
export type CompanyTaskColumn = 'todo' | 'in_progress' | 'blocked' | 'done';

/**
 * One company task as the board renders it.
 *
 * This mirrors the backend `CompanyTaskOut` shape (`server/app/schemas/company.py`)
 * plus the derived column. It is kept separate from the demo-order `Task`: the
 * order task is created by `order_received` and closed by `task_completed`, while
 * company tasks arrive over `company_task_created` / `company_task_updated` and
 * are also synced from the REST list endpoint, which stays authoritative for
 * values the events do not carry.
 */
export interface CompanyBoardTask {
  id: string;
  companyId: string;
  title: string;
  category: string;
  description: string | null;
  /** Raw backend status string (`open`, `in_progress`, `blocked`, `completed`). */
  status: string;
  column: CompanyTaskColumn;
  employeeId: string;
  createdAt: string | null;
}

export interface DomainState {
  actors: Actor[];
  tasks: Task[];
  /** Company task board mirror, fed by task lifecycle events + REST sync. */
  companyTasks: CompanyBoardTask[];
  /** Latest TrustGate decision, lifted from the event stream for the panel. */
  security: { lastDecision: SecurityDecisionView | null };
  collaboration: CollaborationState;
}

function emptyMailboxes(): Record<string, AgentMailboxView> {
  const out: Record<string, AgentMailboxView> = {};
  AGENT_IDS.forEach((id) => {
    out[id] = { inbox: [], outbox: [], activeHandoffId: null, currentTaskId: null };
  });
  return out;
}

/** Maximum speech-bubble cues kept for rendering, newest first. */
const MAX_RECENT_BUBBLES = 6;

/** Reset point for a fresh run or a replay. */
export function initialDomainState(): DomainState {
  return {
    actors: SEED_ACTORS.map((a) => ({ ...a })),
    tasks: [],
    companyTasks: [],
    security: { lastDecision: null },
    collaboration: { messages: [], handoffs: [], mailboxes: emptyMailboxes(), recent: [] },
  };
}

/**
 * Lifts the TrustGate decision carried by a `policy_denied` payload.
 *
 * Pure extraction: the decision was already made by the evaluator upstream.
 */
function readDecision(
  payload: Record<string, unknown> | undefined,
  timestamp: number,
): SecurityDecisionView | null {
  const raw = payload?.policyDecision as PolicyDecision | undefined;
  if (!raw || typeof raw.decision !== 'string') return null;
  return {
    decision: raw.decision === 'allow' ? 'allow' : 'deny',
    policy: raw.policy,
    subject: raw.subject,
    action: raw.action,
    resource: raw.resource,
    reason: raw.reason,
    timestamp,
  };
}

function str(payload: Record<string, unknown> | undefined, key: string): string | undefined {
  const v = payload?.[key];
  return typeof v === 'string' ? v : undefined;
}

function num(payload: Record<string, unknown> | undefined, key: string): number | undefined {
  const v = payload?.[key];
  return typeof v === 'number' ? v : undefined;
}

function ids(payload: Record<string, unknown> | undefined, key: string): string[] {
  const v = payload?.[key];
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [];
}

/** Move one actor to a new state, optionally updating its activity line. */
function setActorState(
  actors: Actor[],
  actorId: string | undefined,
  state: ActorState,
  activity: string | undefined,
  taskId: string | undefined,
): Actor[] {
  if (!actorId) return actors;
  return actors.map((a) =>
    a.id === actorId
      ? {
          ...a,
          state,
          activity: activity ?? a.activity,
          taskId: taskId ?? a.taskId,
        }
      : a,
  );
}

function mapTask(tasks: Task[], taskId: string | undefined, fn: (t: Task) => Task): Task[] {
  if (!taskId) return tasks;
  return tasks.map((t) => (t.id === taskId ? fn(t) : t));
}

/** Backend company-task status → Kanban column. Unknown values keep the card put. */
export function columnForCompanyStatus(status: string | undefined, fallback: CompanyTaskColumn): CompanyTaskColumn {
  switch (status) {
    case 'open':
      return 'todo';
    case 'in_progress':
      return 'in_progress';
    case 'blocked':
      return 'blocked';
    case 'completed':
      return 'done';
    default:
      return fallback;
  }
}

function upsertCompanyTask(
  tasks: CompanyBoardTask[],
  incoming: CompanyBoardTask,
): CompanyBoardTask[] {
  const idx = tasks.findIndex((t) => t.id === incoming.id);
  if (idx === -1) return [...tasks, incoming];
  const next = [...tasks];
  next[idx] = incoming;
  return next;
}

function mapCompanyTask(
  tasks: CompanyBoardTask[],
  taskId: string | undefined,
  fn: (t: CompanyBoardTask) => CompanyBoardTask,
): CompanyBoardTask[] {
  if (!taskId) return tasks;
  return tasks.map((t) => (t.id === taskId ? fn(t) : t));
}

/**
 * Reads a typed AgentMessage out of an event payload.
 *
 * The runtime stores the object under `agentMessage`; `message` carries the human
 * headline, so both are checked and the object shape is verified.
 */
function readMessage(payload: Record<string, unknown> | undefined): AgentMessage | null {
  const candidates = [payload?.agentMessage, payload?.message];
  for (const c of candidates) {
    if (c && typeof c === 'object' && typeof (c as AgentMessage).id === 'string') {
      return c as AgentMessage;
    }
  }
  return null;
}

/** Reads a typed AgentHandoff out of an event payload. */
function readHandoff(payload: Record<string, unknown> | undefined): AgentHandoff | null {
  const h = payload?.handoff as AgentHandoff | undefined;
  return h && typeof h.id === 'string' ? h : null;
}

/**
 * Actor states implied by a message being sent. This is collaboration policy,
 * so it belongs to the reducer rather than the runtime.
 */
function applyMessageToActors(actors: Actor[], message: AgentMessage): Actor[] {
  const activity = message.instructions ?? message.subject;
  switch (message.type) {
case 'instruction':
      // An outside instruction prompts work; whether it may proceed is decided by
      // TrustGate on the intent that follows.
      return setActorState(actors, message.toAgentId, 'working', activity, taskIdOf(message));
    case 'handoff':
    case 'task':
      return setActorState(actors, message.toAgentId, 'working', activity, taskIdOf(message));
    case 'question':
      // Sender is blocked on the answer; recipient must respond.
      return setActorState(
        setActorState(actors, message.fromAgentId, 'waiting', `Waiting on ${message.toAgentId}`, taskIdOf(message)),
        message.toAgentId,
        'working',
        activity,
        taskIdOf(message),
      );
    case 'response':
      return setActorState(
        setActorState(actors, message.fromAgentId, 'working', activity, taskIdOf(message)),
        message.toAgentId,
        'working',
        activity,
        taskIdOf(message),
      );
    case 'approval_request':
      return setActorState(
        setActorState(actors, message.fromAgentId, 'waiting', 'Waiting for approval', taskIdOf(message)),
        message.toAgentId,
        'awaiting_approval',
        activity,
        taskIdOf(message),
      );
    case 'approval_response':
      return setActorState(
        setActorState(actors, message.fromAgentId, 'working', activity, taskIdOf(message)),
        message.toAgentId,
        'working',
        activity,
        taskIdOf(message),
      );
    default:
      return actors;
  }
}

function taskIdOf(message: AgentMessage): string | undefined {
  const t = message.context?.taskId;
  return typeof t === 'string' ? t : undefined;
}

function upsertHandoff(handoffs: AgentHandoff[], incoming: AgentHandoff): AgentHandoff[] {
  const idx = handoffs.findIndex((h) => h.id === incoming.id);
  if (idx === -1) return [...handoffs, incoming];
  const next = [...handoffs];
  next[idx] = incoming;
  return next;
}

export function reduce(state: DomainState, event: KayanEvent): DomainState {
  const { type, actorId, taskId, payload, timestamp } = event;
  const message = str(payload, 'message');

  switch (type) {
    /* ---- order lifecycle ------------------------------------------------ */

    case 'order_received': {
      // A new order resets every seat to idle and opens a task record.
      const participants = ids(payload, 'participants');
      const task: Task = {
        id: taskId ?? 'task',
        title: str(payload, 'title') ?? 'Customer order',
        subject: str(payload, 'subject') ?? '',
        status: 'open',
        participants: participants.length ? participants : state.actors.map((a) => a.id),
        artifacts: [],
        cost: 0,
      };
      const actors = state.actors.map((a) => ({
        ...a,
        state: 'idle' as ActorState,
        taskId: task.id,
        activity: str(payload, 'activity') ?? 'Standing by',
      }));
      return {
        actors,
        tasks: [...state.tasks.filter((t) => t.id !== task.id), task],
        companyTasks: state.companyTasks,
        security: state.security, collaboration: state.collaboration,
      };
    }

case 'task_completed': {
      // A `task_completed` carrying a handoff closes that handoff; otherwise it
      // closes the whole order.
      const handoff = readHandoff(payload);
      if (handoff) {
        return {
          ...state,
          collaboration: {
            ...state.collaboration,
            handoffs: upsertHandoff(state.collaboration.handoffs, {
              ...handoff,
              status: 'completed',
            }),
            mailboxes: {
              ...state.collaboration.mailboxes,
              [handoff.toAgentId]: {
                ...(state.collaboration.mailboxes[handoff.toAgentId] ?? {
                  inbox: [],
                  outbox: [],
                  activeHandoffId: null,
                  currentTaskId: null,
                }),
                activeHandoffId: null,
              },
            },
          },
        };
      }
      const participants = state.tasks.find((t) => t.id === taskId)?.participants ?? [];
      const actors = participants.length
        ? state.actors.map((a) =>
            participants.includes(a.id)
              ? { ...a, state: 'completed' as ActorState, activity: message ?? 'Task complete' }
              : a,
          )
        : state.actors;
      return {
        actors,
        tasks: mapTask(state.tasks, taskId, (t) => ({ ...t, status: 'completed' })),
        companyTasks: state.companyTasks,
        security: state.security, collaboration: state.collaboration,
      };
    }

    case 'rejected':
      return {
        actors: setActorState(state.actors, actorId, 'blocked', message, taskId),
        tasks: mapTask(state.tasks, taskId, (t) => ({ ...t, status: 'blocked' })),
        companyTasks: state.companyTasks,
        security: state.security, collaboration: state.collaboration,
      };

    /* ---- planning -------------------------------------------------------- */

    case 'plan_proposed':
    case 'plan_validated':
    case 'task_assigned':
      // Metadata only: no actor state transition.
      return { ...state };

    /* ---- execution ------------------------------------------------------- */

    case 'task_started':
      return {
        ...state,
        actors: setActorState(state.actors, actorId, 'working', message, taskId),
        // Resuming work reopens a task that a denial had blocked.
        tasks: mapTask(state.tasks, taskId, (t) =>
          t.status === 'blocked' ? { ...t, status: 'open' } : t,
        ),
      };

    case 'awaiting_info':
      return {
        ...state,
        actors: setActorState(state.actors, actorId, 'waiting', message, taskId),
      };

    case 'information_provided':
      return {
        ...state,
        actors: setActorState(state.actors, actorId, 'working', message, taskId),
      };

    case 'blocked':
      return {
        ...state,
        actors: setActorState(state.actors, actorId, 'blocked', message, taskId),
        tasks: mapTask(state.tasks, taskId, (t) => ({ ...t, status: 'blocked' })),
      };

    case 'policy_denied':
      // The gate already refused; this only records the outcome.
      return {
        ...state,
        actors: setActorState(state.actors, actorId, 'blocked', message, taskId),
        tasks: mapTask(state.tasks, taskId, (t) => ({ ...t, status: 'blocked' })),
        security: { lastDecision: readDecision(payload, timestamp) ?? state.security.lastDecision },
      };

    /* ---- agent collaboration --------------------------------------------- */

case 'agent_message_sent': {
      const message = readMessage(payload);
      if (!message) return state;
      const tid = taskIdOf(message);
      // Only seated agents keep mailboxes; external senders do not.
      const mailboxes = { ...state.collaboration.mailboxes };
      if (isSeat(message.fromAgentId)) {
        const from = mailboxes[message.fromAgentId];
        mailboxes[message.fromAgentId] = {
          ...from,
          outbox: [...from.outbox, message.id],
        };
      }
      if (isSeat(message.toAgentId)) {
        const to = mailboxes[message.toAgentId];
        mailboxes[message.toAgentId] = {
          ...to,
          inbox: [...to.inbox, message.id],
          currentTaskId: tid ?? to.currentTaskId,
        };
      }
      return {
        ...state,
        actors: applyMessageToActors(state.actors, message),
        collaboration: {
          messages: [...state.collaboration.messages, message],
          handoffs: state.collaboration.handoffs,
          mailboxes,
          recent: state.collaboration.recent,
        },
      };
    }

case 'agent_message_received': {
      const messageId = str(payload, 'messageId');
      if (!messageId) return state;
      const messages = state.collaboration.messages.map((m) =>
        m.id === messageId ? { ...m, delivered: true } : m,
      );
      // A bubble cue is raised only when this event actually flips a pending
      // message to delivered, so a stream replay never re-pops the same bubble.
      const flipped = state.collaboration.messages.some((m) => m.id === messageId && !m.delivered);
      const recent = flipped
        ? [{ messageId, deliveredAt: timestamp }, ...state.collaboration.recent].slice(0, MAX_RECENT_BUBBLES)
        : state.collaboration.recent;
      return {
        ...state,
        collaboration: {
          ...state.collaboration,
          messages,
          recent,
        },
      };
    }

    case 'task_delegated': {
      const handoff = readHandoff(payload);
      if (!handoff) return state;
      return {
        ...state,
        collaboration: {
          ...state.collaboration,
          handoffs: upsertHandoff(state.collaboration.handoffs, handoff),
        },
      };
    }

    case 'task_accepted': {
      const handoff = readHandoff(payload);
      if (!handoff) return state;
      return {
        ...state,
        actors: setActorState(state.actors, handoff.toAgentId, 'working', handoff.objective, handoff.taskId),
        collaboration: {
          messages: state.collaboration.messages,
          handoffs: upsertHandoff(state.collaboration.handoffs, { ...handoff, status: 'accepted' }),
          mailboxes: {
            ...state.collaboration.mailboxes,
            [handoff.toAgentId]: {
              ...(state.collaboration.mailboxes[handoff.toAgentId] ?? {
                inbox: [],
                outbox: [],
                activeHandoffId: null,
                currentTaskId: null,
              }),
              activeHandoffId: handoff.id,
              currentTaskId: handoff.taskId,
            },
          },
          recent: state.collaboration.recent,
        },
      };
    }

    case 'task_handoff':
    case 'information_requested':
    case 'agent_question':
    case 'agent_response':
    case 'approval_response':
      // These are the semantic, feed-facing counterparts of a message that was
      // already recorded by `agent_message_sent`; no extra state is needed.
      return state;

    /* ---- artifacts and cost --------------------------------------------- */

    case 'artifact_created': {
      const artifact = str(payload, 'artifact');
      return {
        ...state,
        tasks: mapTask(state.tasks, taskId, (t) =>
          artifact && !t.artifacts.includes(artifact)
            ? { ...t, artifacts: [...t.artifacts, artifact] }
            : t,
        ),
      };
    }

    case 'cost_metered': {
      const amount = num(payload, 'amount') ?? 0;
      return {
        ...state,
        tasks: mapTask(state.tasks, taskId, (t) => ({ ...t, cost: t.cost + amount })),
      };
    }

    /* ---- approval -------------------------------------------------------- */

    case 'approval_requested':
      return {
        ...state,
        actors: setActorState(state.actors, actorId, 'awaiting_approval', message, taskId),
        tasks: mapTask(state.tasks, taskId, (t) =>
          t.status === 'open' ? { ...t, status: 'awaiting_approval' } : t,
        ),
      };

    case 'approved':
      return {
        ...state,
        actors: setActorState(state.actors, actorId, 'working', message, taskId),
      };

/* ---- company lifecycle (P0) ------------------------------------------- */

    case 'company_activated': {
      // Replace canonical actors with configured company roster
      const activeCompany = useStore.getState().activeCompany;
      if (activeCompany && activeCompany.employees.length > 0) {
        const actors = activeCompany.employees.map((emp, _index) => ({
          id: emp.id,
          name: emp.displayName,
          role: emp.roleKey,
          kind: emp.kind,
          authority: `${emp.kind === 'human' ? 'Human' : 'AI'} — ${emp.roleKey}`,
          gridPosition: emp.gridPosition,
          zoneId: emp.zoneId,
          state: 'idle' as ActorState,
          taskId: null,
          activity: 'Standing by',
        }));
        return {
          ...state,
          actors,
        };
      }
      return state;
    }

    case 'company_paused':
    case 'company_resumed': {
      // Status changes don't affect actors directly
      return state;
    }

    /* ---- company task board -------------------------------------------- */

    case 'company_task_created': {
      // TaskCreated → a new card lands in Todo.
      const id = event.taskId ?? str(payload, 'taskId');
      if (!id) return state;
      const status = str(payload, 'status') ?? 'open';
      const task: CompanyBoardTask = {
        id,
        companyId: str(payload, 'companyId') ?? '',
        title: str(payload, 'title') ?? 'Untitled task',
        category: str(payload, 'category') ?? '',
        description: str(payload, 'description') ?? null,
        status,
        column: columnForCompanyStatus(status, 'todo'),
        employeeId: str(payload, 'employeeId') ?? '',
        createdAt: null,
      };
      return { ...state, companyTasks: upsertCompanyTask(state.companyTasks, task) };
    }

    case 'company_task_updated': {
      // TaskAssigned keeps the card in its column and updates the assignee;
      // TaskStarted / TaskBlocked / TaskCompleted relocate it when the new
      // status value is known. The backend update event carries `changedFields`
      // without values, so a bare status change is resolved by the board's REST
      // refresh — the reducer never guesses a value it was not given.
      const id = event.taskId ?? str(payload, 'taskId');
      if (!id) return state;
      const nextStatus = str(payload, 'status');
      const nextAssignee = str(payload, 'employeeId');
      const nextTitle = str(payload, 'title');
      const nextCategory = str(payload, 'category');
      const nextDescription = str(payload, 'description');
      if (
        nextStatus === undefined &&
        nextAssignee === undefined &&
        nextTitle === undefined &&
        nextCategory === undefined &&
        nextDescription === undefined
      ) {
        return state;
      }
      return {
        ...state,
        companyTasks: mapCompanyTask(state.companyTasks, id, (t) => ({
          ...t,
          title: nextTitle ?? t.title,
          category: nextCategory ?? t.category,
          description: nextDescription ?? t.description,
          status: nextStatus ?? t.status,
          column: nextStatus !== undefined ? columnForCompanyStatus(nextStatus, t.column) : t.column,
          employeeId: nextAssignee ?? t.employeeId,
        })),
      };
    }

    /* ---- default ---------------------------------------------------------- */

    default:
      return state;
  }
}


