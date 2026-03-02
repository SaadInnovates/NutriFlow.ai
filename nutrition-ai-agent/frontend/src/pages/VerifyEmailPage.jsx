import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { FiCheckCircle, FiKey, FiMail, FiSend, FiShield } from "react-icons/fi";
import api from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function VerifyEmailPage() {
  const { login, token: authToken } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState(params.get("email") || "");
  const [token, setToken] = useState(params.get("token") || "");
  const [info, setInfo] = useState("");
  const [error, setError] = useState("");
  const [loadingRequest, setLoadingRequest] = useState(false);
  const [loadingVerify, setLoadingVerify] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [verifiedStatus, setVerifiedStatus] = useState(null);

  useEffect(() => {
    if (authToken) {
      navigate("/", { replace: true });
    }
  }, [authToken, navigate]);

  const checkStatus = async () => {
    setInfo("");
    setError("");
    setLoadingStatus(true);
    try {
      const { data } = await api.post("/auth/verify/status", { email });
      setVerifiedStatus(Boolean(data.verified));
      if (data.verified) {
        setInfo("This email is already verified. You can log in now.");
      } else {
        setInfo("Email is not verified yet. Please request a verification email.");
      }
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Failed to check status.");
    } finally {
      setLoadingStatus(false);
    }
  };

  const requestToken = async (event) => {
    event.preventDefault();
    setInfo("");
    setError("");
    setLoadingRequest(true);
    try {
      const { data } = await api.post("/auth/verify/request", { email });
      setInfo(data.message || "If the account exists, a verification email has been sent.");
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Failed to request verification token.");
    } finally {
      setLoadingRequest(false);
    }
  };

  const verifyEmail = async (event) => {
    event.preventDefault();
    setInfo("");
    setError("");
    setLoadingVerify(true);
    try {
      const { data } = await api.post("/auth/verify/confirm", { email, token });
      setInfo(data.message || "Email verified successfully.");

      const pendingEmail = sessionStorage.getItem("pending_verify_email") || "";
      const pendingPassword = sessionStorage.getItem("pending_verify_password") || "";
      if (pendingEmail.toLowerCase() === email.toLowerCase() && pendingPassword) {
        try {
          await login(email, pendingPassword);
          sessionStorage.removeItem("pending_verify_email");
          sessionStorage.removeItem("pending_verify_password");
          navigate("/");
          return;
        } catch {
          setInfo("Email verified successfully. Please log in.");
        }
      }
      setToken("");
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Verification failed.");
    } finally {
      setLoadingVerify(false);
    }
  };

  return (
    <div className="auth-shell dashboard-bg">
      <div className="card border-0 auth-card auth-card-elevated">
        <div className="card-body p-4 p-md-5">
          <div className="auth-badge mb-2">NutriFlow.ai</div>
          <h3 className="mb-1 fw-bold">Verify Email</h3>
          <p className="text-secondary mb-3">Request a verification email, then open the link from your inbox.</p>

          <form onSubmit={requestToken} className="mb-3">
            <label className="form-label">Email</label>
            <div className="input-group mb-2">
              <span className="input-group-text"><FiMail /></span>
              <input className="form-control" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </div>
            <div className="d-flex gap-2">
              <button className="btn btn-outline-secondary w-50" type="button" onClick={checkStatus} disabled={loadingStatus || !email.trim()}>
                {loadingStatus ? "Checking..." : "Check Status"}
              </button>
              <button className="btn btn-outline-primary w-50 d-inline-flex align-items-center justify-content-center gap-2" type="submit" disabled={loadingRequest}>
                {loadingRequest ? "Requesting..." : <>Send Email <FiSend /></>}
              </button>
            </div>
          </form>

          {verifiedStatus !== null && (
            <div className={`small mb-3 ${verifiedStatus ? "text-success" : "text-warning"}`}>
              {verifiedStatus ? "Verified account" : "Not verified yet"}
            </div>
          )}

          <form onSubmit={verifyEmail}>
            <label className="form-label">Verification Token</label>
            <div className="input-group mb-2">
              <span className="input-group-text"><FiKey /></span>
              <input className="form-control" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Token from email link" required />
            </div>
            <button className="btn btn-primary w-100 d-inline-flex align-items-center justify-content-center gap-2" type="submit" disabled={loadingVerify}>
              {loadingVerify ? "Verifying..." : <>Verify Email <FiCheckCircle /></>}
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
