"""Synthetic package check; does not access any actual user/provider state."""
from datetime import datetime,timezone
import json
from src.domain.effort import UserEstimate,select_budget
from src.domain.time_windows import forecast_window


def domain_smoke():
    now = datetime(2026,1,1,tzinfo=timezone.utc)
    estimate = UserEstimate(1800,"synthetic-observation",now,now)
    budget = select_budget(task_id="synthetic-package-task",task_revision=1,snapshot_at=now,user_estimate=estimate,prediction=None)
    window = forecast_window(now,3)
    return {"scope":"SYNTHETIC_PACKAGE_CHECK","budget_seconds":budget.seconds,"budget_source":budget.source,"beijing_start_date":window.start_date.isoformat(),"beijing_end_date":window.end_date.isoformat(),"canonical_user_seconds":estimate.seconds}


def main():
    print(json.dumps(domain_smoke(),sort_keys=True))
    return 0


if __name__=="__main__":raise SystemExit(main())
