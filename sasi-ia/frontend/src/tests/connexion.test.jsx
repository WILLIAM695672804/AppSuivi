import { fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';

import Connexion from '../ecrans/Connexion.jsx';

describe('connexion', () => {
  it('refuse une entrée sans nom', () => {
    const surConnexion = vi.fn();
    render(<Connexion surConnexion={surConnexion} />);
    fireEvent.click(screen.getByText('Entrer'));
    expect(surConnexion).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(/Indiquez votre nom/);
  });

  it('ouvre la session avec le nom et le rôle choisis', () => {
    const surConnexion = vi.fn();
    render(<Connexion surConnexion={surConnexion} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Awa N.' } });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'technicien' } });
    fireEvent.click(screen.getByText('Entrer'));
    expect(surConnexion).toHaveBeenCalledWith('Awa N.', 'technicien');
  });
});
