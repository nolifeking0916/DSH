-- 20261025143000 add_m2_m3_raw_and_narrative
-- 1) responses 表补两列：第二项、第三项的**逐题作答**
--    为什么补：只有 m1_raw 时，人格特质能做题级检查（同侧作答、异常盲检），
--    情景处理与逻辑分析能力做不到 —— 报告里的「可信度」三项都要算。
--    补上之后，「一致性检查复核」「错题回顾」也能在服务端重算。
-- 2) 新表 report_narrative：**判读话术库**。
--    规则 = 分数档 × 维度 × 特征极 ⇒ 一段话术。
--    谁写：维护者与 HR 在库里直接改；谁用：云函数按分数匹配后下发。
--    候选人端**读不到**（只给 service_role）。
ALTER TABLE public.responses
  ADD COLUMN IF NOT EXISTS m2_answers JSONB,
  ADD COLUMN IF NOT EXISTS m3_answers JSONB;

CREATE TABLE IF NOT EXISTS public.report_narrative (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  module      TEXT NOT NULL,          -- personality | situation | reasoning | overall
  dimension   TEXT NOT NULL,          -- INT / regu / DED / __overall__
  band        TEXT NOT NULL,          -- 顶尖 / 优秀 / 良好 / 合格 / 待提升 / __all__
  pole        TEXT NOT NULL DEFAULT '__any__',  -- 人格特质的两极：a / b / __any__
  pole_label  TEXT,                   -- 两极的短标签（报告里显示「更偏…的一端」）
  kind        TEXT NOT NULL,          -- profile / fit / potential / strength / caution / conclusion / boundary / method
  title       TEXT,
  text        TEXT NOT NULL,
  sort        INTEGER NOT NULL DEFAULT 0,
  active      BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (module, dimension, band, pole, kind)
);
CREATE INDEX IF NOT EXISTS report_narrative_lookup ON public.report_narrative (module, dimension, band, pole) WHERE active;

ALTER TABLE public.report_narrative ENABLE ROW LEVEL SECURITY;
CREATE POLICY report_narrative_service_all ON public.report_narrative
  FOR ALL TO service_role USING (true) WITH CHECK (true);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.report_narrative TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.report_narrative_id_seq TO service_role;
