import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { PlayerBar } from "./components/PlayerBar";
import { FavoritesPage } from "./pages/FavoritesPage";
import { SearchPage } from "./pages/SearchPage";
import { usePlayer } from "./state/PlayerContext";

export function App() {
  const { state } = usePlayer();

  return (
    <div className={state.sound ? "app-shell with-player" : "app-shell"}>
      <header className="site-header">
        <h1>synthbud</h1>
        <nav className="site-nav">
          <NavLink to="/" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
            Search
          </NavLink>
          <NavLink to="/favorites" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
            Favorites
          </NavLink>
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
