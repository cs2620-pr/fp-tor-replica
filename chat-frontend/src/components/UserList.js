import React from 'react';
import './UserList.css';
import Avatar from "./Avatar";

export default function UserList({ users, unread, onSelect, selected }) {
  return (
    <div className="user-list">
      <h3>Online Users</h3>
      <ul>
        {users.map(user => (
          <li
            key={user.username}
            className={
              "user-list-item" +
              (selected && selected.username === user.username ? " selected" : "")
            }
            onClick={() => onSelect(user)}
          >
            <Avatar username={user.username} avatar={user.avatar} />
            <span className="user-name">{user.username}</span>
            {user.online && <span className="online-dot" />}
            {unread[user.username] > 0 && (
              <span className="unread-badge">{unread[user.username]}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
