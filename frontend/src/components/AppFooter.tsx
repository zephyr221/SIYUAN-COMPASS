import { Link } from "react-router-dom";

export function AppFooter() {
  return (
    <footer className="site-footer">
      <div className="shell site-footer-inner">
        <span>大学生生涯规划智能小助手</span>
        <nav aria-label="页脚导航">
          <Link to="/privacy">隐私政策与数据管理</Link>
        </nav>
      </div>
    </footer>
  );
}
