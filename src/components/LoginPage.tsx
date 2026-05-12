import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LogIn, ShieldAlert, User, Lock, ArrowLeft } from 'lucide-react';
import logo from '../assets/carrier-logo.png';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (login(username, password)) {
      navigate('/');
    } else {
      setError('Invalid username or password');
    }
  };

  return (
    <div className="min-h-screen bg-[#020617] flex items-center justify-center p-6 font-sans">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-[10%] -left-[10%] w-[40%] h-[40%] bg-primary/10 rounded-full blur-[120px]" />
        <div className="absolute -bottom-[10%] -right-[10%] w-[40%] h-[40%] bg-primary/5 rounded-full blur-[120px]" />
      </div>

      <div className="w-full max-w-md relative animate-fade-up">
        {/* Back button */}
        <button 
          onClick={() => navigate('/')}
          className="flex items-center gap-2 text-white/50 hover:text-white transition-colors mb-8 group"
        >
          <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
          <span className="text-sm font-semibold uppercase tracking-wider">Back to Home</span>
        </button>

        <div className="bg-white rounded-3xl shadow-2xl overflow-hidden border border-white/10">
          <div className="p-8 sm:p-10">
            <div className="flex flex-col items-center mb-10">
              <img src={logo} alt="Carrier" className="h-10 w-auto mb-6" />
              <h1 className="text-2xl font-extrabold text-[#020617] tracking-tight">AI Command Center</h1>
              <p className="text-slate-500 text-sm mt-1">Enter your credentials to access the system</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div className="bg-red-50 border border-red-100 text-red-600 px-4 py-3 rounded-xl flex items-center gap-3 text-sm animate-shake">
                  <ShieldAlert className="h-4 w-4 flex-shrink-0" />
                  {error}
                </div>
              )}

              <div className="space-y-1.5">
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400 ml-1">Username</label>
                <div className="relative">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full h-12 bg-slate-50 border border-slate-200 rounded-xl pl-12 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-[#020617]"
                    placeholder="admin or worker"
                    required
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400 ml-1">Password</label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full h-12 bg-slate-50 border border-slate-200 rounded-xl pl-12 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-[#020617]"
                    placeholder="••••••••"
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                className="w-full h-14 bg-gradient-cta text-primary-foreground font-bold uppercase tracking-widest text-sm rounded-xl shadow-lg shadow-primary/20 transition-all hover:-translate-y-0.5 hover:shadow-xl active:scale-[0.98] mt-4 flex items-center justify-center gap-3"
              >
                <LogIn className="h-5 w-5" />
                Authorize Access
              </button>
            </form>

            <div className="mt-10 pt-8 border-t border-slate-100 grid grid-cols-2 gap-4">
              <div className="text-center">
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Admin Access</p>
                <code className="text-xs text-slate-600 bg-slate-50 px-2 py-1 rounded">admin / admin123</code>
              </div>
              <div className="text-center">
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Worker Access</p>
                <code className="text-xs text-slate-600 bg-slate-50 px-2 py-1 rounded">worker / worker123</code>
              </div>
            </div>
          </div>
        </div>
        
        <p className="text-center mt-8 text-white/30 text-xs tracking-widest uppercase font-semibold">
          Secure Carrier Intelligent Systems • 2024
        </p>
      </div>
    </div>
  );
}
