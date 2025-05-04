import React, { useEffect, useRef, useState } from 'react';
import './Conversation.css';
import Avatar from "./Avatar";

export default function Conversation({ currentUser, peerUser, conversations, setConversations }) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef();

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: peerUser ? 'auto' : 'smooth' });
    }
  }, [conversations]);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'auto' });
    }
  }, [peerUser]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || !peerUser) return;
    // --- USE TOR BACKEND ---
    const res = await fetch('/api/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sender: currentUser.username, recipient: peerUser.username, message: input })
    });
    const data = await res.json();
    if (data.success) {
      // Optionally, fetch updated conversations after sending
      fetch(`/api/messages?username=${encodeURIComponent(currentUser.username)}`)
        .then(r => r.json())
        .then(data => {
          setConversations(data.conversations || []);
          setInput('');
        });
    }
  };

  const filtered = peerUser ? conversations.filter(
    m => (m.from === currentUser.username && m.to === peerUser.username) ||
         (m.from === peerUser.username && m.to === currentUser.username)
  ) : [];

  return (
    <div className="conversation">
      <div className="messages">
        {filtered.map((msg, idx) => (
          <div
            key={idx}
            className={
              "message-row" + (msg.from === currentUser.username ? " self" : "")
            }
          >
            <Avatar username={msg.from} />
            <div className="message-bubble">
              <div className="message-text">{msg.text}</div>
              <div className="message-meta">
                <span className="message-time">{msg.timestamp && new Date(msg.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                {msg.from === currentUser.username && (
                  <span className="delivery-status">
                    {msg.read ? "Read" : msg.delivered ? "Delivered" : "Sent"}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      {peerUser && (
        <form className="input-bar" onSubmit={handleSend}>
          <input
            type="text"
            value={input}
            placeholder={"Type a message..."}
            onChange={e => setInput(e.target.value)}
          />
          <button type="submit">Send</button>
        </form>
      )}
      {!peerUser && <div className="no-peer">Select a user to start chatting.</div>}
    </div>
  );
}
