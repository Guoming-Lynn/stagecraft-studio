/** Decide whether a finished run may raise a desktop notice. Permission stays with the browser. */

export function shouldNotify(
  before: string,
  after: string,
  permission: string,
): boolean {
  const wasRunning = before === "running" || before === "starting";
  const finished = after !== "" && after !== "running" && after !== "starting";
  return wasRunning && finished && permission === "granted";
}

export function noticePermission(): string {
  if (typeof Notification === "undefined") return "denied";
  return Notification.permission;
}
