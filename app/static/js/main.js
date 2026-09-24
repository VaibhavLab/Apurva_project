'use strict';
window.mindcare = {
  async request(url, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch(url, {
        ...options,
        credentials: 'same-origin',
        signal: controller.signal,
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content, ...options.headers}
      });
      let data;
      try { data = await response.json(); } catch { throw new Error('The server could not complete that request. Please try again.'); }
      if (!response.ok) {
        const error = new Error(data.error || 'Something went wrong. Please try again.');
        error.status = response.status;
        throw error;
      }
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('The request took too long. Check your conversation history before sending again.');
      if (error instanceof TypeError) throw new Error('Unable to connect. Check your connection and try again.');
      throw error;
    } finally { clearTimeout(timeout); }
  }
};
