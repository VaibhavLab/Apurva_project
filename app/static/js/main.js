'use strict';
window.mindcare = {
  async request(url, options = {}) {
    const {signal, timeoutMs = 30000, responseType = 'json', headers: extraHeaders = {}, ...fetchOptions} = options;
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    signal?.addEventListener('abort', abort, {once: true});
    if (signal?.aborted) abort();
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
    const headers = {'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content, ...extraHeaders};
    if (fetchOptions.body && !(fetchOptions.body instanceof FormData)) headers['Content-Type'] = 'application/json';
    try {
      const response = await fetch(url, {...fetchOptions, credentials: 'same-origin', signal: controller.signal, headers});
      const isJSON = (response.headers.get('Content-Type') || '').includes('application/json');
      if (!response.ok) {
        const data = isJSON ? await response.json() : {};
        const error = new Error(data.error || 'The server could not complete that request. Please try again.');
        error.status = response.status;
        error.code = data.code;
        throw error;
      }
      if (responseType === 'blob') {
        if (!(response.headers.get('Content-Type') || '').startsWith('audio/')) throw new Error('The server returned invalid audio.');
        return await response.blob();
      }
      if (!isJSON) throw new Error('The server returned an unexpected response. Please reload.');
      return await response.json();
    } catch (error) {
      if (error.name === 'AbortError' && timedOut) throw new Error('The request took too long. Your message may still be saved; retry the same message or reopen its conversation.');
      if (error instanceof TypeError) throw new Error('Unable to connect. Check your connection and try again.');
      throw error;
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
    }
  }
};
