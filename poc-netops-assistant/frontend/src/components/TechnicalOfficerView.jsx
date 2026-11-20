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
} from 'lucide-react';

const STATUS_OPTIONS = ['LOGGED', 'IN_PROGRESS', 'CONTACTED_CUSTOMER', 'RESOLVED'];

const QUICK_MESSAGES = [
  'We received your fault ticket and confirmed your visit window. Our field technician will call 30 minutes prior to arrival.',
  'Optical line fault verified on our end. A Fibre maintenance team has been dispatched to your area.',
  'We have resolved the issue and verified stable signal levels. Please restart your router and confirm connectivity.',
];

export default function TechnicalOfficerView({ userRole, defaultOfficerName = 'Eng. Nimal Silva' }) {
  const [tickets, setTickets] = useState([]);
  const [statusFilter, setStatusFilter] = useState('ALL');
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

  const loadTickets = async (filterVal = statusFilter) => {
    setLoading(true);
    setError('');
    try {
      const qs = filterVal && filterVal !== 'ALL' ? `?status=${encodeURIComponent(filterVal)}` : '';
      const resp = await fetch(`/api/officer/tickets${qs}`, {
        headers: { 'X-User-Role': userRole },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || 'Unable to load fault ticket queue.');
      }
      const data = await resp.json();
      setTickets(data.tickets || []);
      if (data.tickets?.length > 0 && !selectedId) {
        setSelectedId(data.tickets[0].ticket_id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTickets(statusFilter);
  }, [statusFilter, userRole]);

  const selectedTicket = tickets.find((t) => t.ticket_id === selectedId) || tickets[0] || null;

  useEffect(() => {
    if (selectedTicket) {
      setNewStatus(selectedTicket.status === 'LOGGED' ? 'CONTACTED_CUSTOMER' : selectedTicket.status);
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
          officer_name: officerName.trim() || 'Technical Officer',
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
      await loadTickets(statusFilter);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const openCount = tickets.filter((t) => t.status !== 'RESOLVED').length;
  const criticalCount = tickets.filter((t) => (t.priority || '').includes('CRITICAL') && t.status !== 'RESOLVED').length;
  const resolvedCount = tickets.filter((t) => t.status === 'RESOLVED').length;

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
          <div className="stat-label">Total Tickets</div>
          <div className="stat-value">{tickets.length}</div>
          <div className="stat-sub">Filtered Queue View</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Open / Active</div>
          <div className="stat-value" style={{ color: '#0056a4' }}>{openCount}</div>
          <div className="stat-sub">Awaiting field or remote resolution</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Critical / High Priority</div>
          <div className="stat-value" style={{ color: '#dc2626' }}>{criticalCount}</div>
          <div className="stat-sub">4-Hour SLA Target</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Resolved</div>
          <div className="stat-value" style={{ color: '#00a859' }}>{resolvedCount}</div>
          <div className="stat-sub">Closed &amp; Verified</div>
        </div>
      </div>

      {/* Filter & Queue Table */}
      <div className="panel-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: '1rem' }}>
          <h3 style={{ margin: 0 }}>
            <ClipboardList size={18} /> Customer Fault Ticket Queue
          </h3>
          <div className="filter-pills">
            {['ALL', ...STATUS_OPTIONS].map((st) => (
              <button
                key={st}
                className={`filter-pill ${statusFilter === st ? 'active' : ''}`}
                onClick={() => setStatusFilter(st)}
              >
                {st.replace('_', ' ')}
              </button>
            ))}
            <button className="btn btn-ghost" onClick={() => loadTickets(statusFilter)} title="Refresh Queue">
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
                <input
                  type="text"
                  value={officerName}
                  onChange={(e) => setOfficerName(e.target.value)}
                  required
                />
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
                placeholder="e.g., Called customer on 077 891 2345. Confirmed Fibre LOS red light; field team dispatched for Morning 08:00-12:00 window."
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
