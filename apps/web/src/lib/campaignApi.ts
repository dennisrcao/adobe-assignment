export type SseEvent = Record<string, unknown> & { type: string };

export function getCampaignStreamUrl(): string {
  return '/generate/campaign';
}

export async function* parseSseResponse(res: Response): AsyncGenerator<SseEvent> {
  if (!res.body) throw new Error('Response has no body');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);

        const dataLine = frame
          .split('\n')
          .map((l) => l.replace(/^data:\s?/, ''))
          .join('\n')
          .trim();

        if (dataLine) {
          try {
            yield JSON.parse(dataLine) as SseEvent;
          } catch {
            // ignore malformed frame, keep streaming
          }
        }
        boundary = buffer.indexOf('\n\n');
      }
    }
  } finally {
    reader.releaseLock();
  }
}
