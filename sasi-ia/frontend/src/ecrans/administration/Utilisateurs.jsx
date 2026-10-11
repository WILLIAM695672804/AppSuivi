import React, { useState } from 'react';

import Panneau from '../../composants/Panneau.jsx';
import { useDonnees } from '../../services/donnees.jsx';
import { abonnements as abonnementsExemple, utilisateurs as utilisateursExemple }
  from '../../services/donneesUtilisateurs.js';
import { ROLES } from '../../services/session.js';
import {
  Button, Checkbox, DataTable, Dialog, EmptyState, Field, LEVEL_LABEL, LevelBadge,
  NIVEAUX, Select, TextInput,
} from '../../systeme.js';

const HEURES = Array.from({ length: 25 }, (_, i) => i);

export default function Utilisateurs() {
  const D = useDonnees();
  const [utilisateurs, setUtilisateurs] = useState(utilisateursExemple);
  const [abonnements, setAbonnements] = useState(abonnementsExemple);
  const [modifie, setModifie] = useState(null);
  const [aDesactiver, setADesactiver] = useState(null);
  const [brouillon, setBrouillon] = useState({});

  const ouvrir = (utilisateur) => {
    setModifie(utilisateur);
    setBrouillon({ ...utilisateur });
  };

  const enregistrer = () => {
    setUtilisateurs(utilisateurs.map(
      (u) => (u.identifiant === modifie.identifiant ? { ...u, ...brouillon } : u)));
    setModifie(null);
  };

  const desactiver = () => {
    setUtilisateurs(utilisateurs.map(
      (u) => (u.identifiant === aDesactiver.identifiant ? { ...u, actif: false } : u)));
    setADesactiver(null);
  };

  const modifierAbonnement = (id, champ, valeur) => setAbonnements(abonnements.map(
    (a) => (a.id === id ? { ...a, [champ]: valeur } : a)));

  const nom = (identifiant) => utilisateurs.find((u) => u.identifiant === identifiant)?.nom
    ?? identifiant;

  return (
    <div className="onglet-contenu">
      <Panneau titre="Utilisateurs" complement={`${utilisateurs.length} comptes`}>
        <DataTable
          rowKey="identifiant"
          rows={utilisateurs}
          columns={[
            { key: 'nom', label: 'Nom' },
            { key: 'identifiant', label: 'Identifiant', width: 150,
              render: (u) => <span className="cellule-forte">{u.identifiant}</span> },
            { key: 'role', label: 'Rôle', width: 200,
              render: (u) => ROLES[u.role]?.libelle ?? u.role },
            { key: 'telephone', label: 'Téléphone', width: 200,
              render: (u) => u.telephone || '—' },
            { key: 'actif', label: 'Compte', width: 120,
              render: (u) => (
                <span className={u.actif ? 'etat-pastille' : 'cellule-relance'}>
                  {u.actif ? 'actif' : 'désactivé'}
                </span>
              ) },
            { key: 'actions', label: '', width: 200, render: (u) => (
              <div className="cellule-actions">
                <Button size="sm" variant="quiet"
                  onClick={(e) => { e.stopPropagation(); ouvrir(u); }}>Modifier</Button>
                {u.actif && (
                  <Button size="sm" variant="quiet"
                    onClick={(e) => { e.stopPropagation(); setADesactiver(u); }}>
                    Désactiver
                  </Button>
                )}
              </div>
            ) },
          ]}
        />
      </Panneau>

      <Panneau
        titre="Qui est prévenu, et quand"
        complement="ordre de relance : 1 d’abord, puis 2, puis 3"
      >
        {abonnements.length === 0 ? (
          <EmptyState title="Personne n’est prévenu" tone="neutral">
            Ajoutez au moins un destinataire pour les alertes d’inspection et d’urgence.
          </EmptyState>
        ) : (
          <DataTable
            rowKey="id"
            rows={abonnements}
            columns={[
              { key: 'utilisateur', label: 'Personne', render: (a) => nom(a.utilisateur) },
              { key: 'zone', label: 'Zone', width: 160,
                render: (a) => (a.zone ? `Zone ${a.zone} — ${D.zones[a.zone]}` : 'Toutes les zones') },
              { key: 'niveauMin', label: 'À partir du niveau', width: 210, render: (a) => (
                <Select value={a.niveauMin}
                  onChange={(e) => modifierAbonnement(a.id, 'niveauMin', e.target.value)}>
                  {NIVEAUX.slice().reverse().map((n) => (
                    <option key={n} value={n}>{LEVEL_LABEL[n]}</option>
                  ))}
                </Select>
              ) },
              { key: 'horaires', label: 'Horaires d’astreinte', width: 220, render: (a) => (
                <div className="cellule-actions">
                  <Select value={String(a.heureDebut)}
                    onChange={(e) => modifierAbonnement(a.id, 'heureDebut', Number(e.target.value))}>
                    {HEURES.map((h) => <option key={h} value={h}>{h} h</option>)}
                  </Select>
                  <Select value={String(a.heureFin)}
                    onChange={(e) => modifierAbonnement(a.id, 'heureFin', Number(e.target.value))}>
                    {HEURES.map((h) => <option key={h} value={h}>{h} h</option>)}
                  </Select>
                </div>
              ) },
              { key: 'ordre', label: 'Ordre', width: 90, numeric: true, align: 'right' },
              { key: 'niveau', label: 'Aperçu', width: 150,
                render: (a) => <LevelBadge level={a.niveauMin} size="sm" /> },
            ]}
          />
        )}
        <p className="note">
          Une alerte d’inspection ou d’urgence non prise en charge en 10 minutes part
          à la personne d’ordre suivant, puis au responsable sécurité à 20 minutes.
        </p>
      </Panneau>

      <Dialog
        open={Boolean(modifie)}
        title={modifie ? `Modifier ${modifie.nom}` : ''}
        confirmLabel="Enregistrer"
        cancelLabel="Annuler"
        onCancel={() => setModifie(null)}
        onConfirm={enregistrer}
      >
        <Field label="Nom" required>
          <TextInput value={brouillon.nom || ''}
            onChange={(e) => setBrouillon({ ...brouillon, nom: e.target.value })} />
        </Field>
        <Field label="Rôle" required>
          <Select value={brouillon.role || 'technicien'}
            onChange={(e) => setBrouillon({ ...brouillon, role: e.target.value })}>
            {Object.entries(ROLES).map(([clef, valeur]) => (
              <option key={clef} value={clef}>{valeur.libelle}</option>
            ))}
          </Select>
        </Field>
        <Field label="Téléphone" hint="Pour les SMS d’inspection et d’urgence.">
          <TextInput value={brouillon.telephone || ''}
            onChange={(e) => setBrouillon({ ...brouillon, telephone: e.target.value })} />
        </Field>
        <Checkbox
          label="Compte actif"
          checked={Boolean(brouillon.actif)}
          onChange={(e) => setBrouillon({ ...brouillon, actif: e.target.checked })}
        />
      </Dialog>

      <Dialog
        open={Boolean(aDesactiver)}
        title="Désactiver le compte"
        irreversible="Cette personne ne recevra plus aucune alerte."
        confirmLabel="Désactiver"
        cancelLabel="Annuler"
        onCancel={() => setADesactiver(null)}
        onConfirm={desactiver}
      >
        <p>{aDesactiver?.nom} ne pourra plus se connecter ni être prévenu.</p>
      </Dialog>
    </div>
  );
}
