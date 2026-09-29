'use strict';
(() => {
  const app = document.querySelector('.chat-app');
  const input = document.getElementById('message-input');
  const sendButton = document.getElementById('send-button');
  const messages = document.getElementById('messages');
  const emptyState = document.getElementById('empty-state');
  const scrollArea = document.getElementById('chat-scroll');
  const historyList = document.getElementById('history-list');
  const title = document.getElementById('conversation-title');
  const errorBox = document.getElementById('chat-error');
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('drawer-overlay');
  const menuButton = document.getElementById('open-sidebar');
  const deleteDialog = document.getElementById('delete-dialog');
  const request = window.mindcare.request;
  let conversationId = Number(app.dataset.conversationId) || null;
  let busy = false;
  let voiceBusy = false;
  let epoch = 0;
  let activeRequest = null;
  let retry = null;
  function cancelActivity() {
    epoch++;
    activeRequest?.abort();
    window.mindcare.voice?.cancel(false);
    busy = false;
    voiceBusy = false;
    setBusy(false);
  }
  let deleteId = null;
  let conversations = [];

  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const svg = (name) => {
    const node = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    node.setAttribute('viewBox', '0 0 24 24');
    node.setAttribute('fill', 'none');
    node.setAttribute('stroke', 'currentColor');
    node.setAttribute('stroke-width', '1.5');
    node.setAttribute('stroke-linecap', 'round');
    node.setAttribute('stroke-linejoin', 'round');
    node.setAttribute('aria-hidden', 'true');
    const path = document.createElementNS(node.namespaceURI, 'path');
    path.setAttribute('d', {
      chat: 'M20 11a8 8 0 0 1-8 8H7l-4 2 1-6a8 8 0 1 1 16-4Z',
      delete: 'M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7',
      mark: 'M12 20C6 17 3 12 5 7c4-1 7 3 7 8 0-5 3-9 7-8 2 5-1 10-7 13ZM12 14C9 10 9 5 12 3c3 2 3 7 0 11Z'
    }[name]);
    node.append(path);
    return node;
  };
  function setBusy(value) {
    busy = value;
    input.disabled = value || voiceBusy;
    sendButton.disabled = value || voiceBusy || !input.value.trim();
    window.dispatchEvent(new Event('mindcare:busy'));
  }
  function showError(error) {
    errorBox.replaceChildren(document.createTextNode(error.message));
    if (error.status === 401) {
      const link = element('a', '', ' Log in again');
      link.href = '/login';
      errorBox.append(link);
    }
    errorBox.hidden = false;
  }
  function updateInput() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 160) + 'px';
    const count = document.getElementById('character-count');
    count.textContent = `${input.value.length.toLocaleString()} / 4,000`;
    count.hidden = input.value.length < 500;
    sendButton.disabled = busy || voiceBusy || !input.value.trim();
  }
  function scrollBottom() { scrollArea.scrollTop = scrollArea.scrollHeight; }
  function setDrawer(open, restoreFocus = true) {
    sidebar.classList.toggle('is-open', open);
    overlay.hidden = !open;
    menuButton.setAttribute('aria-expanded', String(open));
    document.getElementById('main').inert = open;
    if (open) document.getElementById('close-sidebar').focus();
    else if (restoreFocus && window.matchMedia('(max-width:760px)').matches) menuButton.focus();
  }
  menuButton.addEventListener('click', () => setDrawer(true));
  document.getElementById('close-sidebar').addEventListener('click', () => setDrawer(false));
  overlay.addEventListener('click', () => setDrawer(false));
  document.addEventListener('keydown', event => {
    if (!sidebar.classList.contains('is-open') || deleteDialog.open) return;
    if (event.key === 'Escape') setDrawer(false);
    if (event.key === 'Tab') {
      const focusable = [...sidebar.querySelectorAll('a,button:not(:disabled),input:not([type="hidden"])')];
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  window.matchMedia('(min-width:761px)').addEventListener('change', event => { if (event.matches) setDrawer(false, false); });

  function renderHistory() {
    historyList.replaceChildren();
    document.getElementById('history-count').textContent = String(conversations.length);
    if (!conversations.length) historyList.append(element('p', 'history-empty', 'A fresh start. Your conversations will appear here.'));
    conversations.forEach(conversation => {
      const row = element('div', `history-item${conversation.id === conversationId ? ' active' : ''}`);
      const openButton = element('button', 'history-open');
      openButton.append(svg('chat'), element('span', 'history-title', conversation.title));
      openButton.title = conversation.title;
      if (conversation.id === conversationId) openButton.setAttribute('aria-current', 'true');
      openButton.addEventListener('click', () => openConversation(conversation.id));
      const removeButton = element('button', 'history-delete');
      removeButton.setAttribute('aria-label', `Delete ${conversation.title}`);
      removeButton.append(svg('delete'));
      removeButton.addEventListener('click', () => {
        cancelActivity();
        deleteId = conversation.id;
        deleteDialog.returnValue = '';
        deleteDialog.showModal();
      });

      row.append(openButton, removeButton);
      historyList.append(row);
    });
  }
  async function refreshHistory() {
    const data = await request('/api/conversations');
    conversations = data.conversations;
    renderHistory();
  }
  function setConversation(data) {
    conversationId = data.id;
    title.textContent = data.title;
    history.replaceState(null, '', `/conversations/${data.id}`);
    messages.replaceChildren();
    emptyState.hidden = data.messages.length > 0;
    data.messages.forEach(renderMessage);
    renderHistory();
    scrollBottom();
  }
  async function openConversation(id) {
    cancelActivity();
    const generation = epoch;
    const controller = activeRequest = new AbortController();
    setBusy(true);
    errorBox.hidden = true;
    try {
      const data = await request(`/api/conversations/${id}`, {signal: controller.signal});
      if (generation !== epoch) return;
      input.value = '';
      retry = null;
      setConversation(data.conversation);
      setDrawer(false, false);
    } catch (error) { if (error.name !== 'AbortError' && generation === epoch) showError(error); }
    finally { if (generation === epoch) { setBusy(false); updateInput(); input.focus(); } }
  }
  function resetConversation() {
    cancelActivity();
    retry = null;
    conversationId = null;
    title.textContent = 'Your space to reflect';
    messages.replaceChildren();
    emptyState.hidden = false;
    input.value = '';
    updateInput();
    history.replaceState(null, '', '/chat');
    renderHistory();
  }
  document.getElementById('new-conversation').addEventListener('click', async () => {
    cancelActivity();
    const generation = epoch;
    const controller = activeRequest = new AbortController();
    setBusy(true);
    errorBox.hidden = true;
    try {
      const data = await request('/api/conversations/new', {method: 'POST', signal: controller.signal});
      if (generation !== epoch) return;
      retry = null;
      input.value = '';
      updateInput();
      setConversation({...data.conversation, messages: []});
      await refreshHistory();
      setDrawer(false, false);
    } catch (error) { if (error.name !== 'AbortError' && generation === epoch) showError(error); }
    finally { if (generation === epoch) { setBusy(false); updateInput(); input.focus(); } }
  });
  deleteDialog.addEventListener('close', async () => {
    if (deleteDialog.returnValue !== 'delete' || !deleteId) return;
    cancelActivity();
    setBusy(true);
    errorBox.hidden = true;
    try {
      await request(`/api/conversations/${deleteId}`, {method: 'DELETE'});
      if (deleteId === conversationId) resetConversation();
      await refreshHistory();
    } catch (error) { showError(error); }
    finally { deleteId = null; setBusy(false); }
  });

  function renderResources(resources, parent) {
    if (!resources?.length) return;
    const section = element('section', 'resources');
    section.append(element('h3', '', 'Recommended resources'));
    const grid = element('div', 'resource-grid');
    resources.slice(0, 3).forEach(resource => {
      let url;
      try { url = new URL(resource.url); } catch { return; }
      if (url.protocol !== 'https:' || url.hostname !== 'www.youtube.com') return;
      const card = element('a', 'resource-card');
      card.href = url.href;
      card.target = '_blank';
      card.rel = 'noopener noreferrer';
      card.setAttribute('aria-label', `${resource.title} (opens YouTube search in a new tab)`);
      const top = element('div', 'resource-top');
      top.append(element('span', 'resource-play', '▷'), element('span', 'category-badge', resource.category));
      card.append(top, element('h4', '', resource.title), element('p', '', resource.description), element('span', 'resource-link', 'Open resource ↗'));
      grid.append(card);
    });
    section.append(grid, element('p', 'resource-note', 'Explore on YouTube · Search results may vary'));
    parent.append(section);
  }
  function renderMessage(message) {
    const bot = message.sender === 'bot';
    const article = element('article', `message message-${bot ? 'bot' : 'user'}`);
    if (message.id) article.dataset.messageId = message.id;
    if (bot) {
      const heading = element('div', 'message-heading');
      const avatar = element('span', 'bot-avatar');
      avatar.append(svg('mark'));
      heading.append(avatar, document.createTextNode('MindCare'));
      heading.append(element('span', 'provider-label', {gemini: 'Gemini', local_fallback: 'Local fallback', safety: 'Safety support'}[message.provider] || 'Local support'));
      article.append(heading);
    }
    article.append(element('div', 'message-body', message.content));
    if (bot && message.risk_level === 'high') {
      const notice = element('div', 'safety-notice', 'If you may be in immediate danger, contact local emergency services now. This chatbot cannot provide emergency assistance.');
      const link = element('a', '', 'Read our safety information →');
      link.href = '/about#safety';
      notice.append(link);
      article.append(notice);
    } else if (bot) {
      const analysis = element('details', 'analysis');
      const summary = element('summary');
      const label = message.sentiment.label;
      summary.append(document.createTextNode('Message tone '), element('span', `sentiment-badge ${label}`, label[0].toUpperCase() + label.slice(1)), document.createTextNode('View analysis'));
      analysis.append(summary, element('p', '', `Topic: ${message.topic} · Tone score: ${message.sentiment.score.toFixed(2)}. This is an estimate of your words, not an assessment of your mental health.`));
      article.append(analysis);
      renderResources(message.recommendations, article);
    }
    if (message.created_at) {
      const time = element('time', 'message-time', new Date(message.created_at).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}));
      time.dateTime = message.created_at;
      article.append(time);
    }
    if (bot && message.id) {
      const speak = element('button', 'speech-button', 'Read reply aloud');
      speak.type = 'button';
      speak.hidden = !window.mindcare.voice?.available;
      speak.addEventListener('click', () => window.mindcare.voice?.speak(message.id));
      article.append(speak);
    }
    messages.append(article);
    return article;
  }
  function typingIndicator() {
    const article = element('div', 'message message-bot');
    article.setAttribute('aria-label', 'MindCare is responding');
    const heading = element('div', 'message-heading');
    const avatar = element('span', 'bot-avatar');
    avatar.append(svg('mark'));
    heading.append(avatar, document.createTextNode('MindCare'));
    const dots = element('div', 'typing');
    dots.append(element('span'), element('span'), element('span'));
    article.append(heading, dots);
    messages.append(article);
    return article;
  }
  document.querySelectorAll('[data-suggestion]').forEach(button => button.addEventListener('click', () => {
    if (busy || voiceBusy) return;
    input.value = button.dataset.suggestion;
    updateInput();
    input.focus();
  }));
  input.addEventListener('input', updateInput);
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      if (!sendButton.disabled) document.getElementById('chat-form').requestSubmit();
    }
  });
  async function ensureConversation(signal) {
    if (!conversationId) {
      const generation = epoch;
      const created = await request('/api/conversations/new', {method: 'POST', signal});
      if (generation !== epoch || signal?.aborted) throw new DOMException('Cancelled', 'AbortError');
      conversationId = created.conversation_id;
      history.replaceState(null, '', `/conversations/${conversationId}`);
    }
    return conversationId;
  }
  async function submitMessage(text, {inputMode = 'text', signal, useGemini = false} = {}) {
    if (busy) throw new Error('Please wait for the current message.');
    const generation = epoch;
    const controller = activeRequest = new AbortController();
    const abort = () => controller.abort();
    signal?.addEventListener('abort', abort, {once: true});
    if (signal?.aborted) abort();
    setBusy(true);
    errorBox.hidden = true;
    emptyState.hidden = true;
    const optimistic = renderMessage({sender: 'user', content: text});
    const typing = typingIndicator();
    input.value = '';
    updateInput();
    scrollBottom();
    try {
      const id = await ensureConversation(controller.signal);
      // A transcript restored after a lost voice response is retried by the text composer.
      // Preserve its original mode and request ID so it cannot save a second turn.
      if (retry?.conversationId === id && retry.text === text && retry.useGemini === useGemini) inputMode = retry.inputMode;
      const signature = JSON.stringify([id, text, inputMode, useGemini]);
      if (retry?.signature !== signature) retry = {signature, id: crypto.randomUUID?.() || Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join(''), conversationId: id, text, inputMode, useGemini};
      const data = await request('/api/chat', {method: 'POST', signal: controller.signal,
        timeoutMs: window.mindcare.voice?.timeoutMs || 75000,
        body: JSON.stringify({conversation_id: id, message: text, request_id: retry.id, input_mode: inputMode, use_gemini: useGemini})});
      if (generation !== epoch || controller.signal.aborted) throw new DOMException('Cancelled', 'AbortError');
      retry = null;
      optimistic.remove();
      typing.remove();
      // Replays carry stable message IDs, so recovering a lost response never duplicates the display.
      data.messages.forEach(message => {
        messages.querySelector(`[data-message-id="${message.id}"]`)?.remove();
        renderMessage(message);
      });
      title.textContent = data.title;
      if (data.notice) showError(new Error(data.notice));
      scrollBottom();
      refreshHistory().catch(showError);
      return data;
    } catch (error) {
      optimistic.remove();
      if (generation === epoch) {
        input.value = text;
        if (!messages.children.length) emptyState.hidden = false;
      }
      throw error;
    } finally {
      typing.remove();
      signal?.removeEventListener('abort', abort);
      if (generation === epoch) { activeRequest = null; setBusy(false); updateInput(); }
    }
  }
  document.getElementById('chat-form').addEventListener('submit', async event => {
    event.preventDefault();
    const text = input.value.trim();
    if (busy || voiceBusy || !text) return;
    const generation = epoch;
    try {
      const useGemini = await window.mindcare.voice?.ensureConsent(false) || false;
      if (generation !== epoch) return;
      await submitMessage(text, {useGemini});
    } catch (error) { if (error.name !== 'AbortError' && generation === epoch) showError(error); }
    if (generation === epoch) input.focus();
  });
  window.mindcare.chat = {
    ensureConversation, submitMessage,
    get conversationId() { return conversationId; },
    get busy() { return busy; },
    setVoiceBusy(value) { voiceBusy = value; setBusy(busy); },
    setDraft(text) { input.value = text; updateInput(); },
    cancel: cancelActivity
  };
  window.addEventListener('mindcare:capabilities', () => {
    messages.querySelectorAll('.speech-button').forEach(button => { button.hidden = !window.mindcare.voice?.available; });
  });
  window.addEventListener('pagehide', cancelActivity);

  async function initialize() {
    setBusy(true);
    try {
      await refreshHistory();
      if (conversationId) {
        const data = await request(`/api/conversations/${conversationId}`);
        setConversation(data.conversation);
      }
    } catch (error) { showError(error); }
    finally { setBusy(false); }
  }
  initialize();
})();
