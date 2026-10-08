import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchCurrentUser, logout as logoutRequest } from '../../api/auth';
import { AuthContext } from './AuthContext';
import LoginModal from './LoginModal';

export default function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  // Non-null while the login modal is open; holds what to do after logging in
  const [pendingAction, setPendingAction] = useState(null);

  useEffect(() => {
    fetchCurrentUser()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setChecking(false));
  }, []);

  const requireLogin = useCallback((action = () => {}) => {
    if (user) {
      action();
    } else {
      // Wrap in an object: passing a bare function to setState would call it
      setPendingAction({ run: action });
    }
  }, [user]);

  // For a 401 on a form submit: the session expired, so ask the user to log in again
  const promptLogin = useCallback(() => {
    setUser(null);
    setPendingAction({ run: () => {} });
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } finally {
      setUser(null);
    }
  }, []);

  const handleLoggedIn = (loggedInUser) => {
    setUser(loggedInUser);
    const action = pendingAction;
    setPendingAction(null);
    action?.run();
  };

  const value = useMemo(
    () => ({ user, checking, requireLogin, promptLogin, logout }),
    [user, checking, requireLogin, promptLogin, logout]
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
      {pendingAction && (
        <div className="modal-overlay login-overlay" onClick={() => setPendingAction(null)}>
          <div className="modal-content animate-scale-in" onClick={(e) => e.stopPropagation()}>
            <LoginModal onSuccess={handleLoggedIn} onCancel={() => setPendingAction(null)} />
          </div>
        </div>
      )}
    </AuthContext.Provider>
  );
}
