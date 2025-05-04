import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import ChatPage from './pages/ChatPage';
import MonitorPage from './pages/MonitorPage';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/chat" element={<ChatPage />} />
      <Route path="/monitor" element={<MonitorPage />} />
      <Route path="*" element={<Navigate to="/login" />} />
    </Routes>
  );
}
