import React from 'react';

export default function Panneau({ titre, complement, actions, children, className = '' }) {
  return (
    <section className={`panneau ${className}`.trim()}>
      {(titre || actions) && (
        <div className="panneau-entete">
          <h2>
            {titre}
            {complement && <span className="panneau-complement">{complement}</span>}
          </h2>
          {actions && <div className="panneau-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}
