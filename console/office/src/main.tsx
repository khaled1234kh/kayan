import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './TrustGateApp';
import './styles.css';
import './design-system.css';
import './workspace.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
