import React, { useState } from 'react';

import ChampRecherche from '../../composants/ChampRecherche.jsx';
import Panneau from '../../composants/Panneau.jsx';
import { useDonnees } from '../../services/donnees.jsx';
import {
  Button, DataTable, Dialog, EmptyState, Field, LevelBadge, Select, TextInput,
} from '../../systeme.js';

/** Administration des équipements : fiche, criticité, seuils, maintenance. */
export default function Equipements() {
  const D = useDonnees();
  const [recherche, setRecherche] = useState('');
  const [modifie, setModifie] = useState(null);      // équipement en cours de modification
  const [brouillon, setBrouillon] = useState({});

  const lignes = D.equipements.filter((e) => {
    const texte = `${e.id} ${e.nom} ${e.famille} zone ${e.zone}`.toLowerCase();
    return texte.includes(recherche.toLowerCase());
  });

  const ouvrir = (equipement) => {
    setModifie(equipement);
    setBrouillon({
      criticite: String(equipement.criticite),
      seuilInspection: String(equipement.seuilInspection),
      seuilUrgence: String(equipement.seuilUrgence),
    });
  };

  const enregistrer = () => {
    // Les modifications sont locales tant que le service correspondant n'existe
    // pas côté serveur ; elles montrent le parcours complet.
    Object.assign(modifie, {
      criticite: Number(brouillon.criticite),
      seuilInspection: Number(brouillon.seuilInspection),
      seuilUrgence: Number(brouillon.seuilUrgence),
    });
    setModifie(null);
  };

  const incoherent = Number(brouillon.seuilInspection) >= Number(brouillon.seuilUrgence);

  return (
    <div className="onglet-contenu">
      <Panneau
        titre="Équipements surveillés"
        complement={`${lignes.length} sur ${D.equipements.length}`}
        actions={<ChampRecherche valeur={recherche} surChangement={setRecherche} />}
      >
        <DataTable
          rowKey="id"
          rows={lignes}
          columns={[
            { key: 'niveau', label: 'Niveau', width: 130,
              render: (e) => <LevelBadge level={e.niveau} size="sm" /> },
            { key: 'id', label: 'Identifiant', width: 140 },
            { key: 'nom', label: 'Équipement' },
            { key: 'zone', label: 'Zone', width: 70, numeric: true, align: 'right' },
            { key: 'famille', label: 'Famille', width: 180,
              render: (e) => D.familles[e.famille] },
            { key: 'criticite', label: 'Criticité', width: 90, numeric: true, align: 'right',
              render: (e) => `${e.criticite}/3` },
            { key: 'plage', label: 'Plage normale', width: 140, align: 'right',
              render: (e) => `${e.plageBasse} à ${e.plageHaute} °C` },
            { key: 'seuils', label: 'Seuils', width: 150, align: 'right',
              render: (e) => `${e.seuilInspection} / ${e.seuilUrgence} °C` },
            { key: 'actions', label: '', width: 120, render: (e) => (
              <Button size="sm" variant="quiet"
                onClick={(evenement) => { evenement.stopPropagation(); ouvrir(e); }}>
                Modifier
              </Button>
            ) },
          ]}
          empty={<EmptyState title="Aucun équipement ne correspond" tone="neutral">
            Essayez un autre mot, ou effacez la recherche.
          </EmptyState>}
        />
      </Panneau>

      <Dialog
        open={Boolean(modifie)}
        title={modifie ? `Modifier ${modifie.id}` : ''}
        confirmLabel="Enregistrer"
        cancelLabel="Annuler"
        confirmDisabled={incoherent}
        onCancel={() => setModifie(null)}
        onConfirm={enregistrer}
      >
        <Field label="Criticité" hint="1 : faible · 2 : moyenne · 3 : élevée" required>
          <Select value={brouillon.criticite}
            onChange={(e) => setBrouillon({ ...brouillon, criticite: e.target.value })}>
            <option value="1">1 sur 3</option>
            <option value="2">2 sur 3</option>
            <option value="3">3 sur 3</option>
          </Select>
        </Field>
        <Field label="Seuil d’inspection (°C)" required>
          <TextInput type="number" value={brouillon.seuilInspection}
            onChange={(e) => setBrouillon({ ...brouillon, seuilInspection: e.target.value })} />
        </Field>
        <Field
          label="Seuil d’urgence (°C)"
          required
          error={incoherent ? 'Le seuil d’urgence doit être supérieur au seuil d’inspection.'
            : undefined}
        >
          <TextInput type="number" value={brouillon.seuilUrgence}
            onChange={(e) => setBrouillon({ ...brouillon, seuilUrgence: e.target.value })} />
        </Field>
        <p className="note">
          Ces seuils sont le filet de sécurité : ils s’appliquent même pendant la
          période d’apprentissage.
        </p>
      </Dialog>
    </div>
  );
}
