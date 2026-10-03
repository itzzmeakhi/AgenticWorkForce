import React from 'react';
import PropTypes from 'prop-types';

import './Header.scss';

const Header = ({ backendStatus, user, onReset, onShowCapabilities, onSignIn, onSignOut }) => {
  return (
    <header className="header">
      <div className="header-title">
        <span className="header-icon">🤖</span>
        <div>
          <h1>Intellia — Agentic AI Enterprise Digital Workforce</h1>
        </div>
      </div>
      <div className="header-actions">
        <span className={`status-dot status-${backendStatus}`} title={`Backend: ${backendStatus}`} />
        {user ? (
          <span className="user-badge" title={`Customer/policy ID: ${user.customerId}`}>
            <span className="user-badge-name">{user.name}</span>
            <span className="user-badge-type">· {user.accountType}</span>
          </span>
        ) : (
          <span className="user-badge user-badge-guest">Not signed in</span>
        )}
        <button className="capabilities-btn" onClick={onShowCapabilities}>
          What can Intellia do?
        </button>
        <button className="reset-btn" onClick={onReset}>
          New conversation
        </button>
        {user ? (
          <button className="signout-btn" onClick={onSignOut}>
            Sign out
          </button>
        ) : (
          <button className="signin-btn" onClick={onSignIn}>
            Sign in ↗
          </button>
        )}
      </div>
    </header>
  )
};

Header.propTypes = {
  backendStatus: PropTypes.oneOf(['checking', 'online', 'offline']).isRequired,
  user: PropTypes.shape({
    name: PropTypes.string.isRequired,
    customerId: PropTypes.string.isRequired,
    accountType: PropTypes.string.isRequired,
  }),
  onReset: PropTypes.func.isRequired,
  onShowCapabilities: PropTypes.func.isRequired,
  onSignIn: PropTypes.func.isRequired,
  onSignOut: PropTypes.func.isRequired,
};

export default Header;
