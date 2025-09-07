import React, { useState } from 'react';
import Login from './components/Login';
import Dashboard from './components/Dashboard';

function App() {
  const [phoneNumber, setPhoneNumber] = useState<string | null>(null);

  const handleLogin = (phone: string) => {
    setPhoneNumber(phone);
  };

  const handleLogout = () => {
    setPhoneNumber(null);
  };

  return (
    <div className="App">
      {phoneNumber ? (
        <Dashboard phoneNumber={phoneNumber} onLogout={handleLogout} />
      ) : (
        <Login onLogin={handleLogin} />
      )}
    </div>
  );
}

export default App
