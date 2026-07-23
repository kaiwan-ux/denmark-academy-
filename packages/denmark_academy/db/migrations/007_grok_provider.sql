ALTER TABLE ai_providers DROP CONSTRAINT IF EXISTS ai_providers_provider_key_check;
ALTER TABLE ai_providers
  ADD CONSTRAINT ai_providers_provider_key_check
  CHECK (provider_key IN ('ollama', 'openai', 'anthropic', 'gemini', 'grok', 'disabled'));

INSERT INTO ai_providers (provider_key, display_name, is_enabled, default_model, config)
VALUES ('grok', 'Grok / Groq OpenAI-compatible', true, 'llama-3.3-70b-versatile', '{"base_url":"https://api.groq.com/openai/v1"}'::jsonb)
ON CONFLICT (provider_key) DO UPDATE
SET is_enabled = EXCLUDED.is_enabled,
    default_model = COALESCE(ai_providers.default_model, EXCLUDED.default_model),
    config = ai_providers.config || EXCLUDED.config,
    updated_at = now();

UPDATE ai_providers
SET is_enabled = true,
    default_model = COALESCE(default_model, 'gemini-2.5-flash'),
    config = config || '{"base_url":"https://generativelanguage.googleapis.com/v1beta"}'::jsonb,
    updated_at = now()
WHERE provider_key = 'gemini';