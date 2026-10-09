import { createReadStream } from 'node:fs'
import { stat } from 'node:fs/promises'
import { createServer } from 'node:http'
import { extname, resolve, sep } from 'node:path'
import { pipeline } from 'node:stream/promises'

const root = resolve(process.env.STATIC_DIR ?? '/app/dist')
const backend = process.env.BACKEND_URL ?? 'http://backend:8000'
const port = Number(process.env.PORT ?? 8080)
const mime = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp',
  '.woff2': 'font/woff2',
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? '/', 'http://localhost')
  if (url.pathname === '/health') {
    response.writeHead(200, { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' })
    response.end('ok')
    return
  }
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/health/')) {
    if (request.method !== 'GET') {
      response.writeHead(405, { allow: 'GET', 'content-type': 'text/plain; charset=utf-8' })
      response.end('read-only dashboard proxy')
      return
    }
    try {
      const upstream = await fetch(new URL(`${url.pathname}${url.search}`, backend), {
        headers: { accept: request.headers.accept ?? 'application/json' },
        signal: AbortSignal.timeout(10_000),
      })
      response.writeHead(upstream.status, {
        'content-type': upstream.headers.get('content-type') ?? 'application/json',
        'cache-control': 'no-store',
      })
      response.end(Buffer.from(await upstream.arrayBuffer()))
    } catch {
      response.writeHead(502, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' })
      response.end(JSON.stringify({ error: { code: 'upstream_unavailable', message: 'The API could not be reached.' } }))
    }
    return
  }
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    response.writeHead(405, { allow: 'GET, HEAD' })
    response.end()
    return
  }
  let pathname
  try {
    pathname = decodeURIComponent(url.pathname)
  } catch {
    response.writeHead(400)
    response.end()
    return
  }
  const candidate = resolve(root, `.${pathname}`)
  if (candidate !== root && !candidate.startsWith(`${root}${sep}`)) {
    response.writeHead(404)
    response.end()
    return
  }
  let file = candidate
  try {
    if (!(await stat(file)).isFile()) throw new Error('not a file')
  } catch {
    file = resolve(root, 'index.html')
  }
  response.writeHead(200, {
    'content-type': mime[extname(file)] ?? 'application/octet-stream',
    'cache-control': file === resolve(root, 'index.html') ? 'no-cache' : 'public, max-age=31536000, immutable',
    'x-content-type-options': 'nosniff',
  })
  if (request.method === 'HEAD') response.end()
  else await pipeline(createReadStream(file), response)
})

server.listen(port, '0.0.0.0')
