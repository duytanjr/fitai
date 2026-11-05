"use client";

import { Button } from "@/components/ui/Button";

interface Props {
  message: string;
  confirmLabel: string;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Hộp xác nhận ngay trong trang (không dùng window.confirm). Văn bản thuần. */
export function ConfirmBox({ message, confirmLabel, busy, onConfirm, onCancel }: Props) {
  return (
    <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4 text-sm text-indigo-900" role="alertdialog"
         aria-live="polite">
      <p>{message}</p>
      <div className="mt-3 flex gap-2">
        <Button size="sm" onClick={onConfirm} loading={busy}>{confirmLabel}</Button>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={busy}>Huỷ</Button>
      </div>
    </div>
  );
}
