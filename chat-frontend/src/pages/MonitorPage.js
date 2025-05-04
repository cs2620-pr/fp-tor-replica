import React, { useEffect, useState } from 'react';
import NetworkGraph from '../components/NetworkGraph';
import { socket } from "../socket";

export default function MonitorPage() {
  const [network, setNetwork] = useState({ relays: [], clients: [], messages: [] });
  const [relayCount, setRelayCount] = useState(3);

  useEffect(() => {
    const fetchNetwork = () => {
      fetch(`/api/monitor?relayCount=${relayCount}`).then(r => r.json()).then(setNetwork);
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

  return (
    <div className="monitor-page">
      <h2>Server Monitor</h2>
      <div style={{marginBottom:16}}>
        <label htmlFor="relayCount">Number of relays to show: </label>
        <select id="relayCount" value={relayCount} onChange={e => setRelayCount(Number(e.target.value))}>
          {[1,2,3,4,5,6,7,8,9,10].map(n => <option key={n} value={n}>{n}</option>)}
        </select>
      </div>
      <NetworkGraph network={network} />
      <div style={{marginTop:24, background:'#f8f8f8', border:'1px solid #ccc', borderRadius:6, padding:12}}>
        <h4>Raw Monitor Data</h4>
        <pre style={{fontSize:12, maxHeight:200, overflow:'auto'}}>{JSON.stringify(network, null, 2)}</pre>
      </div>
    </div>
  );
}
