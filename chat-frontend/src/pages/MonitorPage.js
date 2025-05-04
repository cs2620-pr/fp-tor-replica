import React, { useEffect, useState } from 'react';
import NetworkGraph from '../components/NetworkGraph';
import { socket } from "../socket";

// Fallback: If props not provided, use local state
export default function MonitorPage() {
  const [network, setNetwork] = useState({ relays: [], clients: [], messages: [] });
  // Default: show all active relays
  const [relayCount, setRelayCount] = useState(null);

  // --- Synchronized relay count state for dropdowns ---
  const [messageRelayCount, setMessageRelayCount] = useState(() => {
    const stored = localStorage.getItem('messageRelayCount');
    return stored ? Number(stored) : 3;
  });

  // Listen for relay count changes in localStorage (from any tab/component)
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'messageRelayCount') {
        setMessageRelayCount(Number(e.newValue));
      }
    };
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, []);

  // Always persist to localStorage when changed in this tab
  useEffect(() => {
    localStorage.setItem('messageRelayCount', messageRelayCount);
  }, [messageRelayCount]);

  useEffect(() => {
    if (typeof messageRelayCount !== 'undefined') {
      localStorage.setItem('messageRelayCount', messageRelayCount);
    }
  }, [messageRelayCount]);

  useEffect(() => {
    const fetchNetwork = () => {
      // If relayCount is null, don't filter by relayCount (show all relays)
      const url = relayCount == null ? '/api/monitor' : `/api/monitor?relayCount=${relayCount}`;
      fetch(url).then(r => r.json()).then(setNetwork);
    };
    fetchNetwork();
    socket.connect();
    socket.on("new_message", fetchNetwork);
    socket.on("user_status", fetchNetwork);
    return () => {
      socket.disconnect();
    };
    // eslint-disable-next-line
  }, [relayCount]);

  // --- Add Relay Modal/Form State ---
  const [showAddRelay, setShowAddRelay] = useState(false);
  const [newRelayPort, setNewRelayPort] = useState('');
  const [newRelayId, setNewRelayId] = useState('');

  const handleAddRelay = async (e) => {
    e.preventDefault();
    if (!newRelayPort) return;
    await startRelay({ id: newRelayId || newRelayPort, port: newRelayPort });
    setShowAddRelay(false);
    setNewRelayPort('');
    setNewRelayId('');
    fetchNetwork();
  };

  // --- Relay and Server Management Functions ---
  const startRelay = async (relay) => {
    const res = await fetch('/api/relay/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ relay_id: relay.id, port: relay.port }),
    });
    await res.json();
    fetchNetwork();
  };
  const stopRelay = async (relay) => {
    const res = await fetch('/api/relay/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ port: relay.port }),
    });
    await res.json();
    fetchNetwork();
  };
  const startDestination = async () => {
    const res = await fetch('/api/destination/start', { method: 'POST' });
    await res.json();
    fetchNetwork();
  };
  const stopDestination = async () => {
    const res = await fetch('/api/destination/stop', { method: 'POST' });
    await res.json();
    fetchNetwork();
  };

  // --- Helper to refresh network state ---
  const fetchNetwork = () => {
    const url = relayCount == null ? '/api/monitor' : `/api/monitor?relayCount=${relayCount}`;
    fetch(url).then(r => r.json()).then(setNetwork);
  };

  // Compute the options for the message relay count dropdown
  const maxRelays = network.relays.length || 10;
  const relayOptions = [];
  for (let i = 1; i <= maxRelays; ++i) relayOptions.push(i);

  // --- Destination server status (simple: running if any relay has 'destination' role, else stopped) ---
  const destinationRunning = network.relays.some(r => r.role === 'destination' || r.id === 'destination');

  return (
    <div className="monitor-page">
      <h2>Server Monitor</h2>
      <div style={{ marginBottom: 24 }}>
        <b>Destination Server:</b> {' '}
        <button onClick={startDestination} disabled={destinationRunning}>Start</button>
        <button onClick={stopDestination} disabled={!destinationRunning}>Stop</button>
        <span style={{ marginLeft: 10, color: destinationRunning ? 'green' : 'red' }}>
          {destinationRunning ? 'Running' : 'Stopped'}
        </span>
      </div>
      <div style={{ marginBottom: 24 }}>
        <b>Relays:</b>
        <button onClick={() => setShowAddRelay(true)} style={{ marginLeft: 12, marginBottom: 8 }}>Add Relay</button>
        {showAddRelay && (
          <form onSubmit={handleAddRelay} style={{ marginTop: 10, marginBottom: 10, background: '#eef3fa', padding: 12, borderRadius: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
            <label>Port:
              <input type="number" value={newRelayPort} onChange={e => setNewRelayPort(e.target.value)} required style={{ marginLeft: 4, width: 90 }} />
            </label>
            <label>ID (optional):
              <input type="text" value={newRelayId} onChange={e => setNewRelayId(e.target.value)} style={{ marginLeft: 4, width: 110 }} />
            </label>
            <button type="submit">Start</button>
            <button type="button" onClick={() => { setShowAddRelay(false); setNewRelayPort(''); setNewRelayId(''); }}>Cancel</button>
          </form>
        )}
        <table style={{ width: '100%', marginTop: 8, borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left' }}>ID</th>
              <th style={{ textAlign: 'left' }}>IP</th>
              <th style={{ textAlign: 'left' }}>Port</th>
              <th style={{ textAlign: 'left' }}>Status</th>
              <th style={{ textAlign: 'left' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {network.relays.map((relay) => (
              <tr key={relay.id || relay.port}>
                <td>{relay.id}</td>
                <td>{relay.ip}</td>
                <td>{relay.port}</td>
                <td style={{ color: relay.status === 'online' ? 'green' : 'red' }}>{relay.status}</td>
                <td>
                  <button onClick={() => stopRelay(relay)} disabled={relay.status !== 'online'}>Stop</button>
                </td>
              </tr>
            ))}
            {network.relays.length === 0 && (
              <tr><td colSpan={5} style={{ textAlign: 'center', color: '#888' }}>No relays running</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <NetworkGraph network={network} />
    </div>
  );
}
