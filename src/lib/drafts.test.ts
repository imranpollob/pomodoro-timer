import { expect, it } from 'vitest';
import { mergeUnedited } from './drafts';

it('menu sound changes reach settings without losing an edited duration', () => {
  const previous = { focus: 25, sound: true };
  expect(mergeUnedited({ focus: 30, sound: true }, previous, { focus: 25, sound: false }))
    .toEqual({ focus: 30, sound: false });
});
it('a pin change preserves unsaved volume and unchanged snapshots retain the draft', () => {
  const previous = { volume: 60, pinned: true };
  const draft = { volume: 40, pinned: true };
  expect(mergeUnedited(draft, previous, { volume: 60, pinned: false })).toEqual({ volume: 40, pinned: false });
  expect(mergeUnedited(draft, previous, previous)).toBe(draft);
});
