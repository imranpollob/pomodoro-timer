<script lang="ts">
  import { onMount } from 'svelte';
  import { getCurrentWindow } from '@tauri-apps/api/window';
  import { invoke, listen } from '../lib/desktop';
  import { actionLabel, formatTime, phaseLabel, type Snapshot } from '../lib/types';

  let { state, busy, send, error }: {
    state: Snapshot;
    busy: boolean;
    send: () => void;
    error: (message: string) => void;
  } = $props();

  let strip: HTMLDivElement;
  let timeRegion: HTMLSpanElement;
  let digits: HTMLSpanElement;
  let options: HTMLButtonElement;
  let menuOpen = false;
  let menuDismissedAt = 0;
  let scheduleMeasure = () => {};
  const display = $derived(formatTime(state.display_seconds));
  const disabled = $derived(busy || state.pending_save);

  async function native(command: string) {
    try { await invoke(command); }
    catch (cause) { error(String(cause)); }
  }

  async function openMenu() {
    if (menuOpen || Date.now() - menuDismissedAt < 300) return;
    menuOpen = true;
    try {
      const anchor = options.getBoundingClientRect();
      await invoke('compact_menu', { x: anchor.left, y: strip.getBoundingClientRect().bottom });
    } catch (cause) { error(String(cause)); }
    finally { menuOpen = false; menuDismissedAt = Date.now(); }
  }

  function keyboard(event: KeyboardEvent) {
    if ((event.shiftKey && event.key === 'F10') || event.key === 'ContextMenu') {
      event.preventDefault();
      void openMenu();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      void native('close_compact');
    } else if (event.code === 'Space' && !(event.target instanceof Element && event.target.closest('button'))) {
      event.preventDefault();
      if (!disabled && !event.repeat) send();
    }
  }

  function drag(event: MouseEvent) {
    // UIA Invoke sends a synthetic mousedown with no physical click count.
    if (event.detail === 0 || event.button !== 0 || !(event.target instanceof Element) ||
        !strip.contains(event.target) || event.target.closest('button')) return;
    event.preventDefault();
    if (event.detail === 2) void native('open_main');
    else void getCurrentWindow().startDragging().catch(cause => error(String(cause)));
  }

  function activateTime(event: MouseEvent) {
    // Direct activation has detail 0; Chromium's accessibility click has
    // buttons 1. Physical clicks finish with buttons 0 and keep drag/double-click.
    if (event.detail === 0 || event.buttons === 1) void native('open_main');
  }

  onMount(() => {
    let disposed = false;
    let frame = 0;
    let lastWidth = 0;
    let generation = 0;
    let appliedGeneration = -1;
    let queuedWidth: number | undefined;
    let resizing = false;
    let unlisten: (() => void) | undefined;

    // GTK sizing is asynchronous. Finish each request before applying the latest
    // measurement, so a stale resize cannot overwrite a newer digit width.
    async function flushSize() {
      if (resizing) return;
      resizing = true;
      try {
        while (!disposed && queuedWidth !== undefined) {
          const width = queuedWidth;
          queuedWidth = undefined;
          const currentGeneration = generation;
          if (width === lastWidth && currentGeneration === appliedGeneration) continue;
          await invoke('resize_compact', { width, height: 44 });
          lastWidth = width;
          appliedGeneration = currentGeneration;
        }
      } catch (cause) {
        if (!disposed) error(String(cause));
      } finally {
        resizing = false;
        if (!disposed && queuedWidth !== undefined) void flushSize();
      }
    }

    scheduleMeasure = () => {
      if (disposed || frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        // Measure the real border, padding and controls. The natural digit span
        // stays measurable even while the visible time region is clipped.
        const chrome = strip.getBoundingClientRect().width - timeRegion.getBoundingClientRect().width;
        const content = digits.getBoundingClientRect().width;
        queuedWidth = Math.min(1200, Math.max(170, Math.ceil(content + chrome + 2)));
        void flushSize();
      });
    };

    const observer = new ResizeObserver(scheduleMeasure);
    observer.observe(digits);
    observer.observe(strip);
    scheduleMeasure();
    void document.fonts.ready.then(scheduleMeasure);
    void listen('compact-shown', () => {
      generation++;
      scheduleMeasure();
    }).then(stop => {
      if (disposed) stop();
      else unlisten = stop;
    }).catch(cause => { if (!disposed) error(String(cause)); });

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      observer.disconnect();
      unlisten?.();
      scheduleMeasure = () => {};
    };
  });
</script>

<svelte:window onkeydown={keyboard} onmousedown={drag} onresize={() => scheduleMeasure()} />

<div class="compact" data-compact-ui="2" bind:this={strip}
  role="group" aria-label="Compact timer" oncontextmenu={event => event.preventDefault()}>
  <span class="compact-time" role="button" tabindex="0" bind:this={timeRegion}
    aria-label={`${phaseLabel[state.phase]}, ${display}${state.active_task ? `, task ${state.active_task.title}` : ''}. Open main window`}
    title={`${phaseLabel[state.phase]} · ${state.status}. Drag to move. Double-click or press Enter to open main window.`}
    onclick={activateTime}
    onkeydown={event => {
      if (event.key === 'Enter') { event.preventDefault(); void native('open_main'); }
    }}><span class="compact-digits" bind:this={digits}>{display}</span></span>

  <div class="compact-controls" role="group" aria-label="Timer controls">
    <button class="compact-action" aria-label={actionLabel(state)} {disabled} onclick={send}>
      <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
        {#if state.status === 'running'}
          <path d="M8 5v14M16 5v14" />
        {:else}
          <path d="M8 5v14l11-7Z" />
        {/if}
      </svg>
    </button>
    <button class="compact-action compact-options" aria-label="Options" title="Options"
      aria-haspopup="menu" bind:this={options} onclick={() => void openMenu()}>
      <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="5" r="1.5" /><circle cx="12" cy="12" r="1.5" /><circle cx="12" cy="19" r="1.5" />
      </svg>
    </button>
  </div>
</div>

<style>
  .compact {
    all: initial;
    box-sizing: border-box;
    display: grid;
    grid-template-columns: minmax(0, 1fr) 68px;
    align-items: center;
    gap: 8px;
    width: 100%;
    height: 44px;
    padding: 5px;
    border: 1px solid #33435c;
    overflow: hidden;
    color: #e6ebf5;
    color-scheme: dark;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    cursor: grab;
    touch-action: none;
  }
  .compact, .compact * {
    box-sizing: border-box;
    -webkit-user-select: none;
    user-select: none;
    -webkit-user-drag: none;
  }
  .compact-time {
    all: unset;
    display: block;
    min-width: 0;
    height: 32px;
    overflow: hidden;
    white-space: nowrap;
    font-size: 25px;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
    letter-spacing: -.6px;
    line-height: 32px;
    cursor: grab;
    -webkit-user-select: none;
    user-select: none;
  }
  .compact-digits { display: inline-block; }
  .compact-controls {
    all: unset;
    display: grid;
    grid-template-columns: 32px 32px;
    gap: 4px;
    width: 68px;
    height: 32px;
    overflow: hidden;
  }
  .compact-action {
    all: unset;
    box-sizing: border-box;
    -webkit-appearance: none;
    appearance: none;
    display: grid;
    place-items: center;
    width: 32px;
    min-width: 0;
    max-width: 32px;
    height: 32px;
    min-height: 0;
    max-height: 32px;
    border-radius: 6px;
    background: #263b5d;
    color: #e6ebf5;
    cursor: pointer;
  }
  .compact-action svg { display: block; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
  .compact-options svg { fill: currentColor; stroke: none; }
  .compact-action:disabled { opacity: .5; cursor: default; }
  .compact-action:hover:enabled { background: #344e76; }
  .compact-action:focus-visible, .compact-time:focus-visible { outline: 2px solid #b5a6ff; outline-offset: -2px; }
</style>
