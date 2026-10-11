import React from 'react';
import { formatTemperature } from '../systeme.js';

/**
 * Règle graduée : où se situe la mesure entre sa plage normale et ses seuils.
 * Reprend la maquette de la fiche équipement.
 */
export default function ReglageSeuils({ equipement, mesuree, attendue }) {
  const minimum = Math.min(equipement.plageBasse, mesuree ?? equipement.plageBasse) - 5;
  const maximum = Math.max(equipement.seuilUrgence, mesuree ?? 0) + 5;
  const position = (valeur) => ((valeur - minimum) / (maximum - minimum)) * 100;

  return (
    <div className="regle">
      <div className="regle-barre">
        <span
          className="regle-plage"
          style={{
            left: `${position(equipement.plageBasse)}%`,
            width: `${position(equipement.plageHaute) - position(equipement.plageBasse)}%`,
          }}
        />
        <span className="regle-seuil regle-seuil-inspection"
          style={{ left: `${position(equipement.seuilInspection)}%` }} />
        <span className="regle-seuil regle-seuil-urgence"
          style={{ left: `${position(equipement.seuilUrgence)}%` }} />
        {attendue !== null && attendue !== undefined && (
          <span className="regle-attendue" style={{ left: `${position(attendue)}%` }} />
        )}
        {mesuree !== null && mesuree !== undefined && (
          <span className="regle-mesuree" style={{ left: `${position(mesuree)}%` }} />
        )}
      </div>
      <div className="regle-legende">
        <span>Plage normale {equipement.plageBasse} à {equipement.plageHaute} °C</span>
        <span>Inspection {equipement.seuilInspection} °C</span>
        <span>Urgence {equipement.seuilUrgence} °C</span>
      </div>
      {mesuree !== null && mesuree !== undefined && (
        <p className="regle-mesure">
          Mesurée {formatTemperature(mesuree)} °C
          {attendue !== null && attendue !== undefined
            && ` · attendue ${formatTemperature(attendue)} °C`}
        </p>
      )}
    </div>
  );
}
