// Composants du système visuel SASI.
//
// Le bundle les dépose dans « window.SASI » (voir main.jsx). Ce fichier sert de
// point d'accès unique : aucun écran ne lit « window » directement.

const S = window.SASI || {};

export const Button = S.Button;
export const LevelBadge = S.LevelBadge;
export const AlertCard = S.AlertCard;
export const DataTable = S.DataTable;
export const TemperatureChart = S.TemperatureChart;
export const StatusBanner = S.StatusBanner;
export const Dialog = S.Dialog;
export const Field = S.Field;
export const TextInput = S.TextInput;
export const Textarea = S.Textarea;
export const Select = S.Select;
export const Checkbox = S.Checkbox;
export const EmptyState = S.EmptyState;
export const Chip = S.Chip;
export const StatCard = S.StatCard;

export const LEVELS = S.LEVELS || ['normal', 'information', 'surveillance', 'inspection', 'urgence'];
export const LEVEL_LABEL = S.LEVEL_LABEL || {};
export const STATE_LABEL = S.STATE_LABEL || {};
export const formatTemperature = S.formatTemperature || ((v) => (v ?? '—').toString());

// Les quatre niveaux d'alerte, du plus grave au moins grave.
export const NIVEAUX = ['urgence', 'inspection', 'surveillance', 'information'];
