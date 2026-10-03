import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ProgressReset } from './ProgressReset';
import { I18nProvider } from '../i18n';
import type { Deck } from '../types';

const mockApi = vi.hoisted(() => vi.fn());
vi.mock('../api/client', async () => ({ ...await vi.importActual('../api/client'), api: mockApi }));
const decks = [{ id: 'deck-1', title: 'Latin' }, { id: 'deck-2', title: 'French' }] as Deck[];
function setup() { render(<I18nProvider><ProgressReset decks={decks} defaultDeckId="deck-1" /></I18nProvider>); }

describe('learning progress reset', () => {
  beforeEach(() => { mockApi.mockReset(); });

  it('requires password and confirmation, resets confirmation when scope changes, and submits once', async () => {
    let resolve!: () => void;
    mockApi.mockImplementation(() => new Promise<void>((done) => { resolve = done; }));
    const user = userEvent.setup(); setup();
    await user.click(screen.getByRole('button', { name: 'Reset progress…' }));
    const dialog = screen.getByRole('dialog');
    await waitFor(() => expect(within(dialog).getByRole('combobox')).toHaveFocus());
    const submit = within(dialog).getByRole('button', { name: 'Reset permanently' });
    expect(submit).toBeDisabled();
    expect(within(dialog).getByRole('combobox')).toHaveValue('deck-1');
    await user.type(within(dialog).getByLabelText('Enter your password to confirm'), 'preview-password');
    await user.click(within(dialog).getByRole('checkbox'));
    expect(submit).toBeEnabled();
    await user.selectOptions(within(dialog).getByRole('combobox'), '');
    expect(submit).toBeDisabled();
    expect(within(dialog).getByRole('checkbox')).not.toBeChecked();
    await user.click(within(dialog).getByRole('checkbox'));
    await user.dblClick(submit);
    expect(mockApi).toHaveBeenCalledTimes(1);
    expect(mockApi).toHaveBeenCalledWith('/account/progress/reset', {
      method: 'POST', body: '{"deck_id":null,"password":"preview-password","confirm":true}',
    });
    await user.keyboard('{Escape}');
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    resolve();
    expect(await screen.findByRole('status')).toHaveTextContent('Learning progress reset for All decks.');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('preserves the form after a failed reset and clears the password on cancel', async () => {
    mockApi.mockRejectedValue(new Error('offline'));
    const user = userEvent.setup(); setup();
    await user.click(screen.getByRole('button', { name: 'Reset progress…' }));
    await waitFor(() => expect(screen.getByRole('combobox')).toHaveFocus());
    await user.type(screen.getByLabelText('Enter your password to confirm'), 'preview-password');
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: 'Reset permanently' }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reset permanently' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    await user.click(screen.getByRole('button', { name: 'Reset progress…' }));
    expect(screen.getByLabelText('Enter your password to confirm')).toHaveValue('');
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
