import React, { useState, useEffect } from 'react';
import {
  PhoneCall,
  Send,
  RefreshCw,
  ClipboardList,
  MapPin,
  Wrench,
  Clock,
  CheckCircle2,
  AlertTriangle,
  MessageCircle,
  Users,
} from 'lucide-react';

const STATUS_OPTIONS = ['IN_PROGRESS', 'CONTACTED_CUSTOMER', 'QUEUED', 'RESOLVED'];

const QUICK_MESSAGES = [
  'We received your fault ticket and confirmed your visit window. Our field technician will call 30 minutes prior to arrival.',
  'Optical line fault verified on our end. A Fibre maintenance team has been dispatched to your area.',
  'We have resolved the issue and verified stable signal levels. Please restart your router and confirm connectivity.',
];

export default function TechnicalOfficerView({ userRole, defaultOfficerName = 'Eng. Nimal Silva' }) {
  const [tickets, setTickets] = useState([]);
  const [workloads, setWorkloads] = useState(null);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [officerFilter, setOfficerFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState(null);

  // Officer Action Form
  const [officerName, setOfficerName] = useState(defaultOfficerName);
  const [newStatus, setNewStatus] = useState('CONTACTED_CUSTOMER');
  const [channel, setChannel] = useState('Phone Call');
  const [customerMessage, setCustomerMessage] = useState('');
  const [internalNote, setInternalNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveBanner, setSaveBanner] = useState('');

  const loadTickets = async (filterVal = statusFilter, offVal = officerFilter) => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (filterVal && filterVal !== 'ALL') params.set('status', filterVal);
      if (offVal && offVal !== 'ALL') params.set('officer', offVal);
      const qs = params.toString() ? `?${params.toString()}` : '';

      const resp = await fetch(`/api/officer/tickets${qs}`, {
        headers: { 'X-User-Role': userRole },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || 'Unable to load fault ticket queue.');
      }
      const data = await resp.json();
      setTickets(data.tickets || []);
      if (data.workloads) setWorkloads(data.workloads);
      if (data.tickets?.length > 0 && !data.tickets.some((t) => t.ticket_id === selectedId)) {
        setSelectedId(data.tickets[0].ticket_id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTickets(statusFilter, officerFilter);
  }, [statusFilter, officerFilter, userRole]);

  const selectedTicket = tickets.find((t) => t.ticket_id === selectedId) || tickets[0] || null;

  useEffect(() => {
    if (selectedTicket) {
      setNewStatus(selectedTicket.status === 'QUEUED' ? 'IN_PROGRESS' : selectedTicket.status);
      if (
        selectedTicket.assigned_officer &&
        !selectedTicket.assigned_officer.toLowerCase().includes('queued') &&
        selectedTicket.assigned_officer !== 'Unassigned'
      ) {
        setOfficerName(selectedTicket.assigned_officer);
      } else {
        setOfficerName(defaultOfficerName);
      }
    }
  }, [selectedTicket?.ticket_id]);

  const handleUpdate = async (e) => {
    e.preventDefault();
    if (!selectedTicket) return;
    setSaving(true);
    setSaveBanner('');
    setError('');
    try {
      const resp = await fetch(`/api/officer/tickets/${encodeURIComponent(selectedTicket.ticket_id)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: newStatus,
          officer_name: officerName.trim() || defaultOfficerName,
          contact_channel: channel,
          customer_message: customerMessage.trim(),
          internal_note: internalNote.trim(),
          user_role: userRole,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || 'Failed to update ticket.');
      }
      setSaveBanner(`Ticket ${selectedTicket.ticket_id} updated (${newStatus}) and customer contact logged.`);
      setCustomerMessage('');
      setInternalNote('');
      await loadTickets(statusFilter, officerFilter);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const openCount = tickets.filter((t) => t.status !== 'RESOLVED').length;
  const criticalCount = tickets.filter((t) => (t.priority || '').includes('CRITICAL') && t.status !== 'RESOLVED').length;
  const queuedCount = workloads?.queued_tickets_count ?? tickets.filter((t) => t.status === 'QUEUED').length;
  const officerRoster = workloads?.officers || [];

  return (
    <div>
      {error && (
        <div className="alert-banner error">
          <AlertTriangle size={18} /> {error}
        </div>
      )}

      {/* Officer Queue KPIs */}
      <div className="dashboard-grid">
        <div className="stat-card">
          <div className="stat-label">Active Tickets</div>
          <div className="stat-value" style={{ color: '#0056a4' }}>{openCount}</div>
          <div className="stat-sub">Total Shown: {tickets.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Critical / High Priority</div>
          <div className="stat-value" style={{ color: '#dc2626' }}>{criticalCount}</div>
          <div className="stat-sub">4-Hour SLA Target</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Queued (Waiting Capacity)</div>
          <div className="stat-value" style={{ color: queuedCount > 0 ? '#d97706' : '#00a859' }}>
            {queuedCount}
          </div>
          <div className="stat-sub">Auto-assigned when officer frees up</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Max In-Progress Limit</div>
          <div className="stat-value">{workloads?.max_in_progress_per_officer ?? 2} / Officer</div>
          <div className="stat-sub">Least-Loaded Round-Robin</div>
        </div>
      </div>

      {/* Technical Officer Workload & Capacity Monitor */}
      {officerRoster.length > 0 && (
        <div className="panel-card">
          <h3>
            <Users size={18} /> Technical Officer Workload &amp; Round-Robin Capacity
          </h3>
          <div className="dashboard-grid" style={{ marginBottom: 0 }}>
            {officerRoster.map((o) => {
              const pct = Math.min(100, Math.round((o.in_progress_count / o.max_in_progress) * 100));
              return (
                <div
                  key={o.officer_id}
                  className="stat-card"
                  style={{
                    boxShadow: 'none',
                    borderColor: o.at_capacity ? '#fca5a5' : '#e2e8f0',
                    background: o.at_capacity ? '#fef2f2' : '#f8fafc',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                    <strong style={{ fontSize: '0.88rem' }}>{o.name}</strong>
                    <span className={`priority-pill ${o.at_capacity ? 'high' : 'normal'}`}>
                      {o.in_progress_count} / {o.max_in_progress}
                    </span>
                  </div>
                  <div className="stat-sub">{o.division}</div>
                  <div className="progress-track">
                    <div
                      className="progress-fill"
                      style={{
                        width: `${pct}%`,
                        background: o.at_capacity ? '#dc2626' : undefined,
                      }}
                    />
                  </div>
                  <div className="stat-sub" style={{ marginTop: 6 }}>
                    {o.at_capacity ? 'At Max Capacity' : 'Available for Next Assignment'} · Resolved: {o.resolved_count}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Filter & Queue Table */}
      <div className="panel-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: '1rem' }}>
          <h3 style={{ margin: 0 }}>
            <ClipboardList size={18} /> Customer Fault Ticket Queue
          </h3>
          <div className="filter-pills">
            <select
              value={officerFilter}
              onChange={(e) => setOfficerFilter(e.target.value)}
              style={{
                padding: '5px 10px',
                borderRadius: 999,
                border: '1px solid #cbd5e1',
                fontSize: '0.78rem',
                fontWeight: 600,
              }}
            >
              <option value="ALL">All Officers</option>
              <option value={defaultOfficerName}>My Assigned ({defaultOfficerName})</option>
              {officerRoster
                .filter((o) => o.name !== defaultOfficerName)
                .map((o) => (
                  <option key={o.officer_id} value={o.name}>
                    {o.name}
                  </option>
                ))}
            </select>

            {['ALL', ...STATUS_OPTIONS].map((st) => (
              <button
                key={st}
                className={`filter-pill ${statusFilter === st ? 'active' : ''}`}
                onClick={() => setStatusFilter(st)}
              >
                {st.replace('_', ' ')}
              </button>
            ))}
            <button className="btn btn-ghost" onClick={() => loadTickets(statusFilter, officerFilter)} title="Refresh Queue">
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {loading ? (
          <p style={{ color: '#64748b' }}>Loading fault tickets...</p>
        ) : tickets.length === 0 ? (
          <p style={{ color: '#64748b' }}>No fault tickets match this filter.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Ticket ID</th>
                <th>Customer &amp; Contact</th>
                <th>Service &amp; Fault</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Assigned Officer</th>
              </tr>
            </thead>
            <tbody>
              {tickets.map((t) => {
                const isSelected = selectedTicket?.ticket_id === t.ticket_id;
                const isCrit = (t.priority || '').includes('CRITICAL');
                return (
                  <tr
                    key={t.ticket_id}
                    onClick={() => {
                      setSelectedId(t.ticket_id);
                      setSaveBanner('');
                    }}
                    style={{
                      cursor: 'pointer',
                      background: isSelected ? '#eff6ff' : undefined,
                    }}
                  >
                    <td><code>{t.ticket_id}</code></td>
                    <td>
                      <strong>{t.contact_name || 'Subscriber'}</strong>
                      <div style={{ fontSize: '0.78rem', color: '#64748b' }}>{t.contact_number}</div>
                    </td>
                    <td>
                      {t.service_type}
                      <div style={{ fontSize: '0.78rem', color: '#64748b' }}>{t.fault_category}</div>
                    </td>
                    <td>
                      <span className={`priority-pill ${isCrit ? 'high' : 'normal'}`}>
                        {isCrit ? 'CRITICAL' : 'NORMAL'}
                      </span>
                    </td>
                    <td><strong>{t.status}</strong></td>
                    <td>{t.assigned_officer || 'Unassigned'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Selected Ticket Review & Customer Contact Console */}
      {selectedTicket && (
        <div className="panel-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: '1rem' }}>
            <h3 style={{ margin: 0 }}>
              <Wrench size={18} /> Review Ticket: <code>{selectedTicket.ticket_id}</code>
            </h3>
            <a
              href={`tel:${(selectedTicket.contact_number || '').replace(/\s+/g, '')}`}
              className="btn btn-green"
              style={{ width: 'auto', textDecoration: 'none' }}
            >
              <PhoneCall size={15} /> Call {selectedTicket.contact_name} ({selectedTicket.contact_number})
            </a>
          </div>

          <div className="review-box" style={{ marginBottom: '1.25rem' }}>
            <div className="review-grid">
              <div>
                <span className="review-label">Account &amp; Customer</span>
                <div className="review-val">
                  <code>{selectedTicket.account_id}</code> · {selectedTicket.contact_name}
                </div>
              </div>
              <div>
                <span className="review-label">Service &amp; Fault Category</span>
                <div className="review-val">{selectedTicket.service_type} — {selectedTicket.fault_category}</div>
              </div>
              <div>
                <span className="review-label">Router / LED Diagnostics</span>
                <div className="review-val">
                  {selectedTicket.led_status || 'N/A'} · Restarted: {selectedTicket.router_restarted ? 'Yes' : 'No'}
                </div>
              </div>
              <div>
                <span className="review-label">Impact &amp; Affected Devices</span>
                <div className="review-val">
                  {selectedTicket.impact_level || 'Standard'} · {selectedTicket.affected_devices || 'All Devices'}
                </div>
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <span className="review-label">
                  <MapPin size={12} style={{ verticalAlign: 'middle' }} /> Premises Address &amp; Preferred Visit Window
                </span>
                <div className="review-val">
                  {selectedTicket.service_address || 'Registered Premises'} ·{' '}
                  <strong>{selectedTicket.preferred_visit_slot || 'Anytime'}</strong>
                </div>
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <span className="review-label">Customer Description</span>
                <div className="review-val">{selectedTicket.issue_description}</div>
              </div>
            </div>
          </div>

          {saveBanner && (
            <div className="alert-banner success">
              <CheckCircle2 size={17} /> {saveBanner}
            </div>
          )}

          {/* Update Status & Contact Customer Form */}
          <form onSubmit={handleUpdate}>
            <h4 style={{ fontSize: '0.92rem', color: '#003d75', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: 6 }}>
              <MessageCircle size={16} /> Update Status &amp; Contact Customer
            </h4>

            <div className="form-grid">
              <div className="field">
                <label>Assigned Technical Officer</label>
                <select value={officerName} onChange={(e) => setOfficerName(e.target.value)}>
                  {officerRoster.length > 0 ? (
                    officerRoster.map((o) => (
                      <option key={o.officer_id} value={o.name}>
                        {o.name} ({o.in_progress_count}/{o.max_in_progress})
                      </option>
                    ))
                  ) : (
                    <option value={defaultOfficerName}>{defaultOfficerName}</option>
                  )}
                </select>
              </div>
              <div className="field">
                <label>Ticket Status</label>
                <select value={newStatus} onChange={(e) => setNewStatus(e.target.value)}>
                  {STATUS_OPTIONS.map((st) => (
                    <option key={st} value={st}>{st.replace('_', ' ')}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Customer Contact Method</label>
                <select value={channel} onChange={(e) => setChannel(e.target.value)}>
                  <option value="Phone Call">Phone Call</option>
                  <option value="SMS Notification">SMS Notification</option>
                  <option value="Portal Message">Portal Message</option>
                  <option value="Field Visit Scheduled">Field Visit Scheduled</option>
                </select>
              </div>
            </div>

            <div style={{ marginBottom: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {QUICK_MESSAGES.map((tpl, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="btn btn-outline"
                  style={{ fontSize: '0.76rem', padding: '5px 10px' }}
                  onClick={() => setCustomerMessage(tpl)}
                >
                  Template #{idx + 1}
                </button>
              ))}
            </div>

            <div className="field" style={{ marginBottom: '0.85rem' }}>
              <label>Message / Update Sent to Customer (Visible in Customer Portal)</label>
              <textarea
                rows={3}
                value={customerMessage}
                onChange={(e) => setCustomerMessage(e.target.value)}
                placeholder="e.g., Called customer. Confirmed Fibre LOS red light; field team dispatched for Morning 08:00-12:00 window."
              />
            </div>

            <div className="field" style={{ marginBottom: '1rem' }}>
              <label>Internal Engineering Note (Staff Only)</label>
              <input
                type="text"
                value={internalNote}
                onChange={(e) => setInternalNote(e.target.value)}
                placeholder="e.g., Check splitter port 4 at Havelock Road DP box; bring spare SC/APC patch cord"
              />
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: 'auto' }} disabled={saving}>
              <Send size={15} /> {saving ? 'Saving Update...' : 'Save Update & Notify Customer'}
            </button>
          </form>

          {/* Contact & Activity Timeline */}
          {selectedTicket.officer_updates?.length > 0 && (
            <div style={{ marginTop: '1.4rem' }}>
              <h4 style={{ fontSize: '0.88rem', color: '#64748b', marginBottom: '0.6rem', display: 'flex', alignItems: 'center', gap: 6 }}>
                <Clock size={14} /> Officer Contact &amp; Activity Log
              </h4>
              <div className="timeline">
                {selectedTicket.officer_updates.map((upd, idx) => (
                  <div key={idx} className="timeline-item">
                    <div className="timeline-meta">
                      <strong>{upd.officer_name}</strong> · <span>{upd.channel}</span> ·{' '}
                      <code>{upd.status_change}</code> · <span>{upd.timestamp}</span>
                    </div>
                    {upd.message && <div className="timeline-msg">{upd.message}</div>}
                    {upd.internal_note && (
                      <div className="timeline-note">Internal Note: {upd.internal_note}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
