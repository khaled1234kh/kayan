/**
 * TaskCard — one task displayed inside a TaskBoard column.
 *
 * Shows: title, assignee (name + role), status chip, budget consumed,
 * evidence count. Clicking opens the detail panel.
 */
import type { Task } from '../../types';

export function TaskCard({ task }: { task: Task }) {
  var statusFor = task.status;
  var STATUS_LABELS = { open: 'Open', awaiting_approval: 'Awaiting Approval', blocked: 'Blocked', completed: 'Done' };
  var chipLabel =
    statusFor === 'blocked'
      ? 'Blocked'
      : statusFor === 'completed'
        ? 'Done'
        : statusFor === 'awaiting_approval'
          ? 'Awaiting Approval'
          : 'Open';

  var assigneeText =
    task.participants.length > 0
      ? task.participants[0] + ' — ' + STATUS_LABELS[statusFor]
      : 'Unassigned';

  var budgetText = task.cost ? String(task.cost) : '0';
  var artifactCount = task.artifacts.length;

  return (
    <div className="task-card" style={{ cursor: 'pointer' }} onClick={() => {}} title={task.title}>
      {task.title}
      <div className="task-assignee">{assigneeText}</div>
      <div className="task-chip">{chipLabel}</div>
      <div className="task-budget">Budget: {budgetText}</div>
      <div className="task-evidence">Evidence: {artifactCount}</div>
      <div className="task-detail">Details: {task.subject} {artifactCount}</div>
    </div>
  );
}