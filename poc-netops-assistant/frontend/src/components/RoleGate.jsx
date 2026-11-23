import React, { useState } from 'react';
import {
  UserCheck,
  UserPlus,
  Wrench,
  CheckCircle2,
  Lock,
  Shield,
  ArrowRight,
  Mail,
  Smartphone,
  KeyRound,
  AlertTriangle,
} from 'lucide-react';

export default function RoleGate({ onSelectRole }) {
  // Existing Customer OTP Sign-In State
  const [connectionNumber, setConnectionNumber] = useState('0112456789');
  const [otpChannel, setOtpChannel] = useState('SMS');
  const [otpStep, setOtpStep] = useState('request'); // 'request' | 'verify'
  const [otpCode, setOtpCode] = useState('');
  const [otpMeta, setOtpMeta] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState('');

  // Technical Officer State
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
      if (!resp.ok) {
        throw new Error(data.detail || 'Could not send OTP.');
      }
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
      if (!resp.ok) {
        throw new Error(data.detail || 'OTP verification failed.');
      }
      onSelectRole(
        'Existing Customer',
        data.connection_number,
        data.service_segment,
        data.profile?.customer_name
      );
    } catch (err) {
      setAuthError(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  return (
    <div className="gate-container">
      <div className="gate-header">
        <div className="brand-pill">
          <Shield size={14} /> SLTMobitel Customer Support
        </div>
        <h1>Welcome to SLTMobitel Support</h1>
        <p>
          Existing subscribers sign in with their connection number and OTP — your service type
          (Fibre, Broadband, PEOTV, or SLT Mobitel) is detected automatically.
        </p>
      </div>

      <div className="gate-cards">
        {/* Existing Customer Card (Connection Number + OTP) */}
        <div className="role-card subscriber">
          <div>
            <div className="role-icon-box green">
              <UserCheck size={24} />
            </div>
            <h2>Existing Customer</h2>
            <p className="role-desc">
              Sign in with your connection number &amp; OTP to view account status, credit, tickets, and AI support.
            </p>

            {authError && (
              <div className="alert-banner error" style={{ padding: '0.6rem 0.75rem', fontSize: '0.8rem', marginBottom: '0.75rem' }}>
                <AlertTriangle size={15} /> {authError}
              </div>
            )}

            {otpStep === 'request' ? (
              <form onSubmit={handleRequestOtp}>
                <div className="account-input-group">
                  <label htmlFor="conn-input">SLTMobitel Connection Number</label>
                  <input
                    id="conn-input"
                    type="text"
                    value={connectionNumber}
                    onChange={(e) => setConnectionNumber(e.target.value)}
                    placeholder="e.g., 0112456789 or 0712345678"
                    required
                  />
                  <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: 4 }}>
                    Sample lines: <code>0112456789</code> (Fibre) · <code>0112889941</code> (Broadband) ·{' '}
                    <code>0812233445</code> (PEOTV) · <code>0712345678</code> (SLT Mobitel)
                  </div>
                </div>

                <div className="account-input-group">
                  <label>Receive OTP Via</label>
                  <div className="segment-grid">
                    <button
                      type="button"
                      className={`segment-pill ${otpChannel === 'SMS' ? 'active' : ''}`}
                      onClick={() => setOtpChannel('SMS')}
                    >
                      <Smartphone size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                      SMS
                    </button>
                    <button
                      type="button"
                      className={`segment-pill ${otpChannel === 'EMAIL' ? 'active' : ''}`}
                      onClick={() => setOtpChannel('EMAIL')}
                    >
                      <Mail size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                      Email
                    </button>
                  </div>
                </div>

                <button type="submit" className="btn btn-green" disabled={authLoading}>
                  {authLoading ? 'Sending OTP...' : 'Send OTP Code'} <ArrowRight size={16} />
                </button>
              </form>
            ) : (
              <form onSubmit={handleVerifyOtp}>
                <div
                  className="alert-banner success"
                  style={{ padding: '0.65rem 0.8rem', fontSize: '0.8rem', marginBottom: '0.85rem', display: 'block' }}
                >
                  <div>
                    OTP sent via <strong>{otpMeta?.channel}</strong> to{' '}
                    <code>{otpMeta?.masked_destination}</code>.
                  </div>
                  {otpMeta?.demo_otp_code && (
                    <div style={{ marginTop: 4 }}>
                      Verification Code: <strong><code>{otpMeta.demo_otp_code}</code></strong>
                    </div>
                  )}
                </div>

                <div className="account-input-group">
                  <label htmlFor="otp-input">
                    <KeyRound size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                    Enter 6-Digit OTP
                  </label>
                  <input
                    id="otp-input"
                    type="text"
                    maxLength={6}
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                    placeholder="123456"
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
                    {authLoading ? 'Verifying...' : 'Verify & Sign In'} <ArrowRight size={16} />
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>

        {/* New Customer Card */}
        <div className="role-card">
          <div>
            <div className="role-icon-box blue">
              <UserPlus size={24} />
            </div>
            <h2>New Customer</h2>
            <p className="role-desc">
              Exploring SLTMobitel Fibre, 4G LTE, or PEOTV packages for the first time.
            </p>
            <ul className="feature-list">
              <li>
                <CheckCircle2 size={16} className="ok" /> AI Assistant for Plans, Pricing &amp; USSD
              </li>
              <li>
                <CheckCircle2 size={16} className="ok" /> Filter Packages by Budget &amp; Speed
              </li>
              <li>
                <Lock size={16} className="locked" /> Fault Ticketing &amp; Account Stats (Subscribers Only)
              </li>
            </ul>
          </div>
          <button
            className="btn btn-primary"
            onClick={() => onSelectRole('New Customer', '', 'Fibre')}
          >
            Continue as New Customer <ArrowRight size={16} />
          </button>
        </div>

        {/* Technical Officer Card */}
        <div className="role-card officer">
          <div>
            <div className="role-icon-box amber">
              <Wrench size={24} />
            </div>
            <h2>Technical Officer</h2>
            <p className="role-desc">
              For SLT field technicians and officers managing assigned customer fault tickets.
            </p>
            <ul className="feature-list">
              <li>
                <CheckCircle2 size={16} className="ok" /> Auto Round-Robin Ticket Assignment &amp; Queue
              </li>
              <li>
                <CheckCircle2 size={16} className="ok" /> Contact Customers (Call / SMS / Portal Updates)
              </li>
              <li>
                <CheckCircle2 size={16} className="ok" /> Workload Capacity Control &amp; Field Dispatch
              </li>
            </ul>
            <div className="account-input-group">
              <label htmlFor="officer-select">Select Technical Officer</label>
              <select
                id="officer-select"
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
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  border: '1px solid #e2e8f0',
                  borderRadius: 10,
                  fontSize: '0.9rem',
                }}
              >
                <option value="Eng. Nimal Silva">Eng. Nimal Silva (TO-101)</option>
                <option value="Tech. Chamara Jayasinghe">Tech. Chamara Jayasinghe (TO-102)</option>
                <option value="Eng. Kavindu Perera">Eng. Kavindu Perera (TO-103)</option>
                <option value="Tech. Sashini Wickramasinghe">Tech. Sashini Wickramasinghe (TO-104)</option>
              </select>
            </div>
          </div>
          <button
            className="btn btn-amber"
            onClick={() => onSelectRole('Technical Officer', officerId, 'All', officerName)}
          >
            Continue as Technical Officer <ArrowRight size={16} />
          </button>
        </div>
      </div>

      <div className="staff-bar">
        <span>Internal Operations / NOC Access:</span>
        <button
          className="btn btn-ghost"
          onClick={() => onSelectRole('Tier-1 NOC / Support Agent', 'NOC-01', 'Fibre', 'NOC Agent')}
        >
          Tier-1 NOC Agent
        </button>
        <button
          className="btn btn-ghost"
          onClick={() => onSelectRole('Tier-2 Core Engineer', 'CORE-01', 'Fibre', 'Core Engineer')}
        >
          Tier-2 Core Engineer
        </button>
        <button
          className="btn btn-ghost"
          onClick={() => onSelectRole('Sovereign Cloud Auditor', 'AUD-01', 'Fibre', 'Cloud Auditor')}
        >
          Cloud Auditor
        </button>
      </div>
    </div>
  );
}
