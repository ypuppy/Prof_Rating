import { createContext, useContext } from 'react';

export const AuthContext = createContext(null);

/**
 * { user, checking, requireLogin(action), promptLogin(), logout }
 * requireLogin runs `action` right away if logged in, otherwise after the user logs in.
 */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
