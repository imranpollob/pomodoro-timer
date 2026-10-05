<script lang="ts">
  let { name, size = 20 }: { name: string; size?: number } = $props();
  const paths: Record<string, string> = {
    timer: 'M10 2h4M12 6a8 8 0 1 0 0 16 8 8 0 0 0 0-16Zm0 4v5l3 2M17 4l2 2',
    history: 'M3 12a9 9 0 1 0 3-6M3 3v5h5M12 7v6l4 2',
    chart: 'M4 4v16h16M8 20v-9M12 20V8M16 20v-7',
    settings: 'M4 7h16M4 17h16M8 4v6M16 14v6',
    compact: 'M4 4h16v16H4ZM8 13h8v4H8Z',
    play: 'M8 5v14l11-7Z', pause: 'M8 5v14M16 5v14',
    finish: 'M6 6h12v12H6Z', check: 'M5 12l4 4L19 6',
  };
</script>
<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d={paths[name] ?? paths.timer} /></svg>
