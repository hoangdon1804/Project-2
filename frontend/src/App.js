import {BrowserRouter,Routes,Route, Navigate} from "react-router-dom";

import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import AdminDashboard from "./pages/AdminDashboard";
import SalesDashboard from "./pages/SalesDashboard";
import CustomerDashboard from "./pages/CustomerDashboard";

// Bảo vệ route - nếu không có token thì chuyển hướng về login
const ProtectedRoute = ({ element, requiredRole }) => {
  const token = localStorage.getItem("token");
  const role = localStorage.getItem("role");

  if (!token) {
    return <Navigate to="/" />;
  }

  if (requiredRole && role !== requiredRole) {
    return <Navigate to="/" />;
  }

  return element;
};

function App(){
  return(
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login/>}/>
        <Route path="/login" element={<Login/>}/>
        <Route path="/register" element={<Register/>}/>
        <Route path="/forgot-password" element={<ForgotPassword/>}/>
        <Route path="/admin" element={<ProtectedRoute element={<AdminDashboard/>} requiredRole="admin" />}/>
        <Route path="/sales" element={<ProtectedRoute element={<SalesDashboard/>} requiredRole="sales" />}/>
        <Route path="/customer" element={<ProtectedRoute element={<CustomerDashboard/>} requiredRole="customer" />}/>
        {/* Legacy routes para tương thích */}
        <Route path="/shipper" element={<Navigate to="/sales" />}/>
        <Route path="/user" element={<Navigate to="/customer" />}/>
        <Route path="/manager" element={<Navigate to="/admin" />}/>
      </Routes>
    </BrowserRouter>
  );
}

export default App;