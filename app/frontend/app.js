const authScreen = document.querySelector("#authScreen");
const authForm = document.querySelector("#authForm");
const authSubmit = document.querySelector("#authSubmit");
const authError = document.querySelector("#authError");
const loginTab = document.querySelector("#loginTab");
const signupTab = document.querySelector("#signupTab");
const nameField = document.querySelector("#nameField");
const nameInput = document.querySelector("#nameInput");
const emailInput = document.querySelector("#emailInput");
const passwordInput = document.querySelector("#passwordInput");
const userName = document.querySelector("#userName");
const userEmail = document.querySelector("#userEmail");
const logoutButton = document.querySelector("#logoutButton");
const recentList = document.querySelector("#recentList");

const conversation = document.querySelector("#conversation");
const welcome = document.querySelector("#welcome");
const messages = document.querySelector("#messages");
const form = document.querySelector("#chatForm");
const input = document.querySelector("#questionInput");
const sendButton = document.querySelector("#sendButton");
const clearButton = document.querySelector("#clearButton");
const newChatButton = document.querySelector("#newChatButton");
const menuButton = document.querySelector("#menuButton");
const sidebar = document.querySelector("#sidebar");
const mobileOverlay = document.querySelector("#mobileOverlay");

const tokenKey = "dataquery.authToken";
const conversationKey = "dataquery.conversationId";

let isWaiting = false;
let authMode = "login";
let authToken = window.localStorage.getItem(tokenKey);
let conversationId = window.localStorage.getItem(conversationKey);

function authHeaders(extraHeaders = {}) {
  return {
    ...extraHeaders,
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
  };
}

function resizeInput() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
}

function scrollToLatest() {
  conversation.scrollTo({ top: conversation.scrollHeight, behavior: "smooth" });
}

function renderMarkdown(text) {
  if (window.marked && window.DOMPurify) {
    return DOMPurify.sanitize(marked.parse(text));
  }
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML.replace(/\n/g, "<br>");
}

function createMessage(role, text, options = {}) {
  const article = document.createElement("article");
  article.className = `message ${role}${options.error ? " error" : ""}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "YOU" : "AI";

  const content = document.createElement("div");
  content.className = "message-content";

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = role === "user" ? "You" : "DataQuery AI";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = renderMarkdown(text);

  content.append(meta, bubble);
  article.append(avatar, content);
  messages.append(article);
  scrollToLatest();
  return article;
}

function createTypingMessage() {
  const article = createMessage("assistant", "");
  const bubble = article.querySelector(".bubble");
  bubble.classList.add("typing");
  bubble.innerHTML = "<span></span><span></span><span></span>";
  return article;
}

function extractAnswer(payload) {
  if (typeof payload === "string") return payload;

  const responseMessages = payload?.messages;
  if (Array.isArray(responseMessages) && responseMessages.length) {
    const lastMessage = responseMessages[responseMessages.length - 1];
    const content = lastMessage?.content;

    if (typeof content === "string") return content;
    if (Array.isArray(content)) {
      return content
        .map((part) => typeof part === "string" ? part : part?.text || "")
        .filter(Boolean)
        .join("\n");
    }
  }

  return payload?.answer || payload?.output || "The query completed, but no readable answer was returned.";
}

function setAuthMode(mode) {
  authMode = mode;
  const isSignup = mode === "signup";
  loginTab.classList.toggle("active", !isSignup);
  signupTab.classList.toggle("active", isSignup);
  nameField.hidden = !isSignup;
  nameInput.required = isSignup;
  passwordInput.autocomplete = isSignup ? "new-password" : "current-password";
  authSubmit.textContent = isSignup ? "Create account" : "Login";
  authError.hidden = true;
}

function showAuth() {
  authScreen.hidden = false;
  emailInput.focus();
}

function hideAuth() {
  authScreen.hidden = true;
  input.focus();
}

function setCurrentUser(user) {
  userName.textContent = user?.name || "Signed in";
  userEmail.textContent = user?.email || "Account";
}

function clearSession() {
  authToken = null;
  conversationId = null;
  window.localStorage.removeItem(tokenKey);
  window.localStorage.removeItem(conversationKey);
  messages.replaceChildren();
  recentList.replaceChildren();
  welcome.hidden = false;
}

async function loadCurrentUser() {
  if (!authToken) {
    showAuth();
    return;
  }

  try {
    const response = await fetch("/api/auth/me", {
      headers: authHeaders({ Accept: "application/json" }),
    });
    if (!response.ok) throw new Error("Session expired.");

    const payload = await response.json();
    setCurrentUser(payload.user);
    hideAuth();
    await loadConversations();
    await loadStoredConversation();
  } catch {
    clearSession();
    showAuth();
  }
}

async function submitAuth(event) {
  event.preventDefault();
  authSubmit.disabled = true;
  authError.hidden = true;

  const body = {
    email: emailInput.value.trim(),
    password: passwordInput.value,
  };
  if (authMode === "signup") body.name = nameInput.value.trim();

  try {
    const response = await fetch(`/api/auth/${authMode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(payload?.detail || "Authentication failed.");
    }

    authToken = payload.token;
    window.localStorage.setItem(tokenKey, authToken);
    setCurrentUser(payload.user);
    authForm.reset();
    hideAuth();
    await loadConversations();
    resetConversation({ keepSidebar: true });
  } catch (error) {
    authError.textContent = error.message || "Authentication failed.";
    authError.hidden = false;
  } finally {
    authSubmit.disabled = false;
  }
}

async function logout() {
  if (authToken) {
    await fetch("/api/auth/logout", {
      method: "POST",
      headers: authHeaders({ Accept: "application/json" }),
    }).catch(() => null);
  }
  clearSession();
  showAuth();
}

async function askQuestion(question) {
  if (!question.trim() || isWaiting) return;

  const params = new URLSearchParams({ question: question.trim() });
  if (conversationId) params.set("conversation_id", conversationId);

  isWaiting = true;
  sendButton.disabled = true;
  welcome.hidden = true;
  createMessage("user", question.trim());
  const typingMessage = createTypingMessage();

  try {
    const response = await fetch(`/api/chat?${params.toString()}`, {
      method: "POST",
      headers: authHeaders({ Accept: "application/json" }),
    });

    const payload = await response.json().catch(() => null);
    if (response.status === 401) {
      clearSession();
      showAuth();
      throw new Error("Please log in again.");
    }
    if (!response.ok) {
      throw new Error(payload?.detail || `Request failed with status ${response.status}`);
    }

    typingMessage.remove();
    if (payload?.conversation_id) {
      conversationId = payload.conversation_id;
      window.localStorage.setItem(conversationKey, conversationId);
    }
    createMessage("assistant", extractAnswer(payload));
    await loadConversations();
  } catch (error) {
    typingMessage.remove();
    createMessage(
      "assistant",
      `I couldn't complete that request. ${error.message || "Please check the API and database connection."}`,
      { error: true },
    );
  } finally {
    isWaiting = false;
    sendButton.disabled = false;
    input.focus();
  }
}

function resetConversation(options = {}) {
  messages.replaceChildren();
  welcome.hidden = false;
  input.value = "";
  conversationId = null;
  window.localStorage.removeItem(conversationKey);
  resizeInput();
  input.focus();
  renderConversationList([]);
  loadConversations();
  if (!options.keepSidebar) closeSidebar();
}

function closeSidebar() {
  sidebar.classList.remove("open");
  mobileOverlay.classList.remove("open");
}

function renderConversationList(conversations) {
  recentList.replaceChildren();
  if (!conversations.length) {
    const empty = document.createElement("p");
    empty.className = "recent-empty";
    empty.textContent = "No saved chats yet.";
    recentList.append(empty);
    return;
  }

  conversations.forEach((item) => {
    const button = document.createElement("button");
    button.className = `recent-item${item.id === conversationId ? " active" : ""}`;
    button.type = "button";
    button.dataset.conversationId = item.id;
    button.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v8Z" />
      </svg>
      <span></span>
    `;
    button.querySelector("span").textContent = item.title || "Untitled chat";
    button.addEventListener("click", () => loadConversation(item.id));
    recentList.append(button);
  });
}

async function loadConversations() {
  if (!authToken) return;

  try {
    const response = await fetch("/api/conversations", {
      headers: authHeaders({ Accept: "application/json" }),
    });
    if (!response.ok) return;
    const payload = await response.json();
    renderConversationList(payload.conversations || []);
  } catch {
    renderConversationList([]);
  }
}

async function loadConversation(id) {
  conversationId = id;
  window.localStorage.setItem(conversationKey, conversationId);
  await loadStoredConversation();
  await loadConversations();
  closeSidebar();
}

async function loadStoredConversation() {
  if (!conversationId || !authToken) return;

  try {
    const response = await fetch(`/api/conversations/${conversationId}/messages`, {
      headers: authHeaders({ Accept: "application/json" }),
    });
    if (!response.ok) return;

    const payload = await response.json();
    if (!Array.isArray(payload?.messages) || !payload.messages.length) return;

    welcome.hidden = true;
    messages.replaceChildren();
    payload.messages.forEach((message) => {
      createMessage(message.role, message.content);
    });
  } catch {
    window.localStorage.removeItem(conversationKey);
    conversationId = null;
  }
}

authForm.addEventListener("submit", submitAuth);
loginTab.addEventListener("click", () => setAuthMode("login"));
signupTab.addEventListener("click", () => setAuthMode("signup"));
logoutButton.addEventListener("click", logout);

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = input.value;
  input.value = "";
  resizeInput();
  askQuestion(question);
});

input.addEventListener("input", resizeInput);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll("[data-question]").forEach((button) => {
  button.addEventListener("click", () => askQuestion(button.dataset.question));
});

clearButton.addEventListener("click", resetConversation);
newChatButton.addEventListener("click", resetConversation);
menuButton.addEventListener("click", () => {
  sidebar.classList.toggle("open");
  mobileOverlay.classList.toggle("open");
});
mobileOverlay.addEventListener("click", closeSidebar);

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    resetConversation();
  }
});

setAuthMode("login");
resizeInput();
loadCurrentUser();
