import React from 'react';
import './NetworkGraph.css';

export default function NetworkGraph({ network }) {
  // network: { relays: [{ip, port, id, status}], clients: [{username, online}], messages: [{from, to, path, time}] }
  function getRelayId(relay, idx) {
    // Use port or ip+port as id if not present
    return relay.id || relay.port || `${relay.ip}:${relay.port}`;
  }
  // Helper to prettify relay label
  function prettyRelay(relay) {
    if (typeof relay === 'string' && relay.match(/\d+\.\d+\.\d+\.\d+:\d+/)) {
      // Show port as main label for compactness
      return relay.split(':')[1];
    }
    return relay;
  }
  const latestMsg = network.messages && network.messages.length > 0 ? network.messages[0] : null;

  // --- Patch: Use real relay path from backend for visualization ---
  // Always prefer latestMsg.path if available (from /api/monitor), fallback to .relay_path (from /api/send)
  // Filter out sender/recipient if present in path for visualization
  const getRelayPath = (msg) => {
    if (!msg) return [];
    let path = [];
    if (Array.isArray(msg.path) && msg.path.length > 0) path = msg.path;
    else if (Array.isArray(msg.relay_path) && msg.relay_path.length > 0) path = msg.relay_path;
    // Filter out usernames (clients) if present
    const relayLike = x => typeof x === 'string' && x.match(/\d+\.\d+\.\d+\.\d+:\d+/);
    return path.filter(relayLike);
  };
  const relayPath = getRelayPath(latestMsg);

  const msgExplanation = latestMsg && (
    <div>
      <strong>Message:</strong> <span style={{color:'#2562c7'}}>{latestMsg.from}</span> → <span style={{color:'#2562c7'}}>{latestMsg.to}</span><br/>
      <strong>Relay Path:</strong> {relayPath.length > 0 ? relayPath.join(' → ') : '(not available)'}<br/>
      <strong>Relays Used:</strong> {relayPath.length}
    </div>
  );

  return (
    <div className="network-graph">
      <svg width="100vw" height="88vh" viewBox="0 0 1800 900" style={{display:'block'}}>
        {/* --- RELAY ZONE: Draw relays in a central band, never overlapping clients --- */}
        {network.relays.map((relay, idx) => {
          // Relays in a central ellipse (no overlap with client bands)
          const relayZone = { cx: 900, cy: 450, rx: 400, ry: 170 };
          const angle = (idx / network.relays.length) * 2 * Math.PI;
          const baseX = relayZone.cx + relayZone.rx * Math.cos(angle);
          const baseY = relayZone.cy + relayZone.ry * Math.sin(angle);
          return (
            <g key={getRelayId(relay, idx)}>
              <circle
                cx={baseX}
                cy={baseY}
                r={55}
                fill={relay.status === 'online' ? '#4e8cff' : '#ccc'}
                stroke="#222"
                strokeWidth="4"
              />
              <text x={baseX} y={baseY} textAnchor="middle" dy=".3em" fontSize="32" fill="#fff">
                {getRelayId(relay, idx)}
              </text>
            </g>
          );
        })}
        {/* --- CLIENT ZONE: Draw clients in a larger ellipse around relays --- */}
        {network.clients.map((client, idx) => {
          // Clients in a larger ellipse (never overlapping relays)
          const clientZone = { cx: 900, cy: 450, rx: 700, ry: 340 };
          const angle = (idx / network.clients.length) * 2 * Math.PI - Math.PI/2;
          const baseX = clientZone.cx + clientZone.rx * Math.cos(angle);
          const baseY = clientZone.cy + clientZone.ry * Math.sin(angle);
          return (
            <g key={client.username}>
              <rect
                x={baseX-60}
                y={baseY-60}
                width={120}
                height={120}
                fill={client.online ? '#6fe27a' : '#aaa'}
                stroke="#222"
                strokeWidth="4"
                rx={28}
              />
              <text x={baseX} y={baseY+12} textAnchor="middle" fontSize="32" fill="#222">
                {client.username}
              </text>
            </g>
          );
        })}
        {/* --- Draw relay path as a highlighted polyline over static relays and clients --- */}
        {relayPath.length > 0 && (() => {
          // Compose a full path including sender and recipient if available
          const msg = latestMsg;
          let fullPath = relayPath;
          if (msg && msg.from && msg.to) {
            fullPath = [msg.from, ...relayPath, msg.to];
          }
          // Map each node in the path to its (x, y) position
          const nodePositions = fullPath.map(node => {
            // Is it a client?
            const clientIdx = network.clients.findIndex(u => u.username === node);
            if (clientIdx !== -1) {
              const clientZone = { cx: 900, cy: 450, rx: 700, ry: 340 };
              const angle = (clientIdx / network.clients.length) * 2 * Math.PI - Math.PI/2;
              const x = clientZone.cx + clientZone.rx * Math.cos(angle);
              const y = clientZone.cy + clientZone.ry * Math.sin(angle);
              return { x, y };
            }
            // Is it a relay?
            const idx = network.relays.findIndex(r => String(r.id) === String(node) || `${r.ip}:${r.port}` === node);
            if (idx !== -1) {
              const relayZone = { cx: 900, cy: 450, rx: 400, ry: 170 };
              const angle = (idx / network.relays.length) * 2 * Math.PI;
              const x = relayZone.cx + relayZone.rx * Math.cos(angle);
              const y = relayZone.cy + relayZone.ry * Math.sin(angle);
              return { x, y };
            }
            return null;
          });
          if (nodePositions.some(pos => !pos)) return null;
          return nodePositions.map((pos, i) => {
            if (i < nodePositions.length - 1) {
              return (
                <line
                  key={fullPath[i] + '-' + fullPath[i+1] + '-' + i}
                  x1={pos.x}
                  y1={pos.y}
                  x2={nodePositions[i+1].x}
                  y2={nodePositions[i+1].y}
                  stroke="#ffb347"
                  strokeWidth="16"
                  opacity={0.7}
                />
              );
            }
            return null;
          });
        })()}
      </svg>
      <div className="legend" style={{ position: 'absolute', left: 24, bottom: 24, zIndex: 10, background: 'rgba(255,255,255,0.9)', borderRadius: 8, padding: '8px 18px', boxShadow: '0 2px 8px #0002' }}>
        <span className="relay-dot" /> Relay
        <span className="client-dot" /> Client
        <span className="msg-line" /> Message Path
      </div>
      {/* Live message explanation */}
      {msgExplanation && (
        <div style={{ position: 'absolute', right: 24, top: 24, zIndex: 20, background: 'rgba(255,255,255,0.97)', borderRadius: 8, padding: '16px', minWidth: 260, maxWidth: 350, boxShadow: '0 2px 8px #0002', pointerEvents: 'none' }}>
          {msgExplanation}
        </div>
      )}
    </div>
  );
}
