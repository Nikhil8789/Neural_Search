import React, { useState, useEffect } from "react";
import Chat from "./components/Chat.jsx";
import AuthPage from "./components/AuthPage.jsx";

export default function App() {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  
  useEffect(() => {
    // Check if user is already logged in
    const storedToken = localStorage.getItem("token");
    const storedName = localStorage.getItem("userName");
    if (storedToken) {
      setToken(storedToken);
      setUser({ name: storedName });
    }
  }, []);

  const handleAuthSuccess = (res) => {
    localStorage.setItem("token", res.access_token);
    localStorage.setItem("userName", res.name);
    setToken(res.access_token);
    setUser({ name: res.name });
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("userName");
    setToken(null);
    setUser(null);
  };

  if (!token) {
    return <AuthPage onAuthSuccess={handleAuthSuccess} />;
  }

  return <Chat user={user} onLogout={handleLogout} />;
}
