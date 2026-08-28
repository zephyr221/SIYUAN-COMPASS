import { useEffect, useState } from "react";
import {
  fetchAssessmentMaintenance,
  type AssessmentMaintenanceStatus
} from "../api/maintenance";

const availableStatus: AssessmentMaintenanceStatus = {
  active: false,
  message: ""
};

export function useAssessmentMaintenance() {
  const [status, setStatus] = useState<AssessmentMaintenanceStatus>(availableStatus);

  useEffect(() => {
    const controller = new AbortController();
    fetchAssessmentMaintenance(controller.signal)
      .then(setStatus)
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  return status;
}

export function AssessmentMaintenanceBanner({ status }: { status: AssessmentMaintenanceStatus }) {
  if (!status.active) return null;

  return (
    <section className="maintenance-banner" role="alert">
      <strong>系统正在维护中</strong>
      <p>{status.message}</p>
    </section>
  );
}
