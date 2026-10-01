/**
 * Reads a request body as text, refusing bodies larger than `maxBytes`.
 *
 * Returns `null` when the limit is exceeded. A `Content-Length` check alone can be
 * bypassed with chunked encoding, so the stream is also counted while reading and
 * cancelled as soon as the limit is crossed.
 */
export async function readTextBody(
  request: Request,
  maxBytes: number
): Promise<string | null> {
  const declared = Number(request.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > maxBytes) return null;

  if (!request.body) return "";

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let received = 0;

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      received += value.byteLength;
      if (received > maxBytes) {
        await reader.cancel();
        return null;
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  const bytes = new Uint8Array(received);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder().decode(bytes);
}
