import { useEffect, useMemo, useState } from "react";
import {
  FiActivity,
  FiCoffee,
  FiCpu,
  FiDownload,
  FiFileText,
  FiList,
  FiLogOut,
  FiMessageSquare,
  FiMoon,
  FiRefreshCcw,
  FiSend,
  FiSettings,
  FiShield,
  FiSun,
  FiTrash2,
  FiUser,
} from "react-icons/fi";
import api from "../api/client";
import { useAuth } from "../context/AuthContext";
import FormattedText from "../components/FormattedText";

const menuTabs = [
  { key: "check-api", icon: FiActivity, label: "Check API" },
  { key: "plan", icon: FiList, label: "Generate Plan" },
  { key: "recipe", icon: FiCoffee, label: "Recipe" },
  { key: "chat-health", icon: FiMessageSquare, label: "Health Chat" },
  { key: "chat-suggestions", icon: FiSend, label: "Suggestions Chat" },
  { key: "chat-debug", icon: FiShield, label: "Diet Debug" },
  { key: "pdf", icon: FiFileText, label: "Last PDF" },
  { key: "profile-settings", icon: FiSettings, label: "Profile Settings" },
];

const activityOptions = ["sedentary", "light", "moderate", "active", "very_active"];
const goalOptions = ["fat loss", "muscle gain", "maintenance", "improve energy", "manage blood sugar"];
const dietPreferenceOptions = ["balanced", "vegetarian", "vegan", "keto", "paleo", "mediterranean", "high_protein"];
const budgetOptions = ["low", "medium", "high"];

const defaultProfile = {
  age: 29,
  sex: "male",
  height_cm: 175,
  height_in: null,
  weight_kg: 78,
  activity_level: "moderate",
  goal: "fat loss",
  locality: "Global",
  diet_preference: "balanced",
  allergies: [],
  medical_conditions: [],
  budget_level: "medium",
  cooking_time_minutes: 45,
  disliked_foods: [],
  constraints: [],
};

const emptyPlanResult = {
  plan: "",
  sources: [],
  evidence_notes: [],
  section_confidence: {},
  section_attribution: {},
  profile_warnings: [],
  general_suggestions: [],
  calculated_targets: {},
  model: "",
};

const createChatState = () => ({
  selectedSessionId: "",
  message: "",
  assistantMessage: "",
  history: [],
  loading: false,
});

const createRecipeState = () => ({
  dishRequest: "",
  cuisine: "Any",
  servings: 2,
  notes: "",
  result: "",
  loading: false,
});

function parseCommaValues(value) {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function toNumberOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function StatusChip({ ok, text }) {
  return <span className={`status-chip ${ok ? "ok" : "bad"}`}>{text}</span>;
}

function ProfileInput({ label, children }) {
  return (
    <label className="profile-field">
      <span className="profile-label">{label}</span>
      {children}
    </label>
  );
}

function SectionTitle({ icon: Icon, title, subtitle = "" }) {
  return (
    <div className="section-title-wrap mb-3">
      <h5 className="fw-bold mb-1 dashboard-title d-flex align-items-center gap-2">
        <span className="title-icon"><Icon size={16} /></span>
        <span>{title}</span>
      </h5>
      {subtitle && <p className="small text-secondary mb-0">{subtitle}</p>}
    </div>
  );
}

function StatTile({ icon: Icon, label, value, helper, delayMs = 0 }) {
  return (
    <div className="stat-tile" style={{ animationDelay: `${delayMs}ms` }}>
      <div className="stat-icon"><Icon size={16} /></div>
      <div className="stat-content">
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
        {helper && <div className="stat-helper">{helper}</div>}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState("check-api");
  const [isDarkMode, setIsDarkMode] = useState(() => localStorage.getItem("nutrition_theme") === "dark");
  const [profile, setProfile] = useState(defaultProfile);
  const [globalError, setGlobalError] = useState("");
  const [globalSuccess, setGlobalSuccess] = useState("");

  const [apiStatus, setApiStatus] = useState(null);
  const [planResult, setPlanResult] = useState(emptyPlanResult);
  const [planLoading, setPlanLoading] = useState(false);
  const [recipeState, setRecipeState] = useState(createRecipeState());

  const [chatHealth, setChatHealth] = useState(createChatState());
  const [chatSuggestions, setChatSuggestions] = useState(createChatState());
  const [chatSessions, setChatSessions] = useState({ health: [], suggestions: [], debug: [] });

  const [debugSelectedSessionId, setDebugSelectedSessionId] = useState("");
  const [debugPlanText, setDebugPlanText] = useState("");
  const [debugInstruction, setDebugInstruction] = useState("");
  const [debugUpdatedPlan, setDebugUpdatedPlan] = useState("");
  const [debugLoading, setDebugLoading] = useState(false);
  const [debugHistory, setDebugHistory] = useState([]);
  const [commaInputs, setCommaInputs] = useState({
    allergies: "",
    medical_conditions: "",
    disliked_foods: "",
    constraints: "",
  });

  const [lastPdfUrl, setLastPdfUrl] = useState("");
  const [lastPdfName, setLastPdfName] = useState("diet_plan.pdf");

  const [groqApiKey, setGroqApiKey] = useState("");
  const [savingGroqKey, setSavingGroqKey] = useState(false);
  const [accountName, setAccountName] = useState(user?.full_name || "");
  const [savingProfile, setSavingProfile] = useState(false);
  const [deletingAccount, setDeletingAccount] = useState(false);

  const activeChat = useMemo(() => (activeTab === "chat-health" ? chatHealth : chatSuggestions), [activeTab, chatHealth, chatSuggestions]);

  const dashboardStats = useMemo(() => {
    const profileScore = [
      profile.age,
      profile.sex,
      profile.height_cm,
      profile.weight_kg,
      profile.goal,
      profile.locality,
      profile.activity_level,
      profile.diet_preference,
    ].filter(Boolean).length;
    const totalSessions = chatSessions.health.length + chatSessions.suggestions.length + chatSessions.debug.length;

    return [
      {
        icon: FiList,
        label: "Plan Status",
        value: planResult.plan ? "Ready" : "Waiting",
        helper: planResult.plan ? "Plan generated" : "Generate your first plan",
      },
      {
        icon: FiMessageSquare,
        label: "Total Sessions",
        value: String(totalSessions),
        helper: `${chatSessions.health.length} health • ${chatSessions.suggestions.length} suggestions • ${chatSessions.debug.length} debug`,
      },
      {
        icon: FiUser,
        label: "Profile Completeness",
        value: `${Math.round((profileScore / 8) * 100)}%`,
        helper: `${profileScore}/8 key fields set`,
      },
      {
        icon: FiFileText,
        label: "Last Export",
        value: lastPdfUrl ? "Available" : "None",
        helper: lastPdfName || "No PDF yet",
      },
    ];
  }, [chatSessions.debug.length, chatSessions.health.length, chatSessions.suggestions.length, lastPdfName, lastPdfUrl, planResult.plan, profile.activity_level, profile.age, profile.diet_preference, profile.goal, profile.height_cm, profile.locality, profile.sex, profile.weight_kg]);

  useEffect(() => {
    const body = document.body;
    if (isDarkMode) {
      body.classList.add("theme-dark");
      localStorage.setItem("nutrition_theme", "dark");
    } else {
      body.classList.remove("theme-dark");
      localStorage.setItem("nutrition_theme", "light");
    }

    return () => {
      body.classList.remove("theme-dark");
    };
  }, [isDarkMode]);

  useEffect(() => {
    if (activeTab === "chat-health" || activeTab === "chat-suggestions") {
      loadSessions(activeTab);
    }
    if (activeTab === "chat-debug") {
      loadSessions("chat-debug");
    }
  }, [activeTab]);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const { data } = await api.get("/auth/profile");
        if (data?.profile && Object.keys(data.profile).length > 0) {
          const merged = { ...defaultProfile, ...data.profile };
          setProfile(merged);
          setCommaInputs({
            allergies: (merged.allergies || []).join(", "),
            medical_conditions: (merged.medical_conditions || []).join(", "),
            disliked_foods: (merged.disliked_foods || []).join(", "),
            constraints: (merged.constraints || []).join(", "),
          });
        }
      } catch {
        // Keep defaults when no profile exists.
      }
    };
    fetchProfile();
  }, []);

  const setProfileField = (key, value) => {
    setProfile((previous) => ({ ...previous, [key]: value }));
  };

  const setNumericProfileField = (key, value) => {
    setProfile((previous) => ({ ...previous, [key]: toNumberOrNull(value) }));
  };

  const setCommaProfileField = (key, value) => {
    setCommaInputs((previous) => ({ ...previous, [key]: value }));
    setProfile((previous) => ({ ...previous, [key]: parseCommaValues(value) }));
  };

  const setChatStateByTab = (tabKey, updater) => {
    if (tabKey === "chat-health") {
      setChatHealth((previous) => updater(previous));
    } else {
      setChatSuggestions((previous) => updater(previous));
    }
  };

  const withErrorHandling = async (action) => {
    setGlobalError("");
    setGlobalSuccess("");
    try {
      await action();
    } catch (error) {
      setGlobalError(error.response?.data?.detail || "Request failed.");
    }
  };

  const fetchApiStatus = async () => {
    await withErrorHandling(async () => {
      const [{ data: health }, { data: keyStatus }] = await Promise.all([
        api.get("/chat/health"),
        api.get("/auth/groq-key"),
      ]);
      setApiStatus({ ...health, key_status: keyStatus });
    });
  };

  const saveGroqKey = async (event) => {
    event.preventDefault();
    if (!groqApiKey.trim()) {
      setGlobalError("Please enter your Groq API key.");
      return;
    }

    setSavingGroqKey(true);
    await withErrorHandling(async () => {
      await api.put("/auth/groq-key", { api_key: groqApiKey.trim() });
      setGroqApiKey("");
      setGlobalSuccess("Groq API key saved to your account.");
      await fetchApiStatus();
    });
    setSavingGroqKey(false);
  };

  const submitPlan = async (event) => {
    event.preventDefault();
    setPlanLoading(true);
    await withErrorHandling(async () => {
      const { data } = await api.post("/chat/plan", profile);
      setPlanResult(data);
      setGlobalSuccess("Plan generated successfully.");
    });
    setPlanLoading(false);
  };

  const submitRecipe = async (event) => {
    event.preventDefault();
    if (!recipeState.dishRequest.trim()) {
      setGlobalError("Please enter a dish name or request.");
      return;
    }

    setRecipeState((previous) => ({ ...previous, loading: true }));
    await withErrorHandling(async () => {
      const { data } = await api.post("/chat/recipe", {
        dish_request: recipeState.dishRequest,
        cuisine: recipeState.cuisine,
        servings: Number(recipeState.servings) || 2,
        notes: recipeState.notes,
        profile,
      });
      setRecipeState((previous) => ({ ...previous, result: data.recipe || "" }));
      setGlobalSuccess("Recipe generated.");
    });
    setRecipeState((previous) => ({ ...previous, loading: false }));
  };

  const savePdfFromResponse = async (planText, model, calculatedTargets, sources) => {
    await withErrorHandling(async () => {
      const response = await api.post(
        "/chat/plan/pdf",
        {
          plan_text: planText,
          payload: profile,
          calculated_targets: calculatedTargets || {},
          sources: sources || [],
          model: model || "unknown",
        },
        { responseType: "blob" }
      );

      const fileUrl = URL.createObjectURL(response.data);
      const generatedName = `diet_plan_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.pdf`;
      setLastPdfUrl(fileUrl);
      setLastPdfName(generatedName);

      const anchor = document.createElement("a");
      anchor.href = fileUrl;
      anchor.download = generatedName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    });
  };

  const submitChatMessage = async (event, tabKey) => {
    event.preventDefault();
    const mode = tabKey === "chat-health" ? "health" : "suggestions";

    setChatStateByTab(tabKey, (previous) => ({ ...previous, loading: true }));
    await withErrorHandling(async () => {
      const current = tabKey === "chat-health" ? chatHealth : chatSuggestions;
      const { data } = await api.post("/chat/message", {
        session_id: current.selectedSessionId || null,
        mode,
        message: current.message,
        profile,
        plan_text: planResult.plan || null,
      });

      setChatStateByTab(tabKey, (previous) => ({
        ...previous,
        selectedSessionId: data.session_id,
        assistantMessage: data.assistant_message,
        message: "",
      }));
      await loadSessions(tabKey, data.session_id);
      await loadHistory(tabKey, data.session_id);
    });
    setChatStateByTab(tabKey, (previous) => ({ ...previous, loading: false }));
  };

  const loadSessions = async (tabKey, preferredSessionId = "") => {
    const mode = tabKey === "chat-health" ? "health" : tabKey === "chat-suggestions" ? "suggestions" : "debug";
    await withErrorHandling(async () => {
      const { data } = await api.get(`/chat/sessions?mode=${mode}`);
      const sessions = data.sessions || [];
      setChatSessions((previous) => ({ ...previous, [mode]: sessions }));

      if (tabKey === "chat-debug") {
        if (preferredSessionId) {
          setDebugSelectedSessionId(preferredSessionId);
        } else if (!debugSelectedSessionId && sessions[0]?.session_id) {
          setDebugSelectedSessionId(sessions[0].session_id);
        }
        return;
      }

      const nextSessionId =
        preferredSessionId ||
        (tabKey === "chat-health" ? chatHealth.selectedSessionId : chatSuggestions.selectedSessionId) ||
        sessions[0]?.session_id ||
        "";

      if (nextSessionId) {
        setChatStateByTab(tabKey, (previous) => ({ ...previous, selectedSessionId: nextSessionId }));
      }
    });
  };

  const loadHistory = async (tabKey, targetSessionId = "") => {
    const current = tabKey === "chat-health" ? chatHealth : chatSuggestions;
    const sessionId = targetSessionId || current.selectedSessionId;
    if (!sessionId) {
      setGlobalError("No session selected.");
      return;
    }

    await withErrorHandling(async () => {
      const { data } = await api.get(`/chat/history/${sessionId}`);
      setChatStateByTab(tabKey, (previous) => ({ ...previous, selectedSessionId: sessionId, history: data.history || [] }));
    });
  };

  const resetHistory = async (tabKey, targetSessionId = "") => {
    const current = tabKey === "chat-health" ? chatHealth : chatSuggestions;
    const sessionId = targetSessionId || current.selectedSessionId;
    if (!sessionId) {
      setGlobalError("No session selected.");
      return;
    }

    await withErrorHandling(async () => {
      await api.post(`/chat/reset/${sessionId}`);
      setChatStateByTab(tabKey, (previous) => ({ ...previous, history: [] }));
      await loadSessions(tabKey);
      setGlobalSuccess("Chat history reset.");
    });
  };

  const extractDebugPlanFromPdf = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    await withErrorHandling(async () => {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await api.post("/chat/debug/extract-plan", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setDebugPlanText(data.plan_text || "");
      setDebugUpdatedPlan("");
      setGlobalSuccess("Plan text extracted from PDF.");
    });
  };

  const submitDebugModify = async (event) => {
    event.preventDefault();
    if (!debugPlanText.trim()) {
      setGlobalError("Upload a plan PDF or paste existing plan text before modifying.");
      return;
    }

    setDebugLoading(true);
    await withErrorHandling(async () => {
      const { data } = await api.post("/chat/debug/modify", {
        profile,
        current_plan_text: debugPlanText,
        instruction: debugInstruction,
      });
      setDebugUpdatedPlan(data.updated_plan || "");
      setDebugPlanText(data.updated_plan || debugPlanText);
      setDebugInstruction("");
      setGlobalSuccess("Diet plan updated.");
    });
    setDebugLoading(false);
  };

  const loadDebugHistory = async (targetSessionId = "") => {
    const sessionId = targetSessionId || debugSelectedSessionId;
    if (!sessionId) {
      setGlobalError("No debug session selected.");
      return;
    }

    await withErrorHandling(async () => {
      const { data } = await api.get(`/chat/history/${sessionId}`);
      setDebugSelectedSessionId(sessionId);
      setDebugHistory(data.history || []);
    });
  };

  const resetDebugHistory = async (targetSessionId = "") => {
    const sessionId = targetSessionId || debugSelectedSessionId;
    if (!sessionId) {
      setGlobalError("No debug session selected.");
      return;
    }

    await withErrorHandling(async () => {
      await api.post(`/chat/reset/${sessionId}`);
      setDebugHistory([]);
      await loadSessions("chat-debug");
      setGlobalSuccess("Debug chat history reset.");
    });
  };

  const saveUserProfile = async (event) => {
    event.preventDefault();
    setSavingProfile(true);
    await withErrorHandling(async () => {
      await api.put("/auth/profile", {
        full_name: accountName,
        ...profile,
      });
      setGlobalSuccess("Profile updated successfully.");
    });
    setSavingProfile(false);
  };

  const deleteMyAccount = async () => {
    const confirmed = window.confirm("Are you sure you want to permanently delete your account?");
    if (!confirmed) return;

    setDeletingAccount(true);
    await withErrorHandling(async () => {
      await api.delete("/auth/me");
      logout();
    });
    setDeletingAccount(false);
  };

  return (
    <div className="dashboard-bg app-shell min-vh-100">
      <div className="container py-4 py-md-5">
        <div className="glass-card dashboard-hero p-3 p-md-4 mb-3 d-flex flex-wrap align-items-center justify-content-between gap-3 fade-in-up">
          <div>
            <h3 className="mb-1 fw-bold">NutriFlow.ai Dashboard</h3>
            <div className="text-secondary">👋 {accountName || user?.full_name} • {user?.email}</div>
          </div>
          <div className="d-flex align-items-center gap-2">
            <button
              className="btn btn-outline-secondary btn-lift d-inline-flex align-items-center gap-2"
              onClick={() => setIsDarkMode((previous) => !previous)}
              type="button"
            >
              {isDarkMode ? <FiSun /> : <FiMoon />} {isDarkMode ? "Light" : "Dark"}
            </button>
            <button className="btn btn-outline-danger btn-lift d-inline-flex align-items-center gap-2" onClick={logout}><FiLogOut /> Logout</button>
          </div>
        </div>

        <div className="stats-grid mb-3 fade-in-up" style={{ animationDelay: "110ms" }}>
          {dashboardStats.map((stat, index) => (
            <StatTile
              key={stat.label}
              icon={stat.icon}
              label={stat.label}
              value={stat.value}
              helper={stat.helper}
              delayMs={index * 70}
            />
          ))}
        </div>

        <div className="tab-scroll mb-3 fade-in-up" style={{ animationDelay: "90ms" }}>
          <ul className="nav nav-pills flex-nowrap gap-2">
            {menuTabs.map((item) => (
              <li className="nav-item" key={item.key}>
                <button
                  className={`nav-link ${activeTab === item.key ? "active" : ""}`}
                  onClick={() => setActiveTab(item.key)}
                  type="button"
                >
                  <item.icon className="tab-icon" aria-hidden="true" />
                  <span>{item.label}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>

          {globalError && <div className="alert alert-danger py-2 mb-3 dashboard-alert">{globalError}</div>}
          {globalSuccess && <div className="alert alert-success py-2 mb-3 dashboard-alert">{globalSuccess}</div>}

          <div className="glass-card dashboard-main p-3 p-md-4 fade-in-up" style={{ animationDelay: "150ms" }}>
            <div key={activeTab} className="tab-panel-enter">
          {(activeTab === "plan" || activeTab === "recipe" || activeTab === "chat-suggestions" || activeTab === "chat-debug") && (
              <div className="mb-4 profile-card profile-card-premium">
                <SectionTitle icon={FiUser} title="Profile" subtitle="Fine-tune your inputs for more personalized outputs." />
              <div className="row g-3">
                <div className="col-md-2">
                  <ProfileInput label="Age">
                    <input className="form-control" type="number" value={profile.age ?? ""} onChange={(event) => setNumericProfileField("age", event.target.value)} placeholder="e.g. 29" />
                  </ProfileInput>
                </div>
                <div className="col-md-2">
                  <ProfileInput label="Sex">
                    <select className="form-select" value={profile.sex || "male"} onChange={(event) => setProfileField("sex", event.target.value)}>
                      <option value="male">Male</option>
                      <option value="female">Female</option>
                      <option value="other">Other</option>
                    </select>
                  </ProfileInput>
                </div>
                <div className="col-md-2">
                  <ProfileInput label="Height (cm)">
                    <input className="form-control" type="number" value={profile.height_cm ?? ""} onChange={(event) => setNumericProfileField("height_cm", event.target.value)} placeholder="e.g. 175" />
                  </ProfileInput>
                </div>
                <div className="col-md-2">
                  <ProfileInput label="Weight (kg)">
                    <input className="form-control" type="number" value={profile.weight_kg ?? ""} onChange={(event) => setNumericProfileField("weight_kg", event.target.value)} placeholder="e.g. 78" />
                  </ProfileInput>
                </div>
                <div className="col-md-4">
                  <ProfileInput label="Goal (option)">
                    <select className="form-select" value={profile.goal || goalOptions[0]} onChange={(event) => setProfileField("goal", event.target.value)}>
                      {goalOptions.map((option) => (
                        <option key={option} value={option}>{option}</option>
                      ))}
                    </select>
                  </ProfileInput>
                </div>
                <div className="col-md-3">
                  <ProfileInput label="Locality/Country">
                    <input className="form-control" value={profile.locality || ""} onChange={(event) => setProfileField("locality", event.target.value)} placeholder="e.g. Pakistan" />
                  </ProfileInput>
                </div>
                <div className="col-md-3">
                  <ProfileInput label="Activity (option)">
                    <select className="form-select" value={profile.activity_level || "moderate"} onChange={(event) => setProfileField("activity_level", event.target.value)}>
                      {activityOptions.map((option) => (
                        <option key={option} value={option}>{option}</option>
                      ))}
                    </select>
                  </ProfileInput>
                </div>
                <div className="col-md-3">
                  <ProfileInput label="Diet preference (option)">
                    <select className="form-select" value={profile.diet_preference || "balanced"} onChange={(event) => setProfileField("diet_preference", event.target.value)}>
                      {dietPreferenceOptions.map((option) => (
                        <option key={option} value={option}>{option}</option>
                      ))}
                    </select>
                  </ProfileInput>
                </div>
                <div className="col-md-3">
                  <ProfileInput label="Budget (option)">
                    <select className="form-select" value={profile.budget_level || "medium"} onChange={(event) => setProfileField("budget_level", event.target.value)}>
                      {budgetOptions.map((option) => (
                        <option key={option} value={option}>{option}</option>
                      ))}
                    </select>
                  </ProfileInput>
                </div>
                <div className="col-md-3">
                  <ProfileInput label="Cooking time (minutes)">
                    <input className="form-control" type="number" min={5} max={240} value={profile.cooking_time_minutes ?? ""} onChange={(event) => setNumericProfileField("cooking_time_minutes", event.target.value)} placeholder="e.g. 45" />
                  </ProfileInput>
                </div>
                <div className="col-md-6">
                  <ProfileInput label="Allergies (comma separated)">
                    <textarea className="form-control" rows={2} value={commaInputs.allergies} onChange={(event) => setCommaProfileField("allergies", event.target.value)} placeholder="e.g. peanut, shellfish" />
                  </ProfileInput>
                </div>
                <div className="col-md-6">
                  <ProfileInput label="Medical conditions (comma separated)">
                    <textarea className="form-control" rows={2} value={commaInputs.medical_conditions} onChange={(event) => setCommaProfileField("medical_conditions", event.target.value)} placeholder="e.g. PCOS, hypertension" />
                  </ProfileInput>
                </div>
                <div className="col-md-6">
                  <ProfileInput label="Disliked foods (comma separated)">
                    <textarea className="form-control" rows={2} value={commaInputs.disliked_foods} onChange={(event) => setCommaProfileField("disliked_foods", event.target.value)} placeholder="e.g. broccoli" />
                  </ProfileInput>
                </div>
                <div className="col-md-6">
                  <ProfileInput label="Other constraints (comma separated)">
                    <textarea className="form-control" rows={2} value={commaInputs.constraints} onChange={(event) => setCommaProfileField("constraints", event.target.value)} placeholder="e.g. high protein" />
                  </ProfileInput>
                </div>
              </div>
            </div>
          )}

          {activeTab === "recipe" && (
            <div className="dashboard-section">
              <SectionTitle icon={FiCoffee} title="Health Recipe Assistant" subtitle="Generate practical recipes with nutrition and oil guidance." />
              <form onSubmit={submitRecipe}>
                <div className="row g-3">
                  <div className="col-md-7">
                    <label className="form-label">Dish name / request</label>
                    <input
                      className="form-control"
                      value={recipeState.dishRequest}
                      onChange={(event) => setRecipeState((previous) => ({ ...previous, dishRequest: event.target.value }))}
                      placeholder="e.g. Chicken Biryani, Pasta, Karahi"
                      required
                    />
                  </div>
                  <div className="col-md-3">
                    <label className="form-label">Cuisine</label>
                    <input
                      className="form-control"
                      value={recipeState.cuisine}
                      onChange={(event) => setRecipeState((previous) => ({ ...previous, cuisine: event.target.value }))}
                      placeholder="e.g. Pakistani"
                    />
                  </div>
                  <div className="col-md-2">
                    <label className="form-label">Servings</label>
                    <input
                      className="form-control"
                      type="number"
                      min={1}
                      max={12}
                      value={recipeState.servings}
                      onChange={(event) => setRecipeState((previous) => ({ ...previous, servings: Number(event.target.value) || 2 }))}
                    />
                  </div>
                  <div className="col-12">
                    <label className="form-label">Additional notes</label>
                    <textarea
                      className="form-control"
                      rows={3}
                      value={recipeState.notes}
                      onChange={(event) => setRecipeState((previous) => ({ ...previous, notes: event.target.value }))}
                      placeholder="e.g. less spicy, no deep fry, diabetic-friendly"
                    />
                  </div>
                </div>
                <button className="btn btn-primary mt-3 btn-lift d-inline-flex align-items-center gap-2" type="submit" disabled={recipeState.loading}>
                  <FiSend /> {recipeState.loading ? "Generating..." : "Generate Healthy Recipe"}
                </button>
              </form>

              {recipeState.result && (
                <div className="output-panel p-3 mt-3 chat-answer-card">
                  <FormattedText text={recipeState.result} />
                </div>
              )}
            </div>
          )}

          {activeTab === "check-api" && (
            <div className="dashboard-section">
              <SectionTitle icon={FiActivity} title="Check API" subtitle="Verify server and model key readiness." />
              <div className="d-flex gap-2 flex-wrap mb-3">
                <button className="btn btn-primary btn-lift d-inline-flex align-items-center gap-2" onClick={fetchApiStatus}><FiRefreshCcw /> Check API Status</button>
              </div>

              {apiStatus && (
                <div className="status-grid mb-4">
                  <div className="status-card card-hover-lift">
                    <div className="small text-secondary mb-1">Backend</div>
                    <StatusChip ok={apiStatus.status === "ok"} text={apiStatus.status === "ok" ? "Running" : "Issue"} />
                  </div>
                  <div className="status-card card-hover-lift">
                    <div className="small text-secondary mb-1">User Groq Key</div>
                    <StatusChip ok={Boolean(apiStatus.user_groq_key_configured || apiStatus.key_status?.configured)} text={Boolean(apiStatus.user_groq_key_configured || apiStatus.key_status?.configured) ? "Configured" : "Missing"} />
                  </div>
                  <div className="status-card card-hover-lift">
                    <div className="small text-secondary mb-1">Server Env Key</div>
                    <StatusChip ok={Boolean(apiStatus.env_groq_key_configured)} text={apiStatus.env_groq_key_configured ? "Configured" : "Missing"} />
                  </div>
                </div>
              )}

              <form className="api-key-form" onSubmit={saveGroqKey}>
                <h6 className="fw-bold mb-2 d-flex align-items-center gap-2"><FiCpu /> Save Your Groq API Key</h6>
                <label className="form-label text-secondary small">Groq API Key</label>
                <div className="row g-2 align-items-center">
                  <div className="col-md-9">
                    <input
                      className="form-control"
                      type="password"
                      value={groqApiKey}
                      onChange={(event) => setGroqApiKey(event.target.value)}
                      placeholder="Paste your Groq API key"
                      autoComplete="off"
                    />
                  </div>
                  <div className="col-md-3 d-grid">
                    <button className="btn btn-dark btn-lift" type="submit" disabled={savingGroqKey}>{savingGroqKey ? "Saving..." : "Save Key"}</button>
                  </div>
                </div>
              </form>
            </div>
          )}

          {activeTab === "plan" && (
            <div className="dashboard-section">
              <SectionTitle icon={FiList} title="Generate Diet Plan" subtitle="Create your complete structured nutrition plan." />
              <form onSubmit={submitPlan}>
                <button type="submit" className="btn btn-success btn-lift d-inline-flex align-items-center gap-2" disabled={planLoading}><FiSend /> {planLoading ? "Generating..." : "Generate Plan"}</button>
              </form>

              {planResult.plan && (
                <div className="mt-3">
                  <div className="d-flex gap-2 mb-2 flex-wrap">
                    <button className="btn btn-outline-primary btn-lift d-inline-flex align-items-center gap-2" onClick={() => savePdfFromResponse(planResult.plan, planResult.model, planResult.calculated_targets, planResult.sources)}>
                      <FiDownload /> Download PDF
                    </button>
                    {lastPdfUrl && (
                      <a className="btn btn-outline-dark btn-lift" href={lastPdfUrl} target="_blank" rel="noreferrer">📄 Open Last Generated PDF</a>
                    )}
                  </div>
                  <div className="output-panel p-3 chat-answer-card">
                    <FormattedText text={planResult.plan} />
                  </div>

                  {(planResult.profile_warnings?.length > 0 || planResult.general_suggestions?.length > 0) && (
                    <div className="mt-3 row g-3">
                      <div className="col-md-6">
                        <h6 className="fw-bold">⚠️ Warnings</h6>
                        <ul className="mb-0">
                          {(planResult.profile_warnings || []).map((item, index) => <li key={index}>{item}</li>)}
                        </ul>
                      </div>
                      <div className="col-md-6">
                        <h6 className="fw-bold">💡 Suggestions</h6>
                        <ul className="mb-0">
                          {(planResult.general_suggestions || []).map((item, index) => <li key={index}>{item}</li>)}
                        </ul>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {(activeTab === "chat-health" || activeTab === "chat-suggestions") && (
            <div className="dashboard-section">
              <SectionTitle icon={FiMessageSquare} title={activeTab === "chat-health" ? "Health Chat" : "Suggestions Chat"} subtitle="Ask questions and review session history in one place." />
              <div className="d-flex gap-2 mb-2 flex-wrap">
                <button className="btn btn-outline-secondary btn-lift d-inline-flex align-items-center gap-2" onClick={() => loadSessions(activeTab)}><FiRefreshCcw /> Refresh Sessions</button>
                <button className="btn btn-outline-danger btn-lift d-inline-flex align-items-center gap-2" onClick={() => resetHistory(activeTab)}><FiTrash2 /> Reset Selected Session</button>
              </div>

              {chatSessions[activeTab === "chat-health" ? "health" : "suggestions"].length > 0 && (
                <div className="output-panel p-2 mb-3">
                  <div className="small text-secondary mb-2">Sessions (click to open history)</div>
                  <div className="d-flex flex-column gap-2">
                    {chatSessions[activeTab === "chat-health" ? "health" : "suggestions"].map((session, idx) => (
                      <button
                        key={session.session_id}
                        type="button"
                        className={`btn text-start session-btn session-btn-stagger ${activeChat.selectedSessionId === session.session_id ? "btn-primary" : "btn-outline-secondary"}`}
                        style={{ animationDelay: `${Math.min(idx * 45, 360)}ms` }}
                        onClick={() => loadHistory(activeTab, session.session_id)}
                      >
                        <div className="small fw-semibold">{session.session_id.slice(0, 8)} • {session.message_count} msgs</div>
                        <div className="small">{session.last_message?.slice(0, 120) || "No message"}</div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <form onSubmit={(event) => submitChatMessage(event, activeTab)}>
                <label className="form-label">Message</label>
                <textarea
                  className="form-control"
                  rows={4}
                  value={activeChat.message}
                  onChange={(event) => setChatStateByTab(activeTab, (previous) => ({ ...previous, message: event.target.value }))}
                  placeholder="Ask about food, meals, calories, swaps, hydration, or suggestions"
                  required
                />
                <button className="btn btn-primary mt-2 btn-lift d-inline-flex align-items-center gap-2" type="submit" disabled={activeChat.loading}>
                  <FiSend /> {activeChat.loading ? "Sending..." : "Send"}
                </button>
              </form>

              {activeChat.loading && (
                <div className="typing-indicator mt-3" aria-live="polite">
                  <span className="dot" />
                  <span className="dot" />
                  <span className="dot" />
                </div>
              )}

              {activeChat.assistantMessage && (
                <div className="output-panel p-3 mt-3 chat-answer-card">
                  <FormattedText text={activeChat.assistantMessage} />
                </div>
              )}

              {activeChat.history.length > 0 && (
                <div className="mt-3">
                  <h6 className="fw-bold">🗂️ Session History</h6>
                  <div className="output-panel p-3">
                    {activeChat.history.map((item, index) => (
                      <div key={index} className="mb-2 history-item history-item-stagger" style={{ animationDelay: `${Math.min(index * 50, 420)}ms` }}>
                        <div className="small text-secondary text-uppercase">{item.role}</div>
                        <FormattedText text={item.message} />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === "chat-debug" && (
            <div className="dashboard-section">
              <SectionTitle icon={FiShield} title="Diet Debug" subtitle="Upload and iteratively refine plan text with AI guidance." />
              <div className="d-flex gap-2 mb-3 flex-wrap">
                <button className="btn btn-outline-secondary btn-lift d-inline-flex align-items-center gap-2" onClick={() => loadSessions("chat-debug")}><FiRefreshCcw /> Refresh Sessions</button>
                <button className="btn btn-outline-danger btn-lift d-inline-flex align-items-center gap-2" onClick={() => resetDebugHistory()}><FiTrash2 /> Reset Selected Session</button>
              </div>

              {chatSessions.debug.length > 0 && (
                <div className="output-panel p-2 mb-3">
                  <div className="small text-secondary mb-2">Debug sessions (click to open history)</div>
                  <div className="d-flex flex-column gap-2">
                    {chatSessions.debug.map((session, idx) => (
                      <button
                        key={session.session_id}
                        type="button"
                        className={`btn text-start session-btn session-btn-stagger ${debugSelectedSessionId === session.session_id ? "btn-primary" : "btn-outline-secondary"}`}
                        style={{ animationDelay: `${Math.min(idx * 45, 360)}ms` }}
                        onClick={() => loadDebugHistory(session.session_id)}
                      >
                        <div className="small fw-semibold">{session.session_id.slice(0, 8)} • {session.message_count} msgs</div>
                        <div className="small">{session.last_message?.slice(0, 120) || "No message"}</div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="mb-3">
                <label className="form-label">Upload Existing Plan PDF</label>
                <input className="form-control" type="file" accept="application/pdf" onChange={extractDebugPlanFromPdf} />
              </div>

              <form onSubmit={submitDebugModify}>
                <div className="mb-2">
                  <label className="form-label">Current Plan Text</label>
                  <textarea className="form-control" rows={10} value={debugPlanText} onChange={(event) => setDebugPlanText(event.target.value)} required />
                </div>
                <div className="mb-2">
                  <label className="form-label">What do you want to change?</label>
                  <textarea className="form-control" rows={3} value={debugInstruction} onChange={(event) => setDebugInstruction(event.target.value)} required />
                </div>
                <button className="btn btn-warning btn-lift d-inline-flex align-items-center gap-2" type="submit" disabled={debugLoading}><FiSend /> {debugLoading ? "Updating..." : "Update Plan"}</button>
              </form>

              {debugLoading && (
                <div className="typing-indicator mt-3" aria-live="polite">
                  <span className="dot" />
                  <span className="dot" />
                  <span className="dot" />
                </div>
              )}

              {debugUpdatedPlan && (
                <div className="mt-3">
                  <div className="d-flex gap-2 mb-2">
                    <button className="btn btn-outline-primary btn-lift d-inline-flex align-items-center gap-2" onClick={() => savePdfFromResponse(debugUpdatedPlan, "debug-modifier", planResult.calculated_targets || {}, ["user_uploaded_pdf_modified"])}>
                      <FiDownload /> Download Updated Plan PDF
                    </button>
                  </div>
                  <div className="output-panel p-3 chat-answer-card">
                    <FormattedText text={debugUpdatedPlan} />
                  </div>
                </div>
              )}

              {debugHistory.length > 0 && (
                <div className="mt-3">
                  <h6 className="fw-bold">🗂️ Session History</h6>
                  <div className="output-panel p-3">
                    {debugHistory.map((item, index) => (
                      <div key={index} className="mb-2 history-item history-item-stagger" style={{ animationDelay: `${Math.min(index * 50, 420)}ms` }}>
                        <div className="small text-secondary text-uppercase">{item.role}</div>
                        <FormattedText text={item.message} />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === "pdf" && (
            <div className="dashboard-section">
              <SectionTitle icon={FiFileText} title="Last Generated PDF" subtitle="Open or download your latest export." />
              {!lastPdfUrl && <div className="text-secondary">No generated PDF yet. Generate a plan first.</div>}
              {lastPdfUrl && (
                <div className="d-flex gap-2">
                  <a className="btn btn-primary btn-lift d-inline-flex align-items-center gap-2" href={lastPdfUrl} download={lastPdfName}><FiDownload /> Download</a>
                  <a className="btn btn-outline-dark btn-lift d-inline-flex align-items-center gap-2" href={lastPdfUrl} target="_blank" rel="noreferrer"><FiFileText /> Open</a>
                </div>
              )}
            </div>
          )}

          {activeTab === "profile-settings" && (
            <div className="dashboard-section">
              <SectionTitle icon={FiSettings} title="Profile Settings" subtitle="Update identity settings and manage your account." />
              <form onSubmit={saveUserProfile} className="profile-card">
                <div className="row g-3">
                  <div className="col-md-6">
                    <ProfileInput label="Full Name">
                      <input className="form-control" value={accountName} onChange={(event) => setAccountName(event.target.value)} required />
                    </ProfileInput>
                  </div>
                  <div className="col-md-6">
                    <ProfileInput label="Email">
                      <input className="form-control" value={user?.email || ""} disabled />
                    </ProfileInput>
                  </div>
                </div>
                <div className="d-flex gap-2 mt-3 flex-wrap">
                  <button className="btn btn-primary btn-lift" type="submit" disabled={savingProfile}>
                    {savingProfile ? "Saving..." : "Save Profile"}
                  </button>
                  <button className="btn btn-outline-danger btn-lift" type="button" onClick={deleteMyAccount} disabled={deletingAccount}>
                    {deletingAccount ? "Deleting..." : "Delete Account"}
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
        </div>

        <div className="mobile-tabbar d-md-none">
          {menuTabs.map((item) => (
            <button
              key={`mobile-${item.key}`}
              className={`mobile-tab-item ${activeTab === item.key ? "active" : ""}`}
              onClick={() => setActiveTab(item.key)}
              type="button"
            >
              <item.icon className="mobile-tab-icon" aria-hidden="true" />
              <span className="mobile-tab-label">{item.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
