import React, { useState } from 'react';
import {
  MessageSquare,
  Ticket,
  ClipboardList,
  Shield,
  LogOut,
  UserCheck,
  UserPlus,
  Wrench,
} from 'lucide-react';
import RoleGate from './components/RoleGate.jsx';
import ChatView from './components/ChatView.jsx';
import AccountTicketsView from './components/AccountTicketsView.jsx';
import TechnicalOfficerView from './components/TechnicalOfficerView.jsx';

export default function App() {
  const [userRole, setUserRole] = useState(null); // null => show RoleGate screen first
  const [accountNumber, setAccountNumber] = useState('SLT-ACC-0112456789');
  const [serviceSegment, setServiceSegment] = useState('Fibre');
  const [officerName, setOfficerName] = useState('Eng. Nimal Silva');
  const [authToken, setAuthToken] = useState('');
  const [activeTab, setActiveTab] = useState('chat');
  const [messages, setMessages] = useState([]);
  const [sessionMemory, setSessionMemory] = useState({});

  const isOfficerRole = (role) =>
    role === 'Technical Officer' ||
    role === 'Tier-1 NOC / Support Agent' ||
    role === 'Tier-2 Core Engineer';

  const handleSelectRole = (role, idVal, segment, staffName, token = '') => {
    setUserRole(role);
    setAuthToken(token || '');
    if (role === 'Existing Customer' && idVal) setAccountNumber(idVal);
    if (staffName) setOfficerName(staffName);
    setServiceSegment(segment || 'Fibre');
    if (role === 'Technical Officer') {
      setActiveTab('officer');
    } else if (role === 'Existing Customer') {
      setActiveTab('account');
    } else {
      setActiveTab('chat');
    }
    setMessages([]);
    setSessionMemory({});
  };

  if (!userRole) {
    return <RoleGate onSelectRole={handleSelectRole} />;
  }

  const canUseAccountPortal = userRole !== 'New Customer';
  const canManageTickets = isOfficerRole(userRole);
  const canUseAgent = userRole !== 'Technical Officer';
  const RoleIcon =
    userRole === 'Existing Customer'
      ? UserCheck
      : userRole === 'New Customer'
      ? UserPlus
      : Wrench;

  return (
    <div className="app-shell">
      <div className="slt-utility-bar">
        <div className="slt-utility-links">
          <span>Personal</span>
          <span>Business</span>
          <span>MySLT Portal</span>
        </div>
        <span>Hotline: 1212 (Fibre / Broadband / PEOTV) · 1717 (SLT Mobitel)</span>
      </div>

      <header className="topbar">
        <div className="topbar-left">
          <div className="slt-wordmark">
            <span className="slt-logo-icon">SLT</span>
            <span>
              SLT<span className="mobitel-text">MOBITEL</span>
            </span>
          </div>
          <div className="topbar-sub" style={{ borderLeft: '1px solid #e2e8f0', paddingLeft: 10 }}>
            {userRole === 'New Customer'
              ? 'Plans & Packages'
              : userRole === 'Technical Officer'
              ? 'Technical Officer Console'
              : 'MySLT Care'}
          </div>
        </div>

        <nav className="topbar-nav">
          {canManageTickets && (
            <button
              className={`nav-tab ${activeTab === 'officer' ? 'active' : ''}`}
              onClick={() => setActiveTab('officer')}
            >
              <ClipboardList size={15} /> Ticket Review Queue
            </button>
          )}

          {canUseAgent && (
            <button
              className={`nav-tab ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => setActiveTab('chat')}
            >
              <MessageSquare size={15} /> AI Assistant
            </button>
          )}

          {canUseAccountPortal && userRole !== 'Technical Officer' && (
            <button
              className={`nav-tab ${activeTab === 'account' ? 'active' : ''}`}
              onClick={() => setActiveTab('account')}
            >
              <Ticket size={15} /> My Account &amp; Fault Tickets
            </button>
          )}
        </nav>

        <div className="topbar-right">
          <span className="role-badge">
            <RoleIcon size={14} />{' '}
            {userRole === 'Existing Customer'
              ? `${serviceSegment === 'Mobile' ? 'SLT Mobitel' : serviceSegment} Customer`
              : userRole === 'Technical Officer'
              ? `${officerName} · Technical Officer`
              : userRole}
          </span>
          <button className="switch-role-btn" onClick={() => setUserRole(null)}>
            <LogOut size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
            Switch Role
          </button>
        </div>
      </header>

      <main className="main-content">
        {activeTab === 'officer' && canManageTickets ? (
          <TechnicalOfficerView userRole={userRole} defaultOfficerName={officerName} authToken={authToken} />
        ) : activeTab === 'account' && canUseAccountPortal ? (
          <AccountTicketsView
            userRole={userRole}
            accountNumber={accountNumber}
            serviceSegment={serviceSegment}
            authToken={authToken}
          />
        ) : (
          <ChatView
            userRole={userRole}
            serviceSegment={serviceSegment}
            authToken={authToken}
            messages={messages}
            setMessages={setMessages}
            sessionMemory={sessionMemory}
            setSessionMemory={setSessionMemory}
          />
        )}
      </main>

      <footer className="slt-footer">
        © SLTMobitel · Sri Lanka Telecom PLC · 24/7 Support: 1212 / 1717
      </footer>
    </div>
  );
}
