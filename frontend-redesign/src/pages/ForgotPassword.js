import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "../styles/Auth.css";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);

    // This is a placeholder - in production, you'd call your API
    try {
      // await API.post("/forgot-password", { email });
      setSuccess("Kiểm tra email của bạn để nhận hướng dẫn khôi phục mật khẩu!");
      setTimeout(() => {
        navigate("/");
      }, 3000);
    } catch (err) {
      setError("Đã có lỗi xảy ra. Vui lòng thử lại.");
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
            <p>Khôi phục mật khẩu</p>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            <h2>Quên Mật khẩu?</h2>

            <p style={{ color: "#666", marginBottom: "20px", fontSize: "14px" }}>
              Nhập địa chỉ email của bạn và chúng tôi sẽ gửi hướng dẫn để đặt lại mật khẩu.
            </p>

            {error && <div className="error-message">{error}</div>}
            {success && <div className="success-message">{success}</div>}

            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                placeholder="Nhập địa chỉ email của bạn"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <button 
              type="submit" 
              className="btn-login"
              disabled={loading}
            >
              {loading ? "Đang xử lý..." : "Gửi hướng dẫn khôi phục"}
            </button>
          </form>

          <div className="auth-footer">
            <p>
              Quay lại{" "}
              <Link to="/" className="register-link">
                Đăng nhập
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
