import { Navigate, Route, Routes } from "react-router-dom";
import Landing from "./Landing";
import PlaybookChat from "./PlaybookChat";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("access_token");
  return token ? <>{children}</> : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route
        path="/chat"
        element={
          <PrivateRoute>
            <PlaybookChat />
          </PrivateRoute>
        }
      />
      {/* Catch-all: redirect unknown paths to root */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
