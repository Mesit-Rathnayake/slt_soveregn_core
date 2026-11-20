import React, { useState } from 'react';
import { MessageSquare, Ticket, Shield, LogOut, UserCheck, UserPlus, Wrench } from 'lucide-react';
import RoleGate from './components/RoleGate.jsx';
import ChatView from './components/ChatView.jsx';
import AccountTicketsView from './components/AccountTicketsView.jsx';

export default function App() {
  const [userRole, setUserRole] = useState(null); // null => show RoleGate screen first
  const [accountNumber, setAccountNumber] = useState('SLT-ACC-0112456789');
  const [activeTab, setActiveTab] = useState('chat');
  const [messages, setMessages] = useState([]);
  const [sessionMemory, setSessionMemory] = useState({});

  const handleSelectRole = (role, accNum) => {
    setUserRole(role);
    if (accNum) setAccountNumber(accNum);
    setActiveTab('chat');
    setMessages([]);
    setSessionMemory({});
  };

  if (!userRole) {
    return <RoleGate onSelectRole={handleSelectRole} />;
  }

  const canUseAccountPortal = userRole !== 'New Customer';
  const RoleIcon =
    userRole === 'Existing Customer'
      ? UserCheck
      : userRole === 'New Customer'
      ? UserPlus
      : Wrench;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-left">
          <Shield size={24} />
          <div>
            <div className="topbar-title">SLTMobitel AI Assistant</div>
            <div className="topbar-sub">
              {userRole === 'New Customer'
                ? 'Plans, Packages & General Inquiries'
                : 'Subscriber Self-Care, Fault Ticketing & Support'}
            </div>
          </div>
        </div>

        <nav className="topbar-nav">
          <button
            className={`nav-tab ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            <MessageSquare size={15} /> AI Assistant
          </button>

          {canUseAccountPortal && (
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
            <RoleIcon size={14} /> {userRole}
          </span>
          <button className="switch-role-btn" onClick={() => setUserRole(null)}>
            <LogOut size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
            Switch Role
          </button>
        </div>
      </header>

      <main className="main-content">
        {activeTab === 'chat' ? (
          <ChatView
            userRole={userRole}
            messages={messages}
            setMessages={setMessages}
            sessionMemory={sessionMemory}
            setSessionMemory={setSessionMemory}
          />
        ) : (
          <AccountTicketsView userRole={userRole} accountNumber={accountNumber} />
        )}
      </main>
    </div>
  );
}
