-- 20261025184500 add_id_hash
-- 2026-10-25（维护者裁定 B）：身份核对码降级为「只用于生成唯一提交码、填完即丢」
--   · 客户端：18 位号码只在本机过一遍格式与校验位校验，算出一个不可逆校验码后立即丢弃原号；
--     本机只保留「末 4 位 + 不可逆校验码」（旧版本留的「前 6 位 + **** + 后 4 位」回显已删）。
--   · 云端：只回传末 4 位与那个不可逆校验码 ⇒ 施测人侧仍能识别「同一个人重复提交」，
--     但库里不再有任何能反推回号码的材料。
-- id_hash = SHA-256(18 位号码) 的前 16 位十六进制（大写）；不可逆。
ALTER TABLE public.responses ADD COLUMN IF NOT EXISTS id_hash TEXT;
CREATE INDEX IF NOT EXISTS responses_id_hash_idx ON public.responses (id_hash);
