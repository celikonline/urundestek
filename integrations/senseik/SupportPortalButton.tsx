// Copy into senseik/web/src/components/support-portal-button.tsx.
import { useState } from 'react';
import { Button } from '@mantine/core';
import { LifeBuoy } from 'lucide-react';
import { AUTH_TOKEN_STORAGE_KEY } from '@senseik/api-client';
import { toast } from '@/hooks/use-toast';

export function SupportPortalButton() {
  const [busy, setBusy] = useState(false);
  const open = async () => {
    const portal = import.meta.env.VITE_SUPPORT_PORTAL_URL;
    if (!portal) { toast({description:'Destek portalı henüz yapılandırılmadı.',variant:'destructive'}); return; }
    setBusy(true);
    try {
      const token = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
      if (!token) throw new Error('SenseİK oturumunuz sona erdi. Tekrar giriş yapın.');
      const response = await fetch(`${portal.replace(/\/$/, '')}/api/v1/auth/launch`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` }, credentials: 'omit',
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Destek portalı açılamadı.');
      const destination = new URL(data.url);
      if (destination.origin !== new URL(portal).origin) throw new Error('Destek adresi doğrulanamadı.');
      window.location.assign(destination.href);
    } catch (error) {
      toast({description:error instanceof Error ? error.message : 'Destek portalı açılamadı.',variant:'destructive'});
    } finally { setBusy(false); }
  };
  return <Button leftSection={<LifeBuoy size={17} />} loading={busy} onClick={() => void open()}>Destek portalını aç</Button>;
}
