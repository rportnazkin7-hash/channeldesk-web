-- Настройка bucket для вложений ChannelDesk.
-- Выполнять в Supabase SQL Editor ОТДЕЛЬНО, по одному блоку, чтобы видеть ошибки.

-- Блок 1: создать публичный bucket (id = name = 'channeldesk-assets', лимит 50 МБ)
INSERT INTO storage.buckets (id, name, public, file_size_limit)
VALUES ('channeldesk-assets', 'channeldesk-assets', true, 52428800)
ON CONFLICT (id) DO UPDATE SET public = true;

-- Блок 2 (НЕ ОБЯЗАТЕЛЕН, если создадите политику через UI):
-- Политика на загрузку для анонимов. ВАЖНО: если SQL Editor ответит
-- "ERROR: 42501: must be owner of table objects" — создайте политику вручную:
--   Supabase → Storage → channeldesk-assets → Policies → New policy →
--   INSERT · role: anon · WITH CHECK: bucket_id = 'channeldesk-assets'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='storage' AND tablename='objects'
                 AND policyname='cd_anon_upload') THEN
    CREATE POLICY "cd_anon_upload" ON storage.objects FOR INSERT TO anon
    WITH CHECK (bucket_id = 'channeldesk-assets');
  END IF;
END $$;
