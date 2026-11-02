export function parseRange(value: string | null, size: number): { start: number; end: number; partial: boolean } | null {
  if (!value) return { start: 0, end: size - 1, partial: false };
  const match = /^bytes=(\d*)-(\d*)$/.exec(value);
  if (!match || (!match[1] && !match[2])) return null;
  let start: number, end: number;
  if (!match[1]) {
    const suffix = Number(match[2]);
    if (!Number.isSafeInteger(suffix) || suffix <= 0) return null;
    start = Math.max(0, size - suffix); end = size - 1;
  } else {
    start = Number(match[1]); end = match[2] ? Number(match[2]) : size - 1;
    if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start >= size || end < start) return null;
    end = Math.min(end, size - 1);
  }
  return { start, end, partial: true };
}

// Pull, rather than eagerly drain, the upstream stream: large audio files must
// not be buffered in the Worker. This also handles origins that ignore Range.
export function spliceAudio(prefix: Uint8Array, body: ReadableStream<Uint8Array> | null, skip: number, length: number) {
  const reader = body?.getReader();
  let headerPending = prefix.length > 0, remaining = length;
  return new ReadableStream<Uint8Array>({
    async pull(controller) {
      try {
        if (headerPending) { headerPending = false; controller.enqueue(prefix); return; }
        if (!remaining) { controller.close(); await reader?.cancel(); return; }
        if (!reader) throw new Error('Missing audio body');
        for (;;) {
          const { value, done } = await reader.read();
          if (done) throw new Error('Incomplete source audio');
          if (skip >= value.length) { skip -= value.length; continue; }
          const part = value.subarray(skip, Math.min(value.length, skip + remaining));
          skip = 0; remaining -= part.length; controller.enqueue(part); return;
        }
      } catch (error) { controller.error(error); await reader?.cancel().catch(() => {}); }
    },
    cancel(reason) { return reader?.cancel(reason); }
  });
}
