-- 20261025044500 create_responses_table
-- 真人试测结果表（票 #26 / 云上版 #33）。建表 + RLS + 授权。
--
-- 落库说明：MCP 的 applyMigration 因项目根指向 DSH profile 目录而拒绝写本地迁移文件，
-- 本次 DDL 走 execute（allowDdlViaExecute）执行，迁移历史未自动落库；
-- 本文件是仓内的可复现源文件，内容与实际执行的 SQL 一致。
--
-- 字段要点：
--   code            测评编号（唯一）；对外只显示后 4 位（ADR-0004）
--   m1_raw          第一项 96 题的逐题作答（0=a 侧 / 1=b 侧）★ 没有它算不出 α
--   m1_scores       客户端算分后的四维分与档位快照（JSONB）
--   limit_hint      到点痕迹 {at, answered}：到点只提示、不自动交卷（裁定 D3）
-- RLS：候选人（publishable key ⇒ anon）只能 INSERT，且必须带满 96 题；
--       读取/更新/删除只给 service_role（施测人管理面），候选人读不到别人的数据。
CREATE TABLE public.responses (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code          TEXT NOT NULL UNIQUE,
  respondent_name TEXT,
  id_last4      TEXT,
  group_name    TEXT,
  level         TEXT,
  dept          TEXT,
  started_at    TIMESTAMPTZ,
  submitted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  duration_ms   INTEGER,
  m1_raw        INTEGER[] NOT NULL,
  m1_scores     JSONB,
  m2_result     JSONB,
  m3_result     JSONB,
  limit_hint    JSONB,
  unanswered_m1 INTEGER,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.responses ENABLE ROW LEVEL SECURITY;
CREATE POLICY responses_anon_insert ON public.responses FOR INSERT TO anon WITH CHECK (array_length(m1_raw, 1) = 96);
CREATE POLICY responses_service_select ON public.responses FOR SELECT TO service_role USING (true);
CREATE POLICY responses_service_update ON public.responses FOR UPDATE TO service_role USING (true);
CREATE POLICY responses_service_delete ON public.responses FOR DELETE TO service_role USING (true);
GRANT INSERT ON public.responses TO anon;
GRANT SELECT, UPDATE, DELETE ON public.responses TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.responses_id_seq TO service_role;
