<script lang="ts">
  import { onMount } from 'svelte';
  import { getCurrentWindow } from '@tauri-apps/api/window';
  import { invoke } from '../lib/desktop';
  import { actionLabel, formatTime, phaseLabel, type Snapshot } from '../lib/types';
  import Icon from './Icon.svelte';
  let { state, busy, send, error }: { state: Snapshot; busy: boolean; send: () => void; error: (message: string) => void } = $props();
  let timeRegion: HTMLSpanElement;
  let strip: HTMLDivElement;
  let display = $derived(formatTime(state.display_seconds));
  async function desktop(command: string) {
    try { await invoke(command); } catch (e) { error(String(e)); }
  }
  function keyboard(event: KeyboardEvent) {
    if (event.shiftKey && event.key === 'F10' || event.key === 'ContextMenu') {
      event.preventDefault(); void desktop('compact_menu');
    } else if (event.key === 'Escape') { event.preventDefault(); void desktop('close_compact'); }
    else if (event.code === 'Space') { event.preventDefault(); send(); }
  }
  onMount(() => {
    const observer = new ResizeObserver(() => {
      const font = parseFloat(getComputedStyle(timeRegion).fontSize);
      const width = Math.max(200, Math.ceil(timeRegion.scrollWidth + 50));
      const height = Math.max(44, Math.ceil(font * 1.5));
      void invoke('resize_compact', { width, height }).catch(e => error(String(e)));
    });
    observer.observe(timeRegion);
    return () => observer.disconnect();
  });
</script>

<svelte:window onkeydown={keyboard} />
<div class="compact" bind:this={strip} class:break-phase={state.phase.includes('break')}
  oncontextmenu={event => { event.preventDefault(); void desktop('compact_menu'); }}
  onpointerdown={event => { if (event.target === strip) void getCurrentWindow().startDragging().catch(e => error(String(e))); }}
  role="group" aria-label="Compact timer">
  <span class="compact-time" role="button" tabindex="0" bind:this={timeRegion}
    aria-label={`${phaseLabel[state.phase]}, ${display}${state.active_task ? `, task ${state.active_task.title}` : ''}. Open main window`}
    title={`${phaseLabel[state.phase]} · ${state.status}${state.active_task ? ` · ${state.active_task.title}` : ''}. Double-click to open main window. Right-click for actions, including close.`}
    ondblclick={() => void desktop('open_main')}
    onclick={() => void desktop('open_main')}
    onkeydown={event => { if (event.key === 'Enter') { event.preventDefault(); void desktop('open_main'); } }}>{display}</span>
  <button class="compact-action" aria-label={actionLabel(state)} disabled={busy || state.pending_save}
    onclick={send}><Icon name={state.status === 'running' ? 'pause' : 'play'} size={16} /></button>
</div>
