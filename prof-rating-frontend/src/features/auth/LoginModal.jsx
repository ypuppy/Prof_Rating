import { useEffect, useState } from 'react';
import { requestLoginCode, verifyLoginCode } from '../../api/auth';
import Button from '../../components/Button';
import './LoginModal.css';

const RESEND_SECONDS = 60;

export default function LoginModal({ onSuccess, onCancel }) {
  const [step, setStep] = useState('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resendIn, setResendIn] = useState(0);

  useEffect(() => {
    if (resendIn <= 0) return;
    const timer = setTimeout(() => setResendIn((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendIn]);

  const sendCode = async () => {
    setLoading(true);
    setError('');
    try {
      await requestLoginCode(email.trim());
      setStep('code');
      setCode('');
      setResendIn(RESEND_SECONDS);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleEmailSubmit = (e) => {
    e.preventDefault();
    if (!email.trim()) {
      setError('Enter your NUS email');
      return;
    }
    sendCode();
  };

  const handleCodeSubmit = async (e) => {
    e.preventDefault();
    if (code.length !== 6) {
      setError('Enter the 6-digit code from your email');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const user = await verifyLoginCode(email.trim(), code);
      onSuccess(user);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  return (
    <div className="login-form">
      <div className="form-header">
        <h2>Log in to ProfRating</h2>
        <p>
          {step === 'email'
            ? 'We\'ll email you a 6-digit code. No password needed.'
            : <>We sent a code to <strong>{email.trim().toLowerCase()}</strong>. Check your junk folder if it isn't there.</>}
        </p>
      </div>

      {step === 'email' ? (
        <form onSubmit={handleEmailSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="loginEmail">NUS email</label>
            <input
              id="loginEmail"
              type="email"
              className="form-input"
              placeholder="e1234567@u.nus.edu"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus
            />
          </div>

          {error && <div className="form-error">{error}</div>}

          <div className="form-actions">
            <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
            <Button type="submit" variant="primary" loading={loading}>Send code</Button>
          </div>
          <p className="login-note">Your reviews are shown anonymously. Other students never see your email.</p>
        </form>
      ) : (
        <form onSubmit={handleCodeSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="loginCode">6-digit code</label>
            <input
              id="loginCode"
              type="text"
              className="form-input code-input"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="000000"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              autoFocus
            />
          </div>

          {error && <div className="form-error">{error}</div>}

          <div className="form-actions">
            <Button type="button" variant="ghost" onClick={() => { setStep('email'); setError(''); }}>
              Change email
            </Button>
            <Button type="submit" variant="primary" loading={loading}>Log in</Button>
          </div>
          <p className="login-note">
            {resendIn > 0 ? (
              `Didn't get it? You can resend in ${resendIn}s`
            ) : (
              <button type="button" className="link-button" onClick={sendCode} disabled={loading}>
                Resend code
              </button>
            )}
          </p>
        </form>
      )}
    </div>
  );
}
