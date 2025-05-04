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

  return (
    <div className="network-graph">
      <svg width="100%" height="400" viewBox="0 0 800 400">
        {/* Draw relays as static circles in a zigzag layout */}
        {network.relays.map((relay, idx) => {
          // Zigzag layout: alternate y positions
          const baseX = 150 + idx * 150;
          const baseY = idx % 2 === 0 ? 150 : 250;
          return (
            <g key={getRelayId(relay, idx)}>
              <circle
                cx={baseX}
                cy={baseY}
                r={35}
                fill={relay.status === 'online' ? '#4e8cff' : '#ccc'}
                stroke="#222"
                strokeWidth="3"
              />
              <text x={baseX} y={baseY} textAnchor="middle" dy=".3em" fontSize="20" fill="#fff">
                {getRelayId(relay, idx)}
              </text>
            </g>
          );
        })}
        {/* Draw clients as rectangles, spaced evenly along the left and right sides */}
        {network.clients.map((client, idx) => {
          const side = idx % 2 === 0 ? 'left' : 'right';
          const verticalSpacing = 70;
          const leftX = 30;
          const rightX = 700;
          const y = 60 + Math.floor(idx / 2) * verticalSpacing;
          const rectX = side === 'left' ? leftX : rightX;
          const textX = side === 'left' ? leftX + 30 : rightX + 30;
          return (
            <g key={client.username}>
              <rect
                x={rectX}
                y={y}
                width={60}
                height={60}
                fill={client.online ? '#6fe27a' : '#aaa'}
                stroke="#222"
                strokeWidth="3"
                rx={16}
              />
              <text x={textX} y={y + 35} textAnchor="middle" fontSize="16" fill="#222">
                {client.username}
              </text>
            </g>
          );
        })}
        {/* Draw relay path as a highlighted polyline over static relays and clients */}
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
              const side = clientIdx % 2 === 0 ? 'left' : 'right';
              const verticalSpacing = 70;
              const leftX = 60;
              const rightX = 730;
              const y = 60 + Math.floor(clientIdx / 2) * verticalSpacing + 30;
              const x = side === 'left' ? leftX : rightX;
              return { x, y };
            }
            // Is it a relay?
            const idx = network.relays.findIndex(r => String(r.id) === String(node) || `${r.ip}:${r.port}` === node);
            if (idx !== -1) {
              const x = 150 + idx * 150;
              const y = idx % 2 === 0 ? 150 : 250;
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
                  strokeWidth="8"
                  opacity={0.7}
                />
              );
            }
            return null;
          });
        })()}
        {/* Draw lines for the latest message path only */}
        {network.messages && network.messages.length > 0 && (() => {
          const msg = network.messages[0];
          if (!msg) return null;
          const path = relayPath;
          const nodePositions = path.map((node, i) => {
            // Is it a client?
            const clientIdx = network.clients.findIndex(u => u.username === node);
            if (clientIdx !== -1) {
              const side = clientIdx % 2 === 0 ? 'left' : 'right';
              const verticalSpacing = 70;
              const leftX = 60;
              const rightX = 730;
              const y = 60 + Math.floor(clientIdx / 2) * verticalSpacing + 30;
              const x = side === 'left' ? leftX : rightX;
              return { x, y };
            }
            // Is it a relay?
            const relayIdx = network.relays.findIndex(r => String(r.id) === String(node));
            if (relayIdx !== -1) {
              const x = 150 + relayIdx * 150;
              const y = relayIdx % 2 === 0 ? 150 : 250;
              return { x, y };
            }
            return null;
          });
          if (nodePositions.some(pos => !pos)) return null;
          return path.map((node, i) => {
            if (i < path.length - 1) {
              return (
                <line
                  key={msg.from + '-' + msg.to + '-' + i}
                  x1={nodePositions[i].x}
                  y1={nodePositions[i].y}
                  x2={nodePositions[i+1].x}
                  y2={nodePositions[i+1].y}
                  stroke="#ffb347"
                  strokeWidth="6"
                  opacity={0.5}
                />
              );
            }
            return null;
          });
        })()}
      </svg>
      <div className="legend">
        <span className="relay-dot" /> Relay
        <span className="client-dot" /> Client
        <span className="msg-line" /> Message Path
      </div>
      {/* Live message explanation */}
      {latestMsg && (
        <div className="msg-explanation" style={{marginTop:24, background:'#f0f4fa', borderRadius:8, padding:'16px 18px'}}>
          <strong>Message:</strong> <span style={{color:'#2562c7'}}>{latestMsg.from}</span> → <span style={{color:'#2562c7'}}>{latestMsg.to}</span><br/>
          <strong>Relay Path:</strong> {relayPath.length > 0 ? relayPath.join(' → ') : '(not available)'}<br/>
          <strong>Relays Used:</strong> {relayPath.length}
        </div>
      )}
    </div>
  );
}
