import React, { useMemo, useState } from 'react';
import PropTypes from 'prop-types';

import './ChatInput.scss';

const SUGGESTIONS = [
  { text: "What's the status of order ORD1001?", domain: 'ecommerce' },
  { text: 'Track my order ORD1002', domain: 'ecommerce' },
  { text: 'Cancel order ORD1004', domain: 'ecommerce' },
  { text: 'Show me gaming laptops under 150000', domain: 'ecommerce' },
  { text: 'Join the waitlist for SKU-CS-501, email me@example.com', domain: 'ecommerce' },
  { text: 'How long does a refund take?', domain: 'ecommerce' },
  { text: 'Check policy POL2001', domain: 'insurance' },
  { text: 'File a claim on POL2002 for accidental damage, amount 5000', domain: 'insurance' },
  { text: "What's your insurance claims process?", domain: 'insurance' },
];

const orderedSuggestions = (accountType) => {
  if (!accountType || accountType === 'both') {
    return SUGGESTIONS.map((s) => s.text);
  }
  const matching = SUGGESTIONS.filter((s) => s.domain === accountType);
  const rest = SUGGESTIONS.filter((s) => s.domain !== accountType);
  return [...matching, ...rest].map((s) => s.text);
};

const ChatInput = ({ onSend, disabled, accountType }) => {
  const [value, setValue] = useState('');
  const suggestions = useMemo(() => orderedSuggestions(accountType), [accountType]);

  const submit = (e) => {
    e?.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue('');
  };

  return (
    <div className="chat-input-area">
      <div className="suggestions">
        {suggestions.map((s) => (
          <button
            key={s}
            type="button"
            className="suggestion-chip"
            disabled={disabled}
            onClick={() => onSend(s)}
          >
            {s}
          </button>
        ))}
      </div>
      <form className="chat-input-form" onSubmit={submit}>
        <input
          type="text"
          value={value}
          placeholder="Type a message..."
          onChange={(e) => setValue(e.target.value)}
          disabled={disabled}
          autoFocus
        />
        <button type="submit" disabled={disabled || !value.trim()}>
          Send
        </button>
      </form>
    </div>
  )
};

ChatInput.propTypes = {
  onSend: PropTypes.func.isRequired,
  disabled: PropTypes.bool.isRequired,
  accountType: PropTypes.oneOf(['ecommerce', 'insurance', 'both', null]),
};

export default ChatInput;
