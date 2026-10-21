import React from 'react';
import PropTypes from 'prop-types';

import { capabilityGroups } from '../../utils/capabilities';

import './CapabilitiesPanel.scss';

const CapabilitiesPanel = ({ open, onClose, accountType, voiceEnabled }) => {
  if (!open) return null;

  const groups = capabilityGroups(accountType, voiceEnabled);

  return (
    <div className="capabilities-overlay" onClick={onClose}>
      <div className="capabilities-panel" onClick={(e) => e.stopPropagation()}>
        <div className="capabilities-header">
          <h2>What Intellia can do</h2>
          <button className="capabilities-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <p className="capabilities-subtitle">
          {accountType
            ? `You're signed in to ${accountType === 'insurance' ? 'Insurance' : 'E-commerce'}, so these are the things I can do for your account. `
            : 'Sign in to use the account features below. '}
          Every item is backed by a real tool or knowledge document. Ask in plain language.
        </p>
        {groups.map((group) => {
          const titleStyle = { '--group-color': group.color }
          return (
            <div key={group.title} className="capabilities-group">
              <div className="capabilities-group-title" style={titleStyle}>
                <span className="capabilities-dot" />
                {group.title}
              </div>
              <ul>
                {group.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          )
        })}
      </div>
    </div>
  )
};

CapabilitiesPanel.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  accountType: PropTypes.oneOf(['ecommerce', 'insurance', 'both', null]),
  voiceEnabled: PropTypes.bool,
};

export default CapabilitiesPanel;
