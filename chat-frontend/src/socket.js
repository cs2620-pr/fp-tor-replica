import { io } from "socket.io-client";

const URL = process.env.NODE_ENV === "production" ? undefined : "http://localhost:5050";
export const socket = io(URL, {
  autoConnect: false
});
