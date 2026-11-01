import sources from './sources.json';

// A fixed allowlist keeps this endpoint from becoming an arbitrary URL proxy.
async function serve(request: Request, context: { params: Promise<{ id: string }> | { id: string } }) {
  const { id } = await context.params;
  const source = (sources as Record<string, { url: string; pageUrl: string }>)[id];
  if (!source || !Object.hasOwn(sources, id)) return new Response('音轨不存在', { status: 404 });
  const range = request.headers.get('range');
  if (range && !/^bytes=\d*-\d*$/.test(range)) return new Response('不支持此分段请求', { status: 416 });
  const headers = new Headers({ Referer: source.pageUrl, Accept: 'audio/mpeg' });
  if (range) headers.set('Range', range);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 25000);
  let upstream: Response;
  try {
    upstream = await fetch(source.url, { method: request.method === 'HEAD' ? 'HEAD' : 'GET', headers, signal: controller.signal, redirect: 'manual' });
  } catch (error) {
    console.warn('Official audio fetch failed:', error instanceof Error ? error.message : 'network error');
    return new Response('原版音频暂不可用，请稍后再试或导入本地音频。', { status: 502 });
  } finally { clearTimeout(timer); }
  if (![200, 206, 416].includes(upstream.status)) return new Response('原版音频暂不可用', { status: 502 });
  const result = new Headers({ 'Content-Type': 'audio/mpeg', 'Cache-Control': 'private, max-age=3600', 'X-Content-Type-Options': 'nosniff' });
  for (const key of ['content-length', 'content-range', 'accept-ranges', 'etag', 'last-modified']) {
    const value = upstream.headers.get(key); if (value) result.set(key, value);
  }
  return new Response(request.method === 'HEAD' ? null : upstream.body, { status: upstream.status, headers: result });
}
export const GET = serve;
export const HEAD = serve;
