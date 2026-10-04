import { invoke, isTauri } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import type { Snapshot } from './types';
import type { Transport } from './client';

export const transport: Transport = {
  read: () => invoke<Snapshot>('get_snapshot'),
  command: command => invoke<Snapshot>('timer_command', { command }),
  subscribe: async callback => {
    if (!isTauri()) throw new Error('Open Pomodoro Beta as a desktop app to connect to the timer.');
    return listen<Snapshot>('timer-state', event => callback(event.payload));
  },
};
export { invoke, listen };
