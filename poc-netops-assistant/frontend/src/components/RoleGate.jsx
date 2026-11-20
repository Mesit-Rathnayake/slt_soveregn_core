import React, { useState } from 'react';
import { UserCheck, UserPlus, CheckCircle2, Lock, Shield, ArrowRight } from 'lucide-react';

export default function RoleGate({ onSelectRole }) {
  const [accountNumber, setAccountNumber] = useState('SLT-ACC-0112456789');

  return (
    <div className="gate-container">
      <div className="gate-header">
        <div className="brand-pill">
          <Shield size={14} /> SLTMobitel Sovereign AI Platform
        </div>
        <h1>Welcome to SLTMobitel Support</h1>
        <p>
          Choose your access profile to continue. Existing subscribers get fault ticketing and
          account self-care; new visitors get a streamlined product & package assistant.
        </p>
      </div>

      <div className="gate-cards">
        {/* Existing Customer Card */}
        <div className="role-card subscriber">
          <div>
            <div className="role-icon-box green">
              <UserCheck size={24} />
            </div>
            <h2>Existing Customer</h2>
            <p className="role-desc">
              For current SLTMobitel Fibre, 4G LTE, PEOTV, and Mobile subscribers.
            </p>
            <ul className="feature-list">
              <li>
                <CheckCircle2 size={16} className="ok" /> AI Assistant & Package Recommendations
              </li>
              <li>
                <CheckCircle2 size={16} className="ok" /> Log & Track Fault Tickets (1212 SLA)
              </li>
              <li>
                <CheckCircle2 size={16} className="ok" /> View Account Profile, Data & Billing Stats
              </li>
            </ul>
            <div className="account-input-group">
              <label htmlFor="acc-input">Account / Telephone Number (Demo Stub)</label>
              <input
                id="acc-input"
                type="text"
                value={accountNumber}
                onChange={(e) => setAccountNumber(e.target.value)}
                placeholder="SLT-ACC-0112456789"
              />
            </div>
          </div>
          <button
            className="btn btn-green"
            onClick={() => onSelectRole('Existing Customer', accountNumber || 'SLT-ACC-0112456789')}
          >
            Continue as Existing Customer <ArrowRight size={16} />
          </button>
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
                <CheckCircle2 size={16} className="ok" /> AI Assistant for Plans, Pricing & USSD
              </li>
              <li>
                <CheckCircle2 size={16} className="ok" /> Filter Packages by Budget & Speed
              </li>
              <li>
                <Lock size={16} className="locked" /> Fault Ticketing & Account Stats (Subscribers Only)
              </li>
            </ul>
          </div>
          <button
            className="btn btn-primary"
            onClick={() => onSelectRole('New Customer', '')}
          >
            Continue as New Customer <ArrowRight size={16} />
          </button>
        </div>
      </div>

      <div className="staff-bar">
        <span>Internal Operations / NOC Access:</span>
        <button
          className="btn btn-ghost"
          onClick={() => onSelectRole('Tier-1 NOC / Support Agent', 'SLT-ACC-0112456789')}
        >
          Tier-1 NOC Agent
        </button>
        <button
          className="btn btn-ghost"
          onClick={() => onSelectRole('Tier-2 Core Engineer', 'SLT-ACC-0112456789')}
        >
          Tier-2 Core Engineer
        </button>
        <button
          className="btn btn-ghost"
          onClick={() => onSelectRole('Sovereign Cloud Auditor', 'SLT-ACC-0112456789')}
        >
          Cloud Auditor
        </button>
      </div>
    </div>
  );
}
