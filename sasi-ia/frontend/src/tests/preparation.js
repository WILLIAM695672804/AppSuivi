// Préparation des tests d'interface.
//
// Les composants du système visuel arrivent normalement par un script qui
// dépose « window.SASI ». Dans les tests, on les remplace par des composants
// très simples : on vérifie nos écrans, pas la bibliothèque du designer.

import '@testing-library/jest-dom/vitest';
import React from 'react';

const simple = (balise, classe) => function Composant({ children, label, title, value, ...reste }) {
  return React.createElement(balise, { className: classe, ...reste },
    label ?? title ?? value ?? children);
};

window.SASI = {
  Button: function Button({ children, ...reste }) {
    return React.createElement('button', { type: 'button', ...reste }, children);
  },
  LevelBadge: function LevelBadge({ level }) {
    return React.createElement('span', { 'data-niveau': level }, level);
  },
  AlertCard: function AlertCard({ equipment, reason, onOpen }) {
    return React.createElement('article', { onClick: onOpen },
      React.createElement('h3', null, equipment),
      React.createElement('p', null, reason));
  },
  DataTable: function DataTable({ columns, rows, rowKey = 'id', onRowOpen, empty }) {
    if (!rows.length) return empty ?? null;
    return React.createElement('table', null,
      React.createElement('thead', null,
        React.createElement('tr', null,
          columns.map((c) => React.createElement('th', { key: c.key }, c.label)))),
      React.createElement('tbody', null,
        rows.map((ligne) => React.createElement('tr', {
          key: ligne[rowKey], onClick: () => onRowOpen?.(ligne),
        }, columns.map((c) => React.createElement('td', { key: c.key },
          c.render ? c.render(ligne) : String(ligne[c.key] ?? '')))))));
  },
  TemperatureChart: function TemperatureChart({ series }) {
    return React.createElement('figure', { 'data-series': series.length }, 'courbe');
  },
  StatusBanner: function StatusBanner({ title, children }) {
    return React.createElement('aside', null, title, ' ', children);
  },
  Dialog: function Dialog({ open, title, children, onConfirm, confirmLabel = 'Confirmer',
    confirmDisabled }) {
    if (!open) return null;
    return React.createElement('div', { role: 'dialog', 'aria-label': title },
      children,
      React.createElement('button', { type: 'button', onClick: onConfirm,
        disabled: confirmDisabled }, confirmLabel));
  },
  Field: function Field({ label, error, children }) {
    return React.createElement('label', null, label, children,
      error ? React.createElement('span', { role: 'alert' }, error) : null);
  },
  // « input » est une balise sans contenu : la valeur passe par un attribut.
  TextInput: function TextInput({ label, ...reste }) {
    return React.createElement('input', { className: 'champ', 'aria-label': label, ...reste });
  },
  Textarea: function Textarea({ label, ...reste }) {
    return React.createElement('textarea', { className: 'champ', 'aria-label': label, ...reste });
  },
  Select: function Select({ children, ...reste }) {
    return React.createElement('select', reste, children);
  },
  Checkbox: function Checkbox({ label, ...reste }) {
    return React.createElement('label', null,
      React.createElement('input', { type: 'checkbox', ...reste }), label);
  },
  EmptyState: function EmptyState({ title, children, action }) {
    return React.createElement('div', null, React.createElement('h3', null, title),
      children, action);
  },
  Chip: function Chip({ label, selected, ...reste }) {
    return React.createElement('button', { type: 'button', 'aria-pressed': selected, ...reste },
      label);
  },
  StatCard: function StatCard({ label, value, unit }) {
    return React.createElement('div', null,
      React.createElement('span', null, label),
      React.createElement('strong', null, `${value}${unit ? ` ${unit}` : ''}`));
  },
  LEVELS: ['normal', 'information', 'surveillance', 'inspection', 'urgence'],
  LEVEL_LABEL: {
    normal: 'Normal', information: 'Information', surveillance: 'Surveillance',
    inspection: 'Inspection', urgence: 'Urgence',
  },
  STATE_LABEL: {
    ouverte: 'Ouverte', acquittee: 'Acquittée', assignee: 'Assignée', cloturee: 'Clôturée',
  },
  formatTemperature: (valeur, decimales = 1) => (valeur === null || valeur === undefined
    ? '—' : Number(valeur).toFixed(decimales).replace('.', ',')),
};
