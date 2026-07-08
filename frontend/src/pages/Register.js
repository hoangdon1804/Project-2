import { useState } from "react";
import { API } from "../api";
import { useNavigate, Link } from "react-router-dom";
import "../styles/Auth.css";

export default function Register() {
  const [formData, setFormData] = useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
    full_name: "",
    phone: "",
    role: "sales",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [passwordValidation, setPasswordValidation] = useState({
    length: false,
    uppercase: false,
    number: false,
    special: false,
  });
  const navigate = useNavigate();

  // Kiểm tra mật khẩu theo các tiêu chí
  const validatePassword = (pwd) => {
    const validation = {
      length: pwd.length >= 8,
      uppercase: /[A-Z]/.test(pwd),
      number: /[0-9]/.test(pwd),
      special: /[!@#$%^&*(),.?":{}|<>]/.test(pwd),
    };
    setPasswordValidation(validation);
    return Object.values(validation).every(v => v === true);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    if (name === "password") {
      validatePassword(value);
    }
    setFormData({
      ...formData,
      [name]: value,
    });
  };

  const register = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    // Validation
    if (!formData.username.trim()) {
      setError("Vui lòng nhập tên đăng nhập!");
      return;
    }

    if (!formData.email.trim()) {
      setError("Vui lòng nhập email!");
      return;
    }

    // Kiểm tra định dạng email
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      setError("Vui lòng nhập email hợp lệ!");
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setError("Mật khẩu không khớp!");
      return;
    }

    // Kiểm tra mật khẩu đáp ứng các tiêu chí
    if (!validatePassword(formData.password)) {
      setError("Mật khẩu phải có ít nhất 8 ký tự, chứa 1 ký tự in hoa, 1 chữ số và 1 ký tự đặc biệt!");
      return;
    }

    setLoading(true);

    try {
      const response = await API.post("/register", {
        username: formData.username,
        email: formData.email,
        password: formData.password,
        role: formData.role,
        full_name: formData.full_name,
        phone: formData.phone,
      });

      const successMsg = response.data?.msg || "Đăng ký thành công!";
      setSuccess(successMsg + " Bạn sẽ được chuyển hướng đến trang đăng nhập...");
      
      setTimeout(() => {
        navigate("/");
      }, 2000);
    } catch (err) {
      setError(err.response?.data?.detail || "Đăng ký thất bại. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-background"></div>

      <div className="auth-wrapper">
        <div className="auth-card auth-card-register">
          <div className="auth-header">
        <h1>Hệ thống Vận chuyển</h1>
            <p>Tạo tài khoản mới</p>
          </div>

          <form className="auth-form" onSubmit={register}>
            <h2>Đăng ký</h2>

            {error && <div className="error-message">{error}</div>}
            {success && <div className="success-message">{success}</div>}

            <div className="form-group">
              <label htmlFor="username">Tên đăng nhập</label>
              <input
                id="username"
                type="text"
                name="username"
                placeholder="Nhập tên đăng nhập"
                value={formData.username}
                onChange={handleChange}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                name="email"
                placeholder="Nhập địa chỉ email"
                value={formData.email}
                onChange={handleChange}
                required
              />
            </div>

            <div className="form-group">
              <label>Vai trò</label>
              <input value="Sales" disabled />
              <div className="role-info">
                <p style={{ color: '#f39c12', fontSize: '12px', marginTop: '5px' }}>
                  Tài khoản sales cần được admin duyệt trước khi có thể đăng nhập. Vui lòng chờ.
                </p>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="password">Mật khẩu</label>
              <input
                id="password"
                type="password"
                name="password"
                placeholder="Nhập mật khẩu"
                value={formData.password}
                onChange={handleChange}
                required
              />
              
              {formData.password && (
                <div className="password-validation">
                  <div className={`validation-item ${passwordValidation.length ? 'valid' : 'invalid'}`}>
                {passwordValidation.length ? 'OK' : 'Chưa đạt'} Ít nhất 8 ký tự
                  </div>
                  <div className={`validation-item ${passwordValidation.uppercase ? 'valid' : 'invalid'}`}>
                {passwordValidation.uppercase ? 'OK' : 'Chưa đạt'} 1 ký tự in hoa
                  </div>
                  <div className={`validation-item ${passwordValidation.number ? 'valid' : 'invalid'}`}>
                {passwordValidation.number ? 'OK' : 'Chưa đạt'} 1 chữ số
                  </div>
                  <div className={`validation-item ${passwordValidation.special ? 'valid' : 'invalid'}`}>
                {passwordValidation.special ? 'OK' : 'Chưa đạt'} 1 ký tự đặc biệt (!@#$%^&*...)
                  </div>
                </div>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="confirmPassword">Xác nhận mật khẩu</label>
              <input
                id="confirmPassword"
                type="password"
                name="confirmPassword"
                placeholder="Nhập lại mật khẩu"
                value={formData.confirmPassword}
                onChange={handleChange}
                required
              />
            </div>

            <button 
              type="submit" 
              className="btn-login"
              disabled={loading}
            >
              {loading ? "Đang xử lý..." : "Đăng ký"}
            </button>
          </form>

          <div className="auth-footer">
            <p>
              Đã có tài khoản?{" "}
              <Link to="/" className="register-link">
                Đăng nhập tại đây
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
