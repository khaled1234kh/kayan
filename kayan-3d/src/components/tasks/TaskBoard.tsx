/**
 * TaskBoard — four-column Kanban board (Todo / In Progress / Blocked / Done).
 *
 * Fetches tasks via GET /api/companies/{id}/tasks and renders task cards
 * in each column. Column headers and cards are abstract shapes — no readable
 * text at 3D distance. Colours update in real time as the reducer changes.
 */
import { useEffect, useState } from 'react';
import { COLORS } from '../../data/layout';
import type { Task } from '../../types';

const COLUMNS = ['todo', 'in-progress', 'blocked', 'done'];
const COLUMN_LABELS = ['Todo', 'In Progress', 'Blocked', 'Done'];
const COLUMN_COLORS = [
  '#1FB8C4', // teal
  '#1FB8C4', // teal
  '#F5A623', // orange (blocked)
  '#8FD4B8', // mint (done)
];

export function TaskBoard({ companyId }: { companyId: string }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/companies/${companyId}/tasks`)
      .then((r) => r.json())
      .then((data) => {
        setTasks(data as Task[]);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [companyId]);

  const columnFor = (task: Task) => {
    if (task.status === 'blocked') return 'blocked';
    if (task.status === 'completed') return 'done';
    return 'todo';
  };

  const statusFor = (task: Task) => {
    if (task.status === 'blocked') return 'blocked';
    if (task.status === 'completed') return 'completed';
    return 'open';
  };

  const colorFor = (status: string) => {
    if (status === 'blocked') return '#F5A623';
    if (status === 'completed') return '#8FD4B8';
    return '#1FB8C4';
  };

  const chipLabel = (status: string) => {
    if (status === 'blocked') return 'Blocked';
    if (status === 'completed') return 'Done';
    return 'Open';
  };

  if (loading) return React.createElement('div', null, 'Loading tasks…');

  const renderTask = (task: Task) => {
    const s = columnFor(task);
    const label = chipLabel(statusFor(task));
    const bg = colorFor(statusFor(task));
    const assignee =
      task.participants.length > 0
        ? participantsText(task)
        : 'Unassigned';
    const assigneeHtml =
      'Unassigned' === participantsText(task)
        ? 'Unassigned'
        : `${participantsText(task)} — ${getStatusLabel(columnFor(task))}`;
    const budgetHtml = 'Budget: ' + task.cost;
    const evidenceHtml = 'Evidence: ' + task.artifacts.length;
    const actions =
      task.status === 'open'
        ? 'Approve Reject Ask for info'
        : task.status !== 'completed'
          ? 'Ask for info'
          : '';

    // Build the card HTML string
    const cardHtml = [
      '<div class="task-card" style="background:' + bg + '; color: #F5F0E6" title="' +
        task.title +
        '">',
      '<div class="task-title">' + task.title + '</div>',
      '<div class="task-meta">',
      '<span class="assignee">' + participantsText(task) + '</span>',
      '<span class="chip">' + chipLabel + '</span>',
      '<span class="budget">Budget: ' + task.cost + '</span>',
      '<span class="evidence">Evidence: ' + task.artifacts.length + '</span>',
      '<div class="task-actions">' +
        (task.status === 'open'
          ? 'Approve Reject Ask for info'
          : task.status !== 'completed'
            ? 'Ask for info'
            : '')
        .split(' ')
        .map(function (action) {
          return '<span class="action ' + action + '">' + action + '</span>';
        }).join(''),
      '</div>',
      '</div>'
    ].join('');

    return React.createElement('div', { className: 'task-card', style: { background: bg, color: '#F5F0E6' }, title: task.title }, cardHtml);
  };

  function participantsText(t: Task) {
    if (t.participants.length > 0) {
      var p = t.participants[0];
      return p + ' — ' + getStatusLabel(columnFor(t));
    }
    return 'Unassigned';
  }

  function getStatusLabel(s) {
    if (s === 'open') return 'Open';
    if (s === 'blocked') return 'Blocked';
    if (s === 'completed') return 'Done';
    return s;
  }

  if (loading) return React.createElement('div', null, 'Loading tasks…');

  return React.createElement(
    'div',
    { className: 'task-board' },
    COLUMNS.map(function (col) {
      var idx = COLUMNS.indexOf(col);
      return React.createElement(
        'div',
        { key: col, className: 'task-column' },
        React.createElement(
          'div',
          { className: 'task-column-header', style: {
            borderColor: COLUMN_COLORS[idx],
            color: COLUMN_COLORS[idx],
          } },
          React.createElement('span', { className: 'header-label' }, COLUMN_LABELS[idx])
        ),
        React.createElement(
          'div',
          { className: 'task-cards' },
          tasks
            .filter(function (t) {
              return columnFor(t) === col;
            })
            .map(renderTask)
        )
      );
    })
  );
}