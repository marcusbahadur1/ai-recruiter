/**
 * AI Recruiter Chat Widget
 * Embed on any website via:
 *
 *   <script>
 *     window.AIRecruiterConfig = {
 *       tenantSlug: 'your-slug',
 *       primaryColor: '#00C2E0'   // optional
 *     };
 *   </script>
 *   <script src="https://app.airecruiterz.com/widget/widget.js" async></script>
 *
 * The widget posts to POST /api/v1/widget/{slug}/chat on the AI Recruiter API.
 */
(function () {
  'use strict';

  var config = window.AIRecruiterConfig || {};
  var slug = config.tenantSlug || '';
  var primaryColor = config.primaryColor || '#00C2E0';
  var botName = config.botName || 'Chat with us';
  var apiBase = config.apiBase || 'https://app.airecruiterz.com';

  if (!slug) {
    console.warn('[AIRecruiter Widget] tenantSlug is required in window.AIRecruiterConfig');
    return;
  }

  // ── Styles ─────────────────────────────────────────────────────────────────

  var css = [
    '#air-widget-btn{position:fixed;bottom:24px;right:24px;z-index:2147483646;',
    'width:56px;height:56px;border-radius:50%;border:none;cursor:pointer;',
    'display:flex;align-items:center;justify-content:center;font-size:26px;',
    'box-shadow:0 4px 20px rgba(0,0,0,0.25);transition:transform 0.2s,box-shadow 0.2s;}',
    '#air-widget-btn:hover{transform:scale(1.08);}',

    '#air-widget-panel{position:fixed;bottom:92px;right:24px;z-index:2147483645;',
    'width:360px;height:520px;border-radius:16px;overflow:hidden;',
    'display:flex;flex-direction:column;',
    'box-shadow:0 8px 40px rgba(0,0,0,0.28);',
    'background:#0d1b2a;border:1px solid rgba(255,255,255,0.08);',
    'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;',
    'transition:opacity 0.2s,transform 0.2s;transform-origin:bottom right;}',
    '#air-widget-panel.air-hidden{opacity:0;transform:scale(0.92);pointer-events:none;}',

    '#air-widget-header{display:flex;align-items:center;gap:10px;padding:14px 16px;',
    'border-bottom:1px solid rgba(255,255,255,0.08);flex-shrink:0;}',
    '#air-widget-header-dot{width:8px;height:8px;border-radius:50%;background:#27c93f;flex-shrink:0;}',
    '#air-widget-header-name{font-size:14px;font-weight:600;color:#f8fafc;flex:1;}',
    '#air-widget-header-close{background:none;border:none;cursor:pointer;',
    'color:rgba(255,255,255,0.4);font-size:20px;line-height:1;padding:0;}',
    '#air-widget-header-close:hover{color:#f8fafc;}',

    '#air-widget-messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;}',
    '#air-widget-messages::-webkit-scrollbar{width:4px;}',
    '#air-widget-messages::-webkit-scrollbar-track{background:transparent;}',
    '#air-widget-messages::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.15);border-radius:2px;}',

    '.air-msg{max-width:82%;padding:9px 13px;border-radius:12px;font-size:13px;line-height:1.55;word-break:break-word;}',
    '.air-msg-bot{background:#162538;color:#f8fafc;border-bottom-left-radius:3px;align-self:flex-start;}',
    '.air-msg-user{color:#fff;border-bottom-right-radius:3px;align-self:flex-end;}',

    '.air-typing{display:flex;gap:4px;align-items:center;padding:10px 13px;}',
    '.air-typing span{width:7px;height:7px;border-radius:50%;background:rgba(255,255,255,0.3);',
    'animation:air-bounce 1.2s infinite ease-in-out;}',
    '.air-typing span:nth-child(2){animation-delay:0.2s;}',
    '.air-typing span:nth-child(3){animation-delay:0.4s;}',
    '@keyframes air-bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-6px)}}',

    '#air-widget-footer{padding:10px 12px;border-top:1px solid rgba(255,255,255,0.08);',
    'display:flex;gap:8px;align-items:flex-end;flex-shrink:0;}',
    '#air-widget-input{flex:1;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);',
    'border-radius:10px;padding:9px 12px;font-size:13px;color:#f8fafc;outline:none;resize:none;',
    'max-height:100px;font-family:inherit;line-height:1.4;}',
    '#air-widget-input::placeholder{color:rgba(255,255,255,0.3);}',
    '#air-widget-input:focus{border-color:rgba(255,255,255,0.2);}',
    '#air-widget-send{border:none;cursor:pointer;width:36px;height:36px;border-radius:8px;',
    'flex-shrink:0;display:flex;align-items:center;justify-content:center;transition:opacity 0.15s;}',
    '#air-widget-send:hover{opacity:0.85;}',
    '#air-widget-send svg{display:block;}',

    '#air-widget-branding{text-align:center;font-size:10px;color:rgba(255,255,255,0.2);',
    'padding:4px 0 8px;flex-shrink:0;}',
    '#air-widget-branding a{color:rgba(255,255,255,0.25);text-decoration:none;}',
    '#air-widget-branding a:hover{color:rgba(255,255,255,0.4);}',
  ].join('');

  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  // ── Build DOM ───────────────────────────────────────────────────────────────

  // Panel
  var panel = document.createElement('div');
  panel.id = 'air-widget-panel';
  panel.className = 'air-hidden';

  // Header
  var header = document.createElement('div');
  header.id = 'air-widget-header';
  header.innerHTML = [
    '<div id="air-widget-header-dot"></div>',
    '<div id="air-widget-header-name">' + botName + '</div>',
    '<button id="air-widget-header-close" aria-label="Close chat">&times;</button>',
  ].join('');
  panel.appendChild(header);

  // Messages area
  var messagesEl = document.createElement('div');
  messagesEl.id = 'air-widget-messages';
  panel.appendChild(messagesEl);

  // Footer input
  var footer = document.createElement('div');
  footer.id = 'air-widget-footer';
  footer.innerHTML = [
    '<textarea id="air-widget-input" rows="1" placeholder="Type a message…" aria-label="Message"></textarea>',
    '<button id="air-widget-send" aria-label="Send">',
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">',
    '<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>',
    '</svg></button>',
  ].join('');
  panel.appendChild(footer);

  // Branding
  var branding = document.createElement('div');
  branding.id = 'air-widget-branding';
  branding.innerHTML = 'Powered by <a href="https://airecruiterz.com" target="_blank" rel="noopener">AI Recruiter</a>';
  panel.appendChild(branding);

  // Trigger button
  var btn = document.createElement('button');
  btn.id = 'air-widget-btn';
  btn.setAttribute('aria-label', 'Open chat');
  btn.style.background = primaryColor;
  btn.style.boxShadow = '0 4px 20px ' + primaryColor + '66';
  btn.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24" fill="white"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>';

  document.body.appendChild(panel);
  document.body.appendChild(btn);

  // Apply primary colour to send button and user messages
  var sendBtn = document.getElementById('air-widget-send');
  sendBtn.style.background = primaryColor;

  // ── State ───────────────────────────────────────────────────────────────────

  var isOpen = false;
  var isLoading = false;
  var tenantName = null;
  var history = []; // [{role:'user'|'assistant', content:'...'}]

  // ── Helpers ─────────────────────────────────────────────────────────────────

  function scrollBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addMessage(role, text) {
    var el = document.createElement('div');
    el.className = 'air-msg ' + (role === 'user' ? 'air-msg-user' : 'air-msg-bot');
    if (role === 'user') el.style.background = primaryColor;
    el.textContent = text;
    messagesEl.appendChild(el);
    scrollBottom();
    return el;
  }

  function showTyping() {
    var el = document.createElement('div');
    el.className = 'air-msg air-msg-bot air-typing';
    el.id = 'air-typing-indicator';
    el.innerHTML = '<span></span><span></span><span></span>';
    messagesEl.appendChild(el);
    scrollBottom();
  }

  function removeTyping() {
    var t = document.getElementById('air-typing-indicator');
    if (t) t.parentNode.removeChild(t);
  }

  function updateHeaderName(name) {
    var nameEl = document.getElementById('air-widget-header-name');
    if (nameEl && name) nameEl.textContent = 'Chat with ' + name;
  }

  function showGreeting() {
    if (messagesEl.children.length === 0) {
      addMessage('assistant', 'Hi! I\'m here to help answer questions about our recruitment services and open positions. What can I help you with?');
    }
  }

  // ── API call ─────────────────────────────────────────────────────────────────

  function sendMessage(text) {
    if (!text.trim() || isLoading) return;

    addMessage('user', text);
    history.push({ role: 'user', content: text });

    isLoading = true;
    showTyping();

    var xhr = new XMLHttpRequest();
    xhr.open('POST', apiBase + '/api/v1/widget/' + encodeURIComponent(slug) + '/chat');
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.timeout = 30000;

    xhr.onload = function () {
      removeTyping();
      isLoading = false;
      if (xhr.status === 200) {
        try {
          var data = JSON.parse(xhr.responseText);
          var reply = data.reply || 'Sorry, I didn\'t catch that.';
          if (data.tenant_name && !tenantName) {
            tenantName = data.tenant_name;
            updateHeaderName(tenantName);
          }
          addMessage('assistant', reply);
          history.push({ role: 'assistant', content: reply });
        } catch (e) {
          addMessage('assistant', 'Something went wrong. Please try again.');
        }
      } else if (xhr.status === 429) {
        addMessage('assistant', 'You\'re sending messages too quickly. Please wait a moment and try again.');
      } else {
        addMessage('assistant', 'I\'m unable to respond right now. Please contact us directly for assistance.');
      }
    };

    xhr.onerror = function () {
      removeTyping();
      isLoading = false;
      addMessage('assistant', 'Connection error. Please check your internet connection and try again.');
    };

    xhr.ontimeout = function () {
      removeTyping();
      isLoading = false;
      addMessage('assistant', 'The response took too long. Please try again.');
    };

    xhr.send(JSON.stringify({
      message: text,
      conversation_history: history.slice(-6), // last 3 exchanges
    }));
  }

  // ── Event handlers ──────────────────────────────────────────────────────────

  btn.addEventListener('click', function () {
    isOpen = !isOpen;
    if (isOpen) {
      panel.classList.remove('air-hidden');
      btn.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
      showGreeting();
      var input = document.getElementById('air-widget-input');
      if (input) setTimeout(function () { input.focus(); }, 150);
    } else {
      panel.classList.add('air-hidden');
      btn.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24" fill="white"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>';
    }
  });

  document.getElementById('air-widget-header-close').addEventListener('click', function () {
    isOpen = false;
    panel.classList.add('air-hidden');
    btn.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24" fill="white"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>';
  });

  var inputEl = document.getElementById('air-widget-input');

  inputEl.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      var text = inputEl.value.trim();
      if (text) {
        inputEl.value = '';
        inputEl.style.height = 'auto';
        sendMessage(text);
      }
    }
  });

  inputEl.addEventListener('input', function () {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 100) + 'px';
  });

  sendBtn.addEventListener('click', function () {
    var text = inputEl.value.trim();
    if (text) {
      inputEl.value = '';
      inputEl.style.height = 'auto';
      sendMessage(text);
    }
  });

})();
