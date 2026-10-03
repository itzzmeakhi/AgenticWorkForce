import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { fakeAuthenticate } from '../../api/authApi';
import { useAuth } from '../../context/AuthContext';

import './LoginPage.scss';

const ACCOUNT_TYPE_OPTIONS = [
  { value: 'ecommerce', label: 'E-commerce' },
  { value: 'insurance', label: 'Insurance' }
];

const LoginPage = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [searchParams] = useSearchParams();

  const returnId = searchParams.get('returnId') ?? '';
  const pendingText = searchParams.get('pending') ?? '';
  const domainParam = searchParams.get('domain');
  const initialAccountType =
    domainParam === 'ecommerce' || domainParam === 'insurance'
      ? domainParam
      : 'ecommerce';

  const [customerEmail, setCustomerEmail] = useState(returnId);
  const [password, setPassword] = useState('');
  const [accountType, setAccountType] = useState(initialAccountType);
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [signedInSession, setSignedInSession] = useState(null);

  const hasOpener = typeof window !== 'undefined' && !!window.opener && window.opener !== window;

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const session = await fakeAuthenticate(customerEmail, password, accountType);
      login(session.user);

      if (hasOpener) {
        try {
          window.opener.postMessage({ type: 'dw-auth-success', session }, window.location.origin);
        } catch {
          // TODO: handle the error
        }
        setSignedInSession(session);
      } else {
        navigate('/', { replace: true });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (signedInSession) {
    return (
      <div className="auth-shell">
        <div className="auth-card">
          <div className="auth-header">
            <span className="auth-icon">✅</span>
            <div>
              <h1>Signed in as {signedInSession.user.name}</h1>
              <p>Your chat tab has been notified — you can close this tab now.</p>
            </div>
          </div>
          <button type="button" className="auth-submit" onClick={() => window.close()}>
            Close this tab
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-header">
          <span className="auth-icon">🔐</span>
          <div>
            <h1>Sign in to Intellia</h1>
            <p>
              {pendingText
                ? 'This question needs your account details.'
                : 'Sign in to ask about your own orders or policy.'}
            </p>
          </div>
        </div>

        {pendingText && <p className="auth-pending-hint">Continuing: “{pendingText}”</p>}

        <form className="auth-form" onSubmit={submit}>
          <div className="auth-field">
            <label htmlFor="auth-customer-email">Email</label>
            <input
              id="auth-customer-email"
              type="text"
              value={customerEmail}
              onChange={(e) => setCustomerEmail(e.target.value)}
              placeholder="e.g. john.doe@example.com"
              autoComplete="off"
              autoFocus
            />
          </div>

          <div className="auth-field">
            <label htmlFor="auth-password">Password</label>
            <input
              id="auth-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="anything 6+ characters"
              autoComplete="current-password"
            />
          </div>

          <fieldset className="auth-account-type">
            <legend>Login to</legend>
            <div className="auth-account-options">
              {ACCOUNT_TYPE_OPTIONS.map((opt) => (
                <label className="auth-account-option" key={opt.value}>
                  <input
                    type="radio"
                    name="account-type"
                    value={opt.value}
                    checked={accountType === opt.value}
                    onChange={() => setAccountType(opt.value)}
                  />
                  <span>{opt.label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {error && <div className="auth-error">{error}</div>}

          <button type="submit" className="auth-submit" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
};

export default LoginPage;
