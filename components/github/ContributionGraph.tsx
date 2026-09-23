import type { GitHubActivity } from "@/types";

interface ContributionGraphProps {
  activity: GitHubActivity;
}

// Placeholder — will render the GitHub contribution calendar + recent repo updates.
export function ContributionGraph({ activity }: ContributionGraphProps) {
  return <div>{activity.commits} commits in {activity.repository}</div>;
}
