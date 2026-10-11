import React from 'react';

/**
 * Attrape une erreur d'affichage et montre un message utile plutôt qu'une page
 * blanche. Règle du système : dire ce qui s'est passé et ce qu'il faut faire.
 */
export default class LimiteErreur extends React.Component {
  constructor(proprietes) {
    super(proprietes);
    this.state = { erreur: null };
  }

  static getDerivedStateFromError(erreur) {
    return { erreur };
  }

  componentDidCatch(erreur, informations) {
    console.error('Erreur d’affichage', erreur, informations);
  }

  render() {
    const { erreur } = this.state;
    if (!erreur) return this.props.children;
    return (
      <div className="panneau">
        <h2>Cet écran n’a pas pu s’afficher</h2>
        <p>{erreur.message}</p>
        <p className="note">
          Rechargez la page. Si le problème persiste, signalez-le avec l’adresse
          affichée dans la barre du navigateur.
        </p>
      </div>
    );
  }
}
