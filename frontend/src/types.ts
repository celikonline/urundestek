export type User = {
  id: string;
  name: string;
  email: string;
  role: string;
  is_staff: boolean;
  tenant: { id: string; name: string; slug: string } | null;
  csrf_token: string;
  email_notifications: boolean;
  mail_enabled: boolean;
  password_changed_at: string | null;
  has_password: boolean;
};
export type Ticket = {
  id: string;
  number: number;
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  subject: string;
  category: string;
  priority: string;
  status: string;
  created_by: string;
  requester_name: string;
  assigned_to: string | null;
  assignee_name: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  unread: number;
  response_target: {
    hours: number;
    due_at: string;
    first_response_at: string | null;
    met: boolean | null;
  };
  rating: number | null;
  rating_comment: string | null;
  rated_at: string | null;
  can_rate: boolean;
  messages?: Message[];
  events?: { id: string; label: string; created_at: string }[];
};
export type Message = {
  id: string;
  body: string;
  body_html: string | null;
  attachments: Attachment[];
  kind: string;
  author_id: string;
  author_name: string;
  author_role: string;
  created_at: string;
};
export type Attachment = {
  id: string;
  filename: string;
  content_type: string;
  size: number;
};
export type TicketList = {
  items: Ticket[];
  total: number;
  page: number;
  page_size: number;
};
export type Reminder = {
  id: string;
  ticket_id: string;
  ticket_number: number;
  subject: string;
  due_at: string;
  note: string;
  status: string;
  notified: boolean;
};
export type Notice = {
  id: string;
  ticket_id: string;
  kind: string;
  text: string;
  read: boolean;
  created_at: string;
};
export type Tenant = {
  id: string;
  name: string;
  slug: string;
  external_id: string;
  active: boolean;
  ai_mode: string;
  ai_effective: string;
  open_count: number;
};
export type Staff = {
  id: string;
  name: string;
  email: string;
  role: string;
  active: boolean;
  locked: boolean;
  password_changed_at: string | null;
};
export type AuditEntry = {
  id: string;
  action: string;
  label: string;
  actor_id: string | null;
  actor_name: string;
  actor_role: string;
  tenant_id: string | null;
  target_type: string;
  target_id: string;
  detail: string;
  outcome: string;
  ip: string;
  correlation_id: string;
  created_at: string;
};
export type AuditList = {
  items: AuditEntry[];
  total: number;
  page: number;
  page_size: number;
  actions: Record<string, string>;
};
export type MailQueue = {
  enabled: boolean;
  counts: Record<string, number>;
  items: {
    id: string;
    status: string;
    kind: string;
    subject: string;
    recipient: string;
    ticket_id: string;
    ticket_number: number | null;
    attempts: number;
    last_error: string | null;
    created_at: string;
    sent_at: string | null;
  }[];
};
export type AdminSettings = {
  ai_available: boolean;
  ai_mode: string;
  ai_model: string;
  ai_max_auto_replies: number;
  auto_close_days: number;
  mail_enabled: boolean;
  staff_idle_minutes: number;
  login_lock_threshold: number;
  login_lock_minutes: number;
  retention: {
    audit_days: number;
    notification_days: number;
    mail_days: number;
    closed_ticket_days: number;
  };
};
export const STATUSES: Record<string, string> = {
  open: "Açık",
  in_progress: "İnceleniyor",
  waiting_customer: "Yanıtınız bekleniyor",
  resolved: "Çözüldü",
  closed: "Kapalı",
};
export const CATEGORIES: Record<string, string> = {
  general: "Genel",
  leaveAndOvertime: "İzin ve fazla mesai",
  payroll: "Bordro",
  dataTransfer: "Veri aktarımı",
  approvals: "Onaylar",
  accessAndPermissions: "Erişim ve yetkiler",
  billing: "Faturalandırma",
  other: "Diğer",
};
export const PRIORITIES: Record<string, string> = {
  normal: "Normal",
  high: "Yüksek",
  urgent: "Acil",
};
export type HelpArticle = { title: string; lines: string[] };
export const RATING_LABELS: Record<number, string> = {
  1: "Çok kötü",
  2: "Kötü",
  3: "Orta",
  4: "İyi",
  5: "Çok iyi",
};
export const AI_MODES: Record<string, string> = {
  inherit: "Varsayılanı kullan",
  off: "Kapalı",
  draft: "Taslak (yalnız ekibe)",
  auto: "Otomatik yanıt",
};
export const date = (value: string) =>
  new Intl.DateTimeFormat("tr-TR", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Istanbul",
  }).format(new Date(value));
export const initials = (name: string) =>
  name
    .split(" ")
    .map((x) => x[0])
    .slice(0, 2)
    .join("");
