import React, { useState, useEffect } from 'react';
import {
  Activity,
  Ticket,
  Search,
  AlertTriangle,
  CheckCircle2,
  KeyRound,
} from 'lucide-react';
import MarkdownText from './MarkdownText.jsx';

export default function AccountTicketsView({ userRole, accountNumber }) {
  const [profile, setProfile] = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [error, setError] = useState('');

  // Fault Ticket Form
  const [serviceType, setServiceType] = useState('Fibre');
  const [issueDesc, setIssueDesc] = useState('');
  const [contactNum, setContactNum] = useState('071 234 5678');
  const [submitting, setSubmitting] = useState(false);
  const [ticketConfirmation, setTicketConfirmation] = useState(null);

  // Ticket Status Lookup
  const [lookupId, setLookupId] = useState('FLT-2026-1042');
  const [lookupResult, setLookupResult] = useState(null);

  const loadProfile = async () => {
    setLoadingProfile(true);
    setError('');
    try {
      const resp = await fetch(`/api/account/${encodeURIComponent(accountNumber || '0112456789')}`, {
        headers: { 'X-User-Role': userRole },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || 'Unable to fetch account profile.');
      }
      const data = await resp.json();
      setProfile(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingProfile(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, [userRole, accountNumber]);

  const handleSubmitTicket = async (e) => {
    e.preventDefault();
    if (!issueDesc.trim()) return;
    setSubmitting(true);
    setTicketConfirmation(null);
    try {
      const resp = await fetch('/api/tickets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_number: accountNumber || 'SLT-ACC-0112456789',
          service_type: serviceType,
          issue_description: issueDesc.trim(),
          contact_number: contactNum.trim(),
          user_role: userRole,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || 'Failed to log fault ticket.');
      }
      setTicketConfirmation(data);
      setLookupId(data.ticket_id);
      setIssueDesc('');
      loadProfile();
    } catch (err) {
      setTicketConfirmation({ error: err.message });
    } finally {
      setSubmitting(false);
    }
  };

  const handleTrackTicket = async (e) => {
    e.preventDefault();
    if (!lookupId.trim()) return;
    try {
      const resp = await fetch(`/api/tickets/${encodeURIComponent(lookupId.trim())}`, {
        headers: { 'X-User-Role': userRole },
      });
      const data = await resp.json();
      setLookupResult(data);
    } catch (err) {
      setLookupResult({ found: false, summary_markdown: err.message });
    }
  };

  if (loadingProfile) {
    return <div className="panel-card">Loading account overview...</div>;
  }

  if (error) {
    return (
      <div className="alert-banner error">
        <AlertTriangle size={18} />
        <span>{error}</span>
      </div>
    );
  }

  const dataPct = profile
    ? Math.min(100, Math.round((profile.data_remaining_gb / profile.data_total_gb) * 100))
    : 0;

  return (
    <div>
      {profile?.is_mock_data && (
        <div className="alert-banner warn">
          <KeyRound size={18} />
          <span>
            <strong>Stub Mode Active:</strong> Displaying verified sample account stats until your
            supervisor provides <code>SLT_CUSTOMER_DATA_API_KEY</code> in <code>.env</code>.
          </span>
        </div>
      )}

      {/* Account Overview Stats */}
      {profile && (
        <div className="dashboard-grid">
          <div className="stat-card">
            <div className="stat-label">Account &amp; Status</div>
            <div className="stat-value" style={{ fontSize: '1.1rem' }}>
              {profile.account_id}
            </div>
            <div className="stat-sub">
              {profile.customer_name} · <strong style={{ color: '#00a859' }}>{profile.connection_status}</strong>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-label">Subscribed Plan</div>
            <div className="stat-value" style={{ fontSize: '1.1rem' }}>
              {profile.subscribed_package.split('(')[0].trim()}
            </div>
            <div className="stat-sub">Optical Rx: {profile.optical_rx_power_dbm} dBm</div>
          </div>

          <div className="stat-card">
            <div className="stat-label">Data Remaining</div>
            <div className="stat-value">
              {profile.data_remaining_gb} GB
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${dataPct}%` }} />
            </div>
            <div className="stat-sub">
              {dataPct}% of {profile.data_total_gb} GB remaining
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-label">Current Bill</div>
            <div className="stat-value">
              Rs. {Number(profile.current_balance_rs).toLocaleString()}
            </div>
            <div className="stat-sub">Due Date: {profile.bill_due_date}</div>
          </div>
        </div>
      )}

      {/* Log Fault Ticket Form */}
      <div className="panel-card">
        <h3>
          <Ticket size={18} /> Report a Service Fault Ticket
        </h3>
        <form onSubmit={handleSubmitTicket}>
          <div className="form-grid">
            <div className="field">
              <label>Service Category</label>
              <select value={serviceType} onChange={(e) => setServiceType(e.target.value)}>
                <option value="Fibre">SLT Fibre Broadband (FTTH)</option>
                <option value="4G LTE">4G LTE Home Broadband</option>
                <option value="PEOTV">PEOTV</option>
                <option value="Copper Voice">Copper Voice / Megaline</option>
              </select>
            </div>
            <div className="field">
              <label>Contact Mobile Number</label>
              <input
                type="text"
                value={contactNum}
                onChange={(e) => setContactNum(e.target.value)}
                placeholder="071 234 5678"
              />
            </div>
          </div>
          <div className="field" style={{ marginBottom: '1rem' }}>
            <label>Fault Description</label>
            <textarea
              rows={3}
              value={issueDesc}
              onChange={(e) => setIssueDesc(e.target.value)}
              placeholder="e.g., Optical LOS light is red on the Fibre router and internet is down..."
              required
            />
          </div>
          <button type="submit" className="btn btn-green" style={{ width: 'auto' }} disabled={submitting}>
            {submitting ? 'Logging Ticket...' : 'Submit Fault Ticket'}
          </button>
        </form>

        {ticketConfirmation && !ticketConfirmation.error && (
          <div className="alert-banner success" style={{ marginTop: '1rem', display: 'block' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <CheckCircle2 size={18} />
              <strong>Ticket Logged: {ticketConfirmation.ticket_id}</strong>
            </div>
            <MarkdownText text={ticketConfirmation.summary_markdown} />
          </div>
        )}
        {ticketConfirmation?.error && (
          <div className="alert-banner error" style={{ marginTop: '1rem' }}>
            <AlertTriangle size={18} /> {ticketConfirmation.error}
          </div>
        )}
      </div>

      {/* Track Ticket Status */}
      <div className="panel-card">
        <h3>
          <Search size={18} /> Track Existing Ticket Status
        </h3>
        <form onSubmit={handleTrackTicket} style={{ display: 'flex', gap: 10, marginBottom: '1rem' }}>
          <input
            type="text"
            value={lookupId}
            onChange={(e) => setLookupId(e.target.value)}
            placeholder="FLT-2026-1042"
            style={{
              flex: 1,
              padding: '9px 12px',
              border: '1px solid #e2e8f0',
              borderRadius: 9,
              fontSize: '0.9rem',
            }}
          />
          <button type="submit" className="btn btn-outline">
            Check Status
          </button>
        </form>

        {lookupResult && (
          <div className={`alert-banner ${lookupResult.found ? 'success' : 'error'}`} style={{ display: 'block' }}>
            <MarkdownText text={lookupResult.summary_markdown} />
          </div>
        )}

        {profile?.recent_tickets?.length > 0 && (
          <div style={{ marginTop: '1rem' }}>
            <h4 style={{ fontSize: '0.88rem', color: '#64748b', marginBottom: '0.5rem' }}>
              <Activity size={14} style={{ verticalAlign: 'middle' }} /> Recent Account Tickets
            </h4>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ticket ID</th>
                  <th>Service</th>
                  <th>Status</th>
                  <th>Priority</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                {profile.recent_tickets.map((t) => (
                  <tr key={t.ticket_id}>
                    <td><code>{t.ticket_id}</code></td>
                    <td>{t.service_type}</td>
                    <td><strong>{t.status}</strong></td>
                    <td>{t.priority}</td>
                    <td>{t.issue_description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
