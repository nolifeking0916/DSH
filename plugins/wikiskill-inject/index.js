/**
 * wikiskill-inject —— WikiSkill 执行层注入器。
 *
 * 论文对应：§3.2.1「技能 provision」——执行者只带**技能索引**，不读 wiki 正文。
 * 因此本插件只注入：①按当前问题命中的技能名 + 一句描述；②wiki 里**相关经验的标题与结论一句话**
 * （不是全文，全文由 `skill` 工具或读文件获得）。
 *
 * 与 memos-autoinject 的分工：那个注入"历史记忆（事实）"，本插件注入"能力清单 + 方法论索引"。
 *
 * 约束：零依赖、fail-open、每轮只注入一次、总量 ≤ maxChars、缓存避免每轮读盘。
 *
 * @module @local/wikiskill-inject
 */

export const name = 'wikiskill-inject';

const DEFAULTS = {
  enabled: true,
  skillsDir: '/Users/leto/.dsh/skills',
  wikiDir: '/Users/leto/.dsh/wiki',
  maxSkills: 6,
  maxPatterns: 3,
  maxChars: 700,
  cacheMs: 60000,
  injectStep: 1,
  debugLog: '',
  // 向量检索（MemOS rerank）：失败自动回退关键词匹配
  apiBase: 'https://memos.memtensor.cn/api/openmem/v1',
  apiKeyEnv: 'MEMOS_API_KEY',
  apiKey: '',
  rerankTimeoutMs: 1500,
  rerankThreshold: 0.25,
  rerankMaxDocs: 60,
  // 主路径：MemOS 知识库里的 Skill 文件语义检索
  kbId: '',
  userId: 'HR',
  skillThreshold: 0.4,
  skillTimeoutMs: 1500,
  skillLimit: 25,

};

const SOURCE_KIND = 'wikiskill-context';

async function debugLog(path, message) {
  if (typeof path !== 'string' || path.length === 0) return;
  try {
    const { appendFile } = await import('node:fs/promises');
    await appendFile(path, `${new Date().toISOString()} ${message}\n`, 'utf8');
  } catch {
    /* 日志失败不影响主流程 */
  }
}

/** 极简 YAML frontmatter 解析（只取标量字段，够用即可）。 */
function parseFrontmatter(text) {
  const match = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text);
  if (!match) return {};
  const out = {};
  const lines = match[1].split(/\r?\n/);
  for (let i = 0; i < lines.length; i += 1) {
    const kv = /^([A-Za-z0-9_-]+):\s*(.*)$/.exec(lines[i]);
    if (!kv) continue;
    let value = kv[2].trim();
    // 折叠/字面块：吃掉后续缩进行
    if (value === '>' || value === '|' || value === '>-' || value === '|-') {
      const buf = [];
      while (i + 1 < lines.length && /^\s+\S/.test(lines[i + 1])) {
        buf.push(lines[i + 1].trim());
        i += 1;
      }
      value = buf.join(value.startsWith('>') ? ' ' : '\n');
    } else if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    out[kv[1]] = value;
  }
  return out;
}

/** 把查询切成可用于匹配的词元（中文取 2-gram，英文取单词）。 */
function tokens(query) {
  const set = new Set();
  const lower = String(query ?? '').toLowerCase();
  for (const word of lower.match(/[a-z0-9][a-z0-9_-]{1,}/g) ?? []) set.add(word);
  const han = lower.replace(/[^\u4e00-\u9fa5]/g, ' ');
  for (const run of han.split(/\s+/)) {
    for (let i = 0; i + 2 <= run.length; i += 1) set.add(run.slice(i, i + 2));
  }
  return set;
}

function hits(toks, text) {
  const hay = String(text ?? '').toLowerCase();
  let n = 0;
  for (const t of toks) if (hay.includes(t)) n += 1;
  return n;
}

/** 读取技能索引（name + description 摘要）。 */
async function loadSkills(dir) {
  const { readdir, readFile } = await import('node:fs/promises');
  const path = await import('node:path');
  let entries = [];
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return [];
  }
  const skills = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    try {
      const text = await readFile(path.join(dir, entry.name, 'SKILL.md'), 'utf8');
      const fm = parseFrontmatter(text);
      const name = (fm.name || entry.name).trim();
      const description = (fm.description || '').replace(/\s+/g, ' ').trim();
      skills.push({ name, description, dir: entry.name });
    } catch {
      /* 没有 SKILL.md 的目录跳过 */
    }
  }
  return skills;
}

/** 读取 wiki 模式（status: active 才算正式经验）。 */
async function loadPatterns(wikiDir) {
  const { readdir, readFile } = await import('node:fs/promises');
  const path = await import('node:path');
  const dir = path.join(wikiDir, 'patterns');
  let names = [];
  try {
    names = (await readdir(dir)).filter((n) => n.endsWith('.md'));
  } catch {
    return [];
  }
  const patterns = [];
  for (const file of names) {
    try {
      const text = await readFile(path.join(dir, file), 'utf8');
      const fm = parseFrontmatter(text);
      if ((fm.status || 'active') !== 'active') continue;
      // 结论行：取正文里第一个 "## 可复用做法" 之后的非空行
      const body = text.replace(/^---[\s\S]*?---/, '');
      const m = /##\s*(?:可复用做法|做法|结论)\s*\n+([^\n#]+)/.exec(body);
      const takeaway = (m?.[1] || '').trim();
      patterns.push({
        id: fm.id || file.replace(/\.md$/, ''),
        title: fm.title || file.replace(/\.md$/, ''),
        tags: fm.tags || '',
        takeaway,
        file,
      });
    } catch {
      /* 单条读取失败忽略 */
    }
  }
  return patterns;
}

function makeCache(loader, ttl) {
  let value = null;
  let at = 0;
  return async () => {
    const now = Date.now();
    if (value !== null && now - at < ttl) return value;
    value = await loader();
    at = now;
    return value;
  };
}

/**
 * 主路径：从 MemOS 知识库检索 Skill 文件（服务端语义排序）。
 * @returns [{name, description, score}] 或 null（失败时回退 rerank / 关键词）
 */
async function searchSkillsKb(cfg, query, signal, log) {
  if (!cfg.apiKey || !cfg.kbId) return null;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), cfg.skillTimeoutMs);
  const relay = () => controller.abort();
  if (signal && typeof signal.addEventListener === 'function') signal.addEventListener('abort', relay, { once: true });
  const started = Date.now();
  try {
    const response = await fetch(`${cfg.apiBase}/search/memory`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Token ${cfg.apiKey}` },
      body: JSON.stringify({
        query,
        user_id: cfg.userId,
        memory_limit_number: cfg.skillLimit,
        relativity: cfg.skillThreshold,
        include_memory_view: ['skill'],
        knowledgebase_ids: [cfg.kbId],
      }),
      signal: controller.signal,
    });
    if (!response.ok) { log(`kb: http ${response.status}`); return null; }
    const payload = await response.json();
    if (!payload || payload.code !== 0) { log(`kb: code ${payload?.code}`); return null; }
    const rows = payload.data?.skill_detail_list || [];
    const picked = rows
      .map((r) => ({
        name: r?.skill_value?.name || '',
        description: r?.skill_value?.description || '',
        score: Number(r?.relativity) || 0,
      }))
      .filter((x) => x.name.length > 0 && x.score >= (query.length < 10 ? Math.max(cfg.skillThreshold, 0.6) : cfg.skillThreshold))
      .slice(0, cfg.maxSkills);
    log(`kb: rows=${rows.length} picked=${picked.length} ms=${Date.now() - started} top=${picked[0]?.score?.toFixed(2) ?? '-'}`);
    return picked;
  } catch (error) {
    log(`kb: failed ${String(error?.message ?? error).slice(0, 120)}`);
    return null;
  } finally {
    clearTimeout(timer);
    if (signal && typeof signal.removeEventListener === 'function') signal.removeEventListener('abort', relay);
  }
}

/**
 * 用 MemOS reranker 对「技能描述 + wiki 经验」做语义排序。
 * @returns {skills, patterns} 或 null（失败时由调用方回退关键词匹配）。
 */
async function rerankMatch(cfg, query, skills, patterns, signal, log) {
  if (!cfg.apiKey) return null;
  const docs = [
    ...skills.map((s) => ({ kind: 'skill', ref: s, text: `${s.name}：${s.description.slice(0, 220)}` })),
    ...patterns.map((p) => ({ kind: 'pattern', ref: p, text: `${p.title}：${(p.takeaway || p.tags || '').slice(0, 160)}` })),
  ].slice(0, cfg.rerankMaxDocs);
  if (docs.length === 0) return null;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), cfg.rerankTimeoutMs);
  const relay = () => controller.abort();
  if (signal && typeof signal.addEventListener === 'function') signal.addEventListener('abort', relay, { once: true });
  const started = Date.now();
  try {
    const response = await fetch(`${cfg.apiBase}/rerank`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Token ${cfg.apiKey}` },
      body: JSON.stringify({
        query,
        documents: docs.map((d) => d.text),
        top_n: Math.min(cfg.maxSkills + cfg.maxPatterns + 4, docs.length),
      }),
      signal: controller.signal,
    });
    if (!response.ok) { log(`rerank: http ${response.status}`); return null; }
    const payload = await response.json();
    if (!payload || payload.code !== 0) { log(`rerank: code ${payload?.code}`); return null; }
    const results = payload.data?.results || [];
    // 短句（<10 字）信息量低，reranker 也会给 0.5 左右的中等分，抬高阈值压噪声
    const threshold = query.length < 10 ? Math.max(cfg.rerankThreshold, 0.6) : cfg.rerankThreshold;
    const scored = results
      .map((r) => ({ ...docs[r.index], score: Number(r.relevance_score) || 0 }))
      .filter((x) => x.ref && x.score >= threshold)
      .sort((a, b) => b.score - a.score);
    const picked = {
      skills: scored.filter((x) => x.kind === 'skill').slice(0, cfg.maxSkills).map((x) => x.ref),
      patterns: scored.filter((x) => x.kind === 'pattern').slice(0, cfg.maxPatterns).map((x) => x.ref),
      scores: scored.slice(0, 5).map((x) => `${x.kind}:${x.score.toFixed(2)}`).join(','),
    };
    log(`rerank: docs=${docs.length} picked=${picked.skills.length}+${picked.patterns.length} ms=${Date.now() - started} top=[${picked.scores}]`);
    return picked;
  } catch (error) {
    log(`rerank: failed ${String(error?.message ?? error).slice(0, 120)}`);
    return null;
  } finally {
    clearTimeout(timer);
    if (signal && typeof signal.removeEventListener === 'function') signal.removeEventListener('abort', relay);
  }
}

function render(skills, patterns, maxChars) {
  const lines = [];
  if (skills.length > 0) {
    lines.push('可用技能（命中即用 `skill` 工具加载，不要凭记忆猜用法）：');
    for (const s of skills) {
      let desc = String(s.description || '').replace(/^["']|["']$/g, '');
      desc = desc.length > 46 ? `${desc.slice(0, 45)}…` : desc;
      lines.push(`- ${s.name}：${desc}`);
    }
  }
  if (patterns.length > 0) {
    lines.push('相关经验（来自 wiki，仅供指路，细节读原文件）：');
    for (const p of patterns) {
      const tail = p.takeaway ? `（${p.takeaway.slice(0, 60)}）` : '';
      lines.push(`- ${p.title}${tail} → ${p.file}`);
    }
  }
  if (lines.length === 0) return '';
  const text = ['<skill_context>', ...lines, '</skill_context>'].join('\n');
  return text.length > maxChars ? `${text.slice(0, maxChars - 1)}…\n</skill_context>` : text;
}

/** 剥离系统注入块，只留用户真实输入（否则检索/匹配会被注入文本污染）。 */
function cleanQuery(text) {
  let s = String(text ?? '');
  s = s.replace(/<system-reminder[\s\S]*?<\/system-reminder>/g, ' ');
  s = s.replace(/<memos_context>[\s\S]*?<\/memos_context>/g, ' ');
  s = s.replace(/<skill_context>[\s\S]*?<\/skill_context>/g, ' ');
  s = s.split('\n')
    .filter((line) => !/^\s*【/.test(line))
    .filter((line) => !/^(Current runtime context|This snapshot supersedes|Instructions from:)/.test(line))
    .join('\n');
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

function lastUserText(messages) {
  if (!Array.isArray(messages)) return '';
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message === null || typeof message !== 'object') continue;
    if (message.role !== 'user') continue;
    if (message.source !== null && typeof message.source === 'object'
      && (message.source.kind === SOURCE_KIND || message.source.kind === 'memos-recall')) continue;
    const content = message.content;
    if (typeof content === 'string') {
      if (content.trim().length > 0) return cleanQuery(content);
      continue;
    }
    if (!Array.isArray(content)) continue;
    const text = content
      .filter((b) => b !== null && typeof b === 'object' && b.type === 'text' && typeof b.text === 'string')
      .map((b) => b.text)
      .join('\n')
      .trim();
    if (text.length > 0) return cleanQuery(text);
  }
  return '';
}

function resolveConfig(config) {
  const merged = { ...DEFAULTS, ...(config !== null && typeof config === 'object' ? config : {}) };
  const envKey = typeof merged.apiKeyEnv === 'string' && merged.apiKeyEnv.length > 0
    ? process.env[merged.apiKeyEnv] : undefined;
  merged.apiKey = typeof envKey === 'string' && envKey.trim().length > 0 ? envKey.trim() : String(merged.apiKey ?? '').trim();
  merged.enabled = merged.enabled !== false;
  return merged;
}

export function apply(ctx, config) {
  const cfg = resolveConfig(config);
  void debugLog(cfg.debugLog, `apply: enabled=${cfg.enabled} skills=${cfg.skillsDir} wiki=${cfg.wikiDir}`);
  if (!cfg.enabled) return;

  const skillsCache = makeCache(() => loadSkills(cfg.skillsDir), cfg.cacheMs);
  const patternsCache = makeCache(() => loadPatterns(cfg.wikiDir), cfg.cacheMs);

  const handler = async ({ agent, messages, step, signal }, next) => {
    const decision = await next();
    try {
      if (decision === null || typeof decision !== 'object') return decision;
      if (decision.kind === 'reject') return decision;
      if (step !== cfg.injectStep) return decision;
      const claimed = Array.isArray(decision.messages) ? decision.messages : [];
      const query = lastUserText(claimed);
      if (query.length < 2 || query.length > 4000) return decision;
      const toks = tokens(query);

      const [skills, patterns] = await Promise.all([skillsCache(), patternsCache()]);
      // ① 主路径：知识库 Skill 语义检索
      const kbSkills = await searchSkillsKb(cfg, query, signal, (m) => void debugLog(cfg.debugLog, m));
      if (kbSkills !== null && kbSkills.length > 0) {
        // 经验仍用本地匹配（数据量小）；技能用服务端语义结果
        const toks0 = tokens(query);
        const localPatterns = patterns
          .map((p) => ({ p, score: hits(toks0, `${p.title} ${p.tags} ${p.takeaway}`) }))
          .filter((x) => x.score > 0)
          .sort((a, b) => b.score - a.score)
          .slice(0, cfg.maxPatterns)
          .map((x) => x.p);
        const kbText = render(kbSkills, localPatterns, cfg.maxChars);
        if (kbText) {
          const kbMsg = {
            role: 'user',
            id: globalThis.crypto?.randomUUID?.() ?? `wikiskill-${Date.now()}`,
            content: [{ type: 'text', text: kbText }],
            source: { kind: SOURCE_KIND, skills: kbSkills.length, patterns: localPatterns.length, via: 'kb' },
          };
          const list0 = Array.isArray(messages) ? messages : [];
          const anchorKb = claimed.findLastIndex((m) => list0.includes(m));
          const atKb = anchorKb >= 0 ? anchorKb + 1 : claimed.length;
          void debugLog(cfg.debugLog, `inject: via=kb skills=${kbSkills.length} patterns=${localPatterns.length} chars=${kbText.length}`);
          return { ...decision, messages: claimed.toSpliced(atKb, 0, kbMsg) };
        }
      }
      // ② 兜底：rerank
      const semantic = await rerankMatch(cfg, query, skills, patterns, signal,
        (m) => void debugLog(cfg.debugLog, m));
      if (semantic !== null) {
        if (semantic.skills.length === 0 && semantic.patterns.length === 0) return decision;
        const semanticText = render(semantic.skills, semantic.patterns, cfg.maxChars);
        if (!semanticText) return decision;
        const semanticMsg = {
          role: 'user',
          id: globalThis.crypto?.randomUUID?.() ?? `wikiskill-${Date.now()}`,
          content: [{ type: 'text', text: semanticText }],
          source: { kind: SOURCE_KIND, skills: semantic.skills.length, patterns: semantic.patterns.length, via: 'rerank' },
        };
        const claimedList0 = Array.isArray(messages) ? messages : [];
        const anchor0 = claimed.findLastIndex((m) => claimedList0.includes(m));
        const at0 = anchor0 >= 0 ? anchor0 + 1 : claimed.length;
        void debugLog(cfg.debugLog, `inject: via=rerank skills=${semantic.skills.length} patterns=${semantic.patterns.length} chars=${semanticText.length}`);
        return { ...decision, messages: claimed.toSpliced(at0, 0, semanticMsg) };
      }
      const rankedSkills = skills
        .map((s) => {
          const nameScore = hits(toks, `${s.name} ${s.dir}`) * 8;
          const descScore = hits(toks, s.description);
          return { s, score: nameScore + descScore, nameScore, descScore };
        })
        // 名称命中优先；纯描述命中要求至少 2 个词元，压掉"表格/文档"这类泛词噪声
        .filter((x) => x.nameScore > 0 || x.descScore >= 2)
        .sort((a, b) => b.score - a.score || b.nameScore - a.nameScore)
        .slice(0, cfg.maxSkills)
        .map((x) => x.s);
      // 短句（<6 字）2-gram 噪声极大，只给技能索引、不推经验
      const rankedPatterns = (query.length < 6 ? [] : patterns)
        .map((p) => ({ p, score: hits(toks, `${p.title} ${p.tags} ${p.takeaway}`) }))
        .filter((x) => x.score > 0)
        .sort((a, b) => b.score - a.score)
        .slice(0, cfg.maxPatterns)
        .map((x) => x.p);

      if (rankedSkills.length === 0 && rankedPatterns.length === 0) {
        void debugLog(cfg.debugLog, `skip: no hit (skills=${skills.length} patterns=${patterns.length})`);
        return decision;
      }
      const text = render(rankedSkills, rankedPatterns, cfg.maxChars);
      if (!text) return decision;

      const injected = {
        role: 'user',
        id: globalThis.crypto?.randomUUID?.() ?? `wikiskill-${Date.now()}`,
        content: [{ type: 'text', text }],
        source: { kind: SOURCE_KIND, skills: rankedSkills.length, patterns: rankedPatterns.length },
      };
      const claimedList = Array.isArray(messages) ? messages : [];
      const anchor = claimed.findLastIndex((m) => claimedList.includes(m));
      const at = anchor >= 0 ? anchor + 1 : claimed.length;
      void debugLog(cfg.debugLog, `inject: skills=${rankedSkills.length} patterns=${rankedPatterns.length} chars=${text.length}`);
      return { ...decision, messages: claimed.toSpliced(at, 0, injected) };
    } catch (error) {
      void debugLog(cfg.debugLog, `error: ${String(error?.message ?? error).slice(0, 200)}`);
      return decision;
    }
  };

  if (typeof ctx.effect === 'function') {
    ctx.effect(() => {
      const disposer = ctx.on('agent/pre-step', handler);
      return typeof disposer === 'function' ? disposer : () => {};
    });
  } else {
    ctx.on('agent/pre-step', handler);
  }
}
