import React from 'react';
import PropTypes from 'prop-types';

import ToolTrace from '../ToolTrace/ToolTrace';
import DomainBadge from '../DomainBadge/DomainBadge';
import MarkdownLite from '../../utils/renderMarkdownLite';

import './MessageBubble.scss';

const MessageBubble = ({ role, text, domain, toolCalls, isError, authPrompt, onOpenLogin }) => {
  const isUser = role === 'user';

  return (
    <div className={`message-row ${isUser ? 'from-user' : 'from-bot'}`}>
      {!isUser && <ToolTrace toolCalls={toolCalls} />}
      <div className={`bubble ${isUser ? 'bubble-user' : 'bubble-bot'} ${isError ? 'bubble-error' : ''}`}>
        {isUser ? text : <MarkdownLite text={text} />}
        {authPrompt && (
          <button
            type="button"
            className="auth-prompt-btn"
            onClick={() => onOpenLogin?.(authPrompt)}
          >
            Sign in to continue ↗
          </button>
        )}
      </div>
      {!isUser && domain && (
        <div className="bubble-meta">
          <DomainBadge domain={domain} />
        </div>
      )}
    </div>
  )
};

MessageBubble.propTypes = {
  role: PropTypes.oneOf(['user', 'bot']).isRequired,
  text: PropTypes.string.isRequired,
  domain: PropTypes.string,
  toolCalls: PropTypes.arrayOf(
    PropTypes.shape({
      tool: PropTypes.string,
      args: PropTypes.object,
      tool_result: PropTypes.string,
      output: PropTypes.string,
    }),
  ),
  isError: PropTypes.bool,
  authPrompt: PropTypes.shape({
    pendingText: PropTypes.string,
    id: PropTypes.string,
    domain: PropTypes.string,
  }),
  onOpenLogin: PropTypes.func,
};

export default MessageBubble;
