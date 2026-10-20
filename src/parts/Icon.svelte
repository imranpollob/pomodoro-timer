<script module lang="ts">
  const paths = {
    timer: 'M10 2h4M12 6a8 8 0 1 0 0 16 8 8 0 0 0 0-16Zm0 4v5l3 2M17 4l2 2',
    history: 'M3 12a9 9 0 1 0 3-6M3 3v5h5M12 7v6l4 2',
    chart: 'M4 4v16h16M8 20v-9M12 20V8M16 20v-7',
    settings: 'M4 7h16M4 17h16M8 4v6M16 14v6',
    compact: 'M4 4h16v16H4ZM8 13h8v4H8Z',
    play: 'M8 5v14l11-7Z', pause: 'M8 5v14M16 5v14',
    finish: 'M6 6h12v12H6Z', check: 'M5 12l4 4L19 6',
    edit: 'M4 20h4L18.5 9.5l-4-4L4 16v4ZM13.5 6.5l4 4', trash: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6', plus: 'M12 5v14M5 12h14',
    more: 'M12 5h.01M12 12h.01M12 19h.01',
    sound: 'M11 5 6 9H3v6h3l5 4V5ZM15 8a6 6 0 0 1 0 8M18 5a10 10 0 0 1 0 14',
    flame: 'M12 22c4.2 0 7-2.8 7-6.8 0-2.7-1.4-4.7-4-6.6.1 2.1-.7 3.4-1.9 4.2.4-4.4-1.8-7.5-5.1-10.8.2 3.9-1 5.9-2.4 7.8C4.3 12 5 14.4 5 15.7 5 19.4 7.8 22 12 22Z',
    sparkles: 'm12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Zm7 12 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15ZM5 15l.8 2.2L8 18l-2.2.8L5 21l-.8-2.2L2 18l2.2-.8L5 15Z',
  } as const;
</script>

<script lang="ts">
  let { name, size = 20 }: { name: keyof typeof paths; size?: number } = $props();
</script>
<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
