import React, { useMemo, useState } from 'react';
import PropTypes from 'prop-types';

import { suggestionChips } from '../../utils/capabilities';
import useRecorder from '../../utils/useRecorder';
import { transcribeAudio } from '../../api/voiceApi';

import './ChatInput.scss';

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
  const suggestions = useMemo(() => suggestionChips(accountType), [accountType]);

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
