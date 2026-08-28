import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AssessmentMaintenanceBanner } from "./AssessmentMaintenanceBanner";

describe("AssessmentMaintenanceBanner", () => {
  it("维护开启时显示公告", () => {
    render(<AssessmentMaintenanceBanner status={{ active: true, message: "请勿重复提交。" }} />);

    expect(screen.getByRole("alert")).toHaveTextContent("系统正在维护中");
    expect(screen.getByRole("alert")).toHaveTextContent("请勿重复提交。");
  });

  it("维护关闭时不占页面空间", () => {
    render(<AssessmentMaintenanceBanner status={{ active: false, message: "" }} />);

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
