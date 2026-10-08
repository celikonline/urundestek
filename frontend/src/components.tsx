import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { X, LifeBuoy, LoaderCircle, ArrowUpRight } from "lucide-react";
import { STATUSES } from "./types";

export function Brand() {
  return (
    <div className="brand">
      <span className="brand-symbol">
        <span />
        <span />
      </span>
      <span>
        Sense<span className="brand-light">İK</span>
        <small>DESTEK</small>
      </span>
    </div>
  );
}
export function Status({ value }: { value: string }) {
  return (
    <span className={`status ${value}`}>
      <i />
      {STATUSES[value] || value}
    </span>
  );
}
export function Loading() {
  return (
    <div className="empty">
      <LoaderCircle className="spin" size={24} />
      <p>Yükleniyor…</p>
    </div>
  );
}
export function Empty({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <LifeBuoy size={28} />
      </span>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current!;
    el.showModal();
    el.querySelector<HTMLElement>("input, textarea, select")?.focus();
    return () => el.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      aria-labelledby="modal-title"
    >
      <div className="modal-head">
        <h2 id="modal-title">{title}</h2>
        <button className="icon-btn" onClick={onClose} aria-label="Kapat">
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}
export function External({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <a className="button secondary" href={href} rel="noreferrer">
      {children}
      <ArrowUpRight size={16} />
    </a>
  );
}
