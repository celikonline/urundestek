import { useEffect, useRef, useState } from "react";
import { EditorContent, useEditor, useEditorState } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import DOMPurify from "dompurify";
import {
  Bold,
  Italic,
  Underline,
  List,
  ListOrdered,
  Link2,
  Unlink,
  Undo2,
  Redo2,
  Paperclip,
  Send,
  X,
  FileText,
  Download,
  ImagePlus,
  Quote,
} from "lucide-react";
import type { Message } from "./types";

const ACCEPT = ".png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.csv,.docx,.xlsx";
const MAX_FILE = 10 * 1024 * 1024;
const MAX_TOTAL = 25 * 1024 * 1024;
export const fileSize = (size: number) =>
  size >= 1024 * 1024
    ? `${(size / 1024 / 1024).toFixed(1)} MB`
    : `${Math.max(1, Math.round(size / 1024))} KB`;

function FilePreview({ file }: { file: File }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    if (!file.type.startsWith("image/")) return;
    const value = URL.createObjectURL(file);
    setUrl(value);
    return () => URL.revokeObjectURL(value);
  }, [file]);
  return url ? <img src={url} alt="" /> : <FileText size={24} />;
}

export function MessageComposer({
  internal,
  busy,
  onSend,
}: {
  internal: boolean;
  busy: boolean;
  onSend: (payload: FormData) => Promise<boolean>;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const filesRef = useRef<File[]>([]);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [link, setLink] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const busyRef = useRef(busy);
  busyRef.current = busy;

  const addFiles = (incoming: File[]) => {
    if (busyRef.current) return;
    const current = filesRef.current;
    if (current.length + incoming.length > 5) {
      setError("Bir mesaja en fazla 5 dosya ekleyebilirsiniz.");
      return;
    }
    for (const file of incoming) {
      if (!/\.(png|jpe?g|webp|gif|pdf|txt|csv|docx|xlsx)$/i.test(file.name)) {
        setError("PNG, JPG, WEBP, GIF, PDF, TXT, CSV, DOCX veya XLSX seçin.");
        return;
      }
      if (!file.size || file.size > MAX_FILE) {
        setError("Dosya boş olmamalı ve 10 MB sınırını aşmamalı.");
        return;
      }
    }
    const next = [...current, ...incoming];
    if (next.reduce((size, file) => size + file.size, 0) > MAX_TOTAL) {
      setError("Dosyaların toplam boyutu en fazla 25 MB olabilir.");
      return;
    }
    filesRef.current = next;
    setFiles(next);
    setError("");
  };
  const addFilesRef = useRef(addFiles);
  addFilesRef.current = addFiles;
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: false,
        codeBlock: false,
        horizontalRule: false,
        link: { openOnClick: false, autolink: false },
      }),
    ],
    editorProps: {
      attributes: {
        role: "textbox",
        "aria-label": internal ? "İç not" : "Mesajınız",
        "aria-multiline": "true",
        class: "rich-input",
      },
      handlePaste: (_view, event) => {
        const pasted = Array.from(event.clipboardData?.items || [])
          .filter((item) => item.kind === "file")
          .map((item) => item.getAsFile())
          .filter((file): file is File => Boolean(file));
        if (!pasted.length) return false;
        event.preventDefault();
        addFilesRef.current(pasted);
        return true;
      },
      handleDrop: (_view, event, _slice, moved) => {
        if (moved || !event.dataTransfer?.files.length) return false;
        event.preventDefault();
        addFilesRef.current(Array.from(event.dataTransfer.files));
        return true;
      },
    },
  });
  const state = useEditorState({
    editor,
    selector: ({ editor: current }) =>
      current
        ? {
            bold: current.isActive("bold"),
            italic: current.isActive("italic"),
            underline: current.isActive("underline"),
            bullet: current.isActive("bulletList"),
            ordered: current.isActive("orderedList"),
            quote: current.isActive("blockquote"),
            link: current.isActive("link"),
            undo: current.can().undo(),
            redo: current.can().redo(),
            length: current.getText().trim().length,
          }
        : null,
  });
  useEffect(() => {
    if (!editor) return;
    editor.setOptions({
      editorProps: {
        ...editor.options.editorProps,
        attributes: {
          ...editor.options.editorProps.attributes,
          "aria-label": internal ? "İç not" : "Mesajınız",
        },
      },
    });
    editor.setEditable(!busy);
  }, [editor, internal, busy]);
  if (!editor) return null;
  const toolbar = (
    label: string,
    icon: React.ReactNode,
    active: boolean,
    action: () => void,
    disabled = false,
  ) => (
    <button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={active}
      disabled={busy || disabled}
      className={active ? "active" : ""}
      onClick={action}
    >
      {icon}
    </button>
  );
  return (
    <form
      className={`message-editor ${internal ? "private-editor" : ""} ${dragging ? "drop-active" : ""}`}
      onDragOver={(e) => {
        if (e.dataTransfer.types.includes("Files")) {
          e.preventDefault();
          setDragging(true);
        }
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node))
          setDragging(false);
      }}
      onDrop={(e) => {
        setDragging(false);
        if (e.dataTransfer.files.length && !e.defaultPrevented) {
          e.preventDefault();
          addFiles(Array.from(e.dataTransfer.files));
        }
      }}
      onSubmit={async (e) => {
        e.preventDefault();
        if (busy) return;
        const text = editor.getText().trim();
        if (text.length > 10000) {
          setError("Mesaj en fazla 10.000 karakter olabilir.");
          return;
        }
        if (text.length < 2 && !files.length) {
          setError("Mesaj yazın veya dosya ekleyin.");
          return;
        }
        const payload = new FormData();
        payload.set("body", text);
        payload.set("body_html", editor.getHTML());
        files.forEach((file) => payload.append("files", file));
        if (await onSend(payload)) {
          filesRef.current = [];
          setFiles([]);
          editor.commands.clearContent();
          setError("");
          setLinkOpen(false);
        }
      }}
    >
      <div
        className="editor-toolbar"
        role="group"
        aria-label="Metin biçimlendirme"
      >
        {toolbar("Kalın", <Bold size={18} />, state?.bold || false, () =>
          editor.chain().focus().toggleBold().run(),
        )}
        {toolbar("İtalik", <Italic size={18} />, state?.italic || false, () =>
          editor.chain().focus().toggleItalic().run(),
        )}
        {toolbar(
          "Altı çizili",
          <Underline size={18} />,
          state?.underline || false,
          () => editor.chain().focus().toggleUnderline().run(),
        )}
        <span className="toolbar-divider" />
        {toolbar(
          "Madde işaretli liste",
          <List size={18} />,
          state?.bullet || false,
          () => editor.chain().focus().toggleBulletList().run(),
        )}
        {toolbar(
          "Numaralı liste",
          <ListOrdered size={18} />,
          state?.ordered || false,
          () => editor.chain().focus().toggleOrderedList().run(),
        )}
        {toolbar("Alıntı", <Quote size={18} />, state?.quote || false, () =>
          editor.chain().focus().toggleBlockquote().run(),
        )}
        {toolbar(
          "Bağlantı ekle",
          <Link2 size={18} />,
          state?.link || false,
          () => {
            setLink(editor.getAttributes("link").href || "");
            setLinkOpen(!linkOpen);
          },
        )}
        {state?.link &&
          toolbar("Bağlantıyı kaldır", <Unlink size={18} />, false, () =>
            editor.chain().focus().unsetLink().run(),
          )}
        <span className="toolbar-divider" />
        {toolbar(
          "Geri al",
          <Undo2 size={18} />,
          false,
          () => editor.chain().focus().undo().run(),
          !state?.undo,
        )}
        {toolbar(
          "Yinele",
          <Redo2 size={18} />,
          false,
          () => editor.chain().focus().redo().run(),
          !state?.redo,
        )}
      </div>
      {linkOpen && (
        <div className="editor-link">
          <input
            autoFocus
            type="url"
            aria-label="Bağlantı adresi"
            placeholder="https://…"
            value={link}
            onChange={(e) => setLink(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.preventDefault();
            }}
          />
          <button
            type="button"
            className="button secondary"
            disabled={busy}
            onClick={() => {
              if (!/^(https?:\/\/|mailto:)/i.test(link.trim())) {
                setError(
                  "https:// veya mailto: ile başlayan bir bağlantı girin.",
                );
                return;
              }
              editor
                .chain()
                .focus()
                .extendMarkRange("link")
                .setLink({ href: link.trim() })
                .run();
              setLinkOpen(false);
              setError("");
            }}
          >
            Ekle
          </button>
          <button
            type="button"
            aria-label="Bağlantı alanını kapat"
            onClick={() => setLinkOpen(false)}
          >
            <X size={18} />
          </button>
        </div>
      )}
      <div className="editor-content">
        <EditorContent editor={editor} />
        {editor.isEmpty && (
          <span className="editor-placeholder">
            {internal
              ? "Ekip için notunuzu yazın…"
              : "Mesajınızı yazın… Ekran görüntüsünü Ctrl+V ile yapıştırabilirsiniz."}
          </span>
        )}
      </div>
      {files.length > 0 && (
        <div className="draft-files" aria-label="Gönderilecek dosyalar">
          {files.map((file, index) => (
            <div className="draft-file" key={`${file.name}-${index}`}>
              <FilePreview file={file} />
              <span>
                <b>{file.name}</b>
                <small>{fileSize(file.size)}</small>
              </span>
              <button
                type="button"
                aria-label={`${file.name} dosyasını kaldır`}
                disabled={busy}
                onClick={() => {
                  const next = files.filter((_, i) => i !== index);
                  filesRef.current = next;
                  setFiles(next);
                  setError("");
                }}
              >
                <X size={17} />
              </button>
            </div>
          ))}
        </div>
      )}
      {error && (
        <p className="editor-error" role="alert">
          {error}
        </p>
      )}
      <div className="editor-file-hint">
        <ImagePlus size={16} />
        <span>
          Dosya sürükleyin veya ekran görüntüsünü yapıştırın. En fazla 5 dosya ·
          10 MB/dosya.
        </span>
      </div>
      <div className="composer-actions">
        <input
          ref={input}
          type="file"
          multiple
          accept={ACCEPT}
          hidden
          aria-label="Mesaja dosya ekle"
          onChange={(e) => {
            addFiles(Array.from(e.target.files || []));
            e.target.value = "";
          }}
        />
        <button
          type="button"
          className="button secondary attach-button"
          disabled={busy}
          onClick={() => input.current?.click()}
        >
          <Paperclip size={18} />
          Dosya ekle
        </button>
        <span className="editor-count">
          {state?.length || 0}/10.000{internal && " · İç not"}
        </span>
        <button
          className="button primary"
          disabled={
            busy ||
            (!files.length && (state?.length || 0) < 2) ||
            (state?.length || 0) > 10000
          }
        >
          <Send size={17} />
          {busy ? "Gönderiliyor…" : internal ? "Notu kaydet" : "Mesajı gönder"}
        </button>
      </div>
    </form>
  );
}

export function MessageContent({ message }: { message: Message }) {
  return (
    <>
      {message.body_html ? (
        <div
          className="rich-message"
          dangerouslySetInnerHTML={{
            __html: DOMPurify.sanitize(message.body_html, {
              ALLOWED_TAGS: [
                "p",
                "br",
                "strong",
                "em",
                "u",
                "s",
                "ul",
                "ol",
                "li",
                "blockquote",
                "pre",
                "code",
                "h2",
                "h3",
                "a",
              ],
              ALLOWED_ATTR: ["href", "title", "rel"],
            }),
          }}
        />
      ) : (
        message.body && <p className="plain-message">{message.body}</p>
      )}
      {message.attachments?.length > 0 && (
        <div className="message-files">
          {message.attachments.map((file) => (
            <a
              key={file.id}
              href={`/api/v1/attachments/${file.id}`}
              className={`message-file ${file.content_type.startsWith("image/") ? "image-file" : ""}`}
              download={file.filename}
            >
              {file.content_type.startsWith("image/") ? (
                <img
                  src={`/api/v1/attachments/${file.id}?preview=true`}
                  alt={file.filename}
                  loading="lazy"
                />
              ) : (
                <FileText size={24} />
              )}
              <span>
                <b>{file.filename}</b>
                <small>{fileSize(file.size)} · İndir</small>
              </span>
              <Download size={17} />
            </a>
          ))}
        </div>
      )}
    </>
  );
}
