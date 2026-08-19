import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <main className="shell page not-found-page">
      <section className="panel empty-state">
        <span className="not-found-code">404</span>
        <h1>页面不存在</h1>
        <p>你访问的地址可能已变更或输入有误。</p>
        <Link className="button" to="/">返回首页</Link>
      </section>
    </main>
  );
}
