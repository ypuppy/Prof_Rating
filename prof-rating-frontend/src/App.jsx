import HomePage from './pages/HomePage';
import AuthProvider from './features/auth/AuthProvider';
import './App.css';

export default function App() {
  return (
    <AuthProvider>
      <HomePage />
    </AuthProvider>
  );
}
