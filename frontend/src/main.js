// ============ CONFIGURATION ============
const STORAGE_KEYS = {
  API_URL: 'dualrag_api_url',
  API_KEY: 'dualrag_api_key',
  MODEL: 'dualrag_model',
  CHAT_HISTORY: 'dualrag_chat_history',
  CURRENT_CHAT: 'dualrag_current_chat',
  SIDEBAR_COLLAPSED: 'dualrag_sidebar_collapsed'
};

let API_CONFIG = {
  baseUrl: localStorage.getItem(STORAGE_KEYS.API_URL) || 'http://localhost:8000/api',
  apiKey: localStorage.getItem(STORAGE_KEYS.API_KEY) || '',
  model: localStorage.getItem(STORAGE_KEYS.MODEL) || 'gemini-2.5-flash',
};

// ============ STATE ============
let chatHistory = [];
let currentChatId = null;
let isProcessing = false;
let indexedDocuments = [];
let abortController = null;
let isManuallyStopped = false;

const MESSAGES_PER_PAGE = 20;
let currentPage = 0;
let allMessages = [];
let isLoadingMore = false;
let hasMoreMessages = false;

// ============ UI ELEMENTS ============
const sidebar = document.getElementById('sidebar');
const collapseBtn = document.getElementById('collapseBtn');
const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const stopBtn = document.getElementById('stopBtn');
const uploadTrigger = document.getElementById('uploadTrigger');
const fileUpload = document.getElementById('fileUpload');
const historyList = document.getElementById('historyList');
const newChatBtn = document.getElementById('newChatBtn');
const clearAllBtn = document.getElementById('clearAllBtn');
const docCountBtn = document.getElementById('docCountBtn');
const docDropdown = document.getElementById('docDropdown');
const docDropdownList = document.getElementById('docDropdownList');
const docCountText = document.getElementById('docCountText');
const refreshDocsBtn = document.getElementById('refreshDocsBtn');
const removeAllDocsBtn = document.getElementById('removeAllDocsBtn');
const uploadProgress = document.getElementById('uploadProgress');
const uploadProgressBar = document.getElementById('uploadProgressBar');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const settingsBtn = document.getElementById('settingsBtn');
const settingsBackdrop = document.getElementById('settingsBackdrop');
const apiUrlInput = document.getElementById('apiUrlInput');
const apiKeyInput = document.getElementById('apiKeyInput');
const modelInput = document.getElementById('modelInput');
const saveSettingsBtn = document.getElementById('saveSettingsBtn');
const closeSettingsBtn = document.getElementById('closeSettingsBtn');

// Alert modal elements
const alertBackdrop = document.getElementById('alertBackdrop');
const alertIcon = document.getElementById('alertIcon');
const alertTitle = document.getElementById('alertTitle');
const alertMessage = document.getElementById('alertMessage');
const alertActions = document.getElementById('alertActions');

// ============ ALERT MODAL SYSTEM ============
let alertResolve = null;

function showAlert({ icon = '', title = '', message = '', buttons = [], type = 'info' }) {
  return new Promise((resolve) => {
    alertResolve = resolve;
    
    const iconMap = {
      info: '<i class="fas fa-info-circle"></i>',
      warning: '<i class="fas fa-exclamation-triangle"></i>',
      error: '<i class="fas fa-times-circle"></i>',
      success: '<i class="fas fa-check-circle"></i>',
      question: '<i class="fas fa-question-circle"></i>'
    };
    
    alertIcon.innerHTML = icon || iconMap[type] || iconMap.info;
    alertIcon.className = 'alert-icon ' + type;
    alertTitle.textContent = title;
    alertMessage.textContent = message;
    
    alertActions.innerHTML = '';
    
    if (buttons.length === 0) {
      buttons = [{ text: 'OK', className: 'primary', value: true }];
    }
    
    buttons.forEach(btn => {
      const button = document.createElement('button');
      button.className = 'alert-btn ' + (btn.className || 'primary');
      button.textContent = btn.text;
      button.addEventListener('click', () => {
        closeAlert();
        resolve(btn.value !== undefined ? btn.value : btn.text);
      });
      alertActions.appendChild(button);
    });
    
    alertBackdrop.classList.add('active');
  });
}

function closeAlert() {
  alertBackdrop.classList.remove('active');
  if (alertResolve) {
    alertResolve = null;
  }
}

// Convenience methods
function showError(title, message) {
  return showAlert({ type: 'error', title, message });
}

function showSuccess(title, message) {
  return showAlert({ type: 'success', title, message });
}

function showWarning(title, message) {
  return showAlert({ type: 'warning', title, message });
}

function showConfirm(title, message) {
  return showAlert({
    type: 'question',
    title,
    message,
    buttons: [
      { text: 'Cancel', className: 'secondary', value: false },
      { text: 'Confirm', className: 'danger', value: true }
    ]
  });
}

// Close alert on backdrop click
alertBackdrop.addEventListener('click', (e) => {
  if (e.target === alertBackdrop) {
    closeAlert();
  }
});

// Close alert on Escape key
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && alertBackdrop.classList.contains('active')) {
    e.preventDefault();
    e.stopPropagation();
    closeAlert();
  }
});

// ============ PERSISTENCE ============
function saveToStorage() {
  try {
    localStorage.setItem(STORAGE_KEYS.CHAT_HISTORY, JSON.stringify(chatHistory));
    localStorage.setItem(STORAGE_KEYS.CURRENT_CHAT, currentChatId || '');
    localStorage.setItem(STORAGE_KEYS.SIDEBAR_COLLAPSED, sidebar.classList.contains('collapsed'));
  } catch (e) {
    console.warn('Failed to save to localStorage:', e);
  }
}

function loadFromStorage() {
  try {
    const savedHistory = localStorage.getItem(STORAGE_KEYS.CHAT_HISTORY);
    const savedChatId = localStorage.getItem(STORAGE_KEYS.CURRENT_CHAT);
    const sidebarCollapsed = localStorage.getItem(STORAGE_KEYS.SIDEBAR_COLLAPSED);
    
    if (savedHistory) {
      chatHistory = JSON.parse(savedHistory);
    }
    
    if (sidebarCollapsed === 'true') {
      sidebar.classList.add('collapsed');
      collapseBtn.querySelector('i').className = 'fas fa-chevron-right';
      collapseBtn.title = 'Expand Sidebar';
    }
    
    return { savedChatId };
  } catch (e) {
    console.warn('Failed to load from localStorage:', e);
    return { savedChatId: null };
  }
}

// ============ POSITION DOC DROPDOWN ============
function positionDocDropdown() {
  const btnRect = docCountBtn.getBoundingClientRect();
  const dropdownWidth = docDropdown.offsetWidth || 320;
  
  let left = btnRect.right - dropdownWidth;
  let top = btnRect.bottom + 8;
  
  if (left < 10) left = 10;
  if (left + dropdownWidth > window.innerWidth - 10) {
    left = window.innerWidth - dropdownWidth - 10;
  }
  
  if (top + 350 > window.innerHeight) {
    top = btnRect.top - 350 - 8;
  }
  
  docDropdown.style.left = `${left}px`;
  docDropdown.style.top = `${top}px`;
}

// ============ VIRTUAL SCROLLING ============
function initVirtualScroll() {
  chatMessages.addEventListener('scroll', handleScroll);
}

function handleScroll() {
  if (isLoadingMore || !hasMoreMessages) return;
  
  if (chatMessages.scrollTop < 100) {
    loadMoreMessages();
  }
}

function loadMoreMessages() {
  if (isLoadingMore || !hasMoreMessages) return;
  
  isLoadingMore = true;
  const prevScrollHeight = chatMessages.scrollHeight;
  const prevScrollTop = chatMessages.scrollTop;
  
  const nextPage = currentPage + 1;
  const startIndex = allMessages.length - (nextPage * MESSAGES_PER_PAGE);
  const endIndex = allMessages.length - (currentPage * MESSAGES_PER_PAGE);
  
  if (startIndex < 0) {
    hasMoreMessages = false;
    isLoadingMore = false;
    return;
  }
  
  const messagesToAdd = allMessages.slice(Math.max(0, startIndex), endIndex);
  
  const fragment = document.createDocumentFragment();
  messagesToAdd.forEach(msg => {
    const msgDiv = createMessageElement(msg.role, msg.content, msg.sources);
    if (msgDiv) fragment.appendChild(msgDiv);
  });
  
  if (chatMessages.firstChild) {
    chatMessages.insertBefore(fragment, chatMessages.firstChild);
  } else {
    chatMessages.appendChild(fragment);
  }
  
  currentPage = nextPage;
  
  const newScrollHeight = chatMessages.scrollHeight;
  const heightDiff = newScrollHeight - prevScrollHeight;
  chatMessages.scrollTop = prevScrollTop + heightDiff;
  
  hasMoreMessages = startIndex > 0;
  isLoadingMore = false;
}

// ============ MARKDOWN RENDERER ============
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function renderMarkdown(text) {
  if (!text) return '';
  
  const codeBlocks = [];
  text = text.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
    codeBlocks.push({ lang: lang || '', code: code.trim() });
    return `%%CODEBLOCK_${codeBlocks.length - 1}%%`;
  });
  
  const inlineCodeBlocks = [];
  text = text.replace(/`([^`]+)`/g, (match, code) => {
    inlineCodeBlocks.push(code);
    return `%%INLINECODE_${inlineCodeBlocks.length - 1}%%`;
  });
  
  let html = escapeHtml(text);
  
  html = html.replace(/%%INLINECODE_(\d+)%%/g, (match, index) => {
    const code = inlineCodeBlocks[parseInt(index)];
    return `<code>${code}</code>`;
  });
  
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  html = html.replace(/^(---+|\*\*\*+)$/gm, '<hr>');
  html = html.replace(/^[\*\-•] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*?<\/li>)\n(?=<li>)/g, '$1');
  html = html.replace(/((?:<li>.*?<\/li>\n?)+)/g, '<ul>$1</ul>');
  html = html.replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>');
  html = html.replace(/((?:<li>.*?<\/li>\n?)+)/g, (match) => {
    if ((match || '').includes('<ul>')) return match;
    return `<ol>${match}</ol>`;
  });
  html = html.replace(/\n\n/g, '<br><br>');
  html = html.replace(/\n/g, '<br>');
  html = html.replace(/<ul>\s*<\/ul>/g, '');
  html = html.replace(/<ol>\s*<\/ol>/g, '');
  
  html = html.replace(/%%CODEBLOCK_(\d+)%%/g, (match, index) => {
    const block = codeBlocks[parseInt(index)];
    return `<pre><code>${escapeHtml(block.code)}</code></pre>`;
  });
  
  return html;
}

function createMessageElement(role, content, sources) {
  try {
    content =
  typeof content === 'string'
    ? content
    : JSON.stringify(content || '');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    const avatarIcon = role === 'user' ? 'fa-user' : 'fa-robot';
    
    const formattedContent = role === 'assistant' ? renderMarkdown(content) : escapeHtml(content);
    
    msgDiv.innerHTML = `
      <div class="avatar"><i class="fas ${avatarIcon}"></i></div>
      <div class="bubble">${formattedContent}</div>`;
    
    if (role === 'assistant') {
      addMessageActions(msgDiv, role);
      if (sources && Array.isArray(sources) && sources.length > 0) {
        const bubble = msgDiv.querySelector('.bubble');
        displaySources(bubble, sources);
      }
    }
    
    return msgDiv;
  } catch (error) {
    console.error('Error creating message element:', error);
    const fallback = document.createElement('div');
    fallback.className = `message ${role}`;
    fallback.innerHTML = `
      <div class="avatar"><i class="fas fa-exclamation-triangle"></i></div>
      <div class="bubble">Error displaying message</div>`;
    return fallback;
  }
}

function addMessageToVirtualList(role, content, sources = null) {
  allMessages.push({ role, content, sources });
  
  if (currentPage === 0 || chatMessages.scrollTop + chatMessages.clientHeight >= chatMessages.scrollHeight - 100) {
    const msgDiv = createMessageElement(role, content, sources);
    if (msgDiv) {
      chatMessages.appendChild(msgDiv);
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  }
}

// ============ API HELPER FUNCTIONS ============
async function apiCall(endpoint, options = {}) {
  const headers = {
    ...options.headers,
  };
  
  if (API_CONFIG.apiKey) {
    headers['Authorization'] = `Bearer ${API_CONFIG.apiKey}`;
    headers['X-API-Key'] = API_CONFIG.apiKey;
  }

  try {
    const response = await fetch(`${API_CONFIG.baseUrl}${endpoint}`, {
      ...options,
      headers,
      signal: options.signal,
    });

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}`;
      try {
        const error = await response.json();
        errorMessage = error.detail || error.message || errorMessage;
      } catch {}
      throw new Error(errorMessage);
    }

    return response;
  } catch (error) {
    if (error.name === 'AbortError') {
      throw error;
    }
    if (error.name === 'TypeError' && error.message === 'Failed to fetch') {
      throw new Error('Network error: Unable to connect to backend. Check your API URL.');
    }
    throw error;
  }
}

// ============ CONNECTION CHECK ============
async function checkConnection() {
  try {
    const response = await fetch(`${API_CONFIG.baseUrl}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(3000),
    });
    if (response.ok) {
      updateConnectionStatus(true);
      return true;
    }
  } catch {
    try {
      await fetch(`${API_CONFIG.baseUrl}/documents`, {
        method: 'GET',
        signal: AbortSignal.timeout(3000),
      });
      updateConnectionStatus(true);
      return true;
    } catch {
      updateConnectionStatus(false);
      return false;
    }
  }
  updateConnectionStatus(false);
  return false;
}

function updateConnectionStatus(connected) {
  if (connected) {
    statusDot.className = 'status-dot-connected';
    statusText.textContent = 'Connected';
    statusText.style.color = '#10b981';
  } else {
    statusDot.className = 'status-dot-disconnected';
    statusText.textContent = 'Disconnected';
    statusText.style.color = '#ef4444';
  }
}

// ============ DOCUMENT MANAGEMENT ============
async function fetchDocuments() {
  try {
    const response = await apiCall('/documents');
    const data = await response.json();
    indexedDocuments = data.documents || data || [];
    updateDocCount();
    renderDocDropdown();
  } catch (err) {
    console.error('Failed to fetch documents:', err);
    indexedDocuments = [];
    updateDocCount();
    renderDocDropdown();
  }
}

async function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);
  
  uploadProgress.classList.add('active');
  uploadProgressBar.style.width = '50%';
  
  try {
    const response = await apiCall('/upload', {
      method: 'POST',
      body: formData,
    });
    
    uploadProgressBar.style.width = '100%';
    const result = await response.json();
    
    addMessageToVirtualList('assistant', 
      `📎 **${escapeHtml(file.name)}** uploaded and indexed successfully.${result.chunks ? ` Created ${result.chunks} chunks.` : ''}`
    );
    
    await fetchDocuments();
  } catch (err) {
    await showError('Upload Failed', `Failed to upload ${file.name}: ${err.message}`);
  } finally {
    setTimeout(() => {
      uploadProgress.classList.remove('active');
      uploadProgressBar.style.width = '0%';
    }, 500);
  }
}

async function deleteDocument(docId) {
  try {
    await apiCall(`/documents/${docId}`, { method: 'DELETE' });
    await fetchDocuments();
  } catch (err) {
    await showError('Delete Failed', `Failed to delete document: ${err.message}`);
  }
}

async function deleteAllDocuments() {
  if (indexedDocuments.length === 0) {
    await showWarning('No Documents', 'There are no documents to remove.');
    return;
  }

  const confirmed = await showConfirm(
    'Remove All Documents',
    `Are you sure you want to remove all ${indexedDocuments.length} indexed document(s)? This action cannot be undone.`
  );

  if (!confirmed) return;

  let successCount = 0;
  let failCount = 0;

  for (const doc of indexedDocuments) {
    const docId = doc.id || doc.doc_id || doc.filename || doc.name;
    try {
      await apiCall(`/documents/${docId}`, { method: 'DELETE' });
      successCount++;
    } catch (err) {
      console.error(`Failed to delete document ${docId}:`, err);
      failCount++;
    }
  }

  await fetchDocuments();

  if (failCount === 0) {
    await showSuccess('Documents Removed', `Successfully removed all ${successCount} document(s).`);
  } else {
    await showWarning('Partial Success', `Removed ${successCount} document(s), but failed to remove ${failCount} document(s).`);
  }
}

function updateDocCount() {
  const count = indexedDocuments.length;
  docCountText.textContent = count === 0 ? 'Documents' : `${count} Documents`;
}

function renderDocDropdown() {
  docDropdownList.innerHTML = '';
  
  if (indexedDocuments.length === 0) {
    docDropdownList.innerHTML = '<div class="no-docs-message">No documents indexed</div>';
  } else {
    indexedDocuments.forEach(doc => {
      const docItem = document.createElement('div');
      docItem.className = 'doc-item';
      const docName = doc.filename || doc.name || doc.id || 'Unknown';
      const docId = doc.id || doc.doc_id || docName;
      docItem.innerHTML = `
        <div class="doc-item-info">
          <i class="fas fa-file-alt"></i>
          <span class="doc-item-name">${escapeHtml(docName)}</span>
        </div>
        <button class="remove-doc-btn" data-doc-id="${escapeHtml(docId)}" title="Remove document">
          <i class="fas fa-times"></i>
        </button>
      `;
      
      const removeBtn = docItem.querySelector('.remove-doc-btn');
      removeBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const confirmed = await showConfirm(
          'Remove Document',
          `Are you sure you want to remove "${docName}" from the index?`
        );
        if (confirmed) {
          deleteDocument(docId);
        }
      });
      
      docDropdownList.appendChild(docItem);
    });
  }
}

// ============ QUERY BACKEND ============
async function queryBackend(query) {
  abortController = new AbortController();
  
  const response = await apiCall('/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: query,
      top_k: 3,
      model: API_CONFIG.model || undefined,
    }),
    signal: abortController.signal,
  });
  return response.json();
}

async function queryBackendStream(query) {
  return await queryBackend(query);
}

// ============ STOP GENERATION ============
function stopGeneration() {
  isManuallyStopped = true;
  
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
  
  const loadingMsg = document.getElementById('loadingMsg');
  if (loadingMsg) loadingMsg.remove();
  
  const streamingMsg = document.getElementById('streamingMsg');
  if (streamingMsg) {
    const bubble = streamingMsg.querySelector('.bubble');
    if (bubble) {
      const partialText = bubble.innerText;
      if (partialText.trim()) {
        addMessageToVirtualList('assistant', partialText + '\n\n*[Generation stopped]*', null);
        saveCurrentChat();
      }
    }
    streamingMsg.remove();
  }
  
  const regenerateLoading = document.getElementById('regenerateLoading');
  if (regenerateLoading) regenerateLoading.remove();
  
  const streamingRegenMsg = document.getElementById('streamingRegenMsg');
  if (streamingRegenMsg) {
    const bubble = streamingRegenMsg.querySelector('.bubble');
    if (bubble) {
      const partialText = bubble.innerText;
      if (partialText.trim()) {
        addMessageToVirtualList('assistant', partialText + '\n\n*[Generation stopped]*', null);
        saveCurrentChat();
      }
    }
    streamingRegenMsg.remove();
  }
  
  isProcessing = false;
  setInputState(false);
  userInput.focus();
  
  setTimeout(() => {
    isManuallyStopped = false;
  }, 100);
}
 async function typeAssistantMessage(text, sources = []) {
  addMessageToVirtualList('assistant', '', []);

  const msgs = document.querySelectorAll('.message.assistant');
  const currentMsg = msgs[msgs.length - 1];
  const bubble = currentMsg.querySelector('.bubble');

  let built = '';

  for (let i = 0; i < text.length; i++) {
    built += text[i];
    bubble.innerHTML = renderMarkdown(built);
    await new Promise(resolve => setTimeout(resolve, 8));
    scrollToBottom();
  }

  const msgIndex = allMessages.length - 1;
  if (allMessages[msgIndex]) {
    allMessages[msgIndex].content = text;
    allMessages[msgIndex].sources = sources;
  }

  if (sources && sources.length > 0) {
    displaySources(bubble, sources);
  }

  saveCurrentChat();
}

// ============ CHAT HISTORY ============
function saveCurrentChat() {
  if (!currentChatId) return;

  const messages = allMessages
    .filter(msg => {
      const contentStr =
        typeof msg.content === 'string'
          ? msg.content
          : JSON.stringify(msg.content || '');

      return !(contentStr || '').includes('uploaded and indexed');
    })
    .map(msg => ({
      role: msg.role,
      content:
        typeof msg.content === 'string'
          ? msg.content
          : JSON.stringify(msg.content || ''),
      sources: msg.sources || null
    }));

  const existingChat = chatHistory.find(c => c.id === currentChatId);

  if (existingChat) {
    existingChat.messages = messages;
    existingChat.title =
      messages.length > 0
        ? messages[0].content.substring(0, 40) +
          (messages[0].content.length > 40 ? '...' : '')
        : 'Empty Chat';
  }

  saveToStorage();
  renderChatHistory();
}

function createNewChat() {
  saveCurrentChat();
  const chatId = Date.now().toString();
  currentChatId = chatId;
  chatHistory.push({
    id: chatId,
    title: 'New Conversation',
    messages: [],
    createdAt: new Date().toISOString()
  });
  
  allMessages = [];
  currentPage = 0;
  hasMoreMessages = false;
  chatMessages.innerHTML = '';
  
  saveToStorage();
  renderChatHistory();
  userInput.focus();
}

function loadChat(chatId) {
  saveCurrentChat();
  const chat = chatHistory.find(c => c.id === chatId);
  if (!chat) return;
  
  currentChatId = chatId;
  
  allMessages = chat.messages.map(msg => ({
    role: msg.role,
    content: msg.content,
    sources: msg.sources || null
  }));
  
  chatMessages.innerHTML = '';
  currentPage = 0;
  
  if (allMessages.length > MESSAGES_PER_PAGE) {
    const startIndex = allMessages.length - MESSAGES_PER_PAGE;
    const initialMessages = allMessages.slice(startIndex);
    
    const fragment = document.createDocumentFragment();
    initialMessages.forEach(msg => {
      const msgDiv = createMessageElement(msg.role, msg.content, msg.sources);
      if (msgDiv) fragment.appendChild(msgDiv);
    });
    
    chatMessages.appendChild(fragment);
    hasMoreMessages = startIndex > 0;
  } else {
    const fragment = document.createDocumentFragment();
    allMessages.forEach(msg => {
      const msgDiv = createMessageElement(msg.role, msg.content, msg.sources);
      if (msgDiv) fragment.appendChild(msgDiv);
    });
    
    chatMessages.appendChild(fragment);
    hasMoreMessages = false;
  }
  
  chatMessages.scrollTop = chatMessages.scrollHeight;
  saveToStorage();
  renderChatHistory();
}

async function deleteChat(chatId, e) {
  e.stopPropagation();
  const confirmed = await showConfirm(
    'Delete Conversation',
    'Are you sure you want to delete this conversation? This cannot be undone.'
  );
  if (confirmed) {
    chatHistory = chatHistory.filter(c => c.id !== chatId);
    if (currentChatId === chatId) {
      currentChatId = null;
      if (chatHistory.length > 0) {
        loadChat(chatHistory[chatHistory.length - 1].id);
      } else {
        createNewChat();
      }
    }
    renderChatHistory();
  }
}

async function clearAllData() {
  const confirmed = await showConfirm(
    'Clear All Data',
    'Are you sure you want to delete ALL conversations and settings? This cannot be undone.'
  );
  if (confirmed) {
    localStorage.removeItem(STORAGE_KEYS.CHAT_HISTORY);
    localStorage.removeItem(STORAGE_KEYS.CURRENT_CHAT);
    chatHistory = [];
    allMessages = [];
    chatMessages.innerHTML = '';
    createNewChat();
  }
}

function renderChatHistory() {
  historyList.innerHTML = '';
  if (chatHistory.length === 0) {
    historyList.innerHTML = `
      <div class="empty-history">
        <i class="fas fa-inbox"></i>
        <p>No conversations yet</p>
        <p style="font-size:0.8rem;">Start a new chat to see it here</p>
      </div>`;
  } else {
    const sortedHistory = [...chatHistory].reverse();
    sortedHistory.forEach(chat => {
      const item = document.createElement('div');
      item.className = `history-item${chat.id === currentChatId ? ' active' : ''}`;
      item.dataset.chatId = chat.id;
      item.innerHTML = `
        <i class="fas fa-comment"></i>
        <span>${escapeHtml(chat.title)}</span>
        <button class="delete-chat" title="Delete conversation">
          <i class="fas fa-trash-alt"></i>
        </button>`;
      item.addEventListener('click', (e) => {
        if (!e.target.closest('.delete-chat')) {
          loadChat(chat.id);
        }
      });
      item.querySelector('.delete-chat').addEventListener('click', (e) => deleteChat(chat.id, e));
      historyList.appendChild(item);
    });
  }
}

// ============ DISPLAY HELPERS ============
function displaySources(bubble, sources) {
  if (!sources || !Array.isArray(sources) || sources.length === 0) return;
  
  const sourcesDiv = document.createElement('div');
  sourcesDiv.className = 'context-badge';
  sourcesDiv.style.marginTop = '14px';
  
  let sourcesHTML = '<strong>📚 Sources Used</strong>';
  
  sources.forEach((source, index) => {
    const filename = source.filename || source.name || `Document ${index + 1}`;
    
    sourcesHTML += `
      <div class="source-item" style="margin-top: 8px;">
        <div class="source-header">
          <span style="color: #60a5fa; font-weight: 600;">
            <i class="fas fa-check-circle" style="color: #10b981; margin-right: 4px;"></i>
            ${escapeHtml(filename)}
          </span>
        </div>
      </div>`;
  });
  
  sourcesDiv.innerHTML = sourcesHTML;
  bubble.appendChild(sourcesDiv);
}

function addMessageActions(messageDiv, role) {
  if (role === 'assistant') {
    const bubble = messageDiv.querySelector('.bubble');
    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'message-actions';
    actionsDiv.innerHTML = `
      <button class="action-btn copy-btn" title="Copy response">
        <i class="fas fa-copy"></i>
      </button>
      <button class="action-btn regenerate-btn" title="Regenerate response">
        <i class="fas fa-redo"></i>
      </button>
    `;
    bubble.appendChild(actionsDiv);
    
    actionsDiv.querySelector('.copy-btn').addEventListener('click', async (e) => {
      e.stopPropagation();
      const textToCopy = bubble.textContent.replace(/📚 Retrieved From:[\s\S]*$/, '').trim();
      try {
        await navigator.clipboard.writeText(textToCopy);
        const btn = actionsDiv.querySelector('.copy-btn');
        btn.innerHTML = '<i class="fas fa-check"></i>';
        setTimeout(() => {
          btn.innerHTML = '<i class="fas fa-copy"></i>';
        }, 2000);
      } catch {
        await showError('Copy Failed', 'Failed to copy to clipboard');
      }
    });
    
    actionsDiv.querySelector('.regenerate-btn').addEventListener('click', async (e) => {
      e.stopPropagation();
      if (isProcessing) return;
      
      const lastUserMsg = [...allMessages].reverse().find(m => m.role === 'user');
      if (!lastUserMsg) return;
      
      const msgIndex = allMessages.findIndex(m => 
        m.role === 'assistant' && m === allMessages[allMessages.length - 1]
      );
      if (msgIndex > -1) {
        allMessages.splice(msgIndex, 1);
      }
      
      messageDiv.remove();
      
      isProcessing = true;
      setInputState(true);
      
      const loadingMsg = document.createElement('div');
      loadingMsg.className = 'message assistant';
      loadingMsg.id = 'regenerateLoading';
      loadingMsg.innerHTML = `
        <div class="avatar"><i class="fas fa-robot"></i></div>
        <div class="bubble">
          <div class="spinner-container">
            <div class="loader"></div>
            <span>Regenerating response...</span>
          </div>
        </div>`;
      chatMessages.appendChild(loadingMsg);
      chatMessages.scrollTop = chatMessages.scrollHeight;
      
      try {
        const isConnected = await checkConnection();
        if (!isConnected) {
          throw new Error('Cannot connect to backend.');
        }

        let response;
        try {
          response = await queryBackendStream(lastUserMsg.content);
        } catch {
          response = await queryBackend(lastUserMsg.content);
        }

        const loader = document.getElementById('regenerateLoading');
        if (loader) loader.remove();

        if (
           response.headers &&
              (response.headers.get('content-type') || '').includes('text/event-stream')
            ) {
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          
          let fullText = '';
          let sources = null;
          
          const tempMsgDiv = document.createElement('div');
          tempMsgDiv.className = 'message assistant';
          tempMsgDiv.id = 'streamingRegenMsg';
          tempMsgDiv.innerHTML = `<div class="avatar"><i class="fas fa-robot"></i></div><div class="bubble"></div>`;
          chatMessages.appendChild(tempMsgDiv);
          addMessageActions(tempMsgDiv, 'assistant');
          
          const bubbleEl = tempMsgDiv.querySelector('.bubble');
          
          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              
              const chunk = decoder.decode(value);
              const lines = chunk.split('\n');
              
              for (const line of lines) {
                if (line.startsWith('data: ')) {
                  try {
                    const data = JSON.parse(line.slice(6));
                    if (data.text || data.content || data.answer) {
                      const text = data.text || data.content || data.answer;
                      fullText += text;
                      bubbleEl.innerHTML = renderMarkdown(fullText);
                      chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                    if (data.sources || data.documents) {
                      sources = data.sources || data.documents;
                    }
                  } catch {}
                }
              }
            }
          } catch (streamError) {
            if (streamError.name === 'AbortError') {
              if (!isManuallyStopped) {
                const streamingMsg = document.getElementById('streamingRegenMsg');
                if (streamingMsg) streamingMsg.remove();
                
                if (fullText.trim()) {
                  addMessageToVirtualList('assistant', fullText + '\n\n*[Connection lost]*', sources);
                  saveCurrentChat();
                }
              }
              return;
            }
            throw streamError;
          }
          
          const streamingMsg = document.getElementById('streamingRegenMsg');
          if (streamingMsg) streamingMsg.remove();
          
          addMessageToVirtualList('assistant', fullText, sources);
          saveCurrentChat();
        } else {
          const data = response;
          const answer = data.answer || data.response || data.text || 'No response received';
          const sources = data.sources || data.documents || [];
          
          addMessageToVirtualList('assistant', answer, sources);
          saveCurrentChat();
        }
      } catch (err) {
        if (err.name === 'AbortError') return;
        
        const loader = document.getElementById('regenerateLoading');
        if (loader) loader.remove();
        
        addMessageToVirtualList('assistant', `❌ Error: ${escapeHtml(err.message)}`);
      } finally {
        isProcessing = false;
        setInputState(false);
        userInput.focus();
      }
    });
  }
}

// ============ SEND MESSAGE ============
async function handleSend() {
  if (isProcessing) return;
  const query = userInput.value.trim();
  if (!query) return;
  
  userInput.value = '';
  isProcessing = true;
  setInputState(true);

  addMessageToVirtualList('user', query);

  const loadingMsg = document.createElement('div');
  loadingMsg.className = 'message assistant';
  loadingMsg.id = 'loadingMsg';
  loadingMsg.innerHTML = `
    <div class="avatar"><i class="fas fa-robot"></i></div>
    <div class="bubble">
      <div class="spinner-container">
        <div class="loader"></div>
        <span>Retrieving documents & generating response...</span>
      </div>
    </div>`;
  chatMessages.appendChild(loadingMsg);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const isConnected = await checkConnection();
    
    if (!isConnected) {
      throw new Error('Cannot connect to backend. Please check your API URL in settings.');
    }

    let response;
    try {
      response = await queryBackendStream(query);
    } catch {
      response = await queryBackend(query);
    }

    const loader = document.getElementById('loadingMsg');
    if (loader) loader.remove();

    if (
     response.headers &&
     (response.headers.get('content-type') || '').includes('text/event-stream')
      ) {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      let fullText = '';
      let sources = null;
      
      const tempMsgDiv = document.createElement('div');
      tempMsgDiv.className = 'message assistant';
      tempMsgDiv.id = 'streamingMsg';
      tempMsgDiv.innerHTML = `<div class="avatar"><i class="fas fa-robot"></i></div><div class="bubble"></div>`;
      chatMessages.appendChild(tempMsgDiv);
      addMessageActions(tempMsgDiv, 'assistant');
      
      const bubble = tempMsgDiv.querySelector('.bubble');
      
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.text || data.content || data.answer) {
                  const text = data.text || data.content || data.answer;
                  fullText += text;
                  bubble.innerHTML = renderMarkdown(fullText);
                  chatMessages.scrollTop = chatMessages.scrollHeight;
                }
                if (data.sources || data.documents) {
                  sources = data.sources || data.documents;
                }
              } catch {}
            }
          }
        }
      } catch (streamError) {
        if (streamError.name === 'AbortError') {
          if (!isManuallyStopped) {
            const streamingMsg = document.getElementById('streamingMsg');
            if (streamingMsg) streamingMsg.remove();
            
            if (fullText.trim()) {
              addMessageToVirtualList('assistant', fullText + '\n\n*[Connection lost]*', sources);
              saveCurrentChat();
            }
          }
          return;
        }
        throw streamError;
      }
      
      const streamingMsg = document.getElementById('streamingMsg');
      if (streamingMsg) streamingMsg.remove();
      
      addMessageToVirtualList('assistant', fullText, sources);
      saveCurrentChat();
    } else {
      const data = response;
      const answer = data.answer || data.response || data.text || 'No response received';
      const sources = data.sources || data.documents || [];
      
      addMessageToVirtualList('assistant', answer, sources);
      saveCurrentChat();
    }

  } catch (err) {
    if (err.name === 'AbortError') return;
    
    const loader = document.getElementById('loadingMsg');
    if (loader) loader.remove();
    
    addMessageToVirtualList('assistant', 
      `❌ Error: ${escapeHtml(err.message)}\nCheck your API settings (click the cog wheel)`
    );
  } finally {
    isProcessing = false;
    setInputState(false);
    userInput.focus();
  }
}

function setInputState(disabled) {
  userInput.disabled = disabled;
  
  if (disabled) {
    sendBtn.classList.add('hidden');
    stopBtn.classList.remove('hidden');
  } else {
    sendBtn.classList.remove('hidden');
    stopBtn.classList.add('hidden');
  }
}

// ============ SETTINGS ============
function openSettings() {
  apiUrlInput.value = API_CONFIG.baseUrl;
  apiKeyInput.value = API_CONFIG.apiKey;
  modelInput.value = API_CONFIG.model;
  settingsBackdrop.classList.add('active');
}

function closeSettings() {
  settingsBackdrop.classList.remove('active');
}

async function saveSettings() {
  API_CONFIG.baseUrl = apiUrlInput.value.trim() || 'http://localhost:8000/api';
  API_CONFIG.apiKey = apiKeyInput.value.trim();
  API_CONFIG.model = modelInput.value.trim();
  
  localStorage.setItem(STORAGE_KEYS.API_URL, API_CONFIG.baseUrl);
  localStorage.setItem(STORAGE_KEYS.API_KEY, API_CONFIG.apiKey);
  localStorage.setItem(STORAGE_KEYS.MODEL, API_CONFIG.model);
  
  closeSettings();
  
  const connected = await checkConnection();
  if (connected) {
    await fetchDocuments();
    await showSuccess('Settings Saved', 'Connected successfully!');
  } else {
    await showWarning('Settings Saved', 'Could not connect to backend. Check your API URL.');
  }
}

// ============ EVENT LISTENERS ============
sidebar.addEventListener('transitionend', () => {
  window.dispatchEvent(new Event('resize'));
});

collapseBtn.addEventListener('click', () => {
  sidebar.classList.toggle('collapsed');
  const icon = collapseBtn.querySelector('i');
  if (sidebar.classList.contains('collapsed')) {
    icon.className = 'fas fa-chevron-right';
    collapseBtn.title = 'Expand Sidebar';
  } else {
    icon.className = 'fas fa-chevron-left';
    collapseBtn.title = 'Collapse Sidebar';
  }
  saveToStorage();
});

docCountBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  docDropdown.classList.toggle('active');
  if (docDropdown.classList.contains('active')) {
    positionDocDropdown();
    fetchDocuments();
  }
});

refreshDocsBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  fetchDocuments();
});

removeAllDocsBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  deleteAllDocuments();
});

document.addEventListener('click', (e) => {
  if (!docDropdown.contains(e.target) && !docCountBtn.contains(e.target)) {
    docDropdown.classList.remove('active');
  }
});

window.addEventListener('scroll', () => {
  if (docDropdown.classList.contains('active')) {
    positionDocDropdown();
  }
}, true);

window.addEventListener('resize', () => {
  if (docDropdown.classList.contains('active')) {
    positionDocDropdown();
  }
});

uploadTrigger.addEventListener('click', () => fileUpload.click());

fileUpload.addEventListener('change', async (e) => {
  const files = Array.from(e.target.files);
  for (const file of files) {
    await uploadDocument(file);
  }
  fileUpload.value = '';
});

sendBtn.addEventListener('click', handleSend);
stopBtn.addEventListener('click', stopGeneration);
userInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
});

document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
    e.preventDefault();
    createNewChat();
  }
  if ((e.ctrlKey || e.metaKey) && e.key === ',') {
    e.preventDefault();
    openSettings();
  }
  if (e.key === 'Escape') {
    if (isProcessing) {
      stopGeneration();
    } else if (!alertBackdrop.classList.contains('active')) {
      closeSettings();
    }
  }
});

newChatBtn.addEventListener('click', createNewChat);
clearAllBtn.addEventListener('click', clearAllData);
settingsBtn.addEventListener('click', openSettings);
closeSettingsBtn.addEventListener('click', closeSettings);
settingsBackdrop.addEventListener('click', (e) => {
  if (e.target === settingsBackdrop) closeSettings();
});
saveSettingsBtn.addEventListener('click', saveSettings);

// ============ INITIALIZE ============
async function initialize() {
  initVirtualScroll();
  
  const { savedChatId } = loadFromStorage();
  
  if (chatHistory.length > 0) {
    if (savedChatId && chatHistory.find(c => c.id === savedChatId)) {
      loadChat(savedChatId);
    } else {
      loadChat(chatHistory[0].id);
    }
  } else {
    createNewChat();
  }
  
  if (API_CONFIG.baseUrl) {
    const connected = await checkConnection();
    if (connected) {
      await fetchDocuments();
    }
  }
  
  setInterval(checkConnection, 30000);
}

initialize();