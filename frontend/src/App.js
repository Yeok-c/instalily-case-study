import React from 'react'; // Remove useState if you're not using it
import './App.css';
import ChatWindow from './components/ChatWindow';

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>Instalily Parts Finder</h1>
      </header>
      <main className="app-main">
        <ChatWindow />
      </main>
      <footer className="app-footer">
        <p>© 2025 Instalily - Appliance Parts Assistant</p>
      </footer>
    </div>
  );
}

export default App;