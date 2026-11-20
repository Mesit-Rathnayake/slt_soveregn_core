import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Mic,
  MicOff,
  Volume2,
  RotateCcw,
  Bot,
  User,
  ShieldCheck,
  Loader2,
} from 'lucide-react';
import MarkdownText from './MarkdownText.jsx';

const QUICK_PROMPTS = {
  'Existing Customer': [
    'Show my account status',
    'What Fibre packages are under Rs. 5,000?',
    'How do I restart or troubleshoot my router?',
    'How do I check my SLTMobitel data balance and USSD codes?',
  ],
  'New Customer': [
    'What Fibre packages are under Rs. 5,000?',
    'Show me packages with at least 500 Mbps',
    'What are the SLTMobitel 4G LTE Home Broadband and PEOTV packages and prices?',
    'How do I check my SLTMobitel data balance?',
  ],
  staff: [
    'What Fibre packages are under Rs. 5,000?',
    'INCIDENT TICKET: INC-2026-1042 | AFFECTED NODE: SLT-CORE-PE-CMB-01 (172.16.45.128). BGP-5-ADJCHANGE link flapped 7 times. Optical Rx Power measured at -21.4 dBm.',
    'How to see active packages',
    'Show my account status',
  ],
};

export default function ChatView({
  userRole,
  messages,
  setMessages,
  sessionMemory,
  setSessionMemory,
}) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [playingIdx, setPlayingIdx] = useState(null);
  const bottomRef = useRef(null);
  const recognitionRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const prompts = QUICK_PROMPTS[userRole] || QUICK_PROMPTS.staff;

  const sendMessage = async (textOverride) => {
    const query = (textOverride ?? input).trim();
    if (!query || loading) return;

    setInput('');
    setLoading(true);

    const historyPayload = messages.map((m) => ({
      user_input: m.user_input,
      agent_response: m.agent_response,
    }));

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_input: query,
          user_role: userRole,
          conversation_history: historyPayload,
          session_memory: sessionMemory,
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `Server error (${resp.status})`);
      }
      const data = await resp.json();
      setMessages((prev) => [...prev, { user_input: query, agent_response: data }]);
      if (data.session_memory) {
        setSessionMemory(data.session_memory);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          user_input: query,
          agent_response: {
            answer_markdown: `Could not reach the backend server: \`${err.message}\`. Make sure the FastAPI server is running on port 8000.`,
            key_points: [],
            redactions_applied: 0,
            mcp_tool_called: 'error',
            latency_ms: 0,
          },
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const toggleVoiceInput = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Your browser does not support Web Speech API voice input. Try Chrome or Edge.');
      return;
    }

    if (recording && recognitionRef.current) {
      recognitionRef.current.stop();
      setRecording(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setRecording(false);
      sendMessage(transcript);
    };
    recognition.onerror = () => setRecording(false);
    recognition.onend = () => setRecording(false);
    recognitionRef.current = recognition;
    setRecording(true);
    recognition.start();
  };

  const playVoice = async (text, idx) => {
    if (!text) return;
    setPlayingIdx(idx);
    try {
      const resp = await fetch('/api/voice/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (resp.ok) {
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.onended = () => setPlayingIdx(null);
        await audio.play();
        return;
      }
    } catch {
      // Fall back to browser SpeechSynthesis
    }
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(text);
      utter.onend = () => setPlayingIdx(null);
      window.speechSynthesis.speak(utter);
    } else {
      setPlayingIdx(null);
    }
  };

  const resetChat = () => {
    setMessages([]);
    setSessionMemory({});
  };

  return (
    <div className="chat-wrapper">
      <div className="chat-toolbar">
        <div>
          <strong>SLTMobitel AI Assistant</strong>{' '}
          <span style={{ color: '#64748b' }}>· 24/7 Customer Support</span>
        </div>
        <button className="btn btn-ghost" onClick={resetChat}>
          <RotateCcw size={14} /> New Chat
        </button>
      </div>

      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="empty-state">
            <h3>How can I help you today?</h3>
            <p>
              {userRole === 'New Customer'
                ? 'Explore Fibre, 4G LTE, and PEOTV packages, filter by budget or speed, or ask about SLTMobitel services.'
                : 'Ask about packages, check your account overview, troubleshoot your router, or log a fault ticket.'}
            </p>
            <div className="quick-grid">
              {prompts.map((p, idx) => (
                <button key={idx} className="quick-chip" onClick={() => sendMessage(p)}>
                  {p}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((turn, idx) => {
            const res = turn.agent_response;
            return (
              <React.Fragment key={idx}>
                <div className="msg-row user">
                  <div className="avatar user">
                    <User size={16} />
                  </div>
                  <div className="bubble user">{turn.user_input}</div>
                </div>

                <div className="msg-row assistant">
                  <div className="avatar assistant">
                    <Bot size={16} />
                  </div>
                  <div className="bubble assistant">
                    {res.redactions_applied > 0 && (
                      <div className="privacy-pill">
                        <ShieldCheck size={13} /> Protected {res.redactions_applied} sensitive field(s)
                      </div>
                    )}

                    <MarkdownText text={res.answer_markdown} />

                    {res.key_points && res.key_points.length > 0 && res.has_enough_knowledge !== false && (
                      <ul className="key-points">
                        {res.key_points.map((kp, kIdx) => (
                          <li key={kIdx}>
                            <MarkdownText text={kp} />
                          </li>
                        ))}
                      </ul>
                    )}

                    {res.spoken_response && (
                      <div className="msg-meta" style={{ justifyContent: 'flex-end' }}>
                        <button
                          className="btn btn-ghost"
                          style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                          onClick={() => playVoice(res.spoken_response, idx)}
                        >
                          <Volume2 size={13} /> {playingIdx === idx ? 'Playing...' : 'Listen'}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </React.Fragment>
            );
          })
        )}

        {loading && (
          <div className="msg-row assistant">
            <div className="avatar assistant">
              <Loader2 size={16} className="spin" />
            </div>
            <div className="bubble assistant" style={{ color: '#64748b' }}>
              Thinking...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        className="chat-input-bar"
        onSubmit={(e) => {
          e.preventDefault();
          sendMessage();
        }}
      >
        <button
          type="button"
          className={`icon-btn ${recording ? 'recording' : ''}`}
          title="Voice Input"
          onClick={toggleVoiceInput}
        >
          {recording ? <MicOff size={18} /> : <Mic size={18} />}
        </button>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            recording
              ? 'Listening... speak now'
              : 'Ask about packages, router issues, or fault tickets...'
          }
          disabled={loading}
        />
        <button type="submit" className="icon-btn send" disabled={loading || !input.trim()}>
          <Send size={18} />
        </button>
      </form>
    </div>
  );
}
