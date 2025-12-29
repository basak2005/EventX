import './App.css';
import Calendar from './Calendar.jsx';
import React, { useState, useEffect, useCallback } from 'react';
import api from './api';




const App = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userEmail, setUserEmail] = useState('');
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [authError, setAuthError] = useState('');

  const authBaseUrl = api.defaults.baseURL ?? 'http://localhost:8000';

  // Check if user is authenticated and load their profile
  const checkAuthStatus = useCallback(async () => {
    setIsCheckingAuth(true);
    setAuthError('');
    try {
      const statusRes = await api.get('/auth/status', { withCredentials: true });
      console.log('Auth status response:', statusRes.data);
      if (statusRes.data?.authenticated) {
        try {
          const userRes = await api.get('/user/me', { withCredentials: true });
          const email = userRes.data?.email ?? '';
          setUserEmail(email);
          setIsAuthenticated(true);
          return;
        } catch (userErr) {
          console.error('Fetching user profile failed:', userErr);
          setAuthError(userErr.response?.data?.detail ?? 'Unable to load user profile');
        }
      }
      setIsAuthenticated(false);
      setUserEmail('');
    } catch (error) {
      console.error('Auth status check failed:', error);
      setIsAuthenticated(false);
      setUserEmail('');
      setAuthError(error.response?.data?.detail ?? 'Authentication check failed');
    } finally {
      setIsCheckingAuth(false);
    }
  }, []);

  // Handle Google Login - redirect to FastAPI OAuth endpoint
  const handleGoogleLogin = async () => {
    // Redirect to your FastAPI Google OAuth endpoint
    window.location.href = `${authBaseUrl}/auth/login`; 
  };

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout', {}, { withCredentials: true });
    } catch (error) {
      console.error('Logout failed:', error);
      setAuthError(error.response?.data?.detail ?? 'Logout failed');
    } finally {
      setIsAuthenticated(false);
      setUserEmail('');
      checkAuthStatus();
    }
  };

  useEffect(() => {
    checkAuthStatus();
  }, [checkAuthStatus]);

  useEffect(() => {
    if (isAuthenticated) {
      // loadEvents(); - uncomment when function is defined
    }
  }, [isAuthenticated]);
  return (
    <div className="dashboard-container">
      {/* Navigation */}
      <nav className="navbar">
        <div className="nav-links">
          <a href="#">Home</a>
          <a href="#">Event</a>
          <a href="#">About Us</a>
          <a href="#">Contact Us</a>
        </div>
        <div className="logo">EvenetX</div>
        <div className="Login">
          {isCheckingAuth ? (
            <span>Checking session...</span>
          ) : isAuthenticated ? (
            <div className="auth-status">
              <span>{userEmail || 'Authenticated user'}</span>
              <button className="login-btn" onClick={handleLogout}>Logout</button>
            </div>
          ) : (
            <button className="login-btn" onClick={handleGoogleLogin}>Login with Google</button>
          )}
          {authError && !isCheckingAuth && (
            <span className="auth-error">{authError}</span>
          )}
        </div>
      </nav>

      {/* Hero Section */}
      <header className="hero">
        <h1>EvenetX a google Workspace Hub</h1>
        <p>Make all google project at one place</p>
      </header>

      {/* Content Grid */}
      <main className="grid-layout">
        <section className="card-section">
          <h2>Create Event</h2>
          <div className="card create-event-card">
            <div className="input-row">
              <input type="text" placeholder="Event Title" />
            </div>
            <div className="input-row">
              <span>StartEvent:</span>
              <input type="date" />
            </div>
            <div className="input-row">
              <span>End Event:</span>
              <input type="date" />
            </div>
            <div className="input-row">
              <input type="email" placeholder="Enter a email to notify" />
              <button className="add-email-btn">Add</button>
            </div>
            <div className='input-row'>
              <input type="text" placeholder="location" />
              <button className="add-email-btn">Add</button>
            </div>
            <button className="save-btn">Save </button>
          </div>
          <section className='clock-section'>
            <h2>Clock</h2>
            <div className="card clock-card">
              <iframe src="https://free.timeanddate.com/clock/ia7w4kyf/n54/tlin/fn7/fs20/fce9b36b/tct/pct/ftb/th2/ta1" frameborder="0" width="176" height="90" allowtransparency="true"></iframe>
            </div>
          </section>
        </section>

        <section className="card-section">
          <h2>Calendar</h2>
          <div className="card calendar-card">
            <Calendar />
          </div>
        </section>
        <section className="card-section full-width">
          <h2>Upcoming Event</h2>
          <div className="card upcoming-card">
            <div className="placeholder-content">
              <span>No Event Created</span>
            </div>
          </div>
        </section>

        <section className="card-section full-width">
          <h2>Yours Tasks</h2>
          <div className="card notes-card">
            <textarea placeholder="Write your event Tasks here..."></textarea>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="footer">
        <div className="footer-content">
          <div className="sitemap">
            <p>SITEMAP</p>
            <div className="socials">FB IG TW LI</div>
          </div>
          <div className="footer-links">
            <span>MENU</span>
            <span>SERVICES</span>
            <span>LEGAL</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;