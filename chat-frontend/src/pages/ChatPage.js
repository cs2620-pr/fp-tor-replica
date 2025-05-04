import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import UserList from '../components/UserList';
import Conversation from '../components/Conversation';
import { socket } from "../socket";
import './ChatPage.css';

export default function ChatPage() {
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [unread, setUnread] = useState({});
  const [loading, setLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState(null);
  const [messageRelayCount, setMessageRelayCount] = useState(() => {
    const stored = localStorage.getItem('messageRelayCount');
    return stored ? Number(stored) : 3;
  });
  const navigate = useNavigate();

  useEffect(() => {
    const user = JSON.parse(localStorage.getItem('user'));
    if (!user) {
      navigate('/login');
      return;
    }
    setCurrentUser(user);
    fetch('/api/users').then(r => r.json()).then(setUsers);
    if (selectedUser) {
      fetch(`/api/messages?username=${encodeURIComponent(user.username)}`)
        .then(r => r.json())
        .then(data => {
          setConversations(
            data.conversations.filter(
              m => (m.from === user.username && m.to === selectedUser.username) ||
                   (m.from === selectedUser.username && m.to === user.username)
            )
          );
          setUnread(data.unread || {});
        });
    }
    setLoading(false);
  }, [selectedUser, navigate]);

  useEffect(() => {
    if (!currentUser) return;
    socket.connect();
    socket.emit("user_online", { username: currentUser.username });
    // Only fetch and update conversations if the new message is for the currently selected chat
    const handleNewMessage = (msg) => {
      if (
        selectedUser &&
        ((msg.from === currentUser.username && msg.to === selectedUser.username) ||
         (msg.from === selectedUser.username && msg.to === currentUser.username))
      ) {
        setConversations(prev => [...prev, msg]);
      }
    };
    socket.on("new_message", handleNewMessage);
    socket.on("read_message", (msg) => {
      if (msg.to === currentUser.username || msg.from === currentUser.username) {
        fetch(`/api/messages?username=${encodeURIComponent(currentUser.username)}`)
          .then(r => r.json())
          .then(data => {
            setConversations(data.conversations || []);
            setUnread(data.unread || {});
          });
      }
    });
    socket.on("user_status", (status) => {
      fetch('/api/users').then(r => r.json()).then(setUsers);
    });
    return () => {
      if (currentUser)
        socket.emit("user_offline", { username: currentUser.username });
      socket.off("new_message", handleNewMessage);
      socket.disconnect();
    };
  }, [currentUser, selectedUser]);

  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'messageRelayCount') {
        setMessageRelayCount(Number(e.newValue));
      }
    };
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, []);

  useEffect(() => {
    localStorage.setItem('messageRelayCount', messageRelayCount);
  }, [messageRelayCount]);

  if (!currentUser) return null;

  // Filter users to exclude current user
  const filteredUsers = users.filter(u => u.username !== currentUser.username);

  return (
    <div className="chat-imessage-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-title">Chats</div>
          <div className="sidebar-user">
            <span className="sidebar-user-label">Logged in as:</span>
            <span className="sidebar-user-name">{currentUser.username}</span>
          </div>
        </div>
        <UserList users={filteredUsers} unread={unread} onSelect={setSelectedUser} selected={selectedUser} />
      </aside>
      <main className="main-chat">
        {selectedUser ? (
          <Conversation
            currentUser={currentUser}
            peerUser={selectedUser}
            conversations={conversations}
            setConversations={setConversations}
          />
        ) : (
          <div className="no-conversation">Select a user to start chatting.</div>
        )}
      </main>
    </div>
  );
}
