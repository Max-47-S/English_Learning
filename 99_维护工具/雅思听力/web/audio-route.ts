import sources from './sources.json';
import { parseRange, spliceAudio } from './audio-range';

type Source = { url: string; pageUrl: string; mp3Index?: { prefixBase64: string; sourceOffset: number; bodyBytes: number; bytes: number; sha256: string } };

async function upstreamAudio(source: Source, range: string | null, method: string) {
  const headers = new Headers({ Referer: source.pageUrl, Accept: 'audio/mpeg' });
  if (range) headers.set('Range', range);
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 25000);
  try { return await fetch(source.url, { method, headers, signal: controller.signal, redirect: 'manual' }); }
  finally { clearTimeout(timer); }
}

// A fixed allowlist keeps this endpoint from becoming an arbitrary URL proxy.
async function serve(request: Request, context: { params: Promise<{ id: string }> | { id: string } }) {
  const { id } = await context.params;
  const source = (sources as Record<string, Source>)[id];
  if (!source || !Object.hasOwn(sources, id)) return new Response('音轨不存在', { status: 404 });
  const range = request.headers.get('range');
  if (range && !/^bytes=\d*-\d*$/.test(range)) return new Response('不支持此分段请求', { status: 416 });
  const result = new Headers({ 'Content-Type': 'audio/mpeg', 'Cache-Control': 'private, max-age=3600', 'X-Content-Type-Options': 'nosniff' });
  if (source.mp3Index) {
    const index = source.mp3Index, selected = parseRange(range, index.bytes);
    result.set('Accept-Ranges', 'bytes'); result.set('ETag', `"${index.sha256}"`);
    if (!selected) { result.set('Content-Range', `bytes */${index.bytes}`); return new Response(null, { status: 416, headers: result }); }
    const { start, end, partial } = selected, status = partial ? 206 : 200;
    result.set('Content-Length', String(end - start + 1));
    if (partial) result.set('Content-Range', `bytes ${start}-${end}/${index.bytes}`);
    if (request.method === 'HEAD') return new Response(null, { status, headers: result });
    const prefix = Uint8Array.from(atob(index.prefixBase64), c => c.charCodeAt(0));
    const header = start < prefix.length ? prefix.slice(start, Math.min(end + 1, prefix.length)) : new Uint8Array();
    const bodyStart = Math.max(start, prefix.length), bodyLength = Math.max(0, end - bodyStart + 1);
    if (!bodyLength) return new Response(header, { status, headers: result });
    const originalStart = index.sourceOffset + bodyStart - prefix.length, originalEnd = originalStart + bodyLength - 1;
    try {
      const upstream = await upstreamAudio(source, `bytes=${originalStart}-${originalEnd}`, 'GET');
      if (![200, 206].includes(upstream.status)) return new Response('原版音频暂不可用', { status: 502 });
      if (upstream.status === 206 && !upstream.headers.get('content-range')?.startsWith(`bytes ${originalStart}-${originalEnd}/`)) return new Response('音频分段不完整', { status: 502 });
      return new Response(spliceAudio(header, upstream.body, upstream.status === 200 ? originalStart : 0, bodyLength), { status, headers: result });
    } catch { return new Response('原版音频暂不可用，请稍后重试或导入本地 MP3。', { status: 502 }); }
  }
  let upstream: Response;
  try {
    upstream = await upstreamAudio(source, range, request.method === 'HEAD' ? 'HEAD' : 'GET');
  } catch (error) {
    console.warn('Official audio fetch failed:', error instanceof Error ? error.message : 'network error');
    return new Response('原版音频暂不可用，请稍后再试或导入本地音频。', { status: 502 });
  }
  if (![200, 206, 416].includes(upstream.status)) return new Response('原版音频暂不可用', { status: 502 });
  for (const key of ['content-length', 'content-range', 'accept-ranges', 'etag', 'last-modified']) {
    const value = upstream.headers.get(key); if (value) result.set(key, value);
  }
  return new Response(request.method === 'HEAD' ? null : upstream.body, { status: upstream.status, headers: result });
}
export const GET = serve;
export const HEAD = serve;
