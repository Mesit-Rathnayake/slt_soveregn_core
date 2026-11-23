import React, { useState, useEffect } from 'react';
import {
  Activity,
  Ticket,
  Search,
  AlertTriangle,
  CheckCircle2,
  KeyRound,
  ArrowRight,
  ArrowLeft,
  ClipboardCheck,
  Wrench,
  MapPin,
} from 'lucide-react';
import MarkdownText from './MarkdownText.jsx';

const FAULT_CATEGORIES = {
  Fibre: [
    'Red LOS / Blinking PON LED',
    'No Internet / Complete Outage',
    'Slow Speed / High Latency',
    'Frequent Disconnections',
    'Wi-Fi / Router Hardware Issue',
    'External Fibre Drop Wire Damage',
  ],
  '4G LTE': [
    'No Signal / Red Signal Light',
    'Slow Speed / High Latency',
    'Frequent Disconnections',
    'SIM / Router Hardware Issue',
  ],
  PEOTV: [
    'No Signal / Black Screen',
    'Channel Freezing / Pixelation',
    'Set-Top Box (STB) / Remote Fault',
    'Audio / Video Sync Issue',
  ],
  'Copper Voice': [
    'No Dial Tone / Dead Line',
    'Static / Noise on Line',
    'Unable to Make or Receive Calls',
    'External Drop Wire Damage',
  ],
  Mobile: [
    'No Mobile Signal / SIM Error',
    'Slow 4G Mobile Data',
    'VoLTE / Call Drop Issue',
    'eSIM / Roaming Activation Issue',
  ],
};

const SEGMENT_TO_SERVICE = {
  Fibre: 'Fibre',
  Broadband: '4G LTE',
  PEOTV: 'PEOTV',
  Mobile: 'Mobile',
  'SLT Mobitel': 'Mobile',
};

const LED_OPTIONS = [
  'LOS Red (Solid or Blinking)',
  'PON Blinking Green',
  'All Lights Green (No Internet)',
  'WLAN / Wi-Fi LED Off',
  'Power LED Off / Router Not Turning On',
  'Not Applicable (PEOTV / Voice)',
];

export default function AccountTicketsView({ userRole, accountNumber, serviceSegment = 'Fibre' }) {
  const initialSvc = SEGMENT_TO_SERVICE[serviceSegment] || 'Fibre';
  const [profile, setProfile] = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [error, setError] = useState('');

  // 3-Step Fault Ticket Wizard State
  const [step, setStep] = useState(1);
  const [serviceType, setServiceType] = useState(initialSvc);
  const [faultCategory, setFaultCategory] = useState(
    (FAULT_CATEGORIES[initialSvc] || FAULT_CATEGORIES.Fibre)[0]
  );
  const [ledStatus, setLedStatus] = useState(LED_OPTIONS[0]);
  const [impactLevel, setImpactLevel] = useState('High (Household Outage)');
  const [affectedDevices, setAffectedDevices] = useState('All Devices (Wi-Fi & Ethernet)');
  const [issueStarted, setIssueStarted] = useState('Today');
  const [routerRestarted, setRouterRestarted] = useState(true);
  const [cablesChecked, setCablesChecked] = useState(true);

  const [issueDesc, setIssueDesc] = useState('');
  const [contactName, setContactName] = useState('Kasun Perera');
  const [contactNum, setContactNum] = useState('071 234 5678');
  const [serviceAddress, setServiceAddress] = useState('No. 42, Galle Road, Colombo 03');
  const [visitSlot, setVisitSlot] = useState('Morning (08:00 - 12:00)');

  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [ticketConfirmation, setTicketConfirmation] = useState(null);

  // Ticket Status Lookup
  const [lookupId, setLookupId] = useState('FLT-2026-1042');
  const [lookupResult, setLookupResult] = useState(null);
  const [selectedTicket, setSelectedTicket] = useState(null);

  const loadProfile = async () => {
    setLoadingProfile(true);
    setError('');
    try {
      const resp = await fetch(
        `/api/account/${encodeURIComponent(accountNumber || '0112456789')}`,
        { headers: { 'X-User-Role': userRole } }
      );
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || 'Unable to fetch account profile.');
      }
      const data = await resp.json();
      setProfile(data);
      if (data.customer_name) setContactName(data.customer_name);
      if (data.telephone_number) setContactNum(data.telephone_number);
      if (data.service_address) setServiceAddress(data.service_address);
      const mapped = SEGMENT_TO_SERVICE[data.service_segment] || 'Fibre';
      setServiceType(mapped);
      setFaultCategory((FAULT_CATEGORIES[mapped] || FAULT_CATEGORIES.Fibre)[0]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingProfile(false);
    }
  };

  useEffect(() => {
    const mapped = SEGMENT_TO_SERVICE[serviceSegment] || 'Fibre';
    setServiceType(mapped);
    setFaultCategory((FAULT_CATEGORIES[mapped] || FAULT_CATEGORIES.Fibre)[0]);
    loadProfile();
  }, [userRole, accountNumber, serviceSegment]);

  const handleServiceChange = (newService) => {
    setServiceType(newService);
    const cats = FAULT_CATEGORIES[newService] || FAULT_CATEGORIES.Fibre;
    setFaultCategory(cats[0]);
  };

  const goToStep2 = () => {
    setFormError('');
    setStep(2);
  };

  const goToStep3 = () => {
    if (issueDesc.trim().length < 15) {
      setFormError('Please provide a detailed description (at least 15 characters) so our technician can diagnose the fault accurately.');
      return;
    }
    if (!contactNum.trim() || !serviceAddress.trim()) {
      setFormError('Please provide both a contact mobile number and service premises address.');
      return;
    }
    setFormError('');
    setStep(3);
  };

  const estimatedCritical =
    `${issueDesc} ${faultCategory} ${ledStatus}`.toLowerCase().match(/(los|red|outage|down|cut|no connection|dead)/) ||
    impactLevel.toLowerCase().includes('critical');

  const handleSubmitTicket = async () => {
    setSubmitting(true);
    setTicketConfirmation(null);
    setFormError('');
    try {
      const fullDescription = cablesChecked
        ? `${issueDesc.trim()} (Pre-check: Power & line cables verified tightly connected)`
        : issueDesc.trim();

      const resp = await fetch('/api/tickets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_number: accountNumber || 'SLT-ACC-0112456789',
          service_type: serviceType,
          fault_category: faultCategory,
          led_status: ledStatus,
          router_restarted: routerRestarted,
          affected_devices: affectedDevices,
          issue_started: issueStarted,
          impact_level: impactLevel,
          issue_description: fullDescription,
          contact_name: contactName.trim(),
          contact_number: contactNum.trim(),
          service_address: serviceAddress.trim(),
          preferred_visit_slot: visitSlot,
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
      setStep(1);
      loadProfile();
    } catch (err) {
      setFormError(err.message);
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
      {/* Account Overview Stats */}
      {profile && (
        <div className="dashboard-grid">
          <div className="stat-card">
            <div className="stat-label">Account &amp; Status</div>
            <div className="stat-value" style={{ fontSize: '1.1rem' }}>
              {profile.account_id}
            </div>
            <div className="stat-sub">
              {profile.customer_name} ·{' '}
              <strong style={{ color: '#00a859' }}>{profile.connection_status}</strong>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-label">Subscribed Plan ({profile.service_segment || serviceSegment})</div>
            <div className="stat-value" style={{ fontSize: '1.1rem' }}>
              {profile.subscribed_package.split('(')[0].trim()}
            </div>
            <div className="stat-sub">
              {profile.signal_metric_label || 'Optical Rx'}: {profile.signal_metric_value || `${profile.optical_rx_power_dbm} dBm`}
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-label">{profile.quota_label || 'Data Remaining'}</div>
            <div className="stat-value">
              {profile.data_remaining_gb} {profile.quota_unit || 'GB'}
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${dataPct}%` }} />
            </div>
            <div className="stat-sub">
              {dataPct}% of {profile.data_total_gb} {profile.quota_unit || 'GB'}
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-label">Current Bill &amp; Credit</div>
            <div className="stat-value">
              Rs. {Number(profile.current_balance_rs).toLocaleString()}
            </div>
            <div className="stat-sub">
              Due: {profile.bill_due_date} · Credit Limit:{' '}
              <strong>Rs. {Number(profile.credit_limit_rs || 15000).toLocaleString()}</strong>
            </div>
            <div className="stat-sub" style={{ color: '#00a859', fontWeight: 600 }}>
              Available Credit: Rs. {Number(profile.available_credit_rs || 0).toLocaleString()}
            </div>
          </div>
        </div>
      )}

      {/* Current & Previous Tickets Summary */}
      {profile && (
        <div className="panel-card">
          <h3>
            <Activity size={18} /> Your Support Tickets (Current &amp; Previous)
          </h3>

          <div style={{ marginBottom: '1.15rem' }}>
            <h4 style={{ fontSize: '0.84rem', color: '#0056a4', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
              Current Active Tickets ({profile.current_tickets?.length || 0})
            </h4>
            {profile.current_tickets?.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Ticket ID</th>
                    <th>Fault &amp; Service</th>
                    <th>Status</th>
                    <th>Assigned Officer</th>
                    <th>Priority / SLA</th>
                  </tr>
                </thead>
                <tbody>
                  {profile.current_tickets.map((t) => (
                    <tr
                      key={t.ticket_id}
                      onClick={() => setSelectedTicket(selectedTicket?.ticket_id === t.ticket_id ? null : t)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td><code>{t.ticket_id}</code></td>
                      <td>
                        <strong>{t.fault_category || 'General'}</strong>
                        <div style={{ fontSize: '0.78rem', color: '#64748b' }}>{t.service_type}</div>
                      </td>
                      <td><strong>{t.status}</strong></td>
                      <td>{t.assigned_officer || 'Pending'}</td>
                      <td>{t.priority}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p style={{ fontSize: '0.86rem', color: '#64748b' }}>
                You have no active fault tickets at the moment.
              </p>
            )}
          </div>

          <div>
            <h4 style={{ fontSize: '0.84rem', color: '#64748b', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
              Previous Resolved Tickets ({profile.previous_tickets?.length || 0})
            </h4>
            {profile.previous_tickets?.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Ticket ID</th>
                    <th>Fault &amp; Service</th>
                    <th>Status</th>
                    <th>Handled By</th>
                    <th>Summary</th>
                  </tr>
                </thead>
                <tbody>
                  {profile.previous_tickets.map((t) => (
                    <tr
                      key={t.ticket_id}
                      onClick={() => setSelectedTicket(selectedTicket?.ticket_id === t.ticket_id ? null : t)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td><code>{t.ticket_id}</code></td>
                      <td>{t.fault_category || 'General'} · {t.service_type}</td>
                      <td><strong style={{ color: '#00a859' }}>{t.status}</strong></td>
                      <td>{t.assigned_officer || 'SLT Ops'}</td>
                      <td>{t.issue_description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p style={{ fontSize: '0.86rem', color: '#64748b' }}>
                No previous resolved tickets found for this connection.
              </p>
            )}
          </div>

          {selectedTicket && (
            <div className="review-box" style={{ marginTop: '0.9rem' }}>
              <div className="review-header">
                <strong>Ticket Details: {selectedTicket.ticket_id}</strong>
                <span className="priority-pill normal">{selectedTicket.status}</span>
              </div>
              <div className="review-grid">
                <div>
                  <span className="review-label">Assigned Officer &amp; Division</span>
                  <div className="review-val">
                    <strong>{selectedTicket.assigned_officer || 'Queued'}</strong> · {selectedTicket.assigned_team}
                  </div>
                </div>
                <div>
                  <span className="review-label">SLA &amp; Visit Window</span>
                  <div className="review-val">
                    {selectedTicket.target_sla || 'Within 8 Hours'} · {selectedTicket.preferred_visit_slot || 'Anytime'}
                  </div>
                </div>
                <div style={{ gridColumn: '1 / -1' }}>
                  <span className="review-label">Description</span>
                  <div className="review-val">{selectedTicket.issue_description}</div>
                </div>
                {selectedTicket.officer_updates?.length > 0 && (
                  <div style={{ gridColumn: '1 / -1', marginTop: '0.4rem' }}>
                    <span className="review-label">Updates from Technical Officer</span>
                    <div className="timeline" style={{ marginTop: 6 }}>
                      {selectedTicket.officer_updates.map((upd, idx) => (
                        <div key={idx} className="timeline-item">
                          <div className="timeline-meta">
                            <strong>{upd.officer_name}</strong> · {upd.channel} · <code>{upd.status_change}</code>
                          </div>
                          {upd.message && <div className="timeline-msg">{upd.message}</div>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 3-Step Descriptive Fault Ticket Wizard */}
      <div className="panel-card">
        <h3>
          <Ticket size={18} /> Lodge a Detailed Service Fault Ticket
        </h3>

        {/* Stepper */}
        <div className="wizard-steps">
          <div className={`wizard-step ${step === 1 ? 'active' : step > 1 ? 'done' : ''}`}>
            <span className="step-num">1</span>
            <span>
              <Wrench size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
              Fault &amp; Diagnostics
            </span>
          </div>
          <div className={`wizard-step ${step === 2 ? 'active' : step > 2 ? 'done' : ''}`}>
            <span className="step-num">2</span>
            <span>
              <MapPin size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
              Description &amp; Visit Info
            </span>
          </div>
          <div className={`wizard-step ${step === 3 ? 'active' : ''}`}>
            <span className="step-num">3</span>
            <span>
              <ClipboardCheck size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
              Review &amp; Confirm
            </span>
          </div>
        </div>

        {formError && (
          <div className="alert-banner error">
            <AlertTriangle size={17} /> {formError}
          </div>
        )}

        {/* STEP 1: Diagnostics */}
        {step === 1 && (
          <div>
            <div className="form-grid">
              <div className="field">
                <label>1. Affected Service</label>
                <select value={serviceType} onChange={(e) => handleServiceChange(e.target.value)}>
                  <option value="Fibre">SLT Fibre Broadband (FTTH)</option>
                  <option value="4G LTE">Home Broadband (4G LTE)</option>
                  <option value="PEOTV">PEOTV</option>
                  <option value="Mobile">SLT Mobitel</option>
                  <option value="Copper Voice">Copper Voice / Megaline</option>
                </select>
              </div>
              <div className="field">
                <label>2. Fault Category</label>
                <select value={faultCategory} onChange={(e) => setFaultCategory(e.target.value)}>
                  {(FAULT_CATEGORIES[serviceType] || FAULT_CATEGORIES.Fibre).map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-grid">
              <div className="field">
                <label>3. Router / ONT LED Indicator Status</label>
                <select value={ledStatus} onChange={(e) => setLedStatus(e.target.value)}>
                  {LED_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>4. Service Impact Level</label>
                <select value={impactLevel} onChange={(e) => setImpactLevel(e.target.value)}>
                  <option value="Critical (Work / Business Halted)">Critical (Work / Business Halted)</option>
                  <option value="High (Household Outage)">High (Household Outage)</option>
                  <option value="Medium (Degraded Service)">Medium (Degraded Service)</option>
                  <option value="Low (Intermittent Issue)">Low (Intermittent Issue)</option>
                </select>
              </div>
            </div>

            <div className="form-grid">
              <div className="field">
                <label>5. Affected Devices</label>
                <select value={affectedDevices} onChange={(e) => setAffectedDevices(e.target.value)}>
                  <option value="All Devices (Wi-Fi & Ethernet)">All Devices (Wi-Fi &amp; Ethernet)</option>
                  <option value="Wi-Fi Devices Only">Wi-Fi Devices Only</option>
                  <option value="Single Device Only">Single Device Only</option>
                  <option value="PEOTV / Telephone Handset Only">PEOTV / Telephone Handset Only</option>
                </select>
              </div>
              <div className="field">
                <label>6. When Did the Issue Start?</label>
                <select value={issueStarted} onChange={(e) => setIssueStarted(e.target.value)}>
                  <option value="Just now (< 1 hour)">Just now (&lt; 1 hour)</option>
                  <option value="Today">Today</option>
                  <option value="1-2 days ago">1–2 days ago</option>
                  <option value="More than 2 days ago">More than 2 days ago</option>
                </select>
              </div>
            </div>

            <div className="precheck-box">
              <div className="precheck-title">Pre-Ticket Verification Checks</div>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={routerRestarted}
                  onChange={(e) => setRouterRestarted(e.target.checked)}
                />
                <span>I have already restarted the router / ONT and waited 2 minutes.</span>
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={cablesChecked}
                  onChange={(e) => setCablesChecked(e.target.checked)}
                />
                <span>I checked that power, fibre patch cord, and Ethernet cables are securely plugged in.</span>
              </label>
            </div>

            <div className="wizard-actions">
              <div />
              <button type="button" className="btn btn-primary" style={{ width: 'auto' }} onClick={goToStep2}>
                Next: Description &amp; Visit Info <ArrowRight size={16} />
              </button>
            </div>
          </div>
        )}

        {/* STEP 2: Description & Visit Details */}
        {step === 2 && (
          <div>
            <div className="field" style={{ marginBottom: '1rem' }}>
              <label>
                Detailed Fault Description *{' '}
                <span style={{ fontWeight: 400, color: '#64748b' }}>
                  ({issueDesc.trim().length} / 15 min chars)
                </span>
              </label>
              <textarea
                rows={4}
                value={issueDesc}
                onChange={(e) => setIssueDesc(e.target.value)}
                placeholder="Describe what happened (e.g., After heavy rain last night, the LOS LED on our Huawei Fibre router turned solid red and internet dropped completely across all rooms...)"
                required
              />
            </div>

            <div className="form-grid">
              <div className="field">
                <label>On-Site Contact Person *</label>
                <input
                  type="text"
                  value={contactName}
                  onChange={(e) => setContactName(e.target.value)}
                  placeholder="Subscriber or family member name"
                />
              </div>
              <div className="field">
                <label>Contact Mobile Number *</label>
                <input
                  type="text"
                  value={contactNum}
                  onChange={(e) => setContactNum(e.target.value)}
                  placeholder="071 234 5678"
                />
              </div>
            </div>

            <div className="form-grid">
              <div className="field">
                <label>Premises Address &amp; Nearest Landmark *</label>
                <input
                  type="text"
                  value={serviceAddress}
                  onChange={(e) => setServiceAddress(e.target.value)}
                  placeholder="House No, Street, City, Landmark"
                />
              </div>
              <div className="field">
                <label>Preferred Technician Visit Window</label>
                <select value={visitSlot} onChange={(e) => setVisitSlot(e.target.value)}>
                  <option value="Morning (08:00 - 12:00)">Morning (08:00 – 12:00)</option>
                  <option value="Afternoon (12:00 - 16:00)">Afternoon (12:00 – 16:00)</option>
                  <option value="Evening (16:00 - 19:00)">Evening (16:00 – 19:00)</option>
                  <option value="Anytime (08:00 - 18:00)">Anytime (08:00 – 18:00)</option>
                </select>
              </div>
            </div>

            <div className="wizard-actions">
              <button type="button" className="btn btn-outline" onClick={() => setStep(1)}>
                <ArrowLeft size={16} /> Back
              </button>
              <button type="button" className="btn btn-primary" style={{ width: 'auto' }} onClick={goToStep3}>
                Review Ticket Summary <ArrowRight size={16} />
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: Review & Confirm */}
        {step === 3 && (
          <div>
            <div className="review-box">
              <div className="review-header">
                <strong>Please review your fault ticket before submitting</strong>
                <span className={`priority-pill ${estimatedCritical ? 'high' : 'normal'}`}>
                  Est. Priority: {estimatedCritical ? 'CRITICAL / HIGH (4h SLA)' : 'NORMAL (8h SLA)'}
                </span>
              </div>

              <div className="review-grid">
                <div>
                  <span className="review-label">Account Number</span>
                  <div className="review-val"><code>{accountNumber || 'SLT-ACC-0112456789'}</code></div>
                </div>
                <div>
                  <span className="review-label">Service &amp; Fault</span>
                  <div className="review-val">{serviceType} — {faultCategory}</div>
                </div>
                <div>
                  <span className="review-label">Router / LED Status</span>
                  <div className="review-val">{ledStatus}</div>
                </div>
                <div>
                  <span className="review-label">Pre-Checks Completed</span>
                  <div className="review-val">
                    Restarted: {routerRestarted ? 'Yes' : 'No'} · Cables Checked: {cablesChecked ? 'Yes' : 'No'}
                  </div>
                </div>
                <div>
                  <span className="review-label">Impact &amp; Scope</span>
                  <div className="review-val">{impactLevel} · {affectedDevices} (Started: {issueStarted})</div>
                </div>
                <div>
                  <span className="review-label">On-Site Contact</span>
                  <div className="review-val">{contactName} ({contactNum})</div>
                </div>
                <div style={{ gridColumn: '1 / -1' }}>
                  <span className="review-label">Premises Address &amp; Visit Window</span>
                  <div className="review-val">{serviceAddress} · <strong>{visitSlot}</strong></div>
                </div>
                <div style={{ gridColumn: '1 / -1' }}>
                  <span className="review-label">Detailed Description</span>
                  <div className="review-val">{issueDesc}</div>
                </div>
              </div>
            </div>

            <div className="wizard-actions">
              <button type="button" className="btn btn-outline" onClick={() => setStep(2)}>
                <ArrowLeft size={16} /> Edit Details
              </button>
              <button
                type="button"
                className="btn btn-green"
                style={{ width: 'auto' }}
                onClick={handleSubmitTicket}
                disabled={submitting}
              >
                <CheckCircle2 size={16} /> {submitting ? 'Logging Ticket...' : 'Confirm & Lodge Fault Ticket'}
              </button>
            </div>
          </div>
        )}

        {ticketConfirmation && !ticketConfirmation.error && (
          <div className="alert-banner success" style={{ marginTop: '1.25rem', display: 'block' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <CheckCircle2 size={18} />
              <strong>Ticket Logged: {ticketConfirmation.ticket_id}</strong>
            </div>
            <MarkdownText text={ticketConfirmation.summary_markdown} />
          </div>
        )}
      </div>

      {/* Track Ticket Status & Recent Tickets */}
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
              <Activity size={14} style={{ verticalAlign: 'middle' }} /> Recent Account Tickets (Click a row to inspect full details)
            </h4>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ticket ID</th>
                  <th>Service &amp; Fault</th>
                  <th>LED Status</th>
                  <th>Status</th>
                  <th>Priority</th>
                </tr>
              </thead>
              <tbody>
                {profile.recent_tickets.map((t) => (
                  <tr
                    key={t.ticket_id}
                    onClick={() => setSelectedTicket(selectedTicket?.ticket_id === t.ticket_id ? null : t)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td><code>{t.ticket_id}</code></td>
                    <td>{t.service_type} · {t.fault_category || 'General'}</td>
                    <td>{t.led_status || 'N/A'}</td>
                    <td><strong>{t.status}</strong></td>
                    <td>{t.priority}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {selectedTicket && (
              <div className="review-box" style={{ marginTop: '0.85rem' }}>
                <div className="review-header">
                  <strong>Ticket Details: {selectedTicket.ticket_id}</strong>
                  <span className="priority-pill normal">{selectedTicket.status}</span>
                </div>
                <div className="review-grid">
                  <div>
                    <span className="review-label">Assigned Team</span>
                    <div className="review-val">{selectedTicket.assigned_team}</div>
                  </div>
                  <div>
                    <span className="review-label">SLA &amp; Visit Window</span>
                    <div className="review-val">
                      {selectedTicket.target_sla || 'Within 8 Hours'} · {selectedTicket.preferred_visit_slot || 'Anytime'}
                    </div>
                  </div>
                  <div style={{ gridColumn: '1 / -1' }}>
                    <span className="review-label">Premises &amp; Contact</span>
                    <div className="review-val">
                      {selectedTicket.service_address || 'Registered Address'} · {selectedTicket.contact_name || 'Subscriber'} ({selectedTicket.contact_number || 'N/A'})
                    </div>
                  </div>
                  <div style={{ gridColumn: '1 / -1' }}>
                    <span className="review-label">Description</span>
                    <div className="review-val">{selectedTicket.issue_description}</div>
                  </div>
                  {selectedTicket.officer_updates?.length > 0 && (
                    <div style={{ gridColumn: '1 / -1', marginTop: '0.5rem' }}>
                      <span className="review-label">Updates from Technical Officer</span>
                      <div className="timeline" style={{ marginTop: 6 }}>
                        {selectedTicket.officer_updates.map((upd, idx) => (
                          <div key={idx} className="timeline-item">
                            <div className="timeline-meta">
                              <strong>{upd.officer_name}</strong> · {upd.channel} · <code>{upd.status_change}</code>
                            </div>
                            {upd.message && <div className="timeline-msg">{upd.message}</div>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
