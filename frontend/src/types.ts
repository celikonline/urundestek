export type User = {
  id: string;
  name: string;
  email: string;
  role: string;
  is_staff: boolean;
  tenant: { id: string; name: string; slug: string } | null;
  csrf_token: string;
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
  open_count: number;
};
export type Staff = {
  id: string;
  name: string;
  email: string;
  role: string;
  active: boolean;
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
