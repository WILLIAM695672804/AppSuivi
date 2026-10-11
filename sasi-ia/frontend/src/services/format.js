// Mise en forme des nombres, des heures et des durées, en français.
// Règles du système visuel : virgule décimale, espace avant l'unité,
// durées en langage courant.

export function heure(instant) {
  return new Date(instant)
    .toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    .replace(':', ' h ');
}

export function date(instant) {
  return new Date(instant).toLocaleDateString('fr-FR');
}

export function depuis(instant, maintenant = Date.now()) {
  const minutes = Math.round((maintenant - instant) / 60000);
  if (minutes < 1) return 'à l’instant';
  if (minutes < 60) return `il y a ${minutes} min`;
  const heures = Math.floor(minutes / 60);
  return `depuis ${heures} h ${String(minutes % 60).padStart(2, '0')}`;
}

export function duree(debut, fin, maintenant = Date.now()) {
  const minutes = Math.round(((fin || maintenant) - debut) / 60000);
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, '0')}`;
}

export function pourcentage(valeur, decimales = 0) {
  if (valeur === null || valeur === undefined) return '—';
  return `${valeur.toLocaleString('fr-FR', { minimumFractionDigits: decimales,
    maximumFractionDigits: decimales })} %`;
}

export function signe(valeur, decimales = 1) {
  if (valeur === null || valeur === undefined) return '—';
  const texte = Math.abs(valeur).toLocaleString('fr-FR', {
    minimumFractionDigits: decimales, maximumFractionDigits: decimales });
  return `${valeur >= 0 ? '+' : '−'}${texte}`;
}
