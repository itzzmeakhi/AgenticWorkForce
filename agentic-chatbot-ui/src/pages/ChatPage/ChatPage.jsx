import { useCallback, useEffect, useRef, useState } from 'react';

import Header from '../../components/Header/Header';
import ChatWindow from '../../components/ChatWindow/ChatWindow';
import ChatInput from '../../components/ChatInput/ChatInput';
import CapabilitiesPanel from '../../components/CapabilitiesPanel/CapabilitiesPanel';

import { useAuth } from '../../context/AuthContext';
import { checkAuthGate } from '../../utils/authGate';
import {
  streamChatMessage,
  checkHealth,
  getStoredSessionId,
  storeSessionId,
  clearStoredSessionId,
  getStoredMessages,
  storeMessages,
  clearStoredMessages,
} from '../../api/chatApi';

import { getVoiceStatus, fetchSpeech } from '../../api/voiceApi';
import SpeechQueue from '../../utils/speechQueue';
import { takeSentences } from '../../utils/sentences';

import './ChatPage.scss';

let idCounter = 0;
const nextId = () => {
  idCounter += 1;
  return `m-${idCounter}-${Date.now()}`;
}

const AUTH_GATE_ENABLED = true;

// Only the first ~400 characters of a reply are read aloud (matches the backend's voice cap).
const MAX_SPOKEN_CHARS = 400;

const WELCOME_MESSAGE =
  "Hi, I'm Intellia. Ask me anything about e-commerce or insurance — refund policies, shipping, " +
  'claims, coverage, you name it.';

const ChatPage = () => {
  const { user, login, logout } = useAuth();
  const [messages, setMessages] = useState(() => {
    const stored = getStoredSessionId() ? getStoredMessages() : [];
    return stored.length > 0 ? stored : [{ id: nextId(), role: 'bot', text: WELCOME_MESSAGE }];
  });
  const [sessionId, setSessionId] = useState(() => getStoredSessionId());
  const [isSending, setIsSending] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [backendStatus, setBackendStatus] = useState('checking');
  const [showCapabilities, setShowCapabilities] = useState(false);

  const [voice, setVoice] = useState({ enabled: false, default_voice: '' });
  const [speakReplies, setSpeakReplies] = useState(false);

  const pendingQuestionRef = useRef(null);
  const voiceNameRef = useRef('');
  const speechRef = useRef(null);
  if (speechRef.current === null) {
    speechRef.current = new SpeechQueue((text) => fetchSpeech(text, voiceNameRef.current));
  }

  const stopSpeaking = useCallback(() => speechRef.current.stop(), [])

  useEffect(() => {
    getVoiceStatus().then((v) => {
      voiceNameRef.current = v.default_voice;
      setVoice(v);
    });
    return stopSpeaking;
  }, [stopSpeaking])

  useEffect(() => {
    storeMessages(messages);
  }, [messages])

  useEffect(() => {
    checkHealth()
      .then(() => setBackendStatus('online'))
      .catch(() => setBackendStatus('offline'))
  }, [])

  const handleSend = useCallback(
    async (text, opts = {}) => {
      if (AUTH_GATE_ENABLED && !opts.skipAuthGate) {
        const gate = checkAuthGate(text);
        if (gate.requiresAuth && !user) {
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
        if (gate.requiresAuth && user && gate.domain && gate.domain !== user.accountType) {
          const wrongAccount =
            `That's an ${gate.domain} question, but you're signed in to your ${user.accountType} account. ` +
            `Sign out and sign in to ${gate.domain} to continue.`;
          setMessages((prev) => [
            ...prev,
            { id: nextId(), role: 'user', text },
            { id: nextId(), role: 'bot', text: wrongAccount },
          ])
          return;
        }
      }

      const userMsg = { id: nextId(), role: 'user', text };
      setMessages((prev) => [...prev, userMsg]);
      setIsSending(true);
      stopSpeaking();

      const wantSpeech = voice.enabled && (opts.viaVoice || speakReplies);
      const botId = nextId();
      let streamed = '';        // everything the model has streamed so far
      let speakBuffer = '';     // streamed text not yet handed to the speech queue
      let spokenChars = 0;
      let startedStreaming = false;

      const speakSentence = (sentence) => {
        if (spokenChars >= MAX_SPOKEN_CHARS) return;
        spokenChars += sentence.length;
        speechRef.current.enqueue(sentence);
      };

      const onToken = (piece) => {
        streamed += piece;
        if (!startedStreaming) {
          startedStreaming = true;
          setIsStreaming(true);
          setMessages((prev) => [...prev, { id: botId, role: 'bot', text: streamed }]);
        } else {
          const snapshot = streamed;
          setMessages((prev) => prev.map((m) => (m.id === botId ? { ...m, text: snapshot } : m)));
        }
        if (wantSpeech) {
          speakBuffer += piece;
          const { sentences, rest } = takeSentences(speakBuffer);
          speakBuffer = rest;
          sentences.forEach(speakSentence);
        }
      };

      try {
        const data = await streamChatMessage(text, sessionId, onToken);
        setSessionId(data.session_id);
        storeSessionId(data.session_id);
        setBackendStatus('online');

        const botMsg = {
          id: botId,
          role: 'bot',
          text: data.reply || '(no reply text returned)',
          domain: data.domain,
          toolCalls: data.tool_calls,
        }
        setMessages((prev) =>
          startedStreaming ? prev.map((m) => (m.id === botId ? botMsg : m)) : [...prev, botMsg]
        );

        if (wantSpeech) {
          if (startedStreaming && streamed.trim() === botMsg.text.trim()) {
            // The live preview matched the final reply: just say what is left.
            const tail = speakBuffer.trim();
            if (tail) speakSentence(tail);
          } else {
            // The final reply differs from what streamed (e.g. text before a
            // tool call): drop the preview audio and speak the real answer.
            stopSpeaking();
            spokenChars = 0;
            speakSentence(botMsg.text);
          }
        }
      } catch (err) {
        stopSpeaking();
        if (startedStreaming) setMessages((prev) => prev.filter((m) => m.id !== botId));
        if (err && err.status === 401) {
          // The token expired (or was rejected): drop it and ask for a fresh sign-in.
          const domain = user ? user.accountType : undefined;
          logout();
          pendingQuestionRef.current = text;
          setMessages((prev) => [
            ...prev,
            {
              id: nextId(),
              role: 'bot',
              text: 'Your session has expired. Please sign in again and I will carry on with your question.',
              authPrompt: { pendingText: text, domain },
            },
          ])
          return;
        }
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
        setIsStreaming(false);
      }
    },
    [sessionId, user, logout, voice.enabled, speakReplies, stopSpeaking]
  )

  // Listens for the login tab's postMessage (see pages/LoginPage). Runs
  // once; reads the latest handleSend/pendingQuestionRef via closures that
  // are recreated each render, so it's safe against stale state.
  useEffect(() => {
    function handleAuthMessage(event) {
      if (event.origin !== window.location.origin) return;
      if (!event.data || event.data.type !== 'dw-auth-success') return;

      const session = event.data.session;
      login(session); // { token, user } -- saved to this tab's sessionStorage too

      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: 'bot', text: `Signed in as ${session.user.name}. Fetching your details…` },
      ])

      const pending = pendingQuestionRef.current;
      pendingQuestionRef.current = null;
      if (pending) {
        void handleSend(pending, { skipAuthGate: true });
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
    clearStoredMessages();
    stopSpeaking();
    setSessionId(null);
    setMessages([{ id: nextId(), role: 'bot', text: WELCOME_MESSAGE }]);
  }, [stopSpeaking])

  const handleSignOut = useCallback(() => {
    logout();
    handleReset(); // the transcript may hold the customer's account details
  }, [logout, handleReset])

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
      <ChatWindow messages={messages} isSending={isSending && !isStreaming} onOpenLogin={handleOpenLogin} />
      <ChatInput
        onSend={(text, opts) => void handleSend(text, opts)}
        voiceEnabled={voice.enabled}
        speakReplies={speakReplies}
        onToggleSpeak={() => { stopSpeaking(); setSpeakReplies((v) => !v); }}
        disabled={isSending}
        accountType={user ? user.accountType : null}
      />
      <CapabilitiesPanel open={showCapabilities} onClose={() => setShowCapabilities(false)} />
    </div>
  )
};

export default ChatPage;


