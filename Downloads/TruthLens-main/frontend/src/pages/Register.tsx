import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Check } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

const registerSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100, 'Name is too long'),
  email: z.string().email('Invalid email address'),
  password: z.string()
    .min(8, 'Password must be at least 8 characters')
    .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
    .regex(/[a-z]/, 'Password must contain at least one lowercase letter')
    .regex(/[0-9]/, 'Password must contain at least one digit'),
  confirm_password: z.string(),
}).refine((data) => data.password === data.confirm_password, {
  message: "Passwords don't match",
  path: ["confirm_password"],
});

type RegisterFormValues = z.infer<typeof registerSchema>;

export const Register: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
  });

  const password = watch('password', '');
  const hasUpperCase = /[A-Z]/.test(password);
  const hasLowerCase = /[a-z]/.test(password);
  const hasDigit = /[0-9]/.test(password);
  const hasLength = password.length >= 8;

  const onSubmit = async (data: RegisterFormValues) => {
    setIsLoading(true);
    setError(null);
    try {
      await apiClient.post('/api/auth/register', {
        name: data.name,
        email: data.email,
        password: data.password,
        confirm_password: data.confirm_password,
      });

      // After registration, log in automatically
      const loginResponse = await apiClient.post('/api/auth/login', {
        email: data.email,
        password: data.password,
      });

      login(
        loginResponse.data.access_token,
        loginResponse.data.refresh_token,
        loginResponse.data.user
      );
      navigate('/dashboard', { replace: true });
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

  const PasswordRequirement = ({ met, text }: { met: boolean; text: string }) => (
    <div className={`text-xs flex items-center gap-2 ${met ? 'text-green-600 dark:text-green-400' : 'text-gray-500 dark:text-gray-400'}`}>
      {met && <Check className="w-4 h-4" />}
      {!met && <div className="w-4 h-4 border border-current rounded" />}
      {text}
    </div>
  );

  return (
    <div className="tl-page flex min-h-screen items-center py-10">
      <div className="tl-container grid max-w-5xl items-center gap-8 md:grid-cols-[1fr_480px] md:gap-16">
        <section className="max-w-lg">
          <Link to="/" className="tl-brand" aria-label="TruthLens home">Truth<span className="tl-brand-accent">Lens</span></Link>
          <p className="tl-eyebrow mb-3 mt-12">A careful second look</p>
          <h1 className="tl-heading">Build a habit of checking the source.</h1>
          <p className="mt-4 max-w-md text-base text-[var(--text-muted)]">
            Create an account to keep your analyses, evidence, and verdict explanations together.
          </p>
        </section>

        <section className="tl-panel w-full p-6 sm:p-8" aria-labelledby="register-heading">
          <div className="mb-6">
            <p className="tl-eyebrow mb-2">Get started</p>
            <h2 id="register-heading" className="font-serif text-2xl font-semibold text-[var(--foreground)]">Create your account</h2>
            <p className="mt-2 text-sm text-[var(--text-muted)]">
              Already registered?{' '}
              <Link to="/login" className="font-semibold text-[var(--teal-dark)] underline-offset-4 hover:underline">
                Sign in
              </Link>
            </p>
          </div>

        {error && (
          <div role="alert" className="tl-alert-error mb-5 p-3">
            <h3 className="text-sm font-medium">{error}</h3>
          </div>
        )}

        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
          <div className="space-y-3.5">
            <div>
              <label htmlFor="name" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">Full name</label>
              <input
                id="name"
                type="text"
                autoComplete="name"
                className="tl-field px-3 py-2.5 text-sm"
                placeholder="Full name"
                {...register('name')}
              />
              {errors.name && <p className="mt-1 text-xs text-[var(--danger)]">{errors.name.message}</p>}
            </div>

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
                autoComplete="new-password"
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
              
              {password && (
                <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 rounded bg-[var(--surface-muted)] p-2.5">
                  <PasswordRequirement met={hasLength} text="At least 8 characters" />
                  <PasswordRequirement met={hasUpperCase} text="One uppercase letter" />
                  <PasswordRequirement met={hasLowerCase} text="One lowercase letter" />
                  <PasswordRequirement met={hasDigit} text="One digit" />
                </div>
              )}
            </div>

            <div className="relative">
              <label htmlFor="confirm_password" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">Confirm password</label>
              <input
                id="confirm_password"
                type={showConfirmPassword ? 'text' : 'password'}
                autoComplete="new-password"
                className="tl-field px-3 py-2.5 pr-11 text-sm"
                placeholder="Confirm password"
                {...register('confirm_password')}
              />
              <button
                type="button"
                aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                className="absolute bottom-0 right-0 top-6 flex items-center px-3 text-[var(--text-muted)] hover:text-[var(--teal-dark)]"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              >
                {showConfirmPassword ? (
                  <EyeOff className="h-5 w-5 text-gray-400" aria-hidden="true" />
                ) : (
                  <Eye className="h-5 w-5 text-gray-400" aria-hidden="true" />
                )}
              </button>
              {errors.confirm_password && <p className="mt-1 text-xs text-[var(--danger)]">{errors.confirm_password.message}</p>}
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={isLoading}
              className="tl-button tl-button-primary w-full"
            >
              {isLoading ? 'Creating account...' : 'Create account'}
            </button>
          </div>
        </form>
        </section>
      </div>
    </div>
  );
};
