import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { login as signIn } from '../../api/authApi';
import { useAuth } from '../../context/AuthContext';

import './LoginPage.scss';

const ACCOUNT_TYPE_OPTIONS = [
  { value: 'ecommerce', label: 'E-commerce' },
  { value: 'insurance', label: 'Insurance' }
];
const REDIRECT_SECONDS = 3;

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

  const [customerEmail, setCustomerEmail] = useState(returnId.includes('@') ? returnId : '');
  const [password, setPassword] = useState('');
  const [accountType, setAccountType] = useState(initialAccountType);
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [signedInSession, setSignedInSession] = useState(null);
  const [secondsLeft, setSecondsLeft] = useState(REDIRECT_SECONDS);

  const hasOpener = typeof window !== 'undefined' && !!window.opener && window.opener !== window;

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const session = await signIn(accountType, customerEmail, password);
      login(session);

      if (hasOpener) {
        try {
          window.opener.postMessage({ type: 'dw-auth-success', session }, window.location.origin);
        } catch {
          // The chat tab could not be notified; the success screen still explains what happened.
        }
      }
      setSignedInSession(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  // After a successful sign-in, count down and then leave: close the pop-up the chat
  // opened (the chat tab already has the session), or go to the chat if opened directly.
  useEffect(() => {
    if (!signedInSession) return undefined;
    if (secondsLeft <= 0) {
      if (hasOpener) window.close();
      navigate('/', { replace: true }); // fallback when the browser refuses window.close()
      return undefined;
    }
    const timer = setTimeout(() => setSecondsLeft((n) => n - 1), 1000);
    return () => clearTimeout(timer);
  }, [signedInSession, secondsLeft, hasOpener, navigate]);

  if (signedInSession) {
    return (
      <div className="auth-shell">
        <div className="auth-card auth-success" role="status" aria-live="polite">
          <div className="auth-success-icon" aria-hidden="true">
            <svg viewBox="0 0 52 52" width="64" height="64">
              <circle className="auth-success-circle" cx="26" cy="26" r="24" fill="none" strokeWidth="3" />
              <path className="auth-success-check" fill="none" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" d="M15 27l8 8 15-17" />
            </svg>
          </div>
          <h1>Signed in successfully</h1>
          <p className="auth-success-name">Welcome, {signedInSession.user.name}</p>
          <p className="auth-success-timer">
            {hasOpener ? 'Returning you to the chat' : 'Taking you to the chat'} in {Math.max(secondsLeft, 0)}…
          </p>
          <div className="auth-success-bar" aria-hidden="true">
            <div className="auth-success-bar-fill" style={{ animationDuration: `${REDIRECT_SECONDS}s` }} />
          </div>
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
              placeholder="you@example.com"
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
              placeholder="Your password"
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

          {error && <div className="auth-error" role="alert">{error}</div>}

          <button type="submit" className="auth-submit" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
};

export default LoginPage;
