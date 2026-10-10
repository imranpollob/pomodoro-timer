import { describe, expect, it } from 'vitest';
import { TimerClient, type Transport } from './client';
import { actionLabel, formatTime, type Snapshot } from './types';

const snapshot = (revision: number) => ({ revision } as Snapshot);
describe('backend subscription', () => {
  it('cannot overwrite a newer event with an older initial read or command reply', async () => {
    let emit!: (snapshot: Snapshot) => void;
    const changes: number[] = [];
    const transport: Transport = {
      subscribe: async callback => { emit = callback; callback(snapshot(5)); return () => {}; },
      read: async () => snapshot(3), command: async () => snapshot(4),
    };
    const client = new TimerClient(transport, state => changes.push(state.revision));
    await client.start(); await client.send({ type: 'toggle' }); emit(snapshot(6));
    expect(changes).toEqual([5, 6]);
    client.dispose(); emit(snapshot(7)); expect(changes).toEqual([5, 6]);
  });
  it('cleans up a subscription that resolves after its view closes', async () => {
    let resolve!: (unsubscribe: () => void) => void;
    let removed = false;
    const client = new TimerClient({
      subscribe: () => new Promise(r => { resolve = r; }),
      read: async () => snapshot(0), command: async () => snapshot(0),
    }, () => { throw new Error('Disposed view was updated'); });
    const starting = client.start(); client.dispose(); resolve(() => { removed = true; });
    await starting; expect(removed).toBe(true);
  });
});
it('displays stopwatch hours without rolling over', () => {
  expect(formatTime(3599)).toBe('59:59'); expect(formatTime(3601)).toBe('1:00:01');
  expect(formatTime(360_001)).toBe('100:00:01');
});
it('prioritizes retry over timer actions when saving failed', () => {
  expect(actionLabel({ pending_save: true, status: 'paused' } as Snapshot)).toBe('Retry save');
});
