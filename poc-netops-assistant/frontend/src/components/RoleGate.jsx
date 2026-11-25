import React, { useState } from 'react';
import {
  UserCheck,
  UserPlus,
  Wrench,
  CheckCircle2,
  ArrowRight,
  Mail,
  Smartphone,
  KeyRound,
  AlertTriangle,
} from 'lucide-react';

export default function RoleGate({ onSelectRole }) {
  const [connectionNumber, setConnectionNumber] = useState('');
  const [otpChannel, setOtpChannel] = useState('SMS');
  const [otpStep, setOtpStep] = useState('request');
  const [otpCode, setOtpCode] = useState('');
  const [otpMeta, setOtpMeta] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState('');

  // Technical Officer OTP Sign-In State
  const [officerStaffId, setOfficerStaffId] = useState('');
  const [officerChannel, setOfficerChannel] = useState('SMS');
  const [officerOtpStep, setOfficerOtpStep] = useState('request'); // 'request' | 'verify'
  const [officerOtpCode, setOfficerOtpCode] = useState('');
  const [officerOtpMeta, setOfficerOtpMeta] = useState(null);
  const [officerLoading, setOfficerLoading] = useState(false);
  const [officerError, setOfficerError] = useState('');

  const handleRequestOtp = async (e) => {
    e.preventDefault();
    setAuthError('');
    setAuthLoading(true);
    try {
      const resp = await fetch('/api/auth/request-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          connection_number: connectionNumber.trim(),
          channel: otpChannel,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Could not send OTP.');
      setOtpMeta(data);
      setOtpCode(data.demo_otp_code || '');
      setOtpStep('verify');
    } catch (err) {
      setAuthError(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    setAuthError('');
    setAuthLoading(true);
    try {
      const resp = await fetch('/api/auth/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          connection_number: connectionNumber.trim(),
          otp_code: otpCode.trim(),
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'OTP verification failed.');
      onSelectRole(
        'Existing Customer',
        data.connection_number,
        data.service_segment,
        data.profile?.customer_name,
        data.access_token || ''
      );
    } catch (err) {
      setAuthError(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleOfficerRequestOtp = async (e) => {
    e.preventDefault();
    setOfficerError('');
    setOfficerLoading(true);
    try {
      const resp = await fetch('/api/auth/officer/request-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          staff_id: officerStaffId.trim(),
          channel: officerChannel,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Could not send officer OTP.');
      setOfficerOtpMeta(data);
      setOfficerOtpCode(data.demo_otp_code || '');
      setOfficerOtpStep('verify');
    } catch (err) {
      setOfficerError(err.message);
    } finally {
      setOfficerLoading(false);
    }
  };

  const handleOfficerVerifyOtp = async (e) => {
    e.preventDefault();
    setOfficerError('');
    setOfficerLoading(true);
    try {
      const resp = await fetch('/api/auth/officer/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          staff_id: officerStaffId.trim(),
          otp_code: officerOtpCode.trim(),
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Officer OTP verification failed.');
      onSelectRole(
        'Technical Officer',
        data.staff_id,
        'All',
        data.display_name,
        data.access_token || ''
      );
    } catch (err) {
      setOfficerError(err.message);
    } finally {
      setOfficerLoading(false);
    }
  };

  return (
    <div className="gate-page">
      <div className="page-shapes" aria-hidden="true">
        <span className="shape shape-1" />
        <span className="shape shape-2" />
        <span className="shape shape-3" />
        <span className="shape shape-4" />
        <span className="shape shape-5" />
        <span className="shape shape-6" />
        <span className="shape shape-7" />
      </div>

      <div className="slt-utility-bar">
        <div className="slt-utility-links">
          <span>Personal</span>
          <span>Business</span>
          <span>MySLT Self-Care</span>
        </div>
        <span>24/7 Support Hotline: 1212 · Mobile: 1717</span>
      </div>

      <header className="gate-nav">
        <div className="slt-wordmark">
          <span className="slt-logo-icon">SLT</span>
          <span>
            SLT<span className="mobitel-text">MOBITEL</span>
          </span>
        </div>
        <span style={{ fontSize: '0.82rem', color: '#64748b', fontWeight: 500 }}>
          Digital Support &amp; Self-Care Portal
        </span>
      </header>

      <section className="gate-hero">
        <div className="gate-hero-content">
          <div className="gate-hero-tag">SLTMobitel · The Connection</div>
          <h1>How can we help you today?</h1>
          <p>
            Verify your registered connection number with OTP to access your account, billing, and
            fault tickets, or continue as a new customer to explore plans.
          </p>
        </div>
      </section>

      <div className="gate-body">
      <div className="gate-cards">
        {/* Existing Customer Card */}
        <div className="role-card subscriber">
          <div>
            <div className="role-card-head">
              <div className="role-icon-box green">
                <UserCheck size={19} />
              </div>
              <h2>Existing Customer</h2>
            </div>
            <p className="role-desc">
              Verify via SMS or Email OTP. Your connection type is detected automatically.
            </p>

            {authError && (
              <div className="alert-banner error" style={{ padding: '0.55rem 0.75rem', fontSize: '0.8rem' }}>
                <AlertTriangle size={15} /> {authError}
              </div>
            )}

            {otpStep === 'request' ? (
              <form onSubmit={handleRequestOtp}>
                <div className="account-input-group">
                  <label htmlFor="conn-input">Registered Connection Number</label>
                  <input
                    id="conn-input"
                    type="text"
                    value={connectionNumber}
                    onChange={(e) => setConnectionNumber(e.target.value)}
                    placeholder="Enter your 10-digit connection number (e.g. 0112456789)"
                    required
                  />
                </div>

                <div className="account-input-group">
                  <label>Send OTP Via</label>
                  <div className="segment-grid">
                    <button
                      type="button"
                      className={`segment-pill ${otpChannel === 'SMS' ? 'active' : ''}`}
                      onClick={() => setOtpChannel('SMS')}
                    >
                      <Smartphone size={13} style={{ verticalAlign: 'middle', marginRight: 5 }} />
                      SMS
                    </button>
                    <button
                      type="button"
                      className={`segment-pill ${otpChannel === 'EMAIL' ? 'active' : ''}`}
                      onClick={() => setOtpChannel('EMAIL')}
                    >
                      <Mail size={13} style={{ verticalAlign: 'middle', marginRight: 5 }} />
                      Email
                    </button>
                  </div>
                </div>

                <button type="submit" className="btn btn-green" disabled={authLoading}>
                  {authLoading ? 'Sending OTP...' : 'Send OTP'} <ArrowRight size={15} />
                </button>
              </form>
            ) : (
              <form onSubmit={handleVerifyOtp}>
                <div className="alert-banner success" style={{ display: 'block', fontSize: '0.81rem' }}>
                  OTP sent via <strong>{otpMeta?.channel}</strong> to <code>{otpMeta?.masked_destination}</code>.
                  {otpMeta?.demo_otp_code && (
                    <div style={{ marginTop: 4 }}>
                      Code: <strong><code>{otpMeta.demo_otp_code}</code></strong>
                    </div>
                  )}
                </div>

                <div className="account-input-group">
                  <label htmlFor="otp-input">
                    <KeyRound size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                    6-Digit Verification Code
                  </label>
                  <input
                    id="otp-input"
                    type="text"
                    maxLength={6}
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                    placeholder="Enter 6-digit OTP"
                    required
                  />
                </div>

                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    type="button"
                    className="btn btn-outline"
                    onClick={() => {
                      setOtpStep('request');
                      setAuthError('');
                    }}
                  >
                    Back
                  </button>
                  <button type="submit" className="btn btn-green" disabled={authLoading}>
                    {authLoading ? 'Verifying...' : 'Verify & Sign In'} <ArrowRight size={15} />
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>

        {/* New Customer Card */}
        <div className="role-card visitor">
          <div>
            <div className="role-card-head">
              <div className="role-icon-box blue">
                <UserPlus size={19} />
              </div>
              <h2>New Customer</h2>
            </div>
            <p className="role-desc">
              Looking for a new Fibre, 4G LTE Broadband, PEOTV, or SLT Mobitel plan?
            </p>
            <ul className="feature-list">
              <li>
                <CheckCircle2 size={15} className="ok" /> Compare Fibre, 4G LTE &amp; PEOTV packages
              </li>
              <li>
                <CheckCircle2 size={15} className="ok" /> Filter plans by monthly budget &amp; speed
              </li>
              <li>
                <CheckCircle2 size={15} className="ok" /> Instant answers on USSD codes &amp; setup
              </li>
            </ul>
          </div>
          <button
            className="btn btn-primary"
            onClick={() => onSelectRole('New Customer', '', 'Fibre', '', '')}
          >
            Continue to Assistant <ArrowRight size={15} />
          </button>
        </div>
      </div>

      {/* Technical Officer OTP Verification Panel */}
      <div className="staff-panel" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
          <div className="staff-panel-left">
            <div className="role-icon-box amber">
              <Wrench size={17} />
            </div>
            <div>
              <strong style={{ fontSize: '0.92rem' }}>Technical Officer Portal</strong>
              <div style={{ fontSize: '0.77rem', color: '#64748b' }}>
                Verify your registered SLT Staff ID via SMS or Email OTP to review &amp; manage fault tickets
              </div>
            </div>
          </div>
        </div>

        {officerError && (
          <div className="alert-banner error" style={{ marginBottom: 0, padding: '0.55rem 0.75rem', fontSize: '0.8rem' }}>
            <AlertTriangle size={15} /> {officerError}
          </div>
        )}

        {officerOtpStep === 'request' ? (
          <form onSubmit={handleOfficerRequestOtp} className="staff-panel-controls" style={{ width: '100%' }}>
            <input
              type="text"
              value={officerStaffId}
              onChange={(e) => setOfficerStaffId(e.target.value)}
              placeholder="Enter SLT Staff ID (e.g. TO-101)"
              required
              style={{
                flex: '1 1 210px',
                padding: '9px 12px',
                border: '1px solid #cbd5e1',
                borderRadius: 9,
                fontSize: '0.88rem',
              }}
            />
            <div style={{ display: 'inline-flex', gap: 6 }}>
              <button
                type="button"
                className={`segment-pill ${officerChannel === 'SMS' ? 'active' : ''}`}
                onClick={() => setOfficerChannel('SMS')}
              >
                <Smartphone size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                SMS
              </button>
              <button
                type="button"
                className={`segment-pill ${officerChannel === 'EMAIL' ? 'active' : ''}`}
                onClick={() => setOfficerChannel('EMAIL')}
              >
                <Mail size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                Email
              </button>
            </div>
            <button type="submit" className="btn btn-amber" disabled={officerLoading}>
              {officerLoading ? 'Sending OTP...' : 'Send Officer OTP'} <ArrowRight size={14} />
            </button>
          </form>
        ) : (
          <form onSubmit={handleOfficerVerifyOtp} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div className="alert-banner success" style={{ marginBottom: 0, display: 'block', fontSize: '0.8rem' }}>
              Officer OTP sent via <strong>{officerOtpMeta?.channel}</strong> to{' '}
              <code>{officerOtpMeta?.masked_destination}</code>.
              {officerOtpMeta?.demo_otp_code && (
                <span style={{ marginLeft: 8 }}>
                  Code: <strong><code>{officerOtpMeta.demo_otp_code}</code></strong>
                </span>
              )}
            </div>
            <div className="staff-panel-controls" style={{ width: '100%' }}>
              <input
                type="text"
                maxLength={6}
                value={officerOtpCode}
                onChange={(e) => setOfficerOtpCode(e.target.value)}
                placeholder="Enter 6-digit Officer OTP"
                required
                style={{
                  flex: '1 1 180px',
                  padding: '9px 12px',
                  border: '1px solid #cbd5e1',
                  borderRadius: 9,
                  fontSize: '0.88rem',
                }}
              />
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => {
                  setOfficerOtpStep('request');
                  setOfficerError('');
                }}
              >
                Back
              </button>
              <button type="submit" className="btn btn-amber" disabled={officerLoading}>
                {officerLoading ? 'Verifying...' : 'Verify & Sign In'} <ArrowRight size={14} />
              </button>
            </div>
          </form>
        )}
      </div>
      </div>

      <footer className="slt-footer">
        © SLTMobitel · Sri Lanka Telecom PLC · Fixed / Fibre / PEOTV: 1212 · Mobile: 1717
      </footer>
    </div>
  );
}
