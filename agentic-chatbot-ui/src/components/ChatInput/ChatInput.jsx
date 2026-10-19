import React, { useMemo, useState } from 'react';
import PropTypes from 'prop-types';

import useRecorder from '../../utils/useRecorder';
import { transcribeAudio } from '../../api/voiceApi';

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

const ChatInput = ({ onSend, disabled, accountType, voiceEnabled, speakReplies, onToggleSpeak }) => {
  const [value, setValue] = useState('');
  const [voiceNote, setVoiceNote] = useState('');
  const [transcribing, setTranscribing] = useState(false);

  const { state: micState, toggle: toggleMic } = useRecorder(
    async (blob) => {
      setVoiceNote('');
      setTranscribing(true);
      try {
        const text = await transcribeAudio(blob);
        if (text) onSend(text, { viaVoice: true });
        else setVoiceNote("I didn't catch that - please try again.");
      } catch (err) {
        setVoiceNote(`Voice input failed: ${err.message}`);
      } finally {
        setTranscribing(false);
      }
    },
    (msg) => setVoiceNote(msg),
  );
  const recording = micState === 'recording';
  const micAvailable = voiceEnabled && micState !== 'unsupported';
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
      {voiceNote && <div className="voice-note" role="status">{voiceNote}</div>}
      <form className="chat-input-form" onSubmit={submit}>
        <input
          type="text"
          value={value}
          placeholder="Type a message..."
          onChange={(e) => setValue(e.target.value)}
          disabled={disabled || recording}
          autoFocus
        />
        {micAvailable && (
          <>
            <button
              type="button"
              className={`voice-btn ${recording ? 'recording' : ''}`}
              onClick={toggleMic}
              disabled={(disabled && !recording) || transcribing}
              aria-pressed={recording}
              title={recording ? 'Stop and send' : 'Speak your message'}
            >
              {transcribing ? '…' : recording ? '■ Stop' : '🎤'}
            </button>
            <button
              type="button"
              className={`voice-btn ${speakReplies ? 'on' : ''}`}
              onClick={onToggleSpeak}
              aria-pressed={speakReplies}
              title={speakReplies ? 'Spoken replies on' : 'Spoken replies off'}
            >
              {speakReplies ? '🔊' : '🔈'}
            </button>
          </>
        )}
        <button type="submit" disabled={disabled || recording || !value.trim()}>
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
  voiceEnabled: PropTypes.bool,
  speakReplies: PropTypes.bool,
  onToggleSpeak: PropTypes.func,
};

export default ChatInput;
