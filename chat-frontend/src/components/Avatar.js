import React from "react";

function stringToColor(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  let color = "#";
  for (let i = 0; i < 3; i++) {
    color += ("00" + ((hash >> (i * 8)) & 0xff).toString(16)).slice(-2);
  }
  return color;
}

export default function Avatar({ username, avatar }) {
  if (avatar && avatar.startsWith("http")) {
    return <img src={avatar} alt="avatar" className="avatar" />;
  }
  const initials = username ? username[0].toUpperCase() : "?";
  const bg = stringToColor(username || "?");
  return (
    <div className="avatar" style={{ background: bg }}>
      {initials}
    </div>
  );
}
