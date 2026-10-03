import { useCallback, useEffect, useRef, useState } from 'react';

import Header from '../../components/Header/Header';
import ChatWindow from '../../components/ChatWindow/ChatWindow';
import ChatInput from '../../components/ChatInput/ChatInput';
import CapabilitiesPanel from '../../components/CapabilitiesPanel/CapabilitiesPanel';

import { useAuth } from '../../context/AuthContext';
import { checkAuthGate } from '../../utils/authGate';
import {
  sendChatMessage,
  checkHealth,
  getStoredSessionId,
  storeSessionId,
  clearStoredSessionId,
} from '../../api/chatApi';

import './ChatPage.scss';

let idCounter = 0;
const nextId = () => {
  idCounter += 1;
  return `m-${idCounter}-${Date.now()}`;
}

const AUTH_GATE_ENABLED = false;

const WELCOME_MESSAGE =
  "Hi, I'm Intellia. Ask me anything about e-commerce or insurance — refund policies, shipping, " +
  'claims, coverage, you name it.';

const ChatPage = () => {
  const { user, login, logout } = useAuth();
  const [messages, setMessages] = useState([{ id: nextId(), role: 'bot', text: WELCOME_MESSAGE }]);
  const [sessionId, setSessionId] = useState(() => getStoredSessionId());
  const [isSending, setIsSending] = useState(false);
  const [backendStatus, setBackendStatus] = useState('checking');
  const [showCapabilities, setShowCapabilities] = useState(false);

  const pendingQuestionRef = useRef(null);

  useEffect(() => {
    checkHealth()
      .then(() => setBackendStatus('online'))
      .catch(() => setBackendStatus('offline'))
  }, [])

  const handleSend = useCallback(
    async (text, opts = {}) => {
      if (AUTH_GATE_ENABLED && !opts.skipAuthGate && !user) {
        const gate = checkAuthGate(text);
        if (gate.requiresAuth) {
          pendingQuestionRef.current = text;
          setMessages((prev) => [
            ...prev,
            { id: nextId(), role: 'user', text },
            {
              id: nextId(),
              role: 'bot',
              text: "That needs your account details — I can't show another customer's order or policy info. Sign in and I'll pick up right where this left off.",
              authPrompt: { pendingText: text, id: gate.id, domain: gate.domain },
            },
          ])
          return;
        }
      }

      const userMsg = { id: nextId(), role: 'user', text };
      setMessages((prev) => [...prev, userMsg]);
      setIsSending(true);

      try {
        const data = await sendChatMessage(text, sessionId);
        setSessionId(data.session_id);
        storeSessionId(data.session_id);
        setBackendStatus('online');

        const botMsg = {
          id: nextId(),
          role: 'bot',
          text: data.reply || '(no reply text returned)',
          domain: data.domain,
          toolCalls: data.tool_calls,
        }
        setMessages((prev) => [...prev, botMsg]);
      } catch (err) {
        setBackendStatus('offline');
        const message = err instanceof Error ? err.message : String(err);
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            role: 'bot',
            text: `Could not reach the backend: ${message}. Is uvicorn running on port 8000?`,
            isError: true,
          },
        ])
      } finally {
        setIsSending(false);
      }
    },
    [sessionId, user]
  )

  // Listens for the login tab's postMessage (see pages/LoginPage). Runs
  // once; reads the latest handleSend/pendingQuestionRef via closures that
  // are recreated each render, so it's safe against stale state.
  useEffect(() => {
    function handleAuthMessage(event) {
      if (event.origin !== window.location.origin) return;
      if (!event.data || event.data.type !== 'dw-auth-success') return;

      const session = event.data.session;
      login(session.user); // saves to this tab's sessionStorage too

      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: 'bot', text: `Signed in as ${session.user.name}. Fetching your details…` },
      ])

      const pending = pendingQuestionRef.current;
      pendingQuestionRef.current = null;
      if (pending) {
        const augmented = /\b(ORD|POL|CLM)\d+/i.test(pending)
          ? pending
          : `${pending} (my customer/policy ID is ${session.user.customerId})`;
        void handleSend(augmented, { skipAuthGate: true });
      }
    }

    window.addEventListener('message', handleAuthMessage);
    return () => window.removeEventListener('message', handleAuthMessage);
  }, [login, handleSend])

  const handleOpenLogin = useCallback((prompt) => {
    pendingQuestionRef.current = prompt.pendingText || pendingQuestionRef.current;
    const params = new URLSearchParams();
    if (prompt.id) params.set('returnId', prompt.id);
    if (prompt.domain) params.set('domain', prompt.domain);
    if (prompt.pendingText) params.set('pending', prompt.pendingText);

    const url = `/login${params.toString() ? `?${params.toString()}` : ''}`;
    // Deliberately no "noopener" in the features string -- LoginPage needs
    // window.opener to post its result back to this tab.
    const popup = window.open(url, 'intellia-login', 'width=480,height=760');

    if (!popup) {
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: 'bot',
          text: 'Your browser blocked the sign-in pop-up. Please allow pop-ups for this site and try again.',
          isError: true,
        },
      ])
      return
    }
    popup.focus();
  }, [])

  const handleReset = useCallback(() => {
    clearStoredSessionId();
    setSessionId(null);
    setMessages([{ id: nextId(), role: 'bot', text: WELCOME_MESSAGE }]);
  }, [])

  const handleSignOut = useCallback(() => {
    logout();
  }, [logout])

  return (
    <div className="chat-page">
      <Header
        backendStatus={backendStatus}
        user={user}
        onReset={handleReset}
        onShowCapabilities={() => setShowCapabilities(true)}
        onSignIn={() => handleOpenLogin({ pendingText: '' })}
        onSignOut={handleSignOut}
      />
      <ChatWindow messages={messages} isSending={isSending} onOpenLogin={handleOpenLogin} />
      <ChatInput
        onSend={(text) => void handleSend(text)}
        disabled={isSending}
        accountType={user ? user.accountType : null}
      />
      <CapabilitiesPanel open={showCapabilities} onClose={() => setShowCapabilities(false)} />
    </div>
  )
};

export default ChatPage;


