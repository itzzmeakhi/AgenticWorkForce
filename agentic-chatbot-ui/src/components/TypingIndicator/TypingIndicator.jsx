import React from 'react';

import './TypingIndicator.scss';

const TypingIndicator = () => {
  return (
    <div className="message-row from-bot">
      <div className="bubble bubble-bot typing-bubble">
        <span className="dot" />
        <span className="dot" />
        <span className="dot" />
      </div>
    </div>
  )
};

export default TypingIndicator;
