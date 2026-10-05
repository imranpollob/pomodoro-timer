/** Refresh fields the user has not edited, while preserving their unsaved fields. */
export function mergeUnedited<T extends object>(draft: T, previous: T, saved: T): T {
  let merged: T | undefined;
  for (const key of Object.keys(saved) as (keyof T)[]) {
    if (draft[key] === previous[key] && draft[key] !== saved[key]) {
      merged ??= { ...draft };
      merged[key] = saved[key];
    }
  }
  return merged ?? draft;
}
