import React from 'react';
import ReactDOM from 'react-dom/client';
import DashboardUI from './components/dashboard_ui.jsx';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <DashboardUI />
  </React.StrictMode>
);
