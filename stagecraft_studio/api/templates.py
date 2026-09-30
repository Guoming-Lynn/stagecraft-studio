"""Markup for the local quicklook page. Placeholders use __NAME__ tokens."""

from __future__ import annotations

_SHELL_HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root {
    --paper: #f3efe6;
    --card: #fffdf8;
    --ink: #1e1a16;
    --muted: #655e55;
    --line: #e4dacb;
    --accent: #0e6b66;
    --accent-ink: #f4fffe;
    --amber-bg: #f4e7cf;
    --amber-ink: #6f4708;
    --bad-bg: #f8e4dc;
    --bad-ink: #8a341c;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    min-height: 100vh;
    color: var(--ink);
    background:
      radial-gradient(900px 420px at 0% -10%, #efe2cc 0%, transparent 60%),
      var(--paper);
    font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    line-height: 1.5;
  }
  .wrap { width: min(42rem, calc(100% - 2rem)); margin: 0 auto; padding: 2.5rem 0 3rem; }
  .top { display: flex; align-items: baseline; gap: 0.75rem; margin-bottom: 1.75rem; }
  .brand { font-weight: 650; letter-spacing: 0.04em; }
  .product { color: var(--muted); font-size: 0.92rem; }
  .badge {
    display: inline-block;
    margin: 0 0 0.8rem;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    background: var(--amber-bg);
    color: var(--amber-ink);
    font-size: 0.78rem;
    letter-spacing: 0.02em;
  }
  h1 { margin: 0 0 0.45rem; font-size: 1.85rem; font-weight: 640; letter-spacing: -0.02em; }
  .lede { margin: 0 0 1.4rem; color: var(--muted); max-width: 38rem; }
  .card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 1.25rem 1.25rem 1.1rem;
    box-shadow: 0 18px 40px rgba(70, 48, 20, 0.06);
  }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.9rem; }
  .field { margin: 0 0 0.95rem; }
  label { display: block; font-size: 0.92rem; font-weight: 620; }
  .opt { color: var(--muted); font-weight: 450; }
  .hint { margin: 0.15rem 0 0.35rem; color: var(--muted); font-size: 0.82rem; }
  input, select {
    width: 100%;
    padding: 0.62rem 0.7rem;
    border: 1px solid #d9cebf;
    border-radius: 10px;
    background: #fff;
    color: var(--ink);
    font: inherit;
  }
  input:focus, select:focus {
    outline: 2px solid rgba(14, 107, 102, 0.28);
    border-color: var(--accent);
  }
  .readonly {
    margin: 0.35rem 0 0;
    padding: 0.62rem 0.7rem;
    border-radius: 10px;
    background: #f6f1e8;
    color: var(--ink);
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 0.88rem;
    word-break: break-all;
  }
  details { margin: 0.2rem 0 1rem; }
  summary { cursor: pointer; color: var(--accent); font-weight: 600; }
  .actions { display: flex; align-items: center; gap: 0.9rem; }
  button {
    border: 0;
    border-radius: 10px;
    padding: 0.68rem 1.1rem;
    background: var(--accent);
    color: var(--accent-ink);
    font: inherit;
    font-weight: 650;
    cursor: pointer;
  }
  button:hover { background: #0b5854; }
  .actions p { margin: 0; color: var(--muted); font-size: 0.82rem; }
  .status {
    display: inline-block;
    margin-bottom: 0.8rem;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    font-size: 0.78rem;
  }
  .ok { background: #dceeea; color: #0d564f; }
  .bad { background: var(--bad-bg); color: var(--bad-ink); }
  dl { margin: 0; }
  .pair { padding: 0.75rem 0; border-top: 1px solid var(--line); }
  dt { color: var(--muted); font-size: 0.78rem; }
  dd {
    margin: 0.15rem 0 0;
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 0.92rem;
    word-break: break-all;
  }
  h2 { margin: 1.15rem 0 0.15rem; font-size: 1rem; font-weight: 650; }
  h2:first-child { margin-top: 0; }
  pre {
    margin: 0.35rem 0 0;
    padding: 0.75rem;
    max-height: 16rem;
    overflow: auto;
    white-space: pre-wrap;
    border: 1px solid var(--line);
    border-radius: 10px;
    background: #f6f1e8;
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 0.82rem;
  }
  .log-name { margin: 0.85rem 0 0; color: var(--muted); font-size: 0.82rem; }
  a.back { display: inline-block; margin-top: 1rem; color: var(--accent); font-weight: 620; }
  @media (max-width: 640px) {
    .row { grid-template-columns: 1fr; }
    .actions { align-items: flex-start; flex-direction: column; }
  }
</style>
</head>
<body>
<div class="wrap">
"""

_SHELL_TAIL = """
</div>
</body>
</html>
"""

FORM_PAGE = (
    _SHELL_HEAD
    + """
<header class="top"><div class="brand">Stagecraft</div><div class="product">速览</div></header>
<p class="badge">探索性 · 细胞水平 · 非正式分析</p>
<h1>看一个数据集里的目标基因</h1>
<p class="lede">先检查输入，再选择分组。没有分组时不出 case/control 对比图。
基因列表不会送到外部富集服务。</p>
<form class="card" method="post" action="/quicklook/inspect">
<input type="hidden" name="token" value="__TOKEN__">
<div class="field">
<label for="input_path">数据路径</label>
<p class="hint">h5ad 文件、10x MTX 目录，或 csv / tsv / txt 矩阵。counts 以你指定的为准。</p>
<input id="input_path" name="input_path" required spellcheck="false"
placeholder="D:\\data\\counts.h5ad">
</div>
<div class="field">
<label for="gene">目标基因</label>
<p class="hint">一个基因符号。</p>
<input id="gene" name="gene" required autocomplete="off" placeholder="IFITM3">
</div>
<details open>
<summary>输出目录与引擎</summary>
<div class="field">
<label for="out">输出目录</label>
<p class="hint">必须是新目录或空目录。结果不会回写到原始数据。</p>
<input id="out" name="out" required spellcheck="false" placeholder="D:\\projects\\quicklook">
</div>
<div class="field">
<label>引擎 Python</label>
<p class="hint">启动服务时确定，页面不能改。</p>
<p class="readonly">__PYTHON__</p>
</div>
<div class="field">
<label>run_pipeline.py</label>
<p class="hint">启动服务时确定，页面不能改。</p>
<p class="readonly">__SCRIPT__</p>
</div>
<div class="field">
<label for="local_gmt">本地 GMT <span class="opt">可选</span></label>
<p class="hint">有这份文件才做富集。没有它就停在聚类之后。</p>
<input id="local_gmt" name="local_gmt" spellcheck="false" value="__GMT__">
</div>
</details>
<div class="actions">
<button type="submit">检查输入</button>
<p>没有本地 GMT 时停在 phase03。cluster 名是临时的。</p>
</div>
</form>
"""
    + _SHELL_TAIL
)

INSPECT_PAGE = (
    _SHELL_HEAD
    + """
<header class="top"><div class="brand">Stagecraft</div><div class="product">速览</div></header>
<p class="badge">探索性 · 细胞水平 · 非正式分析</p>
<h1>选择分组</h1>
<p class="lede">没有分组时不出 case/control 对比图。
这里只列出列名和少量取值，不把表达矩阵送进浏览器。</p>
<form class="card" method="post" action="/quicklook">
<input type="hidden" name="token" value="__TOKEN__">
<input type="hidden" name="input_path" value="__INPUT__">
<input type="hidden" name="gene" value="__GENE__">
<input type="hidden" name="out" value="__OUT__">
<input type="hidden" name="local_gmt" value="__GMT__">
<dl>
<div class="pair"><dt>数据</dt><dd>__INPUT_TEXT__</dd></div>
<div class="pair"><dt>目标基因</dt><dd>__GENE_TEXT__</dd></div>
<div class="pair"><dt>输出目录</dt><dd>__OUT_TEXT__</dd></div>
<div class="pair"><dt>本地 GMT</dt><dd>__GMT_TEXT__</dd></div>
</dl>
<div class="row">
<div class="field">
<label for="group">分组列 <span class="opt">可选</span></label>
<p class="hint">没有分组时留空。</p>
<select id="group" name="group">__GROUP_OPTIONS__</select>
</div>
<div class="field">
<label for="batch_column">批次列 <span class="opt">可选</span></label>
<select id="batch_column" name="batch_column">__BATCH_OPTIONS__</select>
</div>
</div>
<div class="row">
<div class="field">
<label for="case_label">case 取值 <span class="opt">可选</span></label>
<select id="case_label" name="case_label">__CASE_OPTIONS__</select>
</div>
<div class="field">
<label for="control_label">control 取值 <span class="opt">可选</span></label>
<select id="control_label" name="control_label">__CONTROL_OPTIONS__</select>
</div>
</div>
<p class="hint">__NOTE__</p>
<div class="actions">
<button type="submit">开始速览</button>
<p>取值会原样写进配置。留空则不做 case/control 对比图。</p>
</div>
</form>
<p><a class="back" href="/">返回</a></p>
"""
    + _SHELL_TAIL
)

RESULT_PAGE = (
    _SHELL_HEAD
    + """
<header class="top"><div class="brand">Stagecraft</div><div class="product">速览</div></header>
<p class="badge">探索性 · 细胞水平 · 非正式分析</p>
<h1>__HEADING__</h1>
<p class="lede">__LEDE__</p>
<section class="card" data-returncode="__RETURNCODE__">
<p class="status __STATUS_CLASS__">__STATUS__</p>
__BODY__
<a class="back" href="/">返回</a>
</section>
"""
    + _SHELL_TAIL
)

ERROR_PAGE = (
    _SHELL_HEAD
    + """
<header class="top"><div class="brand">Stagecraft</div><div class="product">速览</div></header>
<h1>没有启动</h1>
<p class="lede">__MESSAGE__</p>
<section class="card"><a class="back" href="/">返回表单</a></section>
"""
    + _SHELL_TAIL
)
