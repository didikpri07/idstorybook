import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import "@/App.css";
import "@/Language.css";

import { AuthProvider } from "@/context/AuthContext";
import { ProtectedRoute, AdminRoute } from "@/components/ProtectedRoute";

import Home from "@/pages/Home";
import Create from "@/pages/Create";
import StorybookPage from "@/pages/Storybook";
import Checkout from "@/pages/Checkout";
import CheckoutCancel from "@/pages/CheckoutCancel";
import Dashboard from "@/pages/Dashboard";
import Admin from "@/pages/Admin";
import Login from "@/pages/Login";
import AuthCallback from "@/pages/AuthCallback";
import PasswordReset from "@/pages/PasswordReset";
import "@/Phase2.css";
import "@/Pricing.css";
import Pricing from '@/pages/Pricing';
import AdminPricing from '@/pages/AdminPricing';
import Payment from '@/pages/Payment';
import { PricingProvider } from '@/context/PricingContext';

function AppRouter() {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Login />} />
      <Route path="/forgot-password" element={<PasswordReset />} />
      <Route path="/reset-password" element={<PasswordReset />} />
      <Route path="/create" element={<Create />} />
      <Route path="/pricing" element={<Pricing />} />
      <Route path="/payment/:orderId" element={<ProtectedRoute><Payment /></ProtectedRoute>} />
      <Route path="/storybook/:id" element={<StorybookPage />} />
      <Route path="/checkout" element={<ProtectedRoute><Checkout /></ProtectedRoute>} />
      <Route path="/checkout/success" element={<ProtectedRoute><Payment /></ProtectedRoute>} />
      <Route path="/checkout/cancel" element={<CheckoutCancel />} />
      <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
      <Route path="/admin" element={<AdminRoute><Admin /></AdminRoute>} />
      <Route path="/admin/pricing" element={<AdminRoute><AdminPricing /></AdminRoute>} />
    </Routes>
  );
}

export default function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <PricingProvider><AppRouter /></PricingProvider>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}
