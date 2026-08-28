import { Link } from "react-router-dom";

export function AssessmentClosedPage() {
  return (
    <main className="shell page">
      <section className="panel">
        <h1>问卷填写已关闭</h1>
        <p className="lead">
          当前不再接收新的问卷填写、草稿保存或报告生成请求。此前已经保存的数据会保留并由项目维护人员另行处理。
        </p>
        <div className="actions" style={{ justifyContent: "flex-start" }}>
          <Link className="button secondary" to="/my-reports">查看已有报告</Link>
          <Link className="button secondary" to="/">返回首页</Link>
        </div>
      </section>
    </main>
  );
}
