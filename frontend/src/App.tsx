import { Link, Navigate, Route, Routes } from "react-router-dom";
import { PlayerBar } from "./components/PlayerBar";
import { FavoritesPage } from "./pages/FavoritesPage";
import { SearchPage } from "./pages/SearchPage";

export function App() {
  return (
    <div className="app-shell">
      <header className="site-header">
        <h1>synthbud</h1>
        <nav>
          <Link to="/">Search</Link>
          <Link to="/favorites">Favorites</Link>
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<SearchPage />} />
        <Route path="/favorites" element={<FavoritesPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      <PlayerBar />
    </div>
  );
}
