import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FiArrowRight, FiEye, FiEyeOff, FiLock, FiMail, FiUser } from "react-icons/fi";
import { useAuth } from "../context/AuthContext";

export default function RegisterPage() {
  const { register, token } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (token) {
      navigate("/", { replace: true });
    }
  }, [navigate, token]);

  const onSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register({ full_name: fullName, email, password });
      sessionStorage.setItem("pending_verify_email", email);
      sessionStorage.setItem("pending_verify_password", password);
      navigate(`/verify-email?email=${encodeURIComponent(email)}`);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Registration failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell dashboard-bg auth-bg-animated">
      <form className="card border-0 auth-card auth-card-elevated auth-form-motion" onSubmit={onSubmit}>
        <div className="card-body p-4 p-md-5">
          <div className="auth-badge mb-2">NutriFlow.ai</div>
          <h3 className="mb-1 fw-bold auth-title-gradient">Create Account</h3>
          <p className="text-secondary mb-3">Create your account to generate diet plans and chat with the assistant.</p>
          <div className="input-group mb-2">
            <span className="input-group-text"><FiUser /></span>
            <input
              className="form-control"
              type="text"
              placeholder="Full name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              required
            />
          </div>
          <div className="input-group mb-2">
            <span className="input-group-text"><FiMail /></span>
            <input className="form-control" type="email" placeholder="Email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </div>
          <div className="input-group mb-2">
            <span className="input-group-text"><FiLock /></span>
            <input
              className="form-control"
              type={showPassword ? "text" : "password"}
              placeholder="Password (min 8 chars)"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={8}
            />
            <button className="btn btn-outline-secondary" type="button" onClick={() => setShowPassword((previous) => !previous)}>
              {showPassword ? <FiEyeOff /> : <FiEye />}
            </button>
          </div>
          {error && <p className="text-danger small mb-2">{error}</p>}
          <button className="btn btn-success w-100 d-inline-flex justify-content-center align-items-center gap-2 auth-cta-btn" type="submit" disabled={loading}>{loading ? "Creating..." : <>Create account <FiArrowRight /></>}</button>
          <div className="d-grid mt-3 gap-2">
            <Link to="/login" className="btn btn-outline-primary">Login</Link>
          </div>
        </div>
      </form>
    </div>
  );
}
