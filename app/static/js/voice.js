'use strict';
(() => {
  const chat = window.mindcare.chat;
  const request = window.mindcare.request;
  const byId = id => document.getElementById(id);
  const panel = byId('voice-panel'), status = byId('voice-status'), meter = byId('voice-level'), clock = byId('voice-timer');
  const dictation = byId('dictation-button'), conversation = byId('voice-button'), stop = byId('voice-stop');
  const cancelButton = byId('voice-cancel'), end = byId('voice-end'), replay = byId('voice-replay'), play = byId('voice-play');
  const dialog = byId('voice-consent');
  let caps = {}, state = 'idle', generation = 0, capture = null, controller = null, timer = null;
  let audio = null, audioURL = null, lastMessageId = null, voiceMode = false, localChoice = false;
  let consentPromise = null, consentResolve = null;
  const supported = window.isSecureContext && navigator.mediaDevices?.getUserMedia && window.AudioWorkletNode && window.OfflineAudioContext;
  function update() {
    panel.dataset.state = state;
    const working = !['idle', 'error'].includes(state);
    dictation.disabled = !caps.voice_enabled || !supported || working || chat.busy;
    conversation.disabled = dictation.disabled;
    conversation.textContent = voiceMode ? 'Speak again' : 'Voice conversation';
    stop.hidden = state !== 'recording';
    cancelButton.hidden = !working;
    end.hidden = !voiceMode;
    replay.hidden = !lastMessageId || working;
    play.hidden = state !== 'playback_blocked';
    byId('ai-settings').hidden = !caps.gemini_enabled;
    meter.hidden = clock.hidden = state !== 'recording';
    chat.setVoiceBusy(working);
  }
  function setState(value, message) { state = value; status.textContent = message; update(); }
  function releaseAudio() {
    if (audio) { audio.onended = audio.onerror = null; audio.pause(); audio.removeAttribute('src'); audio.load(); audio = null; }
    if (audioURL) { URL.revokeObjectURL(audioURL); audioURL = null; }
  }
  function cleanup() {
    generation++;
    controller?.abort(); controller = null;
    capture?.cancel(); capture = null;
    clearInterval(timer); timer = null;
    releaseAudio();
    meter.value = 0;
  }
  function cancel(showNotice = true) {
    cleanup();
    voiceMode = false;
    lastMessageId = null;
    setState('idle', showNotice ? 'Voice stopped. A sent message may still finish on the server; reopen its conversation to check.' : defaultStatus());
  }
  function defaultStatus() {
    if (!caps.voice_enabled) return 'Voice is unavailable. Text chat still works.';
    if (!supported) return 'Microphone recording requires HTTPS or localhost and a browser with AudioWorklet support.';
    return 'Dictate an editable draft, or record one voice conversation turn.';
  }
  function errorMessage(error) {
    if (error.name === 'NotAllowedError') return 'Microphone access was denied. Allow it in your browser settings, then try again.';
    if (error.name === 'NotFoundError') return 'No microphone was found. Connect one or use text chat.';
    if (error.name === 'NotReadableError') return 'Your microphone could not start. Check whether another app is using it.';
    return error.message || 'Voice could not complete. You can still type your message.';
  }
  async function ensureConsent(required = false, force = false) {
    await ready;
    if (!caps.gemini_enabled) return false;
    if (!force && caps.consent) return true;
    if (!force && localChoice && !required) return false;
    if (consentPromise) return consentPromise;
    consentPromise = new Promise(resolve => { consentResolve = resolve; });
    byId('consent-error').hidden = true;
    dialog.showModal();
    return consentPromise;
  }
  async function chooseConsent(accepted) {
    const buttons = dialog.querySelectorAll('button');
    buttons.forEach(button => { button.disabled = true; });
    try {
      await request('/api/voice/consent', {method: 'POST', body: JSON.stringify({accepted})});
      caps.consent = accepted;
      localChoice = !accepted;
      dialog.close();
      consentResolve?.(accepted);
      consentPromise = consentResolve = null;

    } catch (error) {
      byId('consent-error').textContent = error.message;
      byId('consent-error').hidden = false;
    } finally { buttons.forEach(button => { button.disabled = false; }); }
  }
  byId('consent-accept').addEventListener('click', () => chooseConsent(true));
  byId('consent-decline').addEventListener('click', () => chooseConsent(false));
  dialog.addEventListener('cancel', event => { event.preventDefault(); chooseConsent(false); });
  byId('ai-settings').addEventListener('click', () => { cancel(false); ensureConsent(false, true); });
  async function start(mode) {
    if (chat.busy || !['idle', 'error'].includes(state)) return;
    const beforeConsent = generation;
    if (!await ensureConsent(true) || beforeConsent !== generation) return;
    cleanup();
    const token = generation;
    voiceMode = mode === 'conversation';
    lastMessageId = null;
    controller = new AbortController();
    capture = new window.mindcare.AudioCapture();
    const recording = capture;
    setState('requesting_permission', 'Waiting for microphone permission…');
    try {
      await chat.ensureConversation(controller.signal);
      if (token !== generation) return;
      await recording.start(caps.max_seconds, value => { meter.value = value; }, () => finish(mode, token));
      if (token !== generation) return;
      const started = performance.now();
      clock.textContent = '0:00 / 0:' + String(caps.max_seconds).padStart(2, '0');
      timer = setInterval(() => {
        const seconds = Math.min(caps.max_seconds, Math.floor((performance.now() - started) / 1000));
        clock.textContent = '0:' + String(seconds).padStart(2, '0') + ' / 0:' + String(caps.max_seconds).padStart(2, '0');
      }, 200);
      stop.onclick = () => finish(mode, token);
      setState('recording', mode === 'dictation' ? 'Recording a draft. Stop when you are ready to transcribe.' : 'Listening. Stop when you are ready to send this turn.');
    } catch (error) {
      recording.cancel();
      if (token === generation && error.name !== 'AbortError') setState('error', errorMessage(error));
    }
  }
  async function finish(mode, token) {
    if (token !== generation || state !== 'recording') return;
    clearInterval(timer); timer = null;
    const recording = capture;
    setState('transcribing', 'Transcribing your recording…');
    try {
      const blob = await recording.finish();
      capture = null;
      if (token !== generation) return;
      if (blob.size > caps.max_upload_bytes) throw new Error('The recording is too large. Please record a shorter turn.');
      const form = new FormData();
      form.append('conversation_id', String(chat.conversationId));
      form.append('audio', blob, 'recording.wav');
      const result = await request('/api/voice/transcribe', {method: 'POST', body: form, signal: controller.signal, timeoutMs: caps.request_timeout_ms});
      if (token !== generation) return;
      chat.setDraft(result.transcript);
      if (mode === 'dictation') {
        setState('idle', 'Your transcript is ready. Edit it and press Send when you are ready.');
        byId('message-input').focus();
        return;
      }
      setState('generating_reply', 'Your transcript is ready. MindCare is responding…');
      const data = await chat.submitMessage(result.transcript, {inputMode: 'voice', useGemini: true, signal: controller.signal});
      if (token !== generation) return;
      lastMessageId = data.messages.find(message => message.sender === 'bot').id;
      await generateSpeech(lastMessageId, token);
    } catch (error) {
      recording?.cancel();
      if (token === generation && error.name !== 'AbortError') setState('error', errorMessage(error));
    }
  }
  async function playback(token) {
    if (token !== generation || !audio) return;
    try {
      await audio.play();
      if (token === generation) setState('playing', 'MindCare is speaking. You can stop playback at any time.');
    } catch (error) {
      if (token !== generation) return;
      if (error.name === 'NotAllowedError') setState('playback_blocked', 'Your browser paused automatic playback. Press Play reply to listen.');
      else { releaseAudio(); setState('error', 'Audio could not play. Your text reply is saved; use Retry speech.'); }
    }
  }
  async function generateSpeech(messageId, token) {
    setState('generating_speech', 'Your text reply is saved. Preparing its spoken version…');
    try {
      const blob = await request('/api/messages/' + messageId + '/speech', {method: 'POST', signal: controller.signal, timeoutMs: caps.request_timeout_ms, responseType: 'blob'});
      if (token !== generation) return;
      releaseAudio();
      audioURL = URL.createObjectURL(blob);
      audio = new Audio(audioURL);
      audio.onended = () => { if (token === generation) { releaseAudio(); setState('idle', voiceMode ? 'Your turn. Press Speak again to record.' : 'Playback finished.'); } };
      audio.onerror = () => { if (token === generation) { releaseAudio(); setState('error', 'Audio could not play. Your text reply is saved; use Retry speech.'); } };
      await playback(token);
    } catch (error) {
      if (token === generation && error.name !== 'AbortError') setState('error', errorMessage(error) + ' Your text reply is saved. Retry speech to hear it.');
    }
  }
  async function speak(messageId) {
    if (chat.busy) return;
    const beforeConsent = generation;
    if (!await ensureConsent(true) || beforeConsent !== generation) return;
    cleanup();
    controller = new AbortController();
    lastMessageId = messageId;
    await generateSpeech(messageId, generation);
  }
  dictation.addEventListener('click', () => start('dictation'));
  conversation.addEventListener('click', () => start('conversation'));
  cancelButton.addEventListener('click', () => { chat.cancel(); status.textContent = 'Stopped. A sent message may still finish; reopen its conversation to check.'; });
  end.addEventListener('click', () => { chat.cancel(); status.textContent = 'Voice conversation ended.'; });
  replay.addEventListener('click', () => speak(lastMessageId));
  play.addEventListener('click', () => playback(generation));
  window.addEventListener('mindcare:busy', () => {
    // Avoid update() here: it notifies chat and would recurse.
    const working = !['idle', 'error'].includes(state);
    dictation.disabled = conversation.disabled = !caps.voice_enabled || !supported || working || chat.busy;
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && ['recording', 'requesting_permission'].includes(state)) chat.cancel();
  });
  window.addEventListener('pagehide', () => cancel(false));
  document.querySelector('form[action="/logout"]')?.addEventListener('submit', () => chat.cancel());
  const ready = request('/api/voice/capabilities').then(data => {
    caps = data;
    setState('idle', defaultStatus());
    window.dispatchEvent(new Event('mindcare:capabilities'));
  }).catch(error => setState('error', 'Voice settings could not load. Text chat remains available. ' + error.message));
  window.mindcare.voice = {cancel, speak, ensureConsent,
    get available() { return !!caps.voice_enabled; },
    get timeoutMs() { return caps.request_timeout_ms; }
  };
})();
