/**
 * TaskDetail — full view of a single task.
 *
 * Shows: description, evidence trail, messages tied to the task,
 * budget reservation and spend, and allowed actions for the current actor
 * (approve, reject, ask for info).
 */
import { useState } from 'react';
import type { Task } from '../../types';

export function TaskDetail({ task }: { task: Task }) {
  var statusName = task.status;
  var budgetText = task.cost ? String(task.cost) : '0';
  var artifactCount = task.artifacts.length;
  var participantsText =
    task.participants.length > 0
      ? task.participants.map(function (p) {
          return p;
        }).join(', ') :
      'Unassigned';

  var detailHtml =
    'Description: ' + task.subject +
    '<br>Artifacts: ' + artifactCount +
    (task.artifacts.length > 0 ? ', ' + task.artifacts.join(', ') : 'none');

  return React.createElement(
    'div',
    { className: 'task-detail-panel' },
    React.createElement('div', { className: 'task-header' },
      React.createElement('span', { className: 'task-title' }, task.title),
      React.createElement('span', { className: 'task-status chip' }, statusName)
    ),
    React.createElement('div', { className: 'task-description' },
      React.createElement('strong', null, 'Description:'),
      task.subject
    ),
    React.createElement('div', { className: 'task-metrics' },
      React.createElement('span', { className: 'budget' }, 'Budget reserved: ' + budgetText),
      React.createElement('span', { className: 'artifacts' }, 'Artifacts: ' + artifactCount),
      React.createElement('span', { className: 'participants' }, 'Participants: ' + participantsText)
    ),
    React.createElement('div', { className: 'task-actions' },
      task.status === 'open' && React.createElement('span', { className: 'action approve' }, 'Approve'),
      task.status === 'open' && React.createElement('span', { className: 'action reject' }, 'Reject'),
      task.status !== 'completed' && React.createElement('span', { className: 'action ask' }, 'Ask for info')
    )
  );
}