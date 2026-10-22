<script lang="ts">
  import { tick } from 'svelte';

  let { options, value, disabled = false, onchange }: {
    options: { value: string; label: string }[];
    value: string;
    disabled?: boolean;
    onchange: (value: string) => void;
  } = $props();
  const id = $props.id();
  let open = $state(false);
  let active = $state(0);
  let root: HTMLDivElement;
  let trigger: HTMLButtonElement;
  let search = '';
  let lastTyped = 0;
  const selected = $derived(options.find(option => option.value === value) ?? options[0]);

  async function reveal(index = Math.max(0, options.findIndex(option => option.value === value))) {
    active = index;
    open = true;
    await tick();
    root.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: 'nearest' });
  }
  function close() { open = false; search = ''; }
  function choose(index: number) {
    close();
    onchange(options[index].value);
  }
  function keydown(event: KeyboardEvent) {
    if (disabled) return;
    if (event.key === 'Tab') { close(); return; }
    if (event.key === 'Escape') { event.preventDefault(); close(); return; }
    if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      let index = active;
      if (!open) index = Math.max(0, options.findIndex(option => option.value === value));
      else if (event.key === 'ArrowDown') index = Math.min(options.length - 1, active + 1);
      else if (event.key === 'ArrowUp') index = Math.max(0, active - 1);
      if (event.key === 'Home') index = 0;
      if (event.key === 'End') index = options.length - 1;
      void reveal(index);
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (open) choose(active); else void reveal();
    } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault();
      const now = Date.now();
      search = (now - lastTyped < 700 ? search : '') + event.key.toLocaleLowerCase();
      lastTyped = now;
      const index = options.findIndex(option => option.label.toLocaleLowerCase().startsWith(search));
      if (index >= 0) void reveal(index);
    }
  }
  $effect(() => { if (disabled) close(); });
</script>

<svelte:window onpointerdown={event => { if (open && !root.contains(event.target as Node)) close(); }} />

<div class="task-picker" bind:this={root}>
  <button bind:this={trigger} type="button" class="task-picker-trigger" role="combobox"
    aria-label="Task for the next session" aria-haspopup="listbox" aria-expanded={open}
    aria-controls={`${id}-list`} aria-activedescendant={open ? `${id}-option-${active}` : undefined}
    {disabled} onclick={() => { if (open) close(); else void reveal(); }} onkeydown={keydown} onblur={close}
    title={selected.label}>
    <span>{selected.label}</span>
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="m4 6 4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" /></svg>
  </button>
  {#if open}
    <div class="task-picker-menu" id={`${id}-list`} role="listbox" aria-label="Focus task">
      {#each options as option, index (option.value)}
        <div class="task-picker-option" class:highlighted={active === index} role="option"
          id={`${id}-option-${index}`} data-index={index} aria-selected={option.value === value}
          tabindex="-1" title={option.label} onpointerdown={event => event.preventDefault()}
          onpointermove={() => active = index} onclick={() => { choose(index); trigger.focus(); }}
          onkeydown={keydown}>
          <span>{option.label}</span><span class="task-picker-check" aria-hidden="true">{option.value === value ? '✓' : ''}</span>
        </div>
      {/each}
    </div>
  {/if}
</div>
