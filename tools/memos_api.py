#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MemOS 云 API 全量命令行封装（25 个端点，2026-10-18）

覆盖：记忆核心 8 / 反馈消息 3 / 对话 1 / 属性记忆 8 / 知识库 5。
用途：memos-mcp 只暴露 10 个工具，其余 15 个端点靠本脚本直调。

鉴权：优先 MEMOS_API_KEY 环境变量，其次 ~/.dsh/secrets/memos_api_key。
文档标准前缀是 `Token`，服务端同时接受 `Bearer`。

示例：
  memos_api.py search --query "武丰对标口径" --limit 5
  memos_api.py get --page 1 --size 20
  memos_api.py add --messages '[{"role":"user","content":"..."}]' --conv c1
  memos_api.py extract --messages '[{"role":"user","content":"..."}]'
  memos_api.py rerank --query "..." --documents '["a","b"]'
  memos_api.py pt-add --name "HR 用户属性" --metadata '{"基础信息":{"姓名":{"value":""}}}'
  memos_api.py pt-bind --template tpl_x --user HR
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("MEMOS_BASE_URL", "https://memos.memtensor.cn/api/openmem/v1").rstrip("/")
KEY_FILE = os.path.expanduser("~/.dsh/secrets/memos_api_key")
DEFAULT_USER = os.environ.get("MEMOS_USER_ID", "HR")


def api_key() -> str:
    key = os.environ.get("MEMOS_API_KEY", "").strip()
    if not key and os.path.exists(KEY_FILE):
        with open(KEY_FILE, encoding="utf-8") as fh:
            key = fh.read().strip()
    if not key:
        sys.exit("缺少 MEMOS_API_KEY（环境变量或 ~/.dsh/secrets/memos_api_key）")
    return key


def call(method: str, path: str, body: dict | None = None) -> dict:
    """单次调用，返回解析后的 JSON；HTTP/业务错误直接抛错。"""
    url = f"{BASE}{path}"
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Token {api_key()}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:500]
        sys.exit(f"HTTP {err.code} {url}: {detail}")
    except urllib.error.URLError as err:
        sys.exit(f"网络错误 {url}: {err.reason}")
    if isinstance(payload, dict) and payload.get("code") not in (None, 0):
        sys.exit(f"接口返回错误 code={payload.get('code')} message={payload.get('message')}")
    return payload


def load_json_arg(raw: str | None, field: str):
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        sys.exit(f"{field} 不是合法 JSON: {err}")


def emit(payload: dict, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="MemOS 云 API 全量封装")
    p.add_argument("--pretty", action="store_true", help="格式化输出")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        return sub.add_parser(name, help=help_text)

    # ---------- 记忆核心 ----------
    s = add("search", "检索记忆 POST /search/memory")
    s.add_argument("--query", required=True)
    s.add_argument("--user", default=DEFAULT_USER)
    s.add_argument("--agent")
    s.add_argument("--conv", help="conversation_id，用于上下文连续性")
    s.add_argument("--relativity", type=float, default=0.45, help="0~1，0 表示不过滤")
    s.add_argument("--limit", type=int, default=9, help="1~25，默认 9")
    s.add_argument("--kb", help='知识库 ID 或 "all"')
    s.add_argument("--memory-view", default="detail_factual,preference")
    s.add_argument("--filter", help="JSON 过滤条件")

    g = add("get", "分页拉取记忆 POST /get/memory")
    g.add_argument("--user", default=DEFAULT_USER)
    g.add_argument("--agent")
    g.add_argument("--page", type=int, default=1)
    g.add_argument("--size", type=int, default=20)
    g.add_argument("--filter")
    g.add_argument("--memory-view")

    o = add("get-one", "单条记忆详情 GET /get/memory/{id}")
    o.add_argument("--memory-id", required=True)

    a = add("add", "写入消息 POST /add/message")
    a.add_argument("--messages", required=True, help='[{"role":"user","content":"..."}]')
    a.add_argument("--user", default=DEFAULT_USER)
    a.add_argument("--conv")
    a.add_argument("--agent")
    a.add_argument("--async-mode", action="store_true", dest="async_mode")
    a.add_argument("--tags", help='["tag1","tag2"]')

    u = add("update", "修改记忆 POST /update/memory")
    u.add_argument("--memory-id", required=True)
    u.add_argument("--content")
    u.add_argument("--title")

    d = add("delete", "删除记忆 POST /delete/memory")
    d.add_argument("--memory-ids", required=True, help="逗号分隔")
    d.add_argument("--user", default=DEFAULT_USER)
    d.add_argument("--agent")

    e = add("extract", "只抽取不落库 POST /extract/memory")
    e.add_argument("--messages", required=True)
    e.add_argument("--types", default="memory,preference")

    r = add("rerank", "记忆重排 POST /rerank")
    r.add_argument("--query", required=True)
    r.add_argument("--documents", required=True, help='["doc1","doc2"]')
    r.add_argument("--top-n", type=int, default=5, dest="top_n")
    r.add_argument("--model")

    # ---------- 反馈 / 消息 / 状态 ----------
    f = add("feedback", "添加反馈 POST /add/feedback")
    f.add_argument("--conv", required=True)
    f.add_argument("--content", required=True)
    f.add_argument("--user", default=DEFAULT_USER)
    f.add_argument("--agent")

    m = add("message", "拉原始消息 POST /get/message")
    m.add_argument("--conv", required=True)
    m.add_argument("--user", default=DEFAULT_USER)
    m.add_argument("--limit", type=int, default=20)

    st = add("status", "查异步任务 POST /get/status")
    st.add_argument("--task-id", required=True)

    # ---------- 对话 ----------
    c = add("chat", "带记忆对话 POST /chat")
    c.add_argument("--query", required=True)
    c.add_argument("--user", default=DEFAULT_USER)
    c.add_argument("--conv", required=True)
    c.add_argument("--stream", action="store_true")

    # ---------- 知识库 ----------
    k = add("kb-create", "创建知识库 POST /create/knowledgebase")
    k.add_argument("--name", required=True)
    k.add_argument("--desc")

    k = add("kb-delete", "删除知识库 POST /delete/knowledgebase")
    k.add_argument("--id", required=True)
    k.add_argument("--all", action="store_true", dest="delete_all")

    k = add("kb-add", "添加知识库文件 POST /add/knowledgebase-file")
    k.add_argument("--kb", required=True)
    k.add_argument("--file", required=True, help='{"content":"绝对路径或URL","mime_type":"..."} 或数组')

    k = add("kb-get", "获取知识库文件 POST /get/knowledgebase-file")
    k.add_argument("--kb", required=True)
    k.add_argument("--type")
    k.add_argument("--page", type=int, default=1)
    k.add_argument("--size", type=int, default=20)
    k.add_argument("--file-ids")

    k = add("kb-del-file", "删除知识库文件 POST /delete/knowledgebase-file")
    k.add_argument("--file-ids", required=True, help="逗号分隔")

    # ---------- 属性记忆 ----------
    t = add("pt-add", "创建属性模板 POST /add/profile_template")
    t.add_argument("--name", required=True)
    t.add_argument("--metadata", required=True, help='{"分类":{"字段":{"value":"","algorithm_updatable":true}}}')

    t = add("pt-list", "列出属性模板 POST /list/profile_template")
    t.add_argument("--page", type=int, default=1)
    t.add_argument("--size", type=int, default=20)

    t = add("pt-get", "模板详情 POST /get/profile_template")
    t.add_argument("--id", required=True)

    t = add("pt-update", "修改属性模板 POST /update/profile_template")
    t.add_argument("--id", required=True)
    t.add_argument("--name", required=True)
    t.add_argument("--metadata", required=True)

    t = add("pt-delete", "删除属性模板 POST /delete/profile_template")
    t.add_argument("--id", required=True)

    t = add("pt-bind", "绑定模板到用户/Agent POST /bind/profile_template")
    t.add_argument("--template", required=True)
    t.add_argument("--user")
    t.add_argument("--agent")

    pr = add("profile-edit", "编辑属性实例 POST /edit/profile")
    pr.add_argument("--template", required=True)
    pr.add_argument("--user")
    pr.add_argument("--agent")
    pr.add_argument("--metadata")
    pr.add_argument("--remove-fields", help='["分类.字段"]')

    pr = add("profile-delete", "删除属性实例 POST /delete/profile")
    pr.add_argument("--template", required=True)
    pr.add_argument("--user")
    pr.add_argument("--agent")

    return p


def main() -> None:
    args = build_parser().parse_args()
    cmd = args.cmd

    if cmd == "search":
        body = {
            "query": args.query,
            "user_id": args.user,
            "relativity": args.relativity,
            "memory_limit_number": args.limit,
            "include_memory_view": [x.strip() for x in args.memory_view.split(",") if x.strip()],
        }
        if args.agent:
            body["agent_id"] = args.agent
        if args.conv:
            body["conversation_id"] = args.conv
        if args.kb:
            body["knowledgebase_ids"] = ["all"] if args.kb == "all" else [args.kb]
        if args.filter:
            body["filter"] = load_json_arg(args.filter, "--filter")
        emit(call("POST", "/search/memory", body), args.pretty)

    elif cmd == "get":
        body = {"user_id": args.user, "page": args.page, "size": args.size}
        if args.agent:
            body["agent_id"] = args.agent
        if args.filter:
            body["filter"] = load_json_arg(args.filter, "--filter")
        if args.memory_view:
            body["include_memory_view"] = [x.strip() for x in args.memory_view.split(",") if x.strip()]
        emit(call("POST", "/get/memory", body), args.pretty)

    elif cmd == "get-one":
        emit(call("GET", f"/get/memory/{args.memory_id}"), args.pretty)

    elif cmd == "add":
        body = {"user_id": args.user, "messages": load_json_arg(args.messages, "--messages")}
        if args.conv:
            body["conversation_id"] = args.conv
        if args.agent:
            body["agent_id"] = args.agent
        if args.async_mode:
            body["async_mode"] = True
        if args.tags:
            body["tags"] = load_json_arg(args.tags, "--tags")
        emit(call("POST", "/add/message", body), args.pretty)

    elif cmd == "update":
        body = {"memory_id": args.memory_id}
        if args.content is not None:
            body["content"] = args.content
        if args.title is not None:
            body["title"] = args.title
        emit(call("POST", "/update/memory", body), args.pretty)

    elif cmd == "delete":
        body = {"memory_ids": [x.strip() for x in args.memory_ids.split(",") if x.strip()]}
        # 服务端只接受 user_id / memory_ids / filter 三者之一；重复传会报 40071
        if args.agent:
            body["agent_id"] = args.agent
        emit(call("POST", "/delete/memory", body), args.pretty)

    elif cmd == "extract":
        body = {"messages": load_json_arg(args.messages, "--messages")}
        if args.types:
            body["extraction_types"] = [x.strip() for x in args.types.split(",") if x.strip()]
        emit(call("POST", "/extract/memory", body), args.pretty)

    elif cmd == "rerank":
        body = {"query": args.query, "documents": load_json_arg(args.documents, "--documents"), "top_n": args.top_n}
        if args.model:
            body["model"] = args.model
        emit(call("POST", "/rerank", body), args.pretty)

    elif cmd == "feedback":
        body = {
            "user_id": args.user,
            "conversation_id": args.conv,
            "feedback_content": args.content,
        }
        if args.agent:
            body["agent_id"] = args.agent
        emit(call("POST", "/add/feedback", body), args.pretty)

    elif cmd == "message":
        emit(call("POST", "/get/message", {
            "user_id": args.user,
            "conversation_id": args.conv,
            "message_limit_number": args.limit,
        }), args.pretty)

    elif cmd == "status":
        emit(call("POST", "/get/status", {"task_id": args.task_id}), args.pretty)

    elif cmd == "chat":
        emit(call("POST", "/chat", {
            "user_id": args.user,
            "conversation_id": args.conv,
            "query": args.query,
            "stream": bool(args.stream),
        }), args.pretty)

    elif cmd == "kb-create":
        body = {"knowledgebase_name": args.name}
        if args.desc:
            body["knowledgebase_description"] = args.desc
        emit(call("POST", "/create/knowledgebase", body), args.pretty)

    elif cmd == "kb-delete":
        body = {"knowledgebase_id": args.id}
        if args.delete_all:
            body["delete_all"] = True
        emit(call("POST", "/delete/knowledgebase", body), args.pretty)

    elif cmd == "kb-add":
        files = load_json_arg(args.file, "--file")
        if isinstance(files, dict):
            files = [files]
        emit(call("POST", "/add/knowledgebase-file", {"knowledgebase_id": args.kb, "file": files}), args.pretty)

    elif cmd == "kb-get":
        body = {"knowledgebase_id": args.kb, "page": args.page, "page_size": args.size}
        if args.type:
            body["type"] = args.type
        if args.file_ids:
            body["file_ids"] = [x.strip() for x in args.file_ids.split(",") if x.strip()]
        emit(call("POST", "/get/knowledgebase-file", body), args.pretty)

    elif cmd == "kb-del-file":
        emit(call("POST", "/delete/knowledgebase-file", {
            "file_ids": [x.strip() for x in args.file_ids.split(",") if x.strip()],
        }), args.pretty)

    elif cmd == "pt-add":
        emit(call("POST", "/add/profile_template", {
            "name": args.name,
            "metadata": load_json_arg(args.metadata, "--metadata"),
        }), args.pretty)

    elif cmd == "pt-list":
        emit(call("POST", "/list/profile_template", {"page": args.page, "size": args.size}), args.pretty)

    elif cmd == "pt-get":
        emit(call("POST", "/get/profile_template", {"profile_template_id": args.id}), args.pretty)

    elif cmd == "pt-update":
        emit(call("POST", "/update/profile_template", {
            "profile_template_id": args.id,
            "name": args.name,
            "metadata": load_json_arg(args.metadata, "--metadata"),
        }), args.pretty)

    elif cmd == "pt-delete":
        emit(call("POST", "/delete/profile_template", {"profile_template_id": args.id}), args.pretty)

    elif cmd == "pt-bind":
        entry = {"profile_template_id": args.template}
        if args.user:
            entry["user_id"] = args.user
        if args.agent:
            entry["agent_id"] = args.agent
        if "user_id" not in entry and "agent_id" not in entry:
            entry["user_id"] = DEFAULT_USER
        emit(call("POST", "/bind/profile_template", {"bind_list": [entry]}), args.pretty)

    elif cmd == "profile-edit":
        body = {"profile_template_id": args.template}
        if args.user:
            body["user_id"] = args.user
        if args.agent:
            body["agent_id"] = args.agent
        if "user_id" not in body and "agent_id" not in body:
            body["user_id"] = DEFAULT_USER
        if args.metadata:
            body["metadata"] = load_json_arg(args.metadata, "--metadata")
        if args.remove_fields:
            body["remove_fields"] = load_json_arg(args.remove_fields, "--remove-fields")
        emit(call("POST", "/edit/profile", body), args.pretty)

    elif cmd == "profile-delete":
        body = {"profile_template_id": args.template}
        if args.user:
            body["user_id"] = args.user
        if args.agent:
            body["agent_id"] = args.agent
        if "user_id" not in body and "agent_id" not in body:
            body["user_id"] = DEFAULT_USER
        emit(call("POST", "/delete/profile", body), args.pretty)


if __name__ == "__main__":
    main()
