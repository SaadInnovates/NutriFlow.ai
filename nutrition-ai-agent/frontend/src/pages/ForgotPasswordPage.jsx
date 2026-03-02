import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { FiEye, FiEyeOff, FiKey, FiLock, FiMail, FiRefreshCw } from "react-icons/fi";
import api from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function ForgotPasswordPage() {
  const { token: authToken } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState(params.get("email") || "");
  const [token, setToken] = useState(params.get("token") || "");
  const [newPassword, setNewPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [info, setInfo] = useState("");
  const [error, setError] = useState("");
  const [loadingRequest, setLoadingRequest] = useState(false);
  const [loadingReset, setLoadingReset] = useState(false);

  useEffect(() => {
    if (authToken) {
      navigate("/", { replace: true });
    }
  }, [authToken, navigate]);

  const requestResetToken = async (event) => {
    event.preventDefault();
    setInfo("");
    setError("");
    setLoadingRequest(true);
    try {
      const { data } = await api.post("/auth/forgot-password", { email });
      setInfo(data.message || "If the account exists, a reset email has been sent.");
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Failed to request reset token.");
    } finally {
      setLoadingRequest(false);
    }
  };

  const resetPassword = async (event) => {
    event.preventDefault();
    setInfo("");
    setError("");
    setLoadingReset(true);
    try {
      const { data } = await api.post("/auth/reset-password", {
        email,
        token,
        new_password: newPassword,
      });
      setInfo(data.message || "Password updated.");
      setToken("");
      setNewPassword("");
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Password reset failed.");
    } finally {
      setLoadingReset(false);
    }
  };

  return (
    <div className="auth-shell dashboard-bg">
      <div className="card border-0 auth-card auth-card-elevated">
        <div className="card-body p-4 p-md-5">
          <div className="auth-badge mb-2">NutriFlow.ai</div>
          <h3 className="mb-1 fw-bold">Forgot Password</h3>
          <p className="text-secondary mb-3">Request a reset email, then open the link from your inbox.</p>

          <form onSubmit={requestResetToken} className="mb-3">
            <label className="form-label">Email</label>
            <div className="input-group mb-2">
              <span className="input-group-text"><FiMail /></span>
              <input className="form-control" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </div>
            <button className="btn btn-outline-primary w-100" type="submit" disabled={loadingRequest}>
              {loadingRequest ? "Requesting..." : "Send Reset Email"}
            </button>
          </form>

          <form onSubmit={resetPassword}>
            <label className="form-label">Reset Token</label>
            <div className="input-group mb-2">
              <span className="input-group-text"><FiKey /></span>
              <input className="form-control" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Token from email link" required />
            </div>
            <label className="form-label">New Password</label>
            <div className="input-group mb-2">
              <span className="input-group-text"><FiLock /></span>
              <input
                className="form-control"
                type={showPassword ? "text" : "password"}
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                placeholder="New password"
                minLength={8}
                required
              />
              <button className="btn btn-outline-secondary" type="button" onClick={() => setShowPassword((previous) => !previous)}>
                {showPassword ? <FiEyeOff /> : <FiEye />}
              </button>
            </div>
            <button className="btn btn-primary w-100 d-inline-flex justify-content-center align-items-center gap-2" type="submit" disabled={loadingReset}>
              {loadingReset ? "Resetting..." : <>Reset Password <FiRefreshCw /></>}
            </button>
          </form>

          {error && <p className="text-danger small mt-3 mb-0">{error}</p>}
          {info && <p className="text-success small mt-3 mb-0">{info}</p>}

          <p className="text-secondary mt-3 mb-0 text-center">
            Back to <Link to="/login">Login</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
