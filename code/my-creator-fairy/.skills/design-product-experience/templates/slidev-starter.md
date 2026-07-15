---
theme: seriph
colorSchema: dark
background: '#0a0a0a'
title: Product Introduction
info: |
  Product introduction and technical walkthrough
class: text-center
drawings:
  persist: false
transition: slide-left
mdc: true
---

# Product Name

Literal category and one-sentence product outcome

<div class="mt-10 text-gray-400 text-sm">
  Audience or supported environment
</div>

<div @click="$slidev.nav.next" class="mt-8 cursor-pointer hover:text-green-400 transition-colors">
  Start <carbon:arrow-right />
</div>

---
layout: center
---

# Agenda

<div class="grid grid-cols-4 gap-4 mt-10 max-w-4xl mx-auto">
  <div v-click class="p-4 rounded-lg border border-blue-500/20 bg-blue-500/5">
    <div class="text-blue-400 font-bold">01</div>
    <div class="mt-2 font-bold">Problem</div>
  </div>
  <div v-click class="p-4 rounded-lg border border-green-500/20 bg-green-500/5">
    <div class="text-green-400 font-bold">02</div>
    <div class="mt-2 font-bold">Product</div>
  </div>
  <div v-click class="p-4 rounded-lg border border-cyan-500/20 bg-cyan-500/5">
    <div class="text-cyan-400 font-bold">03</div>
    <div class="mt-2 font-bold">Workflow</div>
  </div>
  <div v-click class="p-4 rounded-lg border border-amber-500/20 bg-amber-500/5">
    <div class="text-amber-400 font-bold">04</div>
    <div class="mt-2 font-bold">Adoption</div>
  </div>
</div>

---
layout: center
transition: fade-out
---

# Start With Product Name

One direct outcome statement

```bash
verified-command-or-primary-action
```

<div class="mt-10 flex justify-center gap-5">
  <a href="VERIFIED_DOCS_URL" class="px-5 py-2 bg-green-600 text-white rounded-lg">
    Read documentation
  </a>
  <a href="VERIFIED_SOURCE_URL" class="px-5 py-2 border border-gray-600 text-gray-300 rounded-lg">
    View source
  </a>
</div>
