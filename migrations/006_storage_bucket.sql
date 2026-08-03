-- Создать публичный bucket channeldesk-assets (если ещё нет) — выполнить в Supabase SQL Editor.
-- Это делает вручную то же, что ensure_bucket в коде, но от полноправной роли postgres —
-- работает всегда.

INSERT INTO storage.buckets (id, name, public, file_size_limit)
VALUES ('channeldesk-assets', 'channeldesk-assets', true, 52428800)
ON CONFLICT (id) DO UPDATE SET public = true;

-- Разрешить анонимам загружать файлы в этот bucket (прямая загрузка из браузера)
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='storage' AND tablename='objects'
                 AND policyname='cd_anon_upload') THEN
    CREATE POLICY "cd_anon_upload" ON storage.objects FOR INSERT TO anon
    WITH CHECK (bucket_id = 'channeldesk-assets');
  END IF;
END $$;
