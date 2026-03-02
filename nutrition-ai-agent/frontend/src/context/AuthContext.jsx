import { createContext, useContext, useEffect, useMemo, useState } from "react";
import api, { setAuthToken } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem("nutrition_token") || "");
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("nutrition_user");
    return raw ? JSON.parse(raw) : null;
  });

  useEffect(() => {
    setAuthToken(token);
    if (token) {
      localStorage.setItem("nutrition_token", token);
    } else {
      localStorage.removeItem("nutrition_token");
    }
  }, [token]);

  useEffect(() => {
    if (user) {
      localStorage.setItem("nutrition_user", JSON.stringify(user));
    } else {
      localStorage.removeItem("nutrition_user");
    }
  }, [user]);

  const register = async (payload) => {
    await api.post("/auth/register", payload);
  };

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setToken(data.access_token);
    setUser(data.user);
  };

  const logout = () => {
    setToken("");
    setUser(null);
  };

  const value = useMemo(
    () => ({ token, user, register, login, logout }),
    [token, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
