// Point d'entrée de l'interface.
//
// Le bundle du système visuel est un script classique qui attend « window.React ».
// On le charge donc après avoir mis React à disposition, puis on affiche
// l'application.
//
// L'application est importée après coup, et jamais en haut de ce fichier :
// « systeme.js » lit « window.SASI » dès qu'il est évalué, et il doit donc
// l'être une fois le bundle en place — sinon tous les composants sont vides et
// la page reste blanche.

import React from 'react';
import ReactDOM from 'react-dom/client';

import './application.css';

function chargerScript(adresse) {
  return new Promise((resoudre, rejeter) => {
    const balise = document.createElement('script');
    balise.src = adresse;
    balise.onload = resoudre;
    balise.onerror = () => rejeter(new Error(`Chargement impossible : ${adresse}`));
    document.head.appendChild(balise);
  });
}

window.React = React;
window.ReactDOM = ReactDOM;

const racine = ReactDOM.createRoot(document.getElementById('racine'));

chargerScript('/systeme/bundle.js')
  .then(() => import('./App.jsx'))
  .then(({ default: App }) => racine.render(<App />))
  .catch((erreur) => {
    racine.render(
      <p style={{ padding: 24 }}>
        Le système visuel n’a pas pu être chargé : {erreur.message}
      </p>,
    );
  });
