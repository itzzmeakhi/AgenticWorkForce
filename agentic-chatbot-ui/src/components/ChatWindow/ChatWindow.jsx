import React, { useEffect, useRef } from 'react';
import PropTypes from 'prop-types';

import MessageBubble from '../MessageBubble/MessageBubble';
import TypingIndicator from '../TypingIndicator/TypingIndicator';

import './ChatWindow.scss';

const ChatWindow = ({ messages, isSending, onOpenLogin }) => {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isSending]);

  return (
    <div className="chat-window">
      {messages.length === 0 && (
        <div className="empty-state">
          Ask me anything about e-commerce or insurance. Questions about a specific order or
          policy will ask you to sign in first.
        </div>
      )}
      {messages.map((m) => (
        <MessageBubble key={m.id} {...m} onOpenLogin={onOpenLogin} />
      ))}
      {isSending && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  )
};

ChatWindow.propTypes = {
  messages: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      role: PropTypes.oneOf(['user', 'bot']).isRequired,
      text: PropTypes.string.isRequired,
      domain: PropTypes.string,
      toolCalls: PropTypes.array,
      isError: PropTypes.bool,
      authPrompt: PropTypes.shape({
        pendingText: PropTypes.string,
        id: PropTypes.string,
        domain: PropTypes.string,
      }),
    }),
  ).isRequired,
  isSending: PropTypes.bool.isRequired,
  onOpenLogin: PropTypes.func.isRequired,
};

export default ChatWindow;
