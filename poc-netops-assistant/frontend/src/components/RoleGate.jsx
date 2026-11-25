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

  const [officerName, setOfficerName] = useState('Eng. Nimal Silva');
  const [officerId, setOfficerId] = useState('TO-101');

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

  const handleStaffLogin = async (role, staffId, displayName) => {
    try {
      const resp = await fetch('/api/auth/staff-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role, staff_id: staffId, display_name: displayName }),
      });
      const data = await resp.json();
      if (resp.ok && data.access_token) {
        onSelectRole(role, staffId, 'All', displayName, data.access_token);
        return;
      }
    } catch {
      // Dev fallback
    }
    onSelectRole(role, staffId, 'All', displayName, '');
  };

  return (
    <div className="gate-container">
      <div className="gate-header">
        <div className="slt-wordmark" style={{ fontSize: '1.15rem', color: '#003e78' }}>
          <span className="slt-mark-badge">SLT</span>
          <span>SLTMobitel Support</span>
        </div>
        <h1>How can we help you today?</h1>
        <p>
          Sign in with your connection number to manage your account and tickets, or continue as a
          new visitor to explore packages.
        </p>
      </div>

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

      {/* Discrete Staff / Technical Officer Bar */}
      <div className="staff-panel">
        <div className="staff-panel-left">
          <div className="role-icon-box amber">
            <Wrench size={17} />
          </div>
          <div>
            <strong style={{ fontSize: '0.88rem' }}>Technical Officer Portal</strong>
            <div style={{ fontSize: '0.77rem', color: '#64748b' }}>
              Review assigned fault tickets, manage workload capacity, and contact subscribers
            </div>
          </div>
        </div>

        <div className="staff-panel-controls">
          <select
            aria-label="Select Technical Officer"
            value={officerName}
            onChange={(e) => {
              const val = e.target.value;
              setOfficerName(val);
              const idMap = {
                'Eng. Nimal Silva': 'TO-101',
                'Tech. Chamara Jayasinghe': 'TO-102',
                'Eng. Kavindu Perera': 'TO-103',
                'Tech. Sashini Wickramasinghe': 'TO-104',
              };
              setOfficerId(idMap[val] || 'TO-101');
            }}
          >
            <option value="Eng. Nimal Silva">Eng. Nimal Silva (TO-101)</option>
            <option value="Tech. Chamara Jayasinghe">Tech. Chamara Jayasinghe (TO-102)</option>
            <option value="Eng. Kavindu Perera">Eng. Kavindu Perera (TO-103)</option>
            <option value="Tech. Sashini Wickramasinghe">Tech. Sashini Wickramasinghe (TO-104)</option>
          </select>
          <button
            className="btn btn-amber"
            onClick={() => handleStaffLogin('Technical Officer', officerId, officerName)}
          >
            Officer Sign In <ArrowRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
