/**
 * Chat UI — Frontend
 * Features: session management, streaming chat, markdown rendering,
 *           inline thinking and tool-call messages
 */

// ── Markdown (load marked.js from CDN) ──

function loadMarked() {
    return new Promise(resolve => {
        if (window.marked) return resolve();
        const s = document.createElement('script');
        s.src = 'https://cdn.jsdelivr.net/npm/marked/marked.min.js';
        s.onload = () => {
            window.marked.setOptions({ breaks: true, gfm: true });
            resolve();
        };
        s.onerror = () => resolve();
        document.head.appendChild(s);
    });
}

function renderMarkdown(text) {
    if (window.marked) return window.marked.parse(text);
    return text.split('\n\n').map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');
}

// ── State ──

// Same-origin — backend and frontend on port 8004
const API_URL = '';

let sessions = JSON.parse(localStorage.getItem('fuel_demo_sessions') || '{}');
let currentSessionId = null;
let isStreaming = false;

function saveSessions() {
    localStorage.setItem('fuel_demo_sessions', JSON.stringify(sessions));
}

function genId() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

// ── DOM ──

const $ = s => document.querySelector(s);

const newChatBtn    = $('#newChatBtn');
const chatHistory   = $('#chatHistory');
const chatArea      = $('#chatArea');
const messagesEl    = $('#messages');
const welcomeEl     = $('#welcome');
const messageInput  = $('#messageInput');
const sendBtn       = $('#sendBtn');
const chatForm      = $('#chatForm');
const statusBar     = $('#statusBar');
const statusText    = $('#statusText');
// ── Status bar ──

function showStatus(status, text) {
    statusBar.style.display = 'flex';
    statusText.textContent = text || _STATUS_TEXTS[status];
}

function hideStatus() {
    statusBar.style.display = 'none';
}

const _STATUS_TEXTS = {
    thinking: '思考中...',
    replying: '正在回复...',
    tool_running: '调用工具中...',
    idle: '就绪',
};

// ── Session helpers ──

function getMessages(sid) {
    return sessions[sid]?.messages || [];
}

function pushMessage(sid, msg) {
    if (!sessions[sid]) return;
    sessions[sid].messages.push(msg);
    sessions[sid].lastUpdated = Date.now();
    saveSessions();
}

function updateLastAssistant(sid, content) {
    const msgs = sessions[sid].messages;
    for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'assistant') {
            msgs[i].content = content;
            saveSessions();
            return;
        }
    }
}

// ── Render sidebar ──

function renderHistory() {
    chatHistory.innerHTML = '';

    const sorted = Object.entries(sessions)
        .sort((a, b) => b[1].lastUpdated - a[1].lastUpdated);

    for (const [id, session] of sorted) {
        const item = document.createElement('div');
        item.className = 'chat-history-item' + (id === currentSessionId ? ' active' : '');

        const firstUser = session.messages.find(m => m.role === 'user');
        const title = firstUser
            ? firstUser.content.slice(0, 32) + (firstUser.content.length > 32 ? '…' : '')
            : '新对话';

        item.innerHTML = `
            <span>${escapeHtml(title)}</span>
            <button class="delete-btn" data-id="${id}" title="Delete">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
        `;

        item.addEventListener('click', e => {
            if (e.target.closest('.delete-btn')) return;
            if (isStreaming) return;
            switchSession(id);
        });

        item.querySelector('.delete-btn').addEventListener('click', e => {
            e.stopPropagation();
            deleteSession(id);
        });

        chatHistory.appendChild(item);
    }
}

// ── Render messages ──

function renderMessages() {
    messagesEl.innerHTML = '';

    if (!currentSessionId || !sessions[currentSessionId]) return;

    const msgs = getMessages(currentSessionId);
    if (msgs.length === 0) {
        welcomeEl.style.display = '';
        return;
    }

    welcomeEl.style.display = 'none';

    for (const msg of msgs) {
        if (msg.role === 'user') {
            appendMessage('user', msg.content, false);
            continue;
        }

        // Assistant message — use two-area layout (process above, result below)
        let steps = msg.processSteps || [];

        // Backward compatibility: old messages use reasoning/toolCalls
        if (steps.length === 0) {
            if (msg.reasoning) {
                steps.push({ type: 'reasoning', text: msg.reasoning });
            }
            if (msg.toolCalls) {
                for (const tc of msg.toolCalls) {
                    steps.push({ type: 'tool_call', name: tc.name, args: tc.args, status: tc.status, result: tc.result });
                }
            }
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'ai-response-wrapper';

        const processArea = document.createElement('div');
        processArea.className = 'process-area';
        if (steps.length === 0) processArea.style.display = 'none';

        const resultArea = document.createElement('div');
        resultArea.className = 'result-area';

        // Render process steps in chronological order
        for (const step of steps) {
            if (step.type === 'reasoning') {
                appendThinking(step.text, processArea, false);
            } else if (step.type === 'tool_call') {
                appendToolCall(step.name, step.args, step.status, step.result, processArea, false);
            }
        }

        const msgEl = document.createElement('div');
        msgEl.className = 'message assistant';
        msgEl.innerHTML = `
            <div class="message-avatar">AI</div>
            <div class="message-bubble">
                <div class="message-content">${renderMarkdown(msg.content || '')}</div>
            </div>
        `;
        resultArea.appendChild(msgEl);

        wrapper.appendChild(processArea);
        wrapper.appendChild(resultArea);
        messagesEl.appendChild(wrapper);
    }

    scrollBottom();
}

// ── Append inline messages ──

function createMessageEl(role, avatar, bubbleContent) {
    const el = document.createElement('div');
    el.className = `message ${role}`;
    el.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-bubble">
            <div class="message-content">${bubbleContent}</div>
        </div>
    `;
    messagesEl.appendChild(el);
    return el.querySelector('.message-content');
}

function appendMessage(role, content, animate = true) {
    const avatar = role === 'user' ? 'Y' : 'AI';
    const el = document.createElement('div');
    el.className = `message ${role}`;

    el.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-bubble">
            <div class="message-content"></div>
        </div>
    `;

    const contentEl = el.querySelector('.message-content');
    if (role === 'user') {
        contentEl.textContent = content;
    } else {
        contentEl.innerHTML = renderMarkdown(content || '');
    }

    messagesEl.appendChild(el);
    if (animate) scrollBottom();
    return contentEl;
}

function appendThinking(text, processEl, animate = true) {
    const contentHtml = `\n        <button class="collapse-toggle" onclick="toggleCollapse(this)"><span class="collapse-icon open">&#9654;</span>思考过程</button>\n        <div class="collapsible-body" style="max-height:9999px"><div class="thinking-content">${escapeHtml(text)}</div></div>\n    `;
    const el = document.createElement('div');
    el.className = 'message thinking';
    el.innerHTML = `
        <div class="message-avatar">\u{1F914}</div>
        <div class="message-bubble">
            <div class="message-content">${contentHtml}</div>
        </div>
    `;
    (processEl || messagesEl).appendChild(el);
    if (animate) scrollBottom();
    return el.querySelector('.message-content');
}

function appendToolCall(name, args, status, result, processEl, animate = true) {
    const argsStr = args ? JSON.stringify(args, null, 2) : '';
    const resultStr = (result !== undefined && result !== null) ? String(result).slice(0, 500) : '';

    let statusBadge = '';
    if (status === 'completed') {
        statusBadge = '<span class="tool-call-status done">\u2713 完成</span>';
    } else if (status === 'error') {
        statusBadge = '<span class="tool-call-status err">\u2717 失败</span>';
    } else {
        statusBadge = '<span class="tool-call-status running">\u27C3 运行中</span>';
    }

    let bodyHtml = '';
    if (argsStr) {
        bodyHtml += `<pre class="tool-call-args">${escapeHtml(argsStr)}</pre>`;
    }
    if (resultStr) {
        bodyHtml += `<pre class="tool-call-result">${escapeHtml(resultStr)}</pre>`;
    }

    const el = document.createElement('div');
    el.className = 'message tool-call';
    el.innerHTML = `
        <div class="message-avatar">\u{1F527}</div>
        <div class="message-bubble">
            <div class="message-content">
                <div class="tool-call-header">
                    <button class="collapse-toggle" onclick="toggleCollapse(this)"><span class="collapse-icon open">&#9654;</span>${escapeHtml(name)}</button>
                    ${statusBadge}
                </div>
                <div class="collapsible-body" style="max-height:9999px">${bodyHtml}</div>
            </div>
        </div>
    `;
    (processEl || messagesEl).appendChild(el);
    if (animate) scrollBottom();
    return el.querySelector('.message-content');
}

// ── DOM element update helpers for streaming ──

function updateThinkingContent(contentEl, text) {
    const body = contentEl.querySelector('.collapsible-body');
    if (!body) return;
    const thinkingDiv = body.querySelector('.thinking-content');
    if (thinkingDiv) {
        thinkingDiv.textContent = text;
        body.style.maxHeight = body.scrollHeight + 'px';
    }
}

function updateToolCallStatus(contentEl, status, result) {
    const header = contentEl.querySelector('.tool-call-header');
    if (header) {
        const statusEl = header.querySelector('.tool-call-status');
        if (statusEl) {
            statusEl.className = `tool-call-status ${status === 'completed' ? 'done' : status === 'error' ? 'err' : 'running'}`;
            statusEl.textContent = status === 'completed' ? '\u2713 完成' : status === 'error' ? '\u2717 失败' : '\u27C3 运行中';
        }
    }
    const body = contentEl.querySelector('.collapsible-body');
    if (result !== undefined) {
        let resultEl = body ? body.querySelector('.tool-call-result') : null;
        if (!resultEl) {
            resultEl = document.createElement('pre');
            resultEl.className = 'tool-call-result';
            (body || contentEl).appendChild(resultEl);
        }
        resultEl.textContent = String(result).slice(0, 500);
        if (body) body.style.maxHeight = body.scrollHeight + 'px';
    }
}

// ── Scroll & utils ──

function scrollBottom() {
    requestAnimationFrame(() => {
        chatArea.scrollTop = chatArea.scrollHeight;
    });
}

function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

// ── Collapse toggle ──

function toggleCollapse(btn) {
    const content = btn.closest('.message-content');
    const body = content.querySelector('.collapsible-body');
    const icon = btn.querySelector('.collapse-icon');
    if (!body) return;
    if (body.classList.contains('collapsed')) {
        body.classList.remove('collapsed');
        body.style.maxHeight = body.scrollHeight + 'px';
        if (icon) icon.classList.add('open');
    } else {
        body.style.maxHeight = body.scrollHeight + 'px';
        requestAnimationFrame(() => {
            body.classList.add('collapsed');
            if (icon) icon.classList.remove('open');
        });
    }
}

// ── Session actions ──

function newSession() {
    const id = genId();
    sessions[id] = { id, messages: [], created: Date.now(), lastUpdated: Date.now() };
    currentSessionId = id;
    saveSessions();
    renderHistory();
    renderMessages();
    messageInput.focus();
}

function switchSession(id) {
    currentSessionId = id;
    renderHistory();
    renderMessages();
    messageInput.focus();
}

function deleteSession(id) {
    delete sessions[id];
    saveSessions();

    if (currentSessionId === id) {
        const keys = Object.keys(sessions);
        currentSessionId = keys.length ? keys[keys.length - 1] : null;
    }

    renderHistory();
    renderMessages();
}

// ── Chat (Streaming with SSE) ──

async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isStreaming) return;

    if (!currentSessionId || !sessions[currentSessionId]) {
        newSession();
    }

    const sid = currentSessionId;

    // User message
    pushMessage(sid, { role: 'user', content: text });
    appendMessage('user', text);

    messageInput.value = '';
    messageInput.style.height = 'auto';
    updateSendBtn();

    // Create AI response wrapper with two areas: process (top) + result (bottom)
    isStreaming = true;
    updateSendBtn();
    showStatus('thinking', '思考中...');

    const wrapper = document.createElement('div');
    wrapper.className = 'ai-response-wrapper';
    wrapper.innerHTML = `
        <div class="process-area" id="processArea"></div>
        <div class="result-area">
            <div class="message assistant">
                <div class="message-avatar">AI</div>
                <div class="message-bubble">
                    <div class="message-content"></div>
                </div>
            </div>
        </div>
    `;
    messagesEl.appendChild(wrapper);
    scrollBottom();

    const processArea = wrapper.querySelector('#processArea');
    const contentEl = wrapper.querySelector('.result-area .message-content');

    // Typing indicator inside process area
    const typing = document.createElement('div');
    typing.className = 'typing-indicator';
    typing.id = 'typingIndicator';
    typing.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
    processArea.appendChild(typing);
    scrollBottom();

    // State object for streaming
    const state = { processSteps: [], fullContent: '' };

    // DOM element references for streaming inline messages
    const streamEls = { thinkingEls: [], toolCallEls: [] };

    try {
        await streamChat(sid, contentEl, state, streamEls, processArea);
    } catch (err) {
        console.error('Chat error:', err);
        contentEl.innerHTML = `<span style="color:#FF3B30">Error: ${escapeHtml(err.message)}</span>`;
    } finally {
        const ti = document.getElementById('typingIndicator');
        if (ti) ti.remove();

        // Hide empty process area
        if (processArea.children.length === 0) {
            processArea.style.display = 'none';
        }

        // Save final message with process steps (ordered)
        pushMessage(sid, {
            role: 'assistant',
            content: state.fullContent,
            processSteps: state.processSteps.length ? state.processSteps : null
        });

        isStreaming = false;
        updateSendBtn();
        hideStatus();
        messageInput.focus();
    }
}

async function streamChat(sid, contentEl, state, streamEls, processArea) {
    const lastUserMsg = getMessages(sid).filter(m => m.role === 'user').pop();
    if (!lastUserMsg) return;

    const resp = await fetch(`${API_URL}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message: lastUserMsg.content,
            session_id: sid,
            stream: true
        })
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    // Clear state arrays in place (do NOT reassign — caller needs the same object)
    state.processSteps.length = 0;
    state.fullContent = '';
    streamEls.thinkingEls = [];      // 所有思考消息元素
    streamEls.currentThinkingText = ''; // 当前这轮思考的文本
    streamEls.currentThinkingStepIndex = -1; // 当前思考块在 processSteps 中的索引
    streamEls.toolCallEls = [];
    streamEls.lastEventType = null;  // 跟踪上一类事件

    // Remove typing indicator when first content arrives
    let typingRemoved = false;
    function removeTyping() {
        if (!typingRemoved) {
            typingRemoved = true;
            const ti = document.getElementById('typingIndicator');
            if (ti) ti.remove();
        }
    }

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
            if (line.startsWith('event: ')) continue; // skip SSE event type

            if (line.startsWith('data: ')) {
                const data = line.slice(6);
                if (data === '[DONE]') continue;

                // JSON events from Agno stream_events
                if (data.startsWith('{')) {
                    try {
                        const evt = JSON.parse(data);
                        handleStreamEvent(evt, contentEl, state, streamEls, removeTyping, sid, processArea);
                    } catch (e) {
                        // Not valid JSON — skip silently (could be partial chunk)
                        console.warn('Failed to parse SSE data:', data.slice(0, 100), e.message);
                    }
                } else if (data && data !== '[DONE]') {
                    // Plain text streaming (legacy format)
                    removeTyping();
                    state.fullContent += data;
                    contentEl.innerHTML = renderMarkdown(state.fullContent);
                    updateLastAssistant(sid, state.fullContent);
                    scrollBottom();
                }
            }
        }
    }
}

function handleStreamEvent(evt, contentEl, state, streamEls, removeTyping, sid, processArea) {
    const ev = evt.event;
    const d = evt.data || {};

    // Auto-detect status from event type (agno-api doesn't send status events)
    const _STATUS_TEXTS = {
        thinking: '思考中...',
        replying: '正在回复...',
        tool_running: '调用工具...',
    };
    function autoStatus(s) {
        showStatus(s, _STATUS_TEXTS[s] || s);
    }

    switch (ev) {
        case 'content':
        case 'RunContent': {
            // Text content chunk
            const txt = d.content || '';
            if (txt) {
                removeTyping();
                state.fullContent += txt;
                contentEl.innerHTML = renderMarkdown(state.fullContent);
                updateLastAssistant(sid, state.fullContent);
                streamEls.lastEventType = 'content';
                autoStatus('replying');
            }

            // Reasoning embedded in content event (Qwen3 format)
            if (d.reasoning) {
                removeTyping();
                // 判断是否创建新的 thinking step
                if (!streamEls.lastEventType || streamEls.lastEventType !== 'reasoning') {
                    streamEls.currentThinkingText = d.reasoning;
                    const step = { type: 'reasoning', text: d.reasoning };
                    state.processSteps.push(step);
                    streamEls.currentThinkingStepIndex = state.processSteps.length - 1;
                    const el = appendThinking(d.reasoning, processArea, false);
                    streamEls.thinkingEls.push(el);
                } else {
                    // Continuation of same thinking round
                    streamEls.currentThinkingText += d.reasoning;
                    const lastEl = streamEls.thinkingEls[streamEls.thinkingEls.length - 1];
                    if (lastEl) {
                        updateThinkingContent(lastEl, streamEls.currentThinkingText);
                    }
                    if (streamEls.currentThinkingStepIndex >= 0) {
                        state.processSteps[streamEls.currentThinkingStepIndex].text = streamEls.currentThinkingText;
                    }
                }
                streamEls.lastEventType = 'reasoning';
                autoStatus('thinking');
            }
            scrollBottom();
            break;
        }

        case 'reasoning':
        case 'ReasoningContentDelta':
        case 'ReasoningStep': {
            const reasoning = d.content || d.text || '';
            removeTyping();
            autoStatus('thinking');

            if (reasoning) {
                // 判断是否创建新的 thinking step
                // lastEventType 不是 reasoning 说明是新的思考轮次（或首次）
                if (!streamEls.lastEventType || streamEls.lastEventType !== 'reasoning') {
                    streamEls.currentThinkingText = reasoning;
                    const step = { type: 'reasoning', text: reasoning };
                    state.processSteps.push(step);
                    streamEls.currentThinkingStepIndex = state.processSteps.length - 1;
                    const el = appendThinking(reasoning, processArea, true);
                    streamEls.thinkingEls.push(el);
                } else {
                    // 追加到当前的 thinking block
                    streamEls.currentThinkingText += reasoning;
                    const lastEl = streamEls.thinkingEls[streamEls.thinkingEls.length - 1];
                    if (lastEl) {
                        updateThinkingContent(lastEl, streamEls.currentThinkingText);
                    }
                    if (streamEls.currentThinkingStepIndex >= 0) {
                        state.processSteps[streamEls.currentThinkingStepIndex].text = streamEls.currentThinkingText;
                    }
                }
                streamEls.lastEventType = 'reasoning';
                scrollBottom();
            }
            // 空 content 的事件（ReasoningStarted/Completed）不更新 lastEventType
            // 这样下一个有内容的 reasoning 会根据上一次实质性事件判断是否新建
            break;
        }

        case 'tool_call':
        case 'ToolCallStarted':
            removeTyping();
            autoStatus('tool_running');
            const tc = {
                name: d.tool_name || d.name || 'unknown',
                args: d.tool_args || d.args || {},
                status: 'running',
                result: undefined
            };
            const step = { type: 'tool_call', ...tc };
            state.processSteps.push(step);
            const tcEl = appendToolCall(tc.name, tc.args, tc.status, undefined, processArea, true);
            streamEls.toolCallEls.push({ el: tcEl, tc: step, stepIndex: state.processSteps.length - 1 });
            streamEls.lastEventType = 'tool_call';
            scrollBottom();
            break;

        case 'tool_result':
        case 'ToolCallCompleted':
        case 'ToolCallError':
            if (streamEls.toolCallEls.length > 0) {
                const lastEntry = streamEls.toolCallEls[streamEls.toolCallEls.length - 1];
                const step = lastEntry.tc;
                step.status = d.is_error ? 'error' : 'completed';
                step.result = d.content || d.output || '';

                updateToolCallStatus(lastEntry.el, step.status, step.result);
                streamEls.lastEventType = 'tool_result';
                autoStatus('thinking');
                scrollBottom();
            }
            break;

        case 'run_completed':
        case 'RunCompleted':
            // reasoning_steps 是完整字符串，仅在 processSteps 为空时作为 fallback
            if (d.reasoning && state.processSteps.length === 0) {
                state.processSteps.push({ type: 'reasoning', text: d.reasoning });
            }
            if (d.reasoning_steps && state.processSteps.length === 0) {
                state.processSteps.push({ type: 'reasoning', text: d.reasoning_steps });
            }
            break;

        case 'status':
            showStatus(d.status, d.text);
            break;

        case 'error':
            console.warn('Stream error:', d.message);
            break;
    }
}

// ── Input handling ──

function updateSendBtn() {
    sendBtn.disabled = !messageInput.value.trim() || isStreaming;
}

messageInput.addEventListener('input', () => {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 150) + 'px';
    updateSendBtn();
});

messageInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

chatForm.addEventListener('submit', e => {
    e.preventDefault();
    sendMessage();
});

// ── New Chat button ──

newChatBtn.addEventListener('click', newSession);

// ── Init ──

async function init() {
    await loadMarked();

    const keys = Object.keys(sessions);
    if (keys.length > 0) {
        currentSessionId = sessions[currentSessionId]?.id ? currentSessionId : keys[keys.length - 1];
        renderHistory();
        renderMessages();
    } else {
        newSession();
    }

    messageInput.focus();
}

init();
