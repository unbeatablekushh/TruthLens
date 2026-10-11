import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Eye, EyeOff } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export const Login: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  const from = (location.state as any)?.from?.pathname || '/dashboard';

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormValues) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiClient.post('/api/auth/login', data);
      login(response.data.access_token, response.data.refresh_token, response.data.user);
      navigate(from, { replace: true });
    } catch (err: any) {
      if (err.response && err.response.data && err.response.data.detail) {
        setError(err.response.data.detail);
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="tl-page flex min-h-screen items-center py-10">
      <div className="tl-container grid max-w-5xl items-center gap-8 md:grid-cols-[1fr_420px] md:gap-16">
        <section className="max-w-lg">
          <Link to="/" className="tl-brand" aria-label="TruthLens home">Truth<span className="tl-brand-accent">Lens</span></Link>
          <p className="tl-eyebrow mb-3 mt-12">A careful second look</p>
          <h1 className="tl-heading">Evidence before certainty.</h1>
          <p className="mt-4 max-w-md text-base text-[var(--text-muted)]">
            Sign in to review claims, source assessments, and analyses you have saved.
          </p>
        </section>

        <section className="tl-panel w-full p-6 sm:p-8" aria-labelledby="login-heading">
          <div className="mb-7">
            <p className="tl-eyebrow mb-2">Welcome back</p>
            <h2 id="login-heading" className="font-serif text-2xl font-semibold text-[var(--foreground)]">Sign in</h2>
            <p className="mt-2 text-sm text-[var(--text-muted)]">
              New to TruthLens?{' '}
              <Link to="/register" className="font-semibold text-[var(--teal-dark)] underline-offset-4 hover:underline">
                Create an account
              </Link>
            </p>
          </div>
        
        {error && (
          <div role="alert" className="tl-alert-error mb-5 p-3">
            <h3 className="text-sm font-medium">{error}</h3>
          </div>
        )}

        <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
          <div className="space-y-4">
            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">Email address</label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                className="tl-field px-3 py-2.5 text-sm"
                placeholder="Email address"
                {...register('email')}
              />
              {errors.email && <p className="mt-1 text-xs text-[var(--danger)]">{errors.email.message}</p>}
            </div>
            
            <div className="relative">
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">Password</label>
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                className="tl-field px-3 py-2.5 pr-11 text-sm"
                placeholder="Password"
                {...register('password')}
              />
              <button
                type="button"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                className="absolute bottom-0 right-0 top-6 flex items-center px-3 text-[var(--text-muted)] hover:text-[var(--teal-dark)]"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? (
                  <EyeOff className="h-5 w-5 text-gray-400" aria-hidden="true" />
                ) : (
                  <Eye className="h-5 w-5 text-gray-400" aria-hidden="true" />
                )}
              </button>
              {errors.password && <p className="mt-1 text-xs text-[var(--danger)]">{errors.password.message}</p>}
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={isLoading}
              className="tl-button tl-button-primary w-full"
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          </div>
        </form>
        </section>
      </div>
    </div>
  );
};
