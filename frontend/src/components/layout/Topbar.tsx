import { Menu, LogOut } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Button } from "../ui/button";

export function Topbar({ title, onMenu }: { title: string; onMenu: () => void }) {
  const { user, logout } = useAuth();
  return (
    <header className="flex items-center justify-between border-b border-border bg-app/80 px-4 py-3 backdrop-blur lg:px-6">
      <div className="flex items-center gap-3">
        <button onClick={onMenu} className="text-text-sec hover:text-text-prim lg:hidden" aria-label="Open menu">
          <Menu className="h-5 w-5" />
        </button>
        <h1 className="font-display text-lg font-semibold text-text-prim">{title}</h1>
      </div>
      <div className="flex items-center gap-3">
        {user && (
          <span className="hidden font-mono text-[11px] text-text-tert sm:inline">
            {user.username} · {user.role}
          </span>
        )}
        <Button variant="ghost" size="sm" onClick={logout}>
          <LogOut className="h-3.5 w-3.5" />
          Log out
        </Button>
      </div>
    </header>
  );
}
