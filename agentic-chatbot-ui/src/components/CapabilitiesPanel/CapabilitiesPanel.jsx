import React from 'react';
import PropTypes from 'prop-types';

import './CapabilitiesPanel.scss';

const GROUPS = [
  {
    title: 'E-commerce',
    color: '#22c55e',
    items: [
      'Check order status',
      'Track a package (carrier + live location)',
      'Cancel an order (before it ships)',
      'Initiate a return (after delivery)',
      'Place a new order',
      'Search / browse the product catalog',
      'Join a waitlist for out-of-stock items',
      'Request a callback from a human agent',
    ],
  },
  {
    title: 'Insurance',
    color: '#f59e0b',
    items: ['Check policy details', 'Check claim status', 'File a new claim'],
  },
  {
    title: 'Knowledge base (RAG)',
    color: '#64748b',
    items: [
      'Refund & return policy',
      'Shipping & tracking policy',
      'Waitlist & callback policy',
      'Insurance claims & policy FAQ',
      'General contact-center FAQ',
    ],
  },
];

const CapabilitiesPanel = ({ open, onClose }) => {
  if (!open) return null;

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
          Every capability below is backed by a real tool call the LangGraph agent can invoke — not
          scripted responses. Ask in plain language; the agent decides which tool(s) to use.
        </p>
        {GROUPS.map((group) => {
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
};

export default CapabilitiesPanel;
