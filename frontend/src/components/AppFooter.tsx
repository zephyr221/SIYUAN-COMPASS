import { Link } from "react-router-dom";

export function AppFooter() {
  return (
    <footer className="site-footer">
      <div className="shell site-footer-inner">
        <span>交小航——你的AI生涯伙伴</span>
        <nav aria-label="页脚导航">
          <Link to="/privacy">隐私政策与数据管理</Link>
        </nav>
      </div>
    </footer>
  );
}
