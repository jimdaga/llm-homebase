-- LiteLLM Routing Analysis Queries
-- Usage: psql $DATABASE_URL -f scripts/analyze_routing.sql
--
-- Or run individual queries:
-- psql $DATABASE_URL -c "SELECT ..."

-- ════════════════════════════════════════════════════════════════════════════════
-- 1. Tier Distribution (Last 7 Days)
-- ════════════════════════════════════════════════════════════════════════════════
-- Shows how many requests went to each tier

SELECT
  model,
  COUNT(*) as request_count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage,
  ROUND(SUM(spend)::numeric, 4) as total_cost,
  ROUND(AVG(total_tokens)::numeric, 2) as avg_tokens,
  ROUND(AVG(EXTRACT(EPOCH FROM ("endTime" - "startTime")))::numeric, 2) as avg_latency_sec
FROM "LiteLLM_SpendLogs"
WHERE
  "startTime" > NOW() - INTERVAL '7 days'
  AND model IN (
    'vertex_ai/claude-opus-4-6',
    'vertex_ai/claude-sonnet-4-5',
    'vertex_ai/claude-haiku-4-5'
  )
GROUP BY model
ORDER BY request_count DESC;

-- ════════════════════════════════════════════════════════════════════════════════
-- 2. Hourly Tier Distribution (Last 24 Hours)
-- ════════════════════════════════════════════════════════════════════════════════
-- Shows distribution over time to spot patterns

SELECT
  DATE_TRUNC('hour', "startTime") as hour,
  model,
  COUNT(*) as requests,
  ROUND(SUM(spend)::numeric, 4) as cost,
  ROUND(AVG(total_tokens)::numeric, 0) as avg_tokens
FROM "LiteLLM_SpendLogs"
WHERE
  "startTime" > NOW() - INTERVAL '24 hours'
  AND model IN (
    'vertex_ai/claude-opus-4-6',
    'vertex_ai/claude-sonnet-4-5',
    'vertex_ai/claude-haiku-4-5'
  )
GROUP BY DATE_TRUNC('hour', "startTime"), model
ORDER BY hour DESC, requests DESC;

-- ════════════════════════════════════════════════════════════════════════════════
-- 3. Daily Tier Distribution (Last 30 Days)
-- ════════════════════════════════════════════════════════════════════════════════
-- Shows daily trends over a month

SELECT
  DATE("startTime") as date,
  model,
  COUNT(*) as requests,
  ROUND(SUM(spend)::numeric, 2) as cost,
  ROUND(AVG(total_tokens)::numeric, 0) as avg_tokens
FROM "LiteLLM_SpendLogs"
WHERE
  "startTime" > NOW() - INTERVAL '30 days'
  AND model IN (
    'vertex_ai/claude-opus-4-6',
    'vertex_ai/claude-sonnet-4-5',
    'vertex_ai/claude-haiku-4-5'
  )
GROUP BY DATE("startTime"), model
ORDER BY date DESC, requests DESC;

-- ════════════════════════════════════════════════════════════════════════════════
-- 4. Most Expensive Requests (Top 20)
-- ════════════════════════════════════════════════════════════════════════════════
-- Identify which queries are using the most tokens/cost

SELECT
  "startTime",
  model,
  CASE
    WHEN "model" LIKE '%opus%' THEN 'REASONING'
    WHEN "model" LIKE '%sonnet%' THEN 'COMPLEX'
    WHEN "model" LIKE '%haiku%' THEN 'SIMPLE'
    ELSE 'OTHER'
  END as tier,
  total_tokens,
  ROUND(spend::numeric, 4) as cost,
  LEFT(metadata::text, 150) as metadata_preview
FROM "LiteLLM_SpendLogs"
WHERE "startTime" > NOW() - INTERVAL '7 days'
ORDER BY spend DESC, "startTime" DESC
LIMIT 20;

-- ════════════════════════════════════════════════════════════════════════════════
-- 5. Cost Summary by Tier
-- ════════════════════════════════════════════════════════════════════════════════
-- Total cost breakdown

SELECT
  CASE
    WHEN "model" LIKE '%opus%' THEN 'REASONING (Opus)'
    WHEN "model" LIKE '%sonnet%' THEN 'COMPLEX (Sonnet)'
    WHEN "model" LIKE '%haiku%' THEN 'SIMPLE (Haiku)'
    ELSE 'OTHER'
  END as tier,
  COUNT(*) as requests,
  ROUND(SUM(total_tokens)::numeric, 0) as total_tokens,
  ROUND(SUM(spend)::numeric, 2) as total_cost,
  ROUND(AVG(spend)::numeric, 4) as avg_cost_per_request,
  ROUND(AVG(total_tokens)::numeric, 0) as avg_tokens_per_request
FROM "LiteLLM_SpendLogs"
WHERE
  "startTime" > NOW() - INTERVAL '7 days'
  AND model IN (
    'vertex_ai/claude-opus-4-6',
    'vertex_ai/claude-sonnet-4-5',
    'vertex_ai/claude-haiku-4-5'
  )
GROUP BY tier
ORDER BY total_cost DESC;

-- ════════════════════════════════════════════════════════════════════════════════
-- 6. Routing Group Usage (Manual Tier Selection)
-- ════════════════════════════════════════════════════════════════════════════════
-- Track usage of manual routing groups (if configured)

SELECT
  model,
  COUNT(*) as requests,
  ROUND(SUM(spend)::numeric, 2) as cost,
  ROUND(AVG(total_tokens)::numeric, 0) as avg_tokens
FROM "LiteLLM_SpendLogs"
WHERE
  "startTime" > NOW() - INTERVAL '7 days'
  AND model IN (
    'architecture-tier',
    'implementation-tier',
    'quick-info'
  )
GROUP BY model
ORDER BY requests DESC;

-- ════════════════════════════════════════════════════════════════════════════════
-- 7. Request Status by Model
-- ════════════════════════════════════════════════════════════════════════════════
-- Show request status distribution

SELECT
  model,
  status,
  COUNT(*) as request_count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY model), 2) as percentage
FROM "LiteLLM_SpendLogs"
WHERE
  "startTime" > NOW() - INTERVAL '7 days'
  AND model IN (
    'vertex_ai/claude-opus-4-6',
    'vertex_ai/claude-sonnet-4-5',
    'vertex_ai/claude-haiku-4-5'
  )
GROUP BY model, status
ORDER BY model, request_count DESC;

-- ════════════════════════════════════════════════════════════════════════════════
-- 8. Response Time by Tier
-- ════════════════════════════════════════════════════════════════════════════════
-- Latency analysis

SELECT
  CASE
    WHEN "model" LIKE '%opus%' THEN 'REASONING (Opus)'
    WHEN "model" LIKE '%sonnet%' THEN 'COMPLEX (Sonnet)'
    WHEN "model" LIKE '%haiku%' THEN 'SIMPLE (Haiku)'
    ELSE 'OTHER'
  END as tier,
  COUNT(*) as requests,
  ROUND(MIN(EXTRACT(EPOCH FROM ("endTime" - "startTime")))::numeric, 2) as min_latency_sec,
  ROUND(AVG(EXTRACT(EPOCH FROM ("endTime" - "startTime")))::numeric, 2) as avg_latency_sec,
  ROUND(MAX(EXTRACT(EPOCH FROM ("endTime" - "startTime")))::numeric, 2) as max_latency_sec,
  ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM ("endTime" - "startTime")))::numeric, 2) as p95_latency_sec
FROM "LiteLLM_SpendLogs"
WHERE
  "startTime" > NOW() - INTERVAL '7 days'
  AND model IN (
    'vertex_ai/claude-opus-4-6',
    'vertex_ai/claude-sonnet-4-5',
    'vertex_ai/claude-haiku-4-5'
  )
GROUP BY tier
ORDER BY avg_latency_sec DESC;
