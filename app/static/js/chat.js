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
    input.disabled = value;
    document.getElementById('new-conversation').disabled = value;
    historyList.querySelectorAll('button').forEach(button => { button.disabled = value; });
    sendButton.disabled = value || !input.value.trim();
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
    sendButton.disabled = busy || !input.value.trim();
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
        if (busy) return;
        deleteId = conversation.id;
        deleteDialog.returnValue = '';
        deleteDialog.showModal();
      });
      openButton.disabled = removeButton.disabled = busy;
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
    if (busy) return;
    setBusy(true);
    errorBox.hidden = true;
    try {
      const data = await request(`/api/conversations/${id}`);
      setConversation(data.conversation);
      setDrawer(false, false);
    } catch (error) { showError(error); }
    finally { setBusy(false); input.focus(); }
  }
  function resetConversation() {
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
    if (busy) return;
    setBusy(true);
    errorBox.hidden = true;
    try {
      const data = await request('/api/conversations/new', {method: 'POST'});
      input.value = '';
      updateInput();
      setConversation({...data.conversation, messages: []});
      await refreshHistory();
      setDrawer(false, false);
    } catch (error) { showError(error); }
    finally { setBusy(false); input.focus(); }
  });
  deleteDialog.addEventListener('close', async () => {
    if (deleteDialog.returnValue !== 'delete' || !deleteId || busy) return;
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
    if (busy) return;
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
  document.getElementById('chat-form').addEventListener('submit', async event => {
    event.preventDefault();
    const text = input.value.trim();
    if (busy || !text) return;
    setBusy(true);
    errorBox.hidden = true;
    emptyState.hidden = true;
    const optimistic = renderMessage({sender: 'user', content: text});
    const typing = typingIndicator();
    input.value = '';
    updateInput();
    scrollBottom();
    let saved = false;
    try {
      if (!conversationId) {
        const created = await request('/api/conversations/new', {method: 'POST'});
        conversationId = created.conversation_id;
        history.replaceState(null, '', `/conversations/${conversationId}`);
      }
      const data = await request('/api/chat', {method: 'POST', body: JSON.stringify({conversation_id: conversationId, message: text})});
      saved = true;
      optimistic.remove();
      typing.remove();
      data.messages.forEach(renderMessage);
      title.textContent = data.title;
      scrollBottom();
      await refreshHistory();
    } catch (error) {
      typing.remove();
      if (!saved) {
        optimistic.remove();
        input.value = text;
        // A disconnected response may still have committed. Reload before offering a retry.
        if (conversationId && !error.status) {
          try {
            const recovered = await request(`/api/conversations/${conversationId}`);
            setConversation(recovered.conversation);
            error.message += ' History has been refreshed; check for your message before sending again.';
          } catch { error.message += ' Reopen this conversation to check whether it was saved before retrying.'; }
        }
        if (!messages.children.length) emptyState.hidden = false;
      }
      showError(error);
    } finally {
      typing.remove();
      setBusy(false);
      updateInput();
      input.focus();
    }
  });

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
