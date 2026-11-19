import { useState } from "react";
import { API } from "../api";
import { useNavigate, Link } from "react-router-dom";
import "../styles/Auth.css";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const login = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await API.post("/login", {
        username,
        password,
      });

      // Lưu token, role và user ID
      localStorage.setItem("token", res.data.token);
      localStorage.setItem("role", res.data.role);
      localStorage.setItem("user_id", res.data.id);

      // Route dựa trên role
      if (res.data.role === "admin") {
        navigate("/admin");
      } else if (res.data.role === "sales") {
        navigate("/sales");
      } else {
        // Fallback để tương thích với các role cũ
        navigate("/login");
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Đăng nhập thất bại. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-background"></div>
      
      <div className="auth-wrapper">
        <div className="auth-card">
          <div className="auth-header">
        <h1>Hệ thống Vận chuyển</h1>
            <p>Quản lý Giao hàng Thông minh</p>
          </div>

          <form className="auth-form" onSubmit={login}>
            <h2>Đăng nhập</h2>

            {error && <div className="error-message">{error}</div>}

            <div className="form-group">
              <label htmlFor="username">Tên đăng nhập hoặc Email</label>
              <input
                id="username"
                type="text"
                placeholder="Nhập tên đăng nhập hoặc email"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">Mật khẩu</label>
              <input
                id="password"
                type="password"
                placeholder="Nhập mật khẩu"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <div className="form-options">
              <Link to="/forgot-password" className="forgot-password">
                Quên mật khẩu?
              </Link>
            </div>

            <button 
              type="submit" 
              className="btn-login"
              disabled={loading}
            >
              {loading ? "Đang xử lý..." : "Đăng nhập"}
            </button>
          </form>

          <div className="auth-footer">
            <p>
              Chưa có tài khoản?{" "}
              <Link to="/register" className="register-link">
                Đăng ký ngay
              </Link>
            </p>
          </div>

          <div className="auth-info">
            <p className="info-title">Demo Accounts:</p>
            <div className="demo-accounts">
              <div className="demo-item">
                <strong>Admin:</strong> admin1 / Admin123!
              </div>
              <div className="demo-item">
                <strong>Sales (Auto-approved):</strong> sales1 / Sales123!
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
